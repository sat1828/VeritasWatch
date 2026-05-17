"""
utils.py — Helper functions for VeritasWatch.

These are utility functions used across multiple modules.
Each function does one thing and has no side effects.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Optional


def extract_domain(url: str) -> Optional[str]:
    """
    Extract the registered domain from a URL string.
    Returns None if the URL is malformed or empty.

    Examples:
        "https://www.naturalnews.com/article.html" → "naturalnews.com"
        "http://t.co/xyz"                          → "t.co"  (Twitter shortener — low value)
        ""                                          → None
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.lower()
        # Strip www. prefix
        if hostname.startswith('www.'):
            hostname = hostname[4:]
        return hostname if hostname else None
    except Exception:
        return None


def account_age_in_days(created_at_str: str) -> int:
    """
    Compute account age in days from a Twitter ISO 8601 created_at string.
    Returns 9999 if the string is missing or unparseable (safe fallback —
    a 9999-day-old account will not trigger the new-account signal).

    Args:
        created_at_str: e.g. "2024-12-15T14:32:00.000Z"

    Returns:
        Integer number of days since account creation.
    """
    if not created_at_str:
        return 9999
    try:
        # Handle both Z suffix and +00:00 offset
        created_at_str = created_at_str.replace('Z', '+00:00')
        created_dt = datetime.fromisoformat(created_at_str)
        now = datetime.now(timezone.utc)
        delta = now - created_dt
        return max(0, delta.days)
    except (ValueError, TypeError):
        return 9999


def has_default_profile_photo(profile_image_url: str) -> bool:
    """
    Return True if the profile image URL indicates a default/missing avatar.
    X/Twitter uses specific URL patterns for default profile images.

    This check is heuristic — it looks for known default image identifiers
    in the URL string. A missing URL is treated as a default photo.
    """
    if not profile_image_url:
        return True
    url_lower = profile_image_url.lower()
    default_indicators = [
        'default_profile',
        'default_profile_images',
        'twimg.com/sticky/default_profile_images',
    ]
    return any(indicator in url_lower for indicator in default_indicators)


def extract_first_url(tweet_text: str, entities: Optional[dict] = None) -> Optional[str]:
    """
    Extract the first URL from a tweet.
    Prefers the entities dict (which has expanded URLs).
    Falls back to regex on raw text (which will find t.co shorteners).

    Returns the URL string or None.
    """
    # Prefer entities.urls if available
    if entities and 'urls' in entities and entities['urls']:
        url_obj = entities['urls'][0]
        return url_obj.get('expanded_url') or url_obj.get('url')

    # Regex fallback on raw text
    url_pattern = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'
    )
    match = url_pattern.search(tweet_text or '')
    return match.group(0) if match else None


def format_signal_summary(signals_fired: list) -> str:
    """
    Format a list of signal strings into a human-readable summary.
    Used for dashboard display and CSV export.
    """
    if not signals_fired:
        return "no_signals"
    return ' | '.join(signals_fired)


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string. Used for collected_at timestamps."""
    return datetime.now(timezone.utc).isoformat()


def safe_int(value, default: int = 0) -> int:
    """Convert a value to int safely, returning default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
