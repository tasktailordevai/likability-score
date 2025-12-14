"""Likability score calculator."""

from datetime import datetime
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import LikabilityResult, ScoreBreakdown, SourceData


class LikabilityScorer:
    """
    Calculates overall likability score from multiple data sources.
    
    Scoring weights:
    - News Sentiment: 30%
    - Reddit Sentiment: 25%
    - YouTube Sentiment: 25%
    - Engagement/Reach: 15%
    - Trend Direction: 5%
    """
    
    WEIGHTS = {
        "news": 0.30,
        "reddit": 0.25,
        "youtube": 0.25,
        "engagement": 0.15,
        "trend": 0.05
    }
    
    def calculate(
        self,
        politician_name: str,
        news_data: dict,
        rss_data: dict,
        reddit_data: dict,
        youtube_data: dict,
        news_sentiment: dict,
        rss_sentiment: dict,
        reddit_sentiment: dict,
        youtube_sentiment: dict
    ) -> LikabilityResult:
        """
        Calculate comprehensive likability score.
        
        Args:
            politician_name: Name of the politician
            news_data: Raw data from NewsAPI
            rss_data: Raw data from Google News RSS
            reddit_data: Raw data from Reddit
            news_sentiment: Sentiment analysis of news
            rss_sentiment: Sentiment analysis of RSS
            reddit_sentiment: Sentiment analysis of Reddit
            
        Returns:
            LikabilityResult with score and breakdown
        """
        # Build source data objects
        sources = {}
        
        # NewsAPI source
        sources["newsapi"] = SourceData(
            source_name="NewsAPI",
            items_collected=len(news_data.get("articles", [])),
            positive_count=news_sentiment.get("positive_count", 0),
            negative_count=news_sentiment.get("negative_count", 0),
            neutral_count=news_sentiment.get("neutral_count", 0),
            sample_items=[a.get("title", "") for a in news_data.get("articles", [])[:5]],
            error=news_data.get("error") or news_sentiment.get("error")
        )
        
        # RSS source
        sources["rss"] = SourceData(
            source_name="Google News RSS",
            items_collected=len(rss_data.get("articles", [])),
            positive_count=rss_sentiment.get("positive_count", 0),
            negative_count=rss_sentiment.get("negative_count", 0),
            neutral_count=rss_sentiment.get("neutral_count", 0),
            sample_items=[a.get("title", "") for a in rss_data.get("articles", [])[:5]],
            error=rss_data.get("error") or rss_sentiment.get("error")
        )
        
        # Reddit source
        sources["reddit"] = SourceData(
            source_name="Reddit",
            items_collected=len(reddit_data.get("posts", [])),
            positive_count=reddit_sentiment.get("positive_count", 0),
            negative_count=reddit_sentiment.get("negative_count", 0),
            neutral_count=reddit_sentiment.get("neutral_count", 0),
            sample_items=[p.get("title", "") for p in reddit_data.get("posts", [])[:5]],
            error=reddit_data.get("error") or reddit_sentiment.get("error")
        )
        
        # YouTube source
        youtube_videos = youtube_data.get("videos", [])
        all_youtube_comments = []
        for video in youtube_videos:
            all_youtube_comments.extend(video.get("comments", []))
        
        sources["youtube"] = SourceData(
            source_name="YouTube",
            items_collected=len(youtube_videos),
            positive_count=youtube_sentiment.get("positive_count", 0),
            negative_count=youtube_sentiment.get("negative_count", 0),
            neutral_count=youtube_sentiment.get("neutral_count", 0),
            sample_items=[v.get("title", "") for v in youtube_videos[:5]],
            error=youtube_data.get("error") or youtube_sentiment.get("error")
        )
        
        # Calculate individual scores
        news_score = self._calculate_sentiment_score(news_sentiment)
        rss_score = self._calculate_sentiment_score(rss_sentiment)
        reddit_score = self._calculate_sentiment_score(reddit_sentiment)
        youtube_score = self._calculate_sentiment_score(youtube_sentiment)
        
        # Combined news score (NewsAPI + RSS)
        combined_news_score = (news_score + rss_score) / 2 if (news_score > 0 or rss_score > 0) else 50
        
        # Engagement score (based on Reddit + YouTube activity)
        engagement_score = self._calculate_engagement_score(reddit_data, youtube_data)
        
        # Trend score (simplified - would need historical data for real trend)
        trend_score = self._calculate_trend_score(news_sentiment, reddit_sentiment, youtube_sentiment)
        
        # Calculate overall score with weights
        overall_score = (
            combined_news_score * self.WEIGHTS["news"] +
            reddit_score * self.WEIGHTS["reddit"] +
            youtube_score * self.WEIGHTS["youtube"] +
            engagement_score * self.WEIGHTS["engagement"] +
            ((trend_score + 100) / 2) * self.WEIGHTS["trend"]  # Normalize trend to 0-100
        )
        
        # Build breakdown
        breakdown = ScoreBreakdown(
            news_sentiment=round(news_score, 1),
            reddit_sentiment=round(reddit_score, 1),
            rss_sentiment=round(rss_score, 1),
            youtube_sentiment=round(youtube_score, 1),
            engagement=round(engagement_score, 1),
            trend=round(trend_score, 1)
        )
        
        # Generate insights and weaknesses
        insights, weaknesses = self._analyze_strengths_weaknesses(
            breakdown, sources, news_sentiment, reddit_sentiment
        )
        
        return LikabilityResult(
            name=politician_name,
            score=round(overall_score, 1),
            breakdown=breakdown,
            sources=sources,
            insights=insights,
            weaknesses=weaknesses,
            ai_summary="",  # Will be filled separately if needed
            analyzed_at=datetime.now(),
            cached=False
        )
    
    def _calculate_sentiment_score(self, sentiment: dict) -> float:
        """
        Convert sentiment counts to a 0-100 score.
        
        Formula: ((positive - negative) / total + 1) * 50
        This gives 0 for all negative, 50 for neutral, 100 for all positive.
        """
        pos = sentiment.get("positive_count", 0)
        neg = sentiment.get("negative_count", 0)
        neu = sentiment.get("neutral_count", 0)
        total = pos + neg + neu
        
        if total == 0:
            return 50.0  # Neutral default
        
        raw_score = (pos - neg) / total  # -1 to 1
        return max(0, min(100, (raw_score + 1) * 50))  # 0 to 100
    
    def _calculate_engagement_score(self, reddit_data: dict, youtube_data: dict) -> float:
        """
        Calculate engagement score based on Reddit and YouTube activity.
        
        Factors:
        - Number of posts/videos
        - Average score (upvotes/views)
        - Comment count
        """
        posts = reddit_data.get("posts", [])
        videos = youtube_data.get("videos", [])
        
        if not posts and not videos:
            return 50.0  # Neutral default
        
        # Reddit metrics
        reddit_score = 0
        if posts:
            total_score = sum(p.get("score", 0) for p in posts)
            total_comments = sum(p.get("num_comments", 0) for p in posts)
            avg_upvote_ratio = sum(p.get("upvote_ratio", 0.5) for p in posts) / len(posts)
            
            post_score = min(100, len(posts) * 5)
            upvote_score = min(100, total_score / 10)
            comment_score = min(100, total_comments / 5)
            ratio_score = avg_upvote_ratio * 100
            
            reddit_score = (post_score * 0.2 + upvote_score * 0.3 + comment_score * 0.2 + ratio_score * 0.3) / 2
        
        # YouTube metrics
        youtube_score = 0
        if videos:
            total_views = sum(v.get("views", 0) for v in videos)
            total_likes = sum(v.get("likes", 0) for v in videos)
            total_comments = sum(v.get("comments_count", 0) for v in videos)
            
            video_score = min(100, len(videos) * 10)
            views_score = min(100, total_views / 100000)  # 10M views = 100
            likes_score = min(100, total_likes / 10000)   # 1M likes = 100
            comments_score = min(100, total_comments / 1000)  # 100K comments = 100
            
            youtube_score = (video_score * 0.2 + views_score * 0.3 + likes_score * 0.2 + comments_score * 0.3) / 2
        
        # Combine Reddit and YouTube
        if posts and videos:
            engagement = (reddit_score + youtube_score) / 2
        elif posts:
            engagement = reddit_score
        else:
            engagement = youtube_score
        
        
        return max(0, min(100, engagement))
    
    def _calculate_trend_score(self, news_sentiment: dict, reddit_sentiment: dict, youtube_sentiment: dict) -> float:
        """
        Calculate trend score (-100 to +100).
        
        Positive = improving sentiment
        Negative = declining sentiment
        
        Note: For accurate trends, we'd need historical data.
        This is a simplified version based on current data quality.
        """
        # Use confidence and overall sentiment as proxy
        news_confidence = news_sentiment.get("confidence", 50)
        reddit_confidence = reddit_sentiment.get("confidence", 50)
        youtube_confidence = youtube_sentiment.get("confidence", 50)
        
        news_overall = news_sentiment.get("overall_sentiment", "neutral")
        reddit_overall = reddit_sentiment.get("overall_sentiment", "neutral")
        youtube_overall = youtube_sentiment.get("overall_sentiment", "neutral")
        
        # Convert to score
        sentiment_map = {"positive": 1, "neutral": 0, "negative": -1}
        news_direction = sentiment_map.get(news_overall, 0)
        reddit_direction = sentiment_map.get(reddit_overall, 0)
        youtube_direction = sentiment_map.get(youtube_overall, 0)
        
        # Combined trend based on agreement and confidence
        avg_confidence = (news_confidence + reddit_confidence + youtube_confidence) / 3
        avg_direction = (news_direction + reddit_direction + youtube_direction) / 3
        
        # Scale to -100 to 100
        return avg_direction * avg_confidence
    
    def _analyze_strengths_weaknesses(
        self,
        breakdown: ScoreBreakdown,
        sources: dict,
        news_sentiment: dict,
        reddit_sentiment: dict
    ) -> tuple[list[str], list[str]]:
        """Identify key strengths and weaknesses."""
        insights = []
        weaknesses = []
        
        # News sentiment analysis
        if breakdown.news_sentiment >= 65:
            insights.append("Favorable news media coverage")
        elif breakdown.news_sentiment < 40:
            weaknesses.append("Negative news media portrayal")
        
        # RSS sentiment
        if breakdown.rss_sentiment >= 65:
            insights.append("Positive trending news")
        elif breakdown.rss_sentiment < 40:
            weaknesses.append("Negative trending coverage")
        
        # Reddit sentiment
        if breakdown.reddit_sentiment >= 65:
            insights.append("Strong support on social platforms")
        elif breakdown.reddit_sentiment < 40:
            weaknesses.append("Negative social media sentiment")
        
        # Engagement
        if breakdown.engagement >= 70:
            insights.append("High public engagement and discussion")
        elif breakdown.engagement < 35:
            weaknesses.append("Low public engagement")
        
        # Trend
        if breakdown.trend > 20:
            insights.append("Improving public perception trend")
        elif breakdown.trend < -20:
            weaknesses.append("Declining public perception")
        
        # Data quality insights
        total_items = sum(s.items_collected for s in sources.values())
        if total_items < 10:
            weaknesses.append("Limited data available for analysis")
        elif total_items > 50:
            insights.append("Comprehensive data coverage")
        
        # Extract key topics from sentiments
        news_topics = news_sentiment.get("key_topics", [])
        reddit_topics = reddit_sentiment.get("key_topics", [])
        if news_topics or reddit_topics:
            all_topics = list(set(news_topics + reddit_topics))[:3]
            if all_topics:
                insights.append(f"Key topics: {', '.join(all_topics)}")
        
        return insights, weaknesses


# Module-level instance
likability_scorer = LikabilityScorer()


