# Likability Score POC - CLI

Analyze Indian politicians' public perception using AI-powered sentiment analysis.

## Quick Start

### 1. Setup Environment

```bash
cd backend

# Create virtual environment (if not exists)
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys

Create a `.env` file in the `backend` folder:

```env
# Required: OpenAI API Key
OPENAI_API_KEY=sk-your-key-here

# Optional: NewsAPI (free tier: 100 requests/day)
# Get yours at: https://newsapi.org/register
NEWSAPI_KEY=your-newsapi-key

# Optional: Reddit API (free)
# Create app at: https://www.reddit.com/prefs/apps
REDDIT_CLIENT_ID=your-client-id
REDDIT_CLIENT_SECRET=your-client-secret
REDDIT_USER_AGENT=LikabilityBot/1.0
```

**Minimum requirement:** Only `OPENAI_API_KEY` is required. The tool will use Google News RSS (free, no key needed) for data if other APIs aren't configured.

### 3. Run the CLI

```bash
# Analyze a single politician
python cli.py analyze "Narendra Modi"

# Compare two politicians
python cli.py compare "Narendra Modi" "Rahul Gandhi"

# Force refresh (bypass cache)
python cli.py analyze "Amit Shah" --refresh

# View cache statistics
python cli.py cache-stats

# Clear cache
python cli.py cache-clear
```

## Output Format

All output is JSON format for easy parsing:

```json
{
  "name": "Narendra Modi",
  "score": 68.5,
  "breakdown": {
    "news_sentiment": 72.0,
    "reddit_sentiment": 65.0,
    "rss_sentiment": 70.0,
    "engagement": 75.0,
    "trend": 5.0
  },
  "insights": [
    "Favorable news media coverage",
    "Strong support on social platforms"
  ],
  "weaknesses": [],
  "ai_summary": "Overall positive sentiment...",
  "cached": false
}
```

## Data Sources

| Source | API Key Required | Rate Limit |
|--------|------------------|------------|
| Google News RSS | No | Unlimited |
| NewsAPI | Yes (free tier) | 100/day |
| Reddit | Yes (free) | 60/min |

## Architecture

```
cli.py                  # Main entry point
├── config.py           # Environment configuration
├── cache.py            # In-memory cache with TTL
├── models.py           # Pydantic data models
├── fetchers/
│   ├── newsapi.py      # NewsAPI integration
│   ├── rss.py          # Google News RSS (free)
│   └── reddit.py       # Reddit API (PRAW)
└── analyzer/
    ├── sentiment.py    # OpenAI sentiment analysis
    └── scoring.py      # Likability score calculation
```

## Tips

- Use `jq` for parsing JSON output:
  ```bash
  python cli.py analyze "Modi" | jq '.score'
  python cli.py compare "Modi" "Gandhi" | jq '.winner'
  ```

- Results are cached for 24 hours by default
- Use `--refresh` flag to force fresh data fetch


