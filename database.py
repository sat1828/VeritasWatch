"""
database.py — SQLite read/write functions for VeritasWatch.

All persistent state lives in a single SQLite file.
No ORM. Explicit SQL. Each function does one thing.

AUDIT NOTE:
  - INSERT OR IGNORE is used everywhere to make collection
    re-entrant. Run collector.py twice, you get no duplicates.
  - No delete operations are implemented intentionally.
    This is a triage dashboard, not a moderation system.
    We do not remove content.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'collected_tweets.db')


def get_connection():
    """Return a connection with row_factory set to dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialise_db():
    """
    Create the tweets table if it does not already exist.
    Call this once at startup before any reads or writes.
    Schema is append-only after first run — no ALTER TABLE.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tweets (
            tweet_id                  TEXT PRIMARY KEY,
            text                      TEXT NOT NULL,
            created_at                TEXT,
            author_id                 TEXT,
            account_age_days          INTEGER,
            followers_count           INTEGER,
            following_count           INTEGER,
            has_profile_photo         INTEGER DEFAULT 0,   -- 1 or 0
            is_verified               INTEGER DEFAULT 0,   -- 1 or 0
            retweet_count             INTEGER DEFAULT 0,
            like_count                INTEGER DEFAULT 0,
            reply_count               INTEGER DEFAULT 0,
            contains_url              INTEGER DEFAULT 0,   -- 1 or 0
            url_domain                TEXT,
            has_low_credibility_domain INTEGER DEFAULT 0,  -- 1 or 0
            has_keyword_signal        INTEGER DEFAULT 0,   -- 1 or 0
            keyword_hit_count         INTEGER DEFAULT 0,
            signal_summary            TEXT,                -- human-readable signal list
            collected_at              TEXT,
            risk_score                INTEGER,
            triage_decision           TEXT,
            ground_truth_label        INTEGER              -- NULL until manually labelled
        )
    """)
    conn.commit()
    conn.close()


def insert_tweet(tweet_dict: dict):
    """
    Insert a single scored tweet into the database.
    INSERT OR IGNORE — duplicate tweet_ids are silently dropped.
    All scoring fields must be set on the dict before calling this.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO tweets (
            tweet_id, text, created_at, author_id,
            account_age_days, followers_count, following_count,
            has_profile_photo, is_verified,
            retweet_count, like_count, reply_count,
            contains_url, url_domain, has_low_credibility_domain,
            has_keyword_signal, keyword_hit_count, signal_summary,
            collected_at, risk_score, triage_decision, ground_truth_label
        ) VALUES (
            :tweet_id, :text, :created_at, :author_id,
            :account_age_days, :followers_count, :following_count,
            :has_profile_photo, :is_verified,
            :retweet_count, :like_count, :reply_count,
            :contains_url, :url_domain, :has_low_credibility_domain,
            :has_keyword_signal, :keyword_hit_count, :signal_summary,
            :collected_at, :risk_score, :triage_decision, :ground_truth_label
        )
    """, tweet_dict)
    conn.commit()
    conn.close()


def fetch_all_tweets():
    """Return all rows as a list of dicts. Used by the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tweets ORDER BY collected_at ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def fetch_tweets_by_decision(decision: str):
    """Return all tweets matching a specific triage decision."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM tweets WHERE triage_decision = ? ORDER BY collected_at ASC",
        (decision,)
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def fetch_escalated_unlabelled():
    """
    Return all escalated tweets that have NOT been manually labelled yet.
    Used by the evaluation step.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tweets
        WHERE triage_decision = 'escalate'
        AND ground_truth_label IS NULL
        ORDER BY risk_score DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_queue_counts():
    """
    Return dict of counts per triage decision.
    Used by dashboard metrics row.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT triage_decision, COUNT(*) as count
        FROM tweets
        GROUP BY triage_decision
    """)
    counts = {row['triage_decision']: row['count'] for row in cursor.fetchall()}
    conn.close()
    return {
        'auto-pass': counts.get('auto-pass', 0),
        'auto-hold': counts.get('auto-hold', 0),
        'escalate': counts.get('escalate', 0),
        'total': sum(counts.values())
    }


def get_score_distribution():
    """Return list of (tweet_id, risk_score, triage_decision) for histogram."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tweet_id, risk_score, triage_decision FROM tweets")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_total_count():
    """Return total tweet count in db."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as n FROM tweets")
    n = cursor.fetchone()['n']
    conn.close()
    return n
