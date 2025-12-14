"""Data fetchers for collecting information from various sources."""

from .newsapi import NewsAPIFetcher
from .rss import RSSFetcher
from .reddit import RedditFetcher

__all__ = ["NewsAPIFetcher", "RSSFetcher", "RedditFetcher"]


