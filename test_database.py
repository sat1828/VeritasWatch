"""
tests/test_database.py — Integration tests for the database layer.

Uses a temporary in-memory SQLite database to avoid touching the real data.
All tests are isolated — no shared state between test functions.
"""

import sys
import os
import pytest
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# We need to patch DB_PATH before importing database
import database as db_module


def fresh_db(tmp_path):
    """Return a path for a fresh temp database and patch the module."""
    db_path = str(tmp_path / 'test.db')
    db_module.DB_PATH = db_path
    db_module.initialise_db()
    return db_path


def sample_tweet(tweet_id='t001'):
    return {
        'tweet_id': tweet_id,
        'text': 'Test tweet text',
        'created_at': '2024-01-01T00:00:00+00:00',
        'author_id': 'u001',
        'account_age_days': 100,
        'followers_count': 50,
        'following_count': 30,
        'has_profile_photo': 1,
        'is_verified': 0,
        'retweet_count': 5,
        'like_count': 10,
        'reply_count': 2,
        'contains_url': 0,
        'url_domain': None,
        'has_low_credibility_domain': 0,
        'has_keyword_signal': 0,
        'keyword_hit_count': 0,
        'signal_summary': 'no_signals',
        'collected_at': '2024-01-15T12:00:00+00:00',
        'risk_score': 0,
        'triage_decision': 'auto-pass',
        'ground_truth_label': None,
    }


class TestInitialiseDb:
    def test_initialise_creates_tweets_table(self, tmp_path):
        fresh_db(tmp_path)
        conn = sqlite3.connect(db_module.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tweets'")
        result = cursor.fetchone()
        conn.close()
        assert result is not None

    def test_initialise_is_idempotent(self, tmp_path):
        """Calling initialise_db twice should not raise an error."""
        fresh_db(tmp_path)
        db_module.initialise_db()  # Second call
        assert True  # No exception raised


class TestInsertTweet:
    def test_insert_single_tweet(self, tmp_path):
        fresh_db(tmp_path)
        tweet = sample_tweet('t001')
        db_module.insert_tweet(tweet)
        assert db_module.get_total_count() == 1

    def test_insert_or_ignore_prevents_duplicates(self, tmp_path):
        fresh_db(tmp_path)
        tweet = sample_tweet('t001')
        db_module.insert_tweet(tweet)
        db_module.insert_tweet(tweet)  # Same tweet_id again
        assert db_module.get_total_count() == 1

    def test_different_tweet_ids_both_inserted(self, tmp_path):
        fresh_db(tmp_path)
        db_module.insert_tweet(sample_tweet('t001'))
        db_module.insert_tweet(sample_tweet('t002'))
        assert db_module.get_total_count() == 2

    def test_inserted_tweet_fields_are_retrievable(self, tmp_path):
        fresh_db(tmp_path)
        tweet = sample_tweet('t001')
        tweet['risk_score'] = 45
        tweet['triage_decision'] = 'auto-hold'
        db_module.insert_tweet(tweet)

        rows = db_module.fetch_all_tweets()
        assert len(rows) == 1
        assert rows[0]['risk_score'] == 45
        assert rows[0]['triage_decision'] == 'auto-hold'
        assert rows[0]['tweet_id'] == 't001'


class TestFetchTweets:
    def test_fetch_all_returns_all_tweets(self, tmp_path):
        fresh_db(tmp_path)
        for i in range(5):
            db_module.insert_tweet(sample_tweet(f't{i:03d}'))
        rows = db_module.fetch_all_tweets()
        assert len(rows) == 5

    def test_fetch_by_decision_filters_correctly(self, tmp_path):
        fresh_db(tmp_path)
        t1 = sample_tweet('t001')
        t1['triage_decision'] = 'auto-pass'
        t2 = sample_tweet('t002')
        t2['triage_decision'] = 'escalate'
        db_module.insert_tweet(t1)
        db_module.insert_tweet(t2)

        escalated = db_module.fetch_tweets_by_decision('escalate')
        assert len(escalated) == 1
        assert escalated[0]['tweet_id'] == 't002'

    def test_fetch_empty_db_returns_empty_list(self, tmp_path):
        fresh_db(tmp_path)
        assert db_module.fetch_all_tweets() == []


class TestGetQueueCounts:
    def test_counts_match_inserted_decisions(self, tmp_path):
        fresh_db(tmp_path)
        decisions = ['auto-pass', 'auto-pass', 'auto-hold', 'escalate', 'auto-pass']
        for i, d in enumerate(decisions):
            t = sample_tweet(f't{i:03d}')
            t['triage_decision'] = d
            db_module.insert_tweet(t)

        counts = db_module.get_queue_counts()
        assert counts['auto-pass'] == 3
        assert counts['auto-hold'] == 1
        assert counts['escalate'] == 1
        assert counts['total'] == 5

    def test_counts_on_empty_db(self, tmp_path):
        fresh_db(tmp_path)
        counts = db_module.get_queue_counts()
        assert counts['auto-pass'] == 0
        assert counts['auto-hold'] == 0
        assert counts['escalate'] == 0
        assert counts['total'] == 0


class TestGetTotalCount:
    def test_total_count_correct(self, tmp_path):
        fresh_db(tmp_path)
        assert db_module.get_total_count() == 0
        db_module.insert_tweet(sample_tweet('t001'))
        assert db_module.get_total_count() == 1
        db_module.insert_tweet(sample_tweet('t002'))
        assert db_module.get_total_count() == 2
