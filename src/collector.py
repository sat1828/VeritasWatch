"""
collector.py — X API v2 data collection for VeritasWatch.

AUDIT NOTES — READ BEFORE RUNNING:

  This file costs real money to run. The X API Basic tier
  ($100/month) caps you at 10,000 tweets per calendar month.
  At 100 tweets per request, that is 100 requests total before
  your monthly quota is exhausted.

  WHAT THIS SCRIPT DOES:
    1. Polls the X API every 15 minutes (1 request per poll)
    2. Pulls up to 100 English-language original tweets per poll
       (no retweets — -is:retweet in the query)
    3. Extracts all scoring-relevant fields
    4. Scores each tweet immediately using scorer.py
    5. Stores in SQLite via database.py
    6. Logs every API call to api_call_log.txt

  EXPECTED COLLECTION VOLUME (be honest about this):
    - 15-minute polling = 4 requests/hour = 96 requests over 24 hours
    - At 100 tweets/request: up to 9,600 tweets in 24 hours IN THEORY
    - ACTUAL LIMIT: Basic tier monthly cap of 10,000 tweets
    - After 100 requests (≈25 hours of polling), your quota is exhausted
    - Real-world return per request varies: often 20–80 tweets, not 100
    - Realistic 48-hour collection: 500–2,000 tweets total
    - This is the honest number. Do not claim 10,000 tweets on your CV.

  REQUIRED ENVIRONMENT VARIABLES (in .env file, never commit):
    X_BEARER_TOKEN=your_bearer_token_here

  TO RUN:
    python src/collector.py

  TO STOP:
    Ctrl+C — the script handles KeyboardInterrupt cleanly.

  After collection, run the dashboard in replay mode:
    streamlit run dashboard/app.py

KEYWORD SET IN USE: Health misinformation (Set A from spec).
  "vaccine deaths" OR "5G dangers" OR "COVID lab leak CONFIRMED"
  
  WHY THIS SET:
    - Returns results consistently (tested)
    - Misinformation-adjacent without being so specific that
      results dry up after a few hours
    - Avoids election keywords (higher legal/regulatory sensitivity)
  
  WHY -is:retweet:
    Retweets share the original tweet's signals. Scoring a retweet
    using the retweeter's account metadata is misleading — the
    retweeter's account age and follower count are irrelevant to
    the original post's risk. We evaluate original posts only.
    This is documented in ARCHITECTURE.md.
"""

import tweepy
import sqlite3
import time
import os
import sys
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add src directory to path so we can import sibling modules
sys.path.insert(0, os.path.dirname(__file__))

from database import initialise_db, insert_tweet, get_total_count
from scorer import score_tweet
from triage import triage_decision
from utils import (
    extract_domain, account_age_in_days,
    has_default_profile_photo, extract_first_url, now_iso, safe_int
)

# ── CONFIGURATION ──────────────────────────────────────────────────────────────

load_dotenv()
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

POLL_INTERVAL_SECONDS = 900   # 15 minutes — conservative, respects rate limits
MAX_RESULTS_PER_REQUEST = 100  # Maximum allowed by the API per request

# Your keyword set — change only if you change the README to match
QUERY = (
    '"vaccine deaths" OR "5G dangers" OR "COVID lab leak CONFIRMED" '
    'lang:en -is:retweet'
)

LOG_PATH = os.path.join(os.path.dirname(__file__), '..', 'api_call_log.txt')
DB_INIT_DONE = False

# ── LOGGING ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def log_api_call(request_num: int, tweets_returned: int, cumulative: int):
    """
    Append one line to api_call_log.txt.
    This log is the proof that data collection was real.
    A recruiter asking "show me your API call log" gets this file.
    Format: ISO timestamp | request=N | tweets_returned=N | cumulative=N
    """
    line = (
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} | "
        f"request={request_num} | "
        f"tweets_returned={tweets_returned} | "
        f"quota_consumed={tweets_returned} | "
        f"cumulative_total={cumulative}\n"
    )
    with open(LOG_PATH, 'a') as f:
        f.write(line)
    logger.info(line.strip())


# ── TWEET PROCESSING ───────────────────────────────────────────────────────────

def process_tweet(tweet, users_by_id: dict) -> dict:
    """
    Extract all scoring-relevant fields from a Tweepy tweet object
    and its associated user data. Returns a flat dict matching the
    tweets table schema.

    Args:
        tweet: Tweepy Tweet object from search_recent_tweets response
        users_by_id: Dict mapping author_id → Tweepy User object

    Returns:
        Dict ready for scorer.score_tweet() and then database.insert_tweet()
    """
    author = users_by_id.get(str(tweet.author_id))

    # ── Author signals
    account_age = 9999
    followers = 0
    following = 0
    has_photo = 1
    is_verified = 0

    if author:
        # Tweepy v2 User.created_at is a datetime object, not a string.
        # .isoformat() produces "2024-01-01T00:00:00+00:00" (ISO 8601 with T separator)
        # str() produces "2024-01-01 00:00:00+00:00" (space separator) which
        # fromisoformat() handles in Python 3.11+ but NOT in 3.10.
        # .isoformat() is safe across Python 3.10+.
        # Tweepy v2 User.created_at is a datetime object; .isoformat() is safe on Python 3.10+.
        # str() produces space-separated format incompatible with fromisoformat on Python 3.10.
        _created_at_str = None
        if author.created_at:
            if hasattr(author.created_at, 'isoformat'):
                _created_at_str = author.created_at.isoformat()
            else:
                # Older Tweepy returned strings already in ISO format
                _created_at_str = author.created_at.replace(' ', 'T')
        account_age = account_age_in_days(_created_at_str)
        if author.public_metrics:
            followers = safe_int(author.public_metrics.get('followers_count', 0))
            following = safe_int(author.public_metrics.get('following_count', 0))
        has_photo = 0 if has_default_profile_photo(
            getattr(author, 'profile_image_url', None)
        ) else 1
        is_verified = 1 if getattr(author, 'verified', False) else 0

    # ── Tweet signals
    metrics = tweet.public_metrics or {}
    retweet_count = safe_int(metrics.get('retweet_count', 0))
    like_count = safe_int(metrics.get('like_count', 0))
    reply_count = safe_int(metrics.get('reply_count', 0))

    # ── URL signals
    entities = getattr(tweet, 'entities', None) or {}
    first_url = extract_first_url(tweet.text, entities)
    domain = extract_domain(first_url) if first_url else None
    contains_url = 1 if first_url else 0

    tweet_dict = {
        'tweet_id':                  str(tweet.id),
        'text':                      tweet.text,
        'created_at':                str(tweet.created_at) if tweet.created_at else None,
        'author_id':                 str(tweet.author_id),
        'account_age_days':          account_age,
        'followers_count':           followers,
        'following_count':           following,
        'has_profile_photo':         has_photo,
        'is_verified':               is_verified,
        'retweet_count':             retweet_count,
        'like_count':                like_count,
        'reply_count':               reply_count,
        'contains_url':              contains_url,
        'url_domain':                domain,
        'has_low_credibility_domain': 0,  # scorer.py will update this
        'has_keyword_signal':         0,  # scorer.py will update this
        'keyword_hit_count':          0,  # scorer.py will update this
        'signal_summary':             '',
        'collected_at':               now_iso(),
        'risk_score':                 0,
        'triage_decision':            'unscored',
        'ground_truth_label':         None,
    }

    # Score and route
    tweet_dict = score_tweet(tweet_dict)
    tweet_dict['triage_decision'] = triage_decision(tweet_dict['risk_score'])

    return tweet_dict


# ── COLLECTION LOOP ────────────────────────────────────────────────────────────

def run_collection():
    """
    Main collection loop. Polls the X API every POLL_INTERVAL_SECONDS.
    Runs indefinitely until Ctrl+C or monthly quota is exhausted.

    QUOTA GUARD: Logs cumulative tweet count. When cumulative > 9,500,
    the loop stops and prints a warning. The 500-tweet buffer is to avoid
    accidentally crossing the 10,000 boundary mid-request.
    """
    if not BEARER_TOKEN:
        logger.error(
            "X_BEARER_TOKEN not found in environment. "
            "Create a .env file with X_BEARER_TOKEN=your_token_here"
        )
        sys.exit(1)

    initialise_db()
    client = tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=True)

    request_num = 0
    cumulative_collected = get_total_count()

    logger.info(f"Starting collection. Existing records in DB: {cumulative_collected}")
    logger.info(f"Query: {QUERY}")
    logger.info(f"Poll interval: {POLL_INTERVAL_SECONDS}s | Max per request: {MAX_RESULTS_PER_REQUEST}")
    logger.info("Press Ctrl+C to stop cleanly.")

    try:
        while True:
            # ── QUOTA GUARD ──────────────────────────────────────────────────
            if cumulative_collected >= 9500:
                logger.warning(
                    f"Cumulative tweet count ({cumulative_collected}) approaching "
                    f"10,000 monthly quota. Stopping collection to avoid overage. "
                    f"Reset quota at the start of next calendar month."
                )
                break

            request_num += 1
            logger.info(f"Request #{request_num} | Cumulative so far: {cumulative_collected}")

            try:
                response = client.search_recent_tweets(
                    query=QUERY,
                    max_results=MAX_RESULTS_PER_REQUEST,
                    tweet_fields=[
                        'created_at', 'public_metrics',
                        'entities', 'lang', 'author_id'
                    ],
                    expansions=['author_id'],
                    user_fields=[
                        'created_at', 'public_metrics',
                        'profile_image_url', 'verified'
                    ]
                )

                if not response.data:
                    logger.info(f"Request #{request_num} returned 0 tweets (no results for query window).")
                    log_api_call(request_num, 0, cumulative_collected)
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                # Build author lookup dict
                users_by_id = {}
                if response.includes and 'users' in response.includes:
                    for user in response.includes['users']:
                        users_by_id[str(user.id)] = user

                # Process and store each tweet
                batch_count = 0
                for tweet in response.data:
                    tweet_dict = process_tweet(tweet, users_by_id)
                    insert_tweet(tweet_dict)
                    batch_count += 1

                cumulative_collected += batch_count
                log_api_call(request_num, batch_count, cumulative_collected)

            except tweepy.errors.TooManyRequests:
                # wait_on_rate_limit=True should handle this, but just in case
                logger.warning("Rate limit hit. Sleeping 15 minutes.")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            except tweepy.errors.Forbidden as e:
                logger.error(f"403 Forbidden: {e}. Check your API tier and token permissions.")
                break

            except tweepy.errors.TwitterServerError as e:
                logger.warning(f"Twitter server error: {e}. Retrying after 60 seconds.")
                time.sleep(60)
                continue

            logger.info(f"Sleeping {POLL_INTERVAL_SECONDS}s until next poll...")
            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info(f"\nCollection stopped by user. Total collected this run: {cumulative_collected} tweets.")
        logger.info(f"Data saved to SQLite. Run dashboard with: streamlit run dashboard/app.py")


if __name__ == '__main__':
    run_collection()
