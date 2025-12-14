#!/usr/bin/env python3
"""
Likability Score - Natural Language Chat CLI

Just chat naturally - the AI figures out what you want!

Examples:
    "How is Modi doing?"
    "Compare Modi and Rahul Gandhi"
    "What about Amit Shah?"
    "Who is more popular - Kejriwal or Yogi?"
"""

import sys
import json
from datetime import datetime
from openai import OpenAI

from config import settings
from cache import cache
from models import LikabilityResult
from fetchers.newsapi import newsapi_fetcher
from fetchers.rss import rss_fetcher
from fetchers.reddit import reddit_fetcher
from analyzer.sentiment import sentiment_analyzer
from analyzer.scoring import likability_scorer


# Initialize OpenAI client
client = None
if settings.openai_api_key:
    client = OpenAI(api_key=settings.openai_api_key)


def print_box(text: str, width: int = 60) -> None:
    """Print text in a simple box."""
    print("+" + "-" * (width - 2) + "+")
    print("|" + text.center(width - 2) + "|")
    print("+" + "-" * (width - 2) + "+")


def analyze_politician(name: str, force_refresh: bool = False) -> LikabilityResult:
    """Analyze a politician's likability score."""
    cache_key = cache._make_key("politician", name)
    
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"  [Using cached data for '{name}']")
            result = LikabilityResult(**cached_data)
            result.cached = True
            return result
    
    print(f"\n  Analyzing '{name}'...")
    
    # Fetch data
    print("  - Fetching news articles...")
    news_data = newsapi_fetcher.fetch(name)
    
    print("  - Fetching Google News RSS...")
    rss_data = rss_fetcher.fetch_multiple_languages(name)
    
    print("  - Fetching Reddit discussions...")
    reddit_data = reddit_fetcher.fetch(name)
    
    news_count = len(news_data.get("articles", []))
    rss_count = len(rss_data.get("articles", []))
    reddit_count = len(reddit_data.get("posts", []))
    print(f"  - Collected: {news_count} news, {rss_count} RSS, {reddit_count} Reddit")
    
    # Extract texts
    news_texts = [f"{a.get('title', '')}. {a.get('description', '')}" 
                  for a in news_data.get("articles", [])]
    rss_texts = [a.get("title", "") for a in rss_data.get("articles", [])]
    reddit_texts = [f"{p.get('title', '')}. {p.get('text', '')}" 
                   for p in reddit_data.get("posts", [])]
    
    print("  - Analyzing sentiment...")
    news_sentiment = sentiment_analyzer.analyze_batch(news_texts, name, "news")
    rss_sentiment = sentiment_analyzer.analyze_batch(rss_texts, name, "news")
    reddit_sentiment = sentiment_analyzer.analyze_batch(reddit_texts, name, "reddit")
    
    # Add metrics
    news_sentiment["engagement_score"] = 65
    news_sentiment["reach_score"] = 70
    news_sentiment["trend_score"] = 5
    rss_sentiment["articles_count"] = rss_count
    
    print("  - Calculating score...")
    result = likability_scorer.calculate(
        politician_name=name,
        news_data=news_data,
        rss_data=rss_data,
        reddit_data=reddit_data,
        news_sentiment=news_sentiment,
        rss_sentiment=rss_sentiment,
        reddit_sentiment=reddit_sentiment
    )
    
    # Cache result
    cache.set(cache_key, result.to_json())
    
    return result


def format_result_for_llm(result: LikabilityResult) -> str:
    """Format result as text for LLM context."""
    return f"""
Politician: {result.name}
Overall Likability Score: {result.score}/100

Score Breakdown:
- News Sentiment: {result.breakdown.news_sentiment}/100
- RSS/Trending News: {result.breakdown.rss_sentiment}/100  
- Reddit Sentiment: {result.breakdown.reddit_sentiment}/100
- Engagement: {result.breakdown.engagement}/100
- Trend Direction: {result.breakdown.trend:+.1f}

Strengths: {', '.join(result.insights) if result.insights else 'None identified'}
Weaknesses: {', '.join(result.weaknesses) if result.weaknesses else 'None identified'}

Data Sources:
- NewsAPI: {result.sources.get('newsapi', {}).items_collected if 'newsapi' in result.sources else 0} articles
- Google News RSS: {result.sources.get('rss', {}).items_collected if 'rss' in result.sources else 0} articles
- Reddit: {result.sources.get('reddit', {}).items_collected if 'reddit' in result.sources else 0} posts
"""


def understand_intent(user_message: str, conversation_history: list) -> dict:
    """Use LLM to understand what the user wants."""
    
    system_prompt = """You are an assistant that helps analyze Indian politicians' public perception.

Your job is to understand what the user wants and extract:
1. The action: "analyze" (single politician), "compare" (two politicians), "multi_compare" (3+ politicians), "help", "quit", or "chat" (general conversation)
2. The politician name(s) mentioned

Common Indian politicians: Narendra Modi, Rahul Gandhi, Amit Shah, Arvind Kejriwal, Yogi Adityanath, Mamata Banerjee, M.K. Stalin, Uddhav Thackeray, Nitish Kumar, KTR (K. Chandrashekar Rao's son K.T. Rama Rao), Harish Rao, Revanth Reddy, Chandrababu Naidu, Jagan Mohan Reddy, etc.

Respond ONLY with valid JSON in this format:
{
    "action": "analyze" | "compare" | "multi_compare" | "help" | "quit" | "chat",
    "politician1": "Name" or null,
    "politician2": "Name" or null (only for compare),
    "all_politicians": ["Name1", "Name2", "Name3"] (for multi_compare with 3+),
    "response": "Your friendly response to the user"
}

Examples:
- "How is Modi doing?" -> {"action": "analyze", "politician1": "Narendra Modi", "politician2": null, "all_politicians": [], "response": "Let me analyze Narendra Modi's public perception for you!"}
- "Compare Rahul and Modi" -> {"action": "compare", "politician1": "Rahul Gandhi", "politician2": "Narendra Modi", "all_politicians": [], "response": "I'll compare Rahul Gandhi and Narendra Modi for you!"}
- "KTR vs Harish Rao vs Revanth Reddy" -> {"action": "multi_compare", "politician1": null, "politician2": null, "all_politicians": ["K.T. Rama Rao", "Harish Rao", "Revanth Reddy"], "response": "I'll analyze all three Telangana leaders for you!"}
- "What about Kejriwal?" -> {"action": "analyze", "politician1": "Arvind Kejriwal", "politician2": null, "all_politicians": [], "response": "Let me check Arvind Kejriwal's likability score!"}
- "Who is better - Yogi or Akhilesh?" -> {"action": "compare", "politician1": "Yogi Adityanath", "politician2": "Akhilesh Yadav", "all_politicians": [], "response": "Let me compare Yogi Adityanath and Akhilesh Yadav!"}
- "Tell me about yourself" -> {"action": "chat", "politician1": null, "politician2": null, "all_politicians": [], "response": "I'm a likability analysis assistant..."}
- "exit" or "bye" -> {"action": "quit", "politician1": null, "politician2": null, "all_politicians": [], "response": "Goodbye!"}
"""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history for context
    for msg in conversation_history[-6:]:  # Last 6 messages for context
        messages.append(msg)
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=300
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    except Exception as e:
        return {
            "action": "chat",
            "politician1": None,
            "politician2": None,
            "response": f"I had trouble understanding that. Could you rephrase? (Error: {str(e)[:50]})"
        }


def generate_analysis_response(user_message: str, result: LikabilityResult, conversation_history: list) -> str:
    """Generate a natural language response about the analysis."""
    
    result_text = format_result_for_llm(result)
    
    prompt = f"""Based on this likability analysis data, provide a helpful, conversational response to the user.

Analysis Data:
{result_text}

User's question: {user_message}

Provide a natural, friendly response that:
1. Summarizes the key findings
2. Highlights important insights
3. Is conversational and easy to understand
4. Uses the actual numbers from the data

Keep it concise but informative (2-3 paragraphs max)."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful political analyst assistant. Be conversational and insightful."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        # Fallback to simple response
        return f"{result.name} has a likability score of {result.score}/100. " \
               f"News sentiment is at {result.breakdown.news_sentiment}/100, " \
               f"and social media (RSS) sentiment is at {result.breakdown.rss_sentiment}/100."


def generate_multi_comparison_response(user_message: str, results: list) -> str:
    """Generate a natural language response for 3+ politician comparison."""
    
    results_text = "\n\n".join([
        f"#{i+1} {format_result_for_llm(r)}" 
        for i, r in enumerate(results)
    ])
    
    prompt = f"""Compare these {len(results)} politicians based on their likability analysis:

{results_text}

User's question: {user_message}

Provide a natural comparison that:
1. Ranks them clearly with their scores
2. Highlights what makes the leader stand out
3. Notes key differences between them
4. Is balanced and insightful

Keep it conversational (2-3 paragraphs)."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful political analyst. Be balanced and insightful."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        # Fallback
        winner = results[0]
        return f"{winner.name} leads with {winner.score}/100 points."


def generate_comparison_response(user_message: str, result1: LikabilityResult, result2: LikabilityResult) -> str:
    """Generate a natural language comparison response."""
    
    result1_text = format_result_for_llm(result1)
    result2_text = format_result_for_llm(result2)
    
    winner = result1.name if result1.score > result2.score else result2.name
    diff = abs(result1.score - result2.score)
    
    prompt = f"""Compare these two politicians based on the likability analysis data:

POLITICIAN 1:
{result1_text}

POLITICIAN 2:
{result2_text}

User's question: {user_message}

Provide a natural, friendly comparison that:
1. Clearly states who has higher likability and by how much
2. Explains key differences in their scores
3. Mentions specific strengths/weaknesses of each
4. Gives actionable insights

Keep it conversational (2-3 paragraphs)."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful political analyst assistant. Be balanced and insightful."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"{winner} leads with a score of {max(result1.score, result2.score)}/100, " \
               f"ahead by {diff:.1f} points."


def main():
    """Main chat loop."""
    print()
    print_box("LIKABILITY SCORE - Chat Assistant")
    print()
    print("  Just chat naturally! Examples:")
    print("  - 'How is Modi doing?'")
    print("  - 'Compare Rahul Gandhi and Modi'")
    print("  - 'What about Kejriwal?'")
    print("  - 'Who is more popular - Yogi or Akhilesh?'")
    print()
    print("  Type 'quit' or 'exit' to leave.")
    print()
    print("-" * 60)
    
    # Check config
    if not settings.openai_api_key:
        print("\n  ERROR: OPENAI_API_KEY not set in .env file")
        return
    
    print()
    print("  APIs: OpenAI [OK]", end="")
    print(", NewsAPI [OK]" if settings.has_newsapi() else ", NewsAPI [--]", end="")
    print(", Reddit [OK]" if settings.has_reddit() else ", Reddit [--]", end="")
    print(", RSS [OK]")
    print()
    
    conversation_history = []
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Understand intent using LLM
            intent = understand_intent(user_input, conversation_history)
            
            action = intent.get("action", "chat")
            politician1 = intent.get("politician1")
            politician2 = intent.get("politician2")
            initial_response = intent.get("response", "")
            
            # Handle different actions
            if action == "quit":
                print(f"\nAssistant: {initial_response}")
                print()
                break
            
            elif action == "help":
                print(f"\nAssistant: {initial_response}")
                print("\n  I can help you with:")
                print("  - Analyze any Indian politician's public perception")
                print("  - Compare two politicians")
                print("  - Explain what makes someone more/less likable")
                print("\n  Just ask naturally!\n")
            
            elif action == "analyze" and politician1:
                print(f"\nAssistant: {initial_response}")
                
                result = analyze_politician(politician1)
                
                # Generate natural response
                response = generate_analysis_response(user_input, result, conversation_history)
                print(f"\n{response}")
                print(f"\n  [Score: {result.score}/100]\n")
                
                # Add to history
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})
            
            elif action == "compare" and politician1 and politician2:
                print(f"\nAssistant: {initial_response}")
                
                result1 = analyze_politician(politician1)
                print()
                result2 = analyze_politician(politician2)
                
                # Generate comparison response
                response = generate_comparison_response(user_input, result1, result2)
                print(f"\n{response}")
                
                winner = politician1 if result1.score > result2.score else politician2
                print(f"\n  [Winner: {winner} | {result1.name}: {result1.score}/100 vs {result2.name}: {result2.score}/100]\n")
                
                # Add to history
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})
            
            elif action == "multi_compare":
                all_politicians = intent.get("all_politicians", [])
                if len(all_politicians) >= 2:
                    print(f"\nAssistant: {initial_response}")
                    
                    # Analyze all politicians
                    results = []
                    for name in all_politicians:
                        result = analyze_politician(name)
                        results.append(result)
                        print()
                    
                    # Sort by score
                    results.sort(key=lambda x: x.score, reverse=True)
                    
                    # Generate multi-comparison response
                    response = generate_multi_comparison_response(user_input, results)
                    print(f"\n{response}")
                    
                    # Show rankings
                    print("\n  Rankings:")
                    for i, r in enumerate(results, 1):
                        medal = ["  1.", "  2.", "  3."][i-1] if i <= 3 else f"  {i}."
                        print(f"  {medal} {r.name}: {r.score}/100")
                    print()
                    
                    conversation_history.append({"role": "user", "content": user_input})
                    conversation_history.append({"role": "assistant", "content": response})
                else:
                    print("\nAssistant: I need at least 2 politicians to compare. Could you name them?\n")
            
            elif action == "chat":
                print(f"\nAssistant: {initial_response}\n")
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": initial_response})
            
            else:
                print(f"\nAssistant: I'm not sure I understood that. Could you try rephrasing?")
                print("  For example: 'How is Modi doing?' or 'Compare Rahul and Modi'\n")
        
        except KeyboardInterrupt:
            print("\n\nAssistant: Goodbye!\n")
            break
        
        except Exception as e:
            print(f"\nAssistant: Oops, something went wrong: {str(e)[:100]}\n")


if __name__ == "__main__":
    main()
