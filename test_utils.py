"""
tests/test_utils.py — Unit tests for utility helper functions.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils import (
    extract_domain,
    account_age_in_days,
    has_default_profile_photo,
    extract_first_url,
    safe_int,
)


class TestExtractDomain:
    def test_standard_url_with_www(self):
        assert extract_domain('https://www.naturalnews.com/article.html') == 'naturalnews.com'

    def test_url_without_www(self):
        assert extract_domain('https://bbc.com/news') == 'bbc.com'

    def test_url_with_path_and_query(self):
        assert extract_domain('https://reuters.com/article?id=123&ref=abc') == 'reuters.com'

    def test_http_url(self):
        assert extract_domain('http://infowars.com/page') == 'infowars.com'

    def test_empty_string_returns_none(self):
        assert extract_domain('') is None

    def test_none_returns_none(self):
        assert extract_domain(None) is None

    def test_twitter_shortener(self):
        assert extract_domain('https://t.co/xyz123') == 't.co'

    def test_subdomain_is_stripped_to_registered(self):
        """www.example.com → example.com, but sub.example.com → sub.example.com.
        We strip www. only, not arbitrary subdomains."""
        assert extract_domain('https://www.bbc.com/news') == 'bbc.com'
        assert extract_domain('https://health.bbc.co.uk') == 'health.bbc.co.uk'


class TestAccountAgeInDays:
    def test_recent_account_returns_low_days(self):
        """An account created yesterday should return approximately 1 day."""
        from datetime import datetime, timezone, timedelta
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        age = account_age_in_days(yesterday)
        assert 0 <= age <= 2  # Allow 1-day buffer for timing

    def test_old_account_returns_high_days(self):
        """An account from 2015 should return ~3000+ days."""
        age = account_age_in_days('2015-01-01T00:00:00+00:00')
        assert age > 3000

    def test_missing_created_at_returns_safe_fallback(self):
        """Missing account age returns 9999 — will not trigger the new-account signal."""
        assert account_age_in_days(None) == 9999
        assert account_age_in_days('') == 9999

    def test_malformed_date_returns_safe_fallback(self):
        assert account_age_in_days('not-a-date') == 9999

    def test_z_suffix_handled(self):
        """Twitter API returns dates with Z suffix — must be parsed correctly."""
        age = account_age_in_days('2024-01-01T00:00:00.000Z')
        assert age > 0

    def test_result_is_never_negative(self):
        """account_age_days should never be negative."""
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        age = account_age_in_days(future)
        assert age >= 0


class TestHasDefaultProfilePhoto:
    def test_default_profile_image_url_detected(self):
        """Standard Twitter default avatar URLs should be detected."""
        assert has_default_profile_photo(
            'https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png'
        ) is True

    def test_custom_photo_url_not_detected(self):
        """A real user's photo URL should not trigger the default detection."""
        assert has_default_profile_photo(
            'https://pbs.twimg.com/profile_images/123456789/photo_normal.jpg'
        ) is False

    def test_none_url_treated_as_default(self):
        """Missing profile URL = no photo set = treat as default."""
        assert has_default_profile_photo(None) is True

    def test_empty_string_treated_as_default(self):
        assert has_default_profile_photo('') is True


class TestExtractFirstUrl:
    def test_extracts_url_from_text(self):
        text = "Check this out https://naturalnews.com/article.html"
        url = extract_first_url(text)
        assert url == 'https://naturalnews.com/article.html'

    def test_returns_none_for_text_without_url(self):
        text = "No URL in this tweet at all."
        url = extract_first_url(text)
        assert url is None

    def test_prefers_expanded_url_from_entities(self):
        """When entities dict is provided with expanded URLs, prefer those."""
        text = "Check this https://t.co/xyz"
        entities = {'urls': [{'url': 'https://t.co/xyz', 'expanded_url': 'https://naturalnews.com/full-article'}]}
        url = extract_first_url(text, entities)
        assert url == 'https://naturalnews.com/full-article'

    def test_falls_back_to_text_when_entities_empty(self):
        text = "Visit https://bbc.com/news"
        url = extract_first_url(text, entities={})
        assert url == 'https://bbc.com/news'


class TestSafeInt:
    def test_valid_int_string(self):
        assert safe_int('42') == 42

    def test_valid_int(self):
        assert safe_int(100) == 100

    def test_none_returns_default(self):
        assert safe_int(None) == 0
        assert safe_int(None, default=99) == 99

    def test_non_numeric_string_returns_default(self):
        assert safe_int('abc') == 0

    def test_float_truncates(self):
        assert safe_int(3.9) == 3
