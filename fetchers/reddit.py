"""Reddit API fetcher using PRAW library."""

import praw
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


class RedditFetcher:
    """
    Fetches Reddit posts and comments about politicians.
    
    Uses PRAW (Python Reddit API Wrapper) for clean API access.
    
    Free tier:
    - 60 requests per minute
    - Access to all public subreddits
    
    Target subreddits for Indian politics:
    - r/india
    - r/IndiaSpeaks
    - r/indianews
    """
    
    # Indian politics-related subreddits
    SUBREDDITS = ["india", "IndiaSpeaks", "indianews", "IndianPoliticalMemes"]
    
    def __init__(self):
        self.reddit = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize Reddit client if credentials are available."""
        if settings.has_reddit():
            try:
                self.reddit = praw.Reddit(
                    client_id=settings.reddit_client_id,
                    client_secret=settings.reddit_client_secret,
                    user_agent=settings.reddit_user_agent
                )
                # Test the connection
                self.reddit.read_only = True
            except Exception as e:
                print(f"Reddit client initialization failed: {e}")
                self.reddit = None
    
    def is_available(self) -> bool:
        """Check if Reddit API is configured and working."""
        return self.reddit is not None
    
    def fetch(
        self,
        query: str,
        subreddits: Optional[list[str]] = None,
        limit: int = 50,
        time_filter: str = "month"
    ) -> dict:
        """
        Fetch Reddit posts about a politician.
        
        Args:
            query: Politician name to search for
            subreddits: List of subreddits to search (default: Indian politics subs)
            limit: Maximum number of posts to fetch
            time_filter: Time range (hour, day, week, month, year, all)
            
        Returns:
            Dict with posts list and metadata
        """
        if not self.is_available():
            return {
                "posts": [],
                "total_results": 0,
                "error": "Reddit API not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET"
            }
        
        subreddits = subreddits or self.SUBREDDITS
        all_posts = []
        errors = []
        
        try:
            for subreddit_name in subreddits:
                try:
                    subreddit = self.reddit.subreddit(subreddit_name)
                    
                    # Search for posts mentioning the politician
                    search_results = subreddit.search(
                        query,
                        sort="relevance",
                        time_filter=time_filter,
                        limit=limit // len(subreddits)
                    )
                    
                    for post in search_results:
                        all_posts.append({
                            "title": post.title,
                            "text": post.selftext[:500] if post.selftext else "",
                            "subreddit": subreddit_name,
                            "score": post.score,
                            "upvote_ratio": post.upvote_ratio,
                            "num_comments": post.num_comments,
                            "url": f"https://reddit.com{post.permalink}",
                            "created_utc": post.created_utc
                        })
                        
                except Exception as e:
                    errors.append(f"r/{subreddit_name}: {str(e)}")
            
            # Sort by score (most popular first)
            all_posts.sort(key=lambda x: x["score"], reverse=True)
            
            return {
                "posts": all_posts[:limit],
                "total_results": len(all_posts),
                "error": "; ".join(errors) if errors else None
            }
            
        except Exception as e:
            return {
                "posts": [],
                "total_results": 0,
                "error": f"Reddit API error: {str(e)}"
            }
    
    def fetch_with_comments(
        self,
        query: str,
        max_posts: int = 10,
        max_comments_per_post: int = 5
    ) -> dict:
        """
        Fetch posts with top comments for deeper sentiment analysis.
        
        Note: This uses more API calls, so limit usage.
        """
        if not self.is_available():
            return {
                "posts": [],
                "total_results": 0,
                "error": "Reddit API not configured"
            }
        
        # First get posts
        posts_result = self.fetch(query, limit=max_posts)
        
        if posts_result.get("error") and not posts_result["posts"]:
            return posts_result
        
        posts_with_comments = []
        
        try:
            for post_data in posts_result["posts"][:max_posts]:
                # Get the full submission to access comments
                submission_url = post_data["url"]
                submission_id = submission_url.split("/comments/")[1].split("/")[0] if "/comments/" in submission_url else None
                
                if submission_id:
                    try:
                        submission = self.reddit.submission(id=submission_id)
                        submission.comments.replace_more(limit=0)  # Don't expand "more comments"
                        
                        top_comments = [
                            {
                                "text": comment.body[:300],
                                "score": comment.score
                            }
                            for comment in submission.comments[:max_comments_per_post]
                            if hasattr(comment, 'body')
                        ]
                        
                        post_data["top_comments"] = top_comments
                    except:
                        post_data["top_comments"] = []
                else:
                    post_data["top_comments"] = []
                
                posts_with_comments.append(post_data)
            
            return {
                "posts": posts_with_comments,
                "total_results": len(posts_with_comments),
                "error": posts_result.get("error")
            }
            
        except Exception as e:
            return {
                "posts": posts_result["posts"],
                "total_results": posts_result["total_results"],
                "error": f"Error fetching comments: {str(e)}"
            }


# Module-level instance
reddit_fetcher = RedditFetcher()


