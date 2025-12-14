"""Configuration management for Likability POC."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Settings:
    """Application settings loaded from environment variables."""
    
    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    
    # NewsAPI
    newsapi_key: str = os.getenv("NEWSAPI_KEY", "")
    
    # Reddit
    reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    reddit_user_agent: str = os.getenv("REDDIT_USER_AGENT", "LikabilityBot/1.0")
    
    # Cache
    cache_ttl_hours: int = int(os.getenv("CACHE_TTL_HOURS", "24"))
    
    def validate(self) -> list[str]:
        """Validate required settings and return list of missing keys."""
        missing = []
        
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        
        # NewsAPI and Reddit are optional - we have fallbacks
        return missing
    
    def has_newsapi(self) -> bool:
        """Check if NewsAPI is configured."""
        return bool(self.newsapi_key)
    
    def has_reddit(self) -> bool:
        """Check if Reddit API is configured."""
        return bool(self.reddit_client_id and self.reddit_client_secret)


# Global settings instance
settings = Settings()


