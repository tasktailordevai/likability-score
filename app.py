#!/usr/bin/env python3
"""
Likability Score - Flask Web Application

A beautiful chat interface for analyzing politician likability.
Features real-time streaming responses.
"""

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import json
import time
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


app = Flask(__name__)
CORS(app)

# Initialize OpenAI client
client = None
if settings.openai_api_key:
    client = OpenAI(api_key=settings.openai_api_key)

# Store conversation history per session (simple in-memory for POC)
conversations = {}


def analyze_politician(name: str, force_refresh: bool = False) -> LikabilityResult:
    """Analyze a politician's likability score."""
    cache_key = cache._make_key("politician", name)
    
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data:
            result = LikabilityResult(**cached_data)
            result.cached = True
            return result
    
    # Fetch data
    news_data = newsapi_fetcher.fetch(name)
    rss_data = rss_fetcher.fetch_multiple_languages(name)
    reddit_data = reddit_fetcher.fetch(name)
    
    # Extract texts
    news_texts = [f"{a.get('title', '')}. {a.get('description', '')}" 
                  for a in news_data.get("articles", [])]
    rss_texts = [a.get("title", "") for a in rss_data.get("articles", [])]
    reddit_texts = [f"{p.get('title', '')}. {p.get('text', '')}" 
                   for p in reddit_data.get("posts", [])]
    
    # Analyze sentiment
    news_sentiment = sentiment_analyzer.analyze_batch(news_texts, name, "news")
    rss_sentiment = sentiment_analyzer.analyze_batch(rss_texts, name, "news")
    reddit_sentiment = sentiment_analyzer.analyze_batch(reddit_texts, name, "reddit")
    
    # Add metrics
    news_sentiment["engagement_score"] = 65
    news_sentiment["reach_score"] = 70
    news_sentiment["trend_score"] = 5
    rss_sentiment["articles_count"] = len(rss_data.get("articles", []))
    
    # Calculate score
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
"""


def understand_intent(user_message: str) -> dict:
    """Use LLM to understand what the user wants."""
    
    system_prompt = """You are an assistant that helps analyze Indian politicians' public perception.

Understand the user's intent and extract:
1. action: "analyze" (single politician), "compare" (2 politicians), "multi_compare" (3+), "help", "quit", or "chat"
2. politician names mentioned

Common politicians: Narendra Modi, Rahul Gandhi, Amit Shah, Arvind Kejriwal, Yogi Adityanath, Mamata Banerjee, KTR (K.T. Rama Rao), Harish Rao, Revanth Reddy, Chandrababu Naidu, Jagan Mohan Reddy, etc.

Respond ONLY with valid JSON:
{
    "action": "analyze" | "compare" | "multi_compare" | "help" | "chat",
    "politicians": ["Name1", "Name2"],
    "response": "Your friendly response"
}

Examples:
- "How is Modi doing?" -> {"action": "analyze", "politicians": ["Narendra Modi"], "response": "Let me analyze Modi's public perception!"}
- "Compare Rahul and Modi" -> {"action": "compare", "politicians": ["Rahul Gandhi", "Narendra Modi"], "response": "Comparing these two leaders!"}
- "KTR vs Harish Rao vs Revanth" -> {"action": "multi_compare", "politicians": ["K.T. Rama Rao", "Harish Rao", "Revanth Reddy"], "response": "Analyzing all three!"}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=300
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "action": "chat",
            "politicians": [],
            "response": f"I had trouble understanding. Could you rephrase?"
        }


def generate_response(user_message: str, results: list) -> str:
    """Generate AI response based on analysis results."""
    
    if not results:
        return "I couldn't find any politicians to analyze. Could you name them?"
    
    results_text = "\n\n".join([format_result_for_llm(r) for r in results])
    
    prompt = f"""Based on this likability analysis, respond to the user's question.

Analysis Data:
{results_text}

User's question: {user_message}

Provide a natural, conversational response that:
1. Summarizes key findings with actual numbers
2. Compares if multiple politicians
3. Highlights insights
4. Is friendly and helpful

Keep it concise (2-3 paragraphs)."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful political analyst. Be balanced and insightful."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except:
        if len(results) == 1:
            r = results[0]
            return f"{r.name} has a likability score of {r.score}/100."
        else:
            winner = max(results, key=lambda x: x.score)
            return f"{winner.name} leads with {winner.score}/100."


@app.route('/')
def index():
    """Serve the chat interface."""
    return render_template('index.html')


@app.route('/api/config')
def get_config():
    """Return API configuration status."""
    return jsonify({
        "openai": bool(settings.openai_api_key),
        "newsapi": settings.has_newsapi(),
        "reddit": settings.has_reddit(),
        "rss": True
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages."""
    data = request.json
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', 'default')
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    # Understand intent
    intent = understand_intent(user_message)
    action = intent.get("action", "chat")
    politicians = intent.get("politicians", [])
    initial_response = intent.get("response", "")
    
    response_data = {
        "action": action,
        "initial_response": initial_response,
        "politicians": [],
        "final_response": "",
        "rankings": []
    }
    
    if action in ["analyze", "compare", "multi_compare"] and politicians:
        # Analyze politicians
        results = []
        for name in politicians:
            try:
                result = analyze_politician(name)
                results.append(result)
                response_data["politicians"].append({
                    "name": result.name,
                    "score": result.score,
                    "breakdown": {
                        "news": result.breakdown.news_sentiment,
                        "rss": result.breakdown.rss_sentiment,
                        "reddit": result.breakdown.reddit_sentiment,
                        "engagement": result.breakdown.engagement,
                        "trend": result.breakdown.trend
                    },
                    "insights": result.insights,
                    "weaknesses": result.weaknesses,
                    "cached": result.cached
                })
            except Exception as e:
                response_data["politicians"].append({
                    "name": name,
                    "error": str(e)
                })
        
        # Generate AI response
        if results:
            response_data["final_response"] = generate_response(user_message, results)
            
            # Sort for rankings
            results.sort(key=lambda x: x.score, reverse=True)
            response_data["rankings"] = [
                {"rank": i+1, "name": r.name, "score": r.score}
                for i, r in enumerate(results)
            ]
    
    elif action == "help":
        response_data["final_response"] = """I can help you analyze Indian politicians' public perception! 

Try asking things like:
• "How is Narendra Modi doing?"
• "Compare Rahul Gandhi and Modi"
• "KTR vs Harish Rao vs Revanth Reddy"
• "What about Kejriwal's popularity?"

I'll gather data from news sources and social media, then give you a likability score with insights!"""
    
    else:
        response_data["final_response"] = initial_response or "I can help you analyze politicians. Just name one or ask to compare!"
    
    return jsonify(response_data)


@app.route('/api/analyze/<name>')
def analyze_single(name: str):
    """Direct API to analyze a single politician."""
    try:
        result = analyze_politician(name)
        return jsonify(result.to_json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cache/stats')
def cache_stats():
    """Get cache statistics."""
    return jsonify(cache.stats())


@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear the cache."""
    count = cache.clear()
    return jsonify({"cleared": count})


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Handle chat messages with streaming response."""
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    def generate():
        """Generator function for streaming response."""
        
        # Send initial thinking message
        yield f"data: {json.dumps({'type': 'status', 'message': 'Understanding your question...'})}\n\n"
        
        # Understand intent
        intent = understand_intent(user_message)
        action = intent.get("action", "chat")
        politicians = intent.get("politicians", [])
        initial_response = intent.get("response", "")
        
        # Send intent response
        yield f"data: {json.dumps({'type': 'intent', 'action': action, 'politicians': politicians, 'response': initial_response})}\n\n"
        
        if action in ["analyze", "compare", "multi_compare"] and politicians:
            results = []
            
            for i, name in enumerate(politicians):
                # Check cache first
                cache_key = cache._make_key("politician", name)
                cached_data = cache.get(cache_key)
                
                if cached_data:
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Using cached data for {name}...'})}\n\n"
                    result = LikabilityResult(**cached_data)
                    result.cached = True
                else:
                    # Stream each data fetching step
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Fetching news for {name}...'})}\n\n"
                    news_data = newsapi_fetcher.fetch(name)
                    
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Fetching trending news for {name}...'})}\n\n"
                    rss_data = rss_fetcher.fetch_multiple_languages(name)
                    
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Fetching social discussions for {name}...'})}\n\n"
                    reddit_data = reddit_fetcher.fetch(name)
                    
                    # Extract texts
                    news_texts = [f"{a.get('title', '')}. {a.get('description', '')}" 
                                  for a in news_data.get("articles", [])]
                    rss_texts = [a.get("title", "") for a in rss_data.get("articles", [])]
                    reddit_texts = [f"{p.get('title', '')}. {p.get('text', '')}" 
                                   for p in reddit_data.get("posts", [])]
                    
                    total_items = len(news_texts) + len(rss_texts) + len(reddit_texts)
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Analyzing {total_items} items with AI...'})}\n\n"
                    
                    # Analyze sentiment
                    news_sentiment = sentiment_analyzer.analyze_batch(news_texts, name, "news")
                    rss_sentiment = sentiment_analyzer.analyze_batch(rss_texts, name, "news")
                    reddit_sentiment = sentiment_analyzer.analyze_batch(reddit_texts, name, "reddit")
                    
                    # Add metrics
                    news_sentiment["engagement_score"] = 65
                    news_sentiment["reach_score"] = 70
                    news_sentiment["trend_score"] = 5
                    rss_sentiment["articles_count"] = len(rss_data.get("articles", []))
                    
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Calculating score for {name}...'})}\n\n"
                    
                    # Calculate score
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
                
                results.append(result)
                
                # Send score card data
                politician_data = {
                    "name": result.name,
                    "score": result.score,
                    "breakdown": {
                        "news": result.breakdown.news_sentiment,
                        "rss": result.breakdown.rss_sentiment,
                        "reddit": result.breakdown.reddit_sentiment,
                        "engagement": result.breakdown.engagement,
                        "trend": result.breakdown.trend
                    },
                    "insights": result.insights,
                    "weaknesses": result.weaknesses,
                    "cached": result.cached
                }
                yield f"data: {json.dumps({'type': 'score', 'politician': politician_data})}\n\n"
            
            # Generate AI response with streaming
            yield f"data: {json.dumps({'type': 'status', 'message': 'Generating insights...'})}\n\n"
            
            # Stream the AI response
            if results:
                results_text = "\n\n".join([format_result_for_llm(r) for r in results])
                
                prompt = f"""Based on this likability analysis, respond to the user's question.

Analysis Data:
{results_text}

User's question: {user_message}

Provide a natural, conversational response that summarizes key findings with numbers, compares if multiple politicians, and highlights insights. Keep it concise (2-3 paragraphs)."""

                try:
                    # Use streaming from OpenAI
                    stream = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful political analyst. Be balanced and insightful."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=500,
                        stream=True
                    )
                    
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                    
                except Exception as e:
                    # Fallback non-streaming response
                    if len(results) == 1:
                        r = results[0]
                        fallback = f"{r.name} has a likability score of {r.score}/100."
                    else:
                        winner = max(results, key=lambda x: x.score)
                        fallback = f"{winner.name} leads with {winner.score}/100."
                    yield f"data: {json.dumps({'type': 'text', 'content': fallback})}\n\n"
                
                # Send rankings if multiple
                if len(results) > 1:
                    results.sort(key=lambda x: x.score, reverse=True)
                    rankings = [{"rank": i+1, "name": r.name, "score": r.score} for i, r in enumerate(results)]
                    yield f"data: {json.dumps({'type': 'rankings', 'data': rankings})}\n\n"
        
        elif action == "help":
            help_text = """I can help you analyze Indian politicians' public perception! 

Try asking things like:
- "How is Narendra Modi doing?"
- "Compare Rahul Gandhi and Modi"
- "KTR vs Harish Rao vs Revanth Reddy"

I'll gather data from news sources and social media, then give you a likability score with insights!"""
            
            # Stream help text word by word for effect
            words = help_text.split(' ')
            for i, word in enumerate(words):
                yield f"data: {json.dumps({'type': 'text', 'content': word + ' '})}\n\n"
                if i % 5 == 0:
                    time.sleep(0.02)  # Small delay for visual effect
        
        else:
            # General chat response
            for word in initial_response.split(' '):
                yield f"data: {json.dumps({'type': 'text', 'content': word + ' '})}\n\n"
                time.sleep(0.02)
        
        # Send completion signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  LIKABILITY SCORE - Web Application")
    print("="*60)
    print(f"\n  OpenAI API:  {'[OK]' if settings.openai_api_key else '[--]'}")
    print(f"  NewsAPI:     {'[OK]' if settings.has_newsapi() else '[--]'}")
    print(f"  Reddit API:  {'[OK]' if settings.has_reddit() else '[--]'}")
    print(f"  Google RSS:  [OK] Always available")
    print(f"\n  Starting server at: http://localhost:5000")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000)

