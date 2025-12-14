"""NewsAPI fetcher for news articles about politicians."""

import httpx
from datetime import datetime, timedelta
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


class NewsAPIFetcher:
    """
    Fetches news articles using NewsAPI.
    
    Free tier limitations:
    - 100 requests per day
    - Articles up to 1 month old
    - No access to some premium sources
    """
    
    BASE_URL = "https://newsapi.org/v2/everything"
    
    def __init__(self):
        self.api_key = settings.newsapi_key
    
    def is_available(self) -> bool:
        """Check if NewsAPI is configured."""
        return bool(self.api_key)
    
    def fetch(
        self,
        query: str,
        days_back: int = 30,
        max_articles: int = 50
    ) -> dict:
        """
        Fetch news articles about a politician.
        
        Args:
            query: Politician name to search for
            days_back: How many days back to search (max 30 for free tier)
            max_articles: Maximum number of articles to return
            
        Returns:
            Dict with articles list and metadata
        """
        if not self.is_available():
            return {
                "articles": [],
                "total_results": 0,
                "error": "NewsAPI key not configured"
            }
        
        # Calculate date range (free tier: max 1 month)
        from_date = (datetime.now() - timedelta(days=min(days_back, 30))).strftime("%Y-%m-%d")
        
        params = {
            "q": f'"{query}"',  # Exact phrase match
            "from": from_date,
            "sortBy": "relevancy",
            "pageSize": min(max_articles, 100),
            "language": "en",
            "apiKey": self.api_key
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(self.BASE_URL, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "articles": [
                            {
                                "title": article.get("title", ""),
                                "description": article.get("description", ""),
                                "source": article.get("source", {}).get("name", "Unknown"),
                                "url": article.get("url", ""),
                                "published_at": article.get("publishedAt", "")
                            }
                            for article in data.get("articles", [])
                        ],
                        "total_results": data.get("totalResults", 0),
                        "error": None
                    }
                elif response.status_code == 401:
                    return {
                        "articles": [],
                        "total_results": 0,
                        "error": "Invalid NewsAPI key"
                    }
                elif response.status_code == 429:
                    return {
                        "articles": [],
                        "total_results": 0,
                        "error": "NewsAPI rate limit exceeded (100/day for free tier)"
                    }
                else:
                    return {
                        "articles": [],
                        "total_results": 0,
                        "error": f"NewsAPI error: {response.status_code}"
                    }
                    
        except httpx.TimeoutException:
            return {
                "articles": [],
                "total_results": 0,
                "error": "NewsAPI request timed out"
            }
        except Exception as e:
            return {
                "articles": [],
                "total_results": 0,
                "error": f"NewsAPI error: {str(e)}"
            }
    
    def fetch_indian_news(
        self,
        query: str,
        max_articles: int = 30
    ) -> dict:
        """
        Fetch news specifically from Indian sources.
        
        Note: Free tier has limited source filtering capabilities.
        """
        if not self.is_available():
            return {
                "articles": [],
                "total_results": 0,
                "error": "NewsAPI key not configured"
            }
        
        # Add India-specific terms to improve relevance
        enhanced_query = f'"{query}" AND (India OR BJP OR Congress OR Parliament OR Lok Sabha)'
        
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        params = {
            "q": enhanced_query,
            "from": from_date,
            "sortBy": "relevancy",
            "pageSize": min(max_articles, 100),
            "apiKey": self.api_key
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(self.BASE_URL, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "articles": [
                            {
                                "title": article.get("title", ""),
                                "description": article.get("description", ""),
                                "source": article.get("source", {}).get("name", "Unknown"),
                                "url": article.get("url", ""),
                                "published_at": article.get("publishedAt", "")
                            }
                            for article in data.get("articles", [])
                        ],
                        "total_results": data.get("totalResults", 0),
                        "error": None
                    }
                else:
                    return {
                        "articles": [],
                        "total_results": 0,
                        "error": f"NewsAPI error: {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "articles": [],
                "total_results": 0,
                "error": f"NewsAPI error: {str(e)}"
            }


# Module-level instance
newsapi_fetcher = NewsAPIFetcher()


