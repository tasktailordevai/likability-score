#!/usr/bin/env python3
"""
Likability Score CLI - Analyze politician likability from public data.

Usage:
    python cli.py analyze "Narendra Modi"
    python cli.py compare "Narendra Modi" "Rahul Gandhi"
    python cli.py cache-stats
"""

import argparse
import json
import sys
from datetime import datetime

from config import settings
from cache import cache
from models import LikabilityResult, ComparisonResult
from fetchers.newsapi import newsapi_fetcher
from fetchers.rss import rss_fetcher
from fetchers.reddit import reddit_fetcher
from analyzer.sentiment import sentiment_analyzer
from analyzer.scoring import likability_scorer


def print_status(message: str, is_error: bool = False) -> None:
    """Print status message to stderr so it doesn't interfere with JSON output."""
    prefix = "ERROR:" if is_error else ">"
    print(f"{prefix} {message}", file=sys.stderr)


def analyze_politician(name: str, force_refresh: bool = False) -> LikabilityResult:
    """
    Analyze a politician's likability score.
    
    Args:
        name: Politician name
        force_refresh: If True, bypass cache
        
    Returns:
        LikabilityResult object
    """
    # Check cache first
    cache_key = cache._make_key("politician", name)
    
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data:
            print_status(f"Using cached data for '{name}'")
            result = LikabilityResult(**cached_data)
            result.cached = True
            return result
    
    print_status(f"Analyzing '{name}'...")
    
    # Step 1: Fetch data from all sources
    print_status("Fetching news articles...")
    news_data = newsapi_fetcher.fetch(name)
    
    print_status("Fetching Google News RSS...")
    rss_data = rss_fetcher.fetch_multiple_languages(name)
    
    print_status("Fetching Reddit discussions...")
    reddit_data = reddit_fetcher.fetch(name)
    
    # Report data collection results
    news_count = len(news_data.get("articles", []))
    rss_count = len(rss_data.get("articles", []))
    reddit_count = len(reddit_data.get("posts", []))
    print_status(f"Collected: {news_count} news, {rss_count} RSS, {reddit_count} Reddit posts")
    
    # Step 2: Extract texts for sentiment analysis
    news_texts = [
        f"{a.get('title', '')}. {a.get('description', '')}"
        for a in news_data.get("articles", [])
    ]
    
    rss_texts = [
        a.get("title", "")
        for a in rss_data.get("articles", [])
    ]
    
    reddit_texts = [
        f"{p.get('title', '')}. {p.get('text', '')}"
        for p in reddit_data.get("posts", [])
    ]
    
    # Step 3: Analyze sentiment
    print_status("Analyzing sentiment with AI...")
    
    news_sentiment = sentiment_analyzer.analyze_batch(news_texts, name, "news")
    rss_sentiment = sentiment_analyzer.analyze_batch(rss_texts, name, "news")
    reddit_sentiment = sentiment_analyzer.analyze_batch(reddit_texts, name, "reddit")
    
    # Step 4: Calculate likability score
    print_status("Calculating likability score...")
    
    result = likability_scorer.calculate(
        politician_name=name,
        news_data=news_data,
        rss_data=rss_data,
        reddit_data=reddit_data,
        news_sentiment=news_sentiment,
        rss_sentiment=rss_sentiment,
        reddit_sentiment=reddit_sentiment
    )
    
    # Generate AI summary
    if news_sentiment.get("summary"):
        summaries = [news_sentiment.get("summary", "")]
        if reddit_sentiment.get("summary"):
            summaries.append(reddit_sentiment.get("summary", ""))
        result.ai_summary = " ".join(s for s in summaries if s)
    
    # Cache the result
    cache.set(cache_key, result.to_json())
    print_status(f"Analysis complete. Score: {result.score}/100")
    
    return result


def compare_politicians(name1: str, name2: str, force_refresh: bool = False) -> ComparisonResult:
    """
    Compare two politicians' likability scores.
    
    Args:
        name1: First politician name
        name2: Second politician name
        force_refresh: If True, bypass cache
        
    Returns:
        ComparisonResult object
    """
    # Check cache for comparison
    cache_key = cache._make_key("compare", name1, name2)
    
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data:
            print_status(f"Using cached comparison for '{name1}' vs '{name2}'")
            return ComparisonResult(**cached_data)
    
    print_status(f"Comparing '{name1}' vs '{name2}'...")
    print_status("-" * 40)
    
    # Analyze both politicians
    result1 = analyze_politician(name1, force_refresh)
    print_status("-" * 40)
    result2 = analyze_politician(name2, force_refresh)
    
    # Determine winner
    winner = name1 if result1.score > result2.score else name2
    score_diff = abs(result1.score - result2.score)
    
    # Generate comparison insights
    insights = []
    recommendations = []
    
    # Score comparison
    insights.append(f"{winner} leads by {score_diff:.1f} points")
    
    # Breakdown comparison
    if result1.breakdown.news_sentiment > result2.breakdown.news_sentiment:
        diff = result1.breakdown.news_sentiment - result2.breakdown.news_sentiment
        insights.append(f"{name1} has better news coverage (+{diff:.0f})")
    elif result2.breakdown.news_sentiment > result1.breakdown.news_sentiment:
        diff = result2.breakdown.news_sentiment - result1.breakdown.news_sentiment
        insights.append(f"{name2} has better news coverage (+{diff:.0f})")
    
    if result1.breakdown.reddit_sentiment > result2.breakdown.reddit_sentiment:
        diff = result1.breakdown.reddit_sentiment - result2.breakdown.reddit_sentiment
        insights.append(f"{name1} has stronger social media support (+{diff:.0f})")
    elif result2.breakdown.reddit_sentiment > result1.breakdown.reddit_sentiment:
        diff = result2.breakdown.reddit_sentiment - result1.breakdown.reddit_sentiment
        insights.append(f"{name2} has stronger social media support (+{diff:.0f})")
    
    # Recommendations for trailing politician
    trailing = name2 if result1.score > result2.score else name1
    trailing_result = result2 if result1.score > result2.score else result1
    leading_result = result1 if result1.score > result2.score else result2
    
    if trailing_result.breakdown.news_sentiment < leading_result.breakdown.news_sentiment:
        recommendations.append(f"{trailing} should focus on improving news media presence")
    
    if trailing_result.breakdown.reddit_sentiment < leading_result.breakdown.reddit_sentiment:
        recommendations.append(f"{trailing} should increase social media engagement")
    
    if trailing_result.breakdown.engagement < leading_result.breakdown.engagement:
        recommendations.append(f"{trailing} should generate more public discussion and engagement")
    
    # Add weaknesses as recommendations
    for weakness in trailing_result.weaknesses[:2]:
        recommendations.append(f"Address: {weakness}")
    
    comparison = ComparisonResult(
        politician1=result1,
        politician2=result2,
        winner=winner,
        score_difference=round(score_diff, 1),
        comparison_insights=insights,
        recommendations=recommendations,
        ai_analysis=f"{winner} has higher likability with a {score_diff:.1f} point lead.",
        analyzed_at=datetime.now()
    )
    
    # Cache the comparison
    cache.set(cache_key, comparison.to_json())
    
    return comparison


def cmd_analyze(args) -> None:
    """Handle analyze command."""
    result = analyze_politician(args.name, args.refresh)
    print(json.dumps(result.to_json(), indent=2))


def cmd_compare(args) -> None:
    """Handle compare command."""
    result = compare_politicians(args.politician1, args.politician2, args.refresh)
    print(json.dumps(result.to_json(), indent=2))


def cmd_cache_stats(args) -> None:
    """Handle cache-stats command."""
    stats = cache.stats()
    print(json.dumps(stats, indent=2))


def cmd_cache_clear(args) -> None:
    """Handle cache-clear command."""
    count = cache.clear()
    print(json.dumps({"cleared_entries": count, "status": "success"}, indent=2))


def check_config() -> bool:
    """Check configuration and print warnings."""
    missing = settings.validate()
    
    if missing:
        print_status(f"Warning: Missing required config: {', '.join(missing)}", is_error=True)
        print_status("Create a .env file with your API keys. See .env.example", is_error=True)
        return False
    
    # Print available integrations
    print_status("Configuration check:")
    print_status(f"  OpenAI API: {'✓ configured' if settings.openai_api_key else '✗ not set'}")
    print_status(f"  NewsAPI: {'✓ configured' if settings.has_newsapi() else '○ not set (will skip)'}")
    print_status(f"  Reddit API: {'✓ configured' if settings.has_reddit() else '○ not set (will skip)'}")
    print_status(f"  Google News RSS: ✓ always available")
    print_status("")
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Likability Score CLI - Analyze politician public perception",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py analyze "Narendra Modi"
  python cli.py analyze "Rahul Gandhi" --refresh
  python cli.py compare "Narendra Modi" "Rahul Gandhi"
  python cli.py cache-stats
  python cli.py cache-clear

Output is JSON format, suitable for piping to other tools:
  python cli.py analyze "Modi" | jq '.score'
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a politician's likability score"
    )
    analyze_parser.add_argument(
        "name",
        help="Politician name to analyze"
    )
    analyze_parser.add_argument(
        "--refresh", "-r",
        action="store_true",
        help="Force refresh, bypass cache"
    )
    analyze_parser.set_defaults(func=cmd_analyze)
    
    # Compare command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two politicians"
    )
    compare_parser.add_argument(
        "politician1",
        help="First politician name"
    )
    compare_parser.add_argument(
        "politician2",
        help="Second politician name"
    )
    compare_parser.add_argument(
        "--refresh", "-r",
        action="store_true",
        help="Force refresh, bypass cache"
    )
    compare_parser.set_defaults(func=cmd_compare)
    
    # Cache stats command
    cache_stats_parser = subparsers.add_parser(
        "cache-stats",
        help="Show cache statistics"
    )
    cache_stats_parser.set_defaults(func=cmd_cache_stats)
    
    # Cache clear command
    cache_clear_parser = subparsers.add_parser(
        "cache-clear",
        help="Clear all cached data"
    )
    cache_clear_parser.set_defaults(func=cmd_cache_clear)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Check configuration before running commands that need it
    if args.command in ["analyze", "compare"]:
        if not check_config():
            sys.exit(1)
    
    # Execute command
    try:
        args.func(args)
    except KeyboardInterrupt:
        print_status("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print_status(f"Error: {str(e)}", is_error=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


