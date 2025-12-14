"""Google News RSS fetcher - completely free, no API key needed."""

import feedparser
from typing import Optional
from urllib.parse import quote
import httpx


class RSSFetcher:
    """
    Fetches news from Google News RSS feeds.
    
    Advantages:
    - Completely free
    - No API key required
    - No rate limits
    - Always up-to-date
    
    Limitations:
    - Only headlines and basic descriptions
    - Limited to ~20-30 recent articles
    """
    
    # Google News RSS base URL for India
    BASE_URL = "https://news.google.com/rss/search"
    
    def __init__(self):
        pass
    
    def is_available(self) -> bool:
        """RSS is always available - no API key needed."""
        return True
    
    def fetch(
        self,
        query: str,
        language: str = "en",
        country: str = "IN"
    ) -> dict:
        """
        Fetch news articles from Google News RSS.
        
        Args:
            query: Search query (politician name)
            language: Language code (en, hi, etc.)
            country: Country code (IN for India)
            
        Returns:
            Dict with articles list and metadata
        """
        # Build RSS URL
        encoded_query = quote(query)
        url = f"{self.BASE_URL}?q={encoded_query}&hl={language}-{country}&gl={country}&ceid={country}:{language}"
        
        try:
            # Fetch and parse RSS feed
            feed = feedparser.parse(url)
            
            if feed.bozo and not feed.entries:
                return {
                    "articles": [],
                    "total_results": 0,
                    "error": f"RSS parse error: {feed.bozo_exception}"
                }
            
            articles = []
            for entry in feed.entries:
                # Extract source from title (Google News format: "Title - Source")
                title = entry.get("title", "")
                source = "Unknown"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2:
                        title = parts[0]
                        source = parts[1]
                
                articles.append({
                    "title": title,
                    "description": entry.get("summary", ""),
                    "source": source,
                    "url": entry.get("link", ""),
                    "published_at": entry.get("published", "")
                })
            
            return {
                "articles": articles,
                "total_results": len(articles),
                "error": None
            }
            
        except Exception as e:
            return {
                "articles": [],
                "total_results": 0,
                "error": f"RSS fetch error: {str(e)}"
            }
    
    def fetch_hindi_news(self, query: str) -> dict:
        """Fetch Hindi news for the politician."""
        return self.fetch(query, language="hi", country="IN")
    
    def fetch_multiple_languages(self, query: str) -> dict:
        """
        Fetch news in multiple Indian languages.
        
        Returns combined results from English and Hindi sources.
        """
        # Fetch English news
        english_results = self.fetch(query, language="en", country="IN")
        
        # Fetch Hindi news
        hindi_results = self.fetch(query, language="hi", country="IN")
        
        # Combine results
        all_articles = english_results.get("articles", []) + hindi_results.get("articles", [])
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                unique_articles.append(article)
        
        errors = []
        if english_results.get("error"):
            errors.append(f"English: {english_results['error']}")
        if hindi_results.get("error"):
            errors.append(f"Hindi: {hindi_results['error']}")
        
        return {
            "articles": unique_articles,
            "total_results": len(unique_articles),
            "error": "; ".join(errors) if errors else None
        }


# Module-level instance
rss_fetcher = RSSFetcher()


