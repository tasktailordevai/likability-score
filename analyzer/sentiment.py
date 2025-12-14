"""OpenAI-powered sentiment analysis with batch processing."""

from openai import OpenAI
import json
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from models import Sentiment


class SentimentAnalyzer:
    """
    AI-powered sentiment analysis using OpenAI GPT-4o-mini.
    
    Features:
    - Batch processing for efficiency
    - Multilingual support (English + Hindi)
    - Indian political context awareness
    - Structured JSON output
    """
    
    def __init__(self):
        self.client = None
        if settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)
    
    def is_available(self) -> bool:
        """Check if OpenAI is configured."""
        return self.client is not None
    
    def analyze_batch(
        self,
        texts: list[str],
        politician_name: str,
        source_type: str = "news"
    ) -> dict:
        """
        Analyze sentiment of multiple texts in a single API call.
        
        Args:
            texts: List of texts to analyze (headlines, posts, comments)
            politician_name: Name of the politician being analyzed
            source_type: Type of source (news, reddit, social)
            
        Returns:
            Dict with sentiment counts and details
        """
        if not texts:
            return {
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "results": [],
                "key_topics": [],
                "summary": "No texts to analyze",
                "error": None
            }
        
        if not self.is_available():
            # Fall back to rule-based analysis
            return self._rule_based_analysis(texts, politician_name)
        
        # Limit batch size to avoid token limits
        texts_to_analyze = texts[:25]
        
        prompt = self._build_prompt(texts_to_analyze, politician_name, source_type)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert sentiment analyst specializing in Indian politics. 
Analyze texts about politicians and return structured JSON.
Consider:
- Hindi/English mixed content (Hinglish)
- Indian political context and terminology
- Sarcasm and satire common in Indian discourse
- Regional language nuances
- Terms like "ji" (respect), "pappu" (derogatory for Rahul Gandhi), "feku" (derogatory for Modi)"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1500
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                "positive_count": result.get("positive_count", 0),
                "negative_count": result.get("negative_count", 0),
                "neutral_count": result.get("neutral_count", 0),
                "results": result.get("results", []),
                "key_topics": result.get("key_topics", []),
                "summary": result.get("summary", ""),
                "overall_sentiment": result.get("overall_sentiment", "neutral"),
                "confidence": result.get("confidence", 70),
                "error": None
            }
            
        except json.JSONDecodeError as e:
            return self._rule_based_analysis(texts, politician_name, 
                                            error=f"JSON parse error: {str(e)}")
        except Exception as e:
            return self._rule_based_analysis(texts, politician_name,
                                            error=f"OpenAI API error: {str(e)}")
    
    def _build_prompt(self, texts: list[str], politician_name: str, source_type: str) -> str:
        """Build the analysis prompt."""
        texts_formatted = "\n".join(f"{i+1}. \"{text[:200]}\"" for i, text in enumerate(texts))
        
        return f"""Analyze the sentiment of these {source_type} texts about Indian politician "{politician_name}".

TEXTS:
{texts_formatted}

Respond with this exact JSON structure:
{{
    "positive_count": <number of positive texts>,
    "negative_count": <number of negative texts>,
    "neutral_count": <number of neutral texts>,
    "overall_sentiment": "positive" | "negative" | "neutral",
    "confidence": <0-100>,
    "key_topics": ["topic1", "topic2", "topic3"],
    "summary": "One sentence summary of overall sentiment",
    "results": [
        {{"index": 1, "sentiment": "positive|negative|neutral", "reason": "brief reason"}}
    ]
}}

Be accurate and consider Indian political context."""
    
    def _rule_based_analysis(
        self,
        texts: list[str],
        politician_name: str,
        error: Optional[str] = None
    ) -> dict:
        """
        Fallback rule-based sentiment analysis.
        
        Uses keyword matching when OpenAI is unavailable.
        """
        positive_words = [
            "great", "amazing", "good", "excellent", "best", "proud", "support",
            "love", "victory", "success", "progress", "development", "growth",
            "अच्छा", "शानदार", "बधाई", "जीत", "विकास", "प्रगति",
            "visionary", "leader", "historic", "landmark", "achievement"
        ]
        
        negative_words = [
            "bad", "worst", "hate", "fail", "failure", "corrupt", "scam",
            "disaster", "crisis", "problem", "issue", "wrong", "terrible",
            "pappu", "feku", "jumla", "lies", "false", "fake",
            "बुरा", "घोटाला", "झूठ", "असफल", "भ्रष्ट"
        ]
        
        results = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for i, text in enumerate(texts):
            text_lower = text.lower()
            
            pos_matches = sum(1 for word in positive_words if word in text_lower)
            neg_matches = sum(1 for word in negative_words if word in text_lower)
            
            if pos_matches > neg_matches:
                sentiment = "positive"
                positive_count += 1
            elif neg_matches > pos_matches:
                sentiment = "negative"
                negative_count += 1
            else:
                sentiment = "neutral"
                neutral_count += 1
            
            results.append({
                "index": i + 1,
                "sentiment": sentiment,
                "reason": "rule-based analysis"
            })
        
        total = len(texts)
        if positive_count > negative_count:
            overall = "positive"
        elif negative_count > positive_count:
            overall = "negative"
        else:
            overall = "neutral"
        
        return {
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "results": results,
            "key_topics": ["politics", "governance"],
            "summary": f"Rule-based analysis: {positive_count} positive, {negative_count} negative, {neutral_count} neutral",
            "overall_sentiment": overall,
            "confidence": 50,  # Lower confidence for rule-based
            "error": error or "Using rule-based fallback (OpenAI not available)"
        }
    
    def analyze_single(self, text: str, politician_name: str) -> dict:
        """Analyze a single text. Wrapper around batch for convenience."""
        result = self.analyze_batch([text], politician_name)
        
        if result["results"]:
            return {
                "sentiment": result["results"][0].get("sentiment", "neutral"),
                "confidence": result.get("confidence", 50),
                "error": result.get("error")
            }
        
        return {
            "sentiment": "neutral",
            "confidence": 0,
            "error": "Analysis failed"
        }


# Module-level instance
sentiment_analyzer = SentimentAnalyzer()


