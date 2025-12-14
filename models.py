"""Data models for Likability POC."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class Sentiment(str, Enum):
    """Sentiment classification."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class SourceData(BaseModel):
    """Data collected from a single source."""
    source_name: str
    items_collected: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    sample_items: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    
    @property
    def sentiment_score(self) -> float:
        """Calculate sentiment score (0-100) for this source."""
        total = self.positive_count + self.negative_count + self.neutral_count
        if total == 0:
            return 50.0  # Neutral default
        
        # Score = (positive - negative) normalized to 0-100
        raw_score = (self.positive_count - self.negative_count) / total
        return round((raw_score + 1) * 50, 1)  # Convert -1..1 to 0..100


class ScoreBreakdown(BaseModel):
    """Detailed breakdown of likability score components."""
    news_sentiment: float = Field(ge=0, le=100, description="News sentiment score")
    reddit_sentiment: float = Field(ge=0, le=100, description="Reddit sentiment score")
    rss_sentiment: float = Field(ge=0, le=100, description="Google News RSS sentiment")
    engagement: float = Field(ge=0, le=100, description="Overall engagement score")
    trend: float = Field(ge=-100, le=100, description="Trend direction")


class LikabilityResult(BaseModel):
    """Complete likability analysis result."""
    name: str
    score: float = Field(ge=0, le=100, description="Overall likability score")
    breakdown: ScoreBreakdown
    sources: dict[str, SourceData] = Field(default_factory=dict)
    insights: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    ai_summary: str = ""
    analyzed_at: datetime = Field(default_factory=datetime.now)
    cached: bool = False
    
    def to_json(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "name": self.name,
            "score": self.score,
            "breakdown": {
                "news_sentiment": self.breakdown.news_sentiment,
                "reddit_sentiment": self.breakdown.reddit_sentiment,
                "rss_sentiment": self.breakdown.rss_sentiment,
                "engagement": self.breakdown.engagement,
                "trend": self.breakdown.trend
            },
            "insights": self.insights,
            "weaknesses": self.weaknesses,
            "ai_summary": self.ai_summary,
            "analyzed_at": self.analyzed_at.isoformat(),
            "cached": self.cached,
            "sources": {
                key: {
                    "source_name": src.source_name,
                    "items_collected": src.items_collected,
                    "positive_count": src.positive_count,
                    "negative_count": src.negative_count,
                    "neutral_count": src.neutral_count,
                    "sample_items": src.sample_items[:3],
                    "error": src.error
                }
                for key, src in self.sources.items()
            }
        }


class ComparisonResult(BaseModel):
    """Result of comparing two politicians."""
    politician1: LikabilityResult
    politician2: LikabilityResult
    winner: str
    score_difference: float
    comparison_insights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    ai_analysis: str = ""
    analyzed_at: datetime = Field(default_factory=datetime.now)
    
    def to_json(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "politician1": self.politician1.to_json(),
            "politician2": self.politician2.to_json(),
            "winner": self.winner,
            "score_difference": self.score_difference,
            "comparison_insights": self.comparison_insights,
            "recommendations": self.recommendations,
            "ai_analysis": self.ai_analysis,
            "analyzed_at": self.analyzed_at.isoformat()
        }


