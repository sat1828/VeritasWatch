"""
tests/test_scorer.py — Unit tests for the VeritasWatch scoring engine.

WHY THESE TESTS EXIST:
  The scoring engine is the intellectual core of the project. If the signals
  fire incorrectly, the entire pipeline produces garbage. These tests verify:
  
  1. Each individual signal fires exactly when expected and not otherwise
  2. Signal combinations produce correct total scores
  3. Score capping at 100 works
  4. Edge cases don't crash the engine (None values, zero followers, etc.)
  5. The blocklist integration works

  Running these tests before every commit is mandatory.
  A pipeline with untested scoring logic is not a pipeline — it is a hope.

RUNNING:
  pytest tests/test_scorer.py -v
  pytest tests/ -v --tb=short   # all tests

AUDIT NOTE ON WHAT IS NOT TESTED:
  - The content of the HIGH_RISK_PHRASES list (editorial decision, not logic)
  - The blocklist contents (data decision, not logic)
  - Database I/O (tested separately in test_database.py)
  - The Streamlit dashboard (UI testing is out of scope for this project)
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from scorer import score_tweet, HIGH_RISK_PHRASES, load_blocklist
from triage import triage_decision, DEFAULT_HOLD_THRESHOLD, DEFAULT_ESCALATE_THRESHOLD


# ── FIXTURES ──────────────────────────────────────────────────────────────────

def make_tweet(**overrides):
    """
    Return a tweet dict with all fields set to safe defaults.
    Override specific fields to test individual signals.

    Defaults represent a perfectly clean, established account
    with no risk signals — expected score: 0.
    """
    defaults = {
        'tweet_id': 'test_001',
        'text': 'Interesting data on vaccine immunogenicity. Long-term findings look reassuring.',
        'account_age_days': 1000,    # well-established account
        'followers_count': 5000,     # meaningful following
        'has_profile_photo': 1,      # has a photo
        'is_verified': 0,
        'retweet_count': 20,
        'like_count': 80,
        'reply_count': 10,
        'url_domain': 'bbc.com',     # clean domain
        'has_low_credibility_domain': 0,
        'has_keyword_signal': 0,
        'keyword_hit_count': 0,
        'signal_summary': '',
    }
    defaults.update(overrides)
    return defaults


# ── BASELINE: CLEAN TWEET SCORES ZERO ────────────────────────────────────────

class TestBaseline:
    def test_clean_tweet_scores_zero(self):
        """An established account with clean content should score zero.
        If this fails, a signal is firing without justification."""
        tweet = make_tweet()
        result = score_tweet(tweet)
        assert result['risk_score'] == 0, (
            f"Clean tweet scored {result['risk_score']}. "
            f"Signals fired: {result['signal_summary']}"
        )

    def test_clean_tweet_routes_to_auto_pass(self):
        tweet = make_tweet()
        result = score_tweet(tweet)
        decision = triage_decision(result['risk_score'])
        assert decision == 'auto-pass'

    def test_no_signals_fired_on_clean_tweet(self):
        tweet = make_tweet()
        result = score_tweet(tweet)
        assert result['signal_summary'] == 'no_signals'


# ── SIGNAL 1: ACCOUNT AGE ─────────────────────────────────────────────────────

class TestSignalAccountAge:
    def test_new_account_under_30_days_fires_at_plus_20(self):
        """Brand new account should score +20."""
        tweet = make_tweet(account_age_days=15)
        result = score_tweet(tweet)
        assert result['risk_score'] == 20
        assert 'new_account(<30d,+20)' in result['signal_summary']

    def test_account_29_days_triggers_new_account_signal(self):
        """29 days is still new — should fire at +20."""
        tweet = make_tweet(account_age_days=29)
        result = score_tweet(tweet)
        assert result['risk_score'] == 20

    def test_account_30_days_does_not_trigger_high_weight(self):
        """30 days exactly: should NOT trigger the <30d signal.
        Should trigger the 30-90d partial signal at +10."""
        tweet = make_tweet(account_age_days=30)
        result = score_tweet(tweet)
        assert result['risk_score'] == 10
        assert 'new_account(<30d,+20)' not in result['signal_summary']
        assert 'new_account(<90d,+10)' in result['signal_summary']

    def test_account_between_30_and_90_days_scores_plus_10(self):
        """30-90 day accounts: partial signal at +10."""
        for age in [31, 50, 89]:
            tweet = make_tweet(account_age_days=age)
            result = score_tweet(tweet)
            assert result['risk_score'] == 10, f"Age {age} scored {result['risk_score']}, expected 10"

    def test_account_90_days_exactly_does_not_trigger(self):
        """At 90 days, neither account age signal should fire."""
        tweet = make_tweet(account_age_days=90)
        result = score_tweet(tweet)
        assert result['risk_score'] == 0

    def test_established_account_does_not_trigger(self):
        """Old accounts score zero on account age."""
        for age in [91, 365, 1000, 3650]:
            tweet = make_tweet(account_age_days=age)
            result = score_tweet(tweet)
            assert result['risk_score'] == 0, f"Age {age} incorrectly scored {result['risk_score']}"


# ── SIGNAL 2: FOLLOWER COUNT ──────────────────────────────────────────────────

class TestSignalFollowerCount:
    def test_under_10_followers_scores_plus_15(self):
        tweet = make_tweet(followers_count=5)
        result = score_tweet(tweet)
        assert result['risk_score'] == 15
        assert 'low_followers(<10,+15)' in result['signal_summary']

    def test_zero_followers_triggers_low_follower_signal(self):
        """
        Zero followers is valid — new accounts start at zero.
        NOTE: The default make_tweet has retweet_count=20. With 0 followers,
        the RT velocity signal also fires (20/max(0,1) = 20x ratio > 10).
        This test uses retweet_count=5 to isolate the follower signal only.
        The interaction between zero followers and RT velocity is documented
        in SCORING_RATIONALE.md — it is not a bug, it is expected behaviour.
        """
        tweet = make_tweet(followers_count=0, retweet_count=5)
        result = score_tweet(tweet)
        assert 'low_followers(<10,+15)' in result['signal_summary']
        assert result['risk_score'] == 15  # Only follower signal fires at rt=5

    def test_exactly_10_followers_does_not_trigger_high_weight(self):
        """10 followers: should NOT trigger <10 signal. Triggers <50 at +5."""
        tweet = make_tweet(followers_count=10)
        result = score_tweet(tweet)
        assert result['risk_score'] == 5
        assert 'low_followers(<10,+15)' not in result['signal_summary']

    def test_under_50_followers_scores_plus_5(self):
        for count in [10, 25, 49]:
            tweet = make_tweet(followers_count=count)
            result = score_tweet(tweet)
            assert result['risk_score'] == 5, f"{count} followers scored {result['risk_score']}"

    def test_50_or_more_followers_does_not_trigger(self):
        for count in [50, 100, 1000, 100000]:
            tweet = make_tweet(followers_count=count)
            result = score_tweet(tweet)
            assert result['risk_score'] == 0, f"{count} followers scored {result['risk_score']}"


# ── SIGNAL 3: PROFILE PHOTO ───────────────────────────────────────────────────

class TestSignalProfilePhoto:
    def test_no_profile_photo_scores_plus_10(self):
        tweet = make_tweet(has_profile_photo=0)
        result = score_tweet(tweet)
        assert result['risk_score'] == 10
        assert 'no_profile_photo(+10)' in result['signal_summary']

    def test_has_profile_photo_does_not_score(self):
        tweet = make_tweet(has_profile_photo=1)
        result = score_tweet(tweet)
        assert 'no_profile_photo' not in result['signal_summary']


# ── SIGNAL 4: KEYWORD SIGNALS ─────────────────────────────────────────────────

class TestSignalKeywords:
    def test_two_keyword_hits_scores_plus_20(self):
        """Two high-risk phrases in text should score +20."""
        tweet = make_tweet(text="BREAKING: Government CONFIRMED covering up deaths.")
        result = score_tweet(tweet)
        assert result['risk_score'] == 20
        assert result['keyword_hit_count'] == 2
        assert 'keyword_match(2_hits,+20)' in result['signal_summary']

    def test_one_keyword_hit_scores_plus_10(self):
        tweet = make_tweet(text="BREAKING: New data on vaccine efficacy released.")
        result = score_tweet(tweet)
        assert result['risk_score'] == 10
        assert result['keyword_hit_count'] == 1
        assert 'keyword_match(1_hit,+10)' in result['signal_summary']

    def test_no_keywords_scores_zero(self):
        tweet = make_tweet(text="New paper on vaccine immunogenicity. Results are reassuring.")
        result = score_tweet(tweet)
        assert result['keyword_hit_count'] == 0
        assert result['risk_score'] == 0

    def test_three_keywords_still_scores_plus_20(self):
        """3+ keywords: same weight as 2. No additional bonus. Capped at +20 for this signal."""
        tweet = make_tweet(text="BREAKING: CONFIRMED CENSORED data. WAKE UP everyone.")
        result = score_tweet(tweet)
        # keyword contribution is capped at 20 regardless of count
        keyword_contribution = 20
        assert result['risk_score'] == keyword_contribution

    def test_keyword_matching_is_case_insensitive(self):
        """Keyword matching uses .upper() — all cases should match."""
        variants = [
            "breaking: new study",
            "BREAKING: new study",
            "Breaking: new study",
        ]
        for text in variants:
            tweet = make_tweet(text=text)
            result = score_tweet(tweet)
            assert result['keyword_hit_count'] >= 1, f"Case variant not matched: {text}"

    def test_word_boundary_prevents_substring_false_positives(self):
        """
        v1.1 fix: scorer now uses \bPHRASE\b word-boundary matching.
        'breakingly' must NOT match 'BREAKING' (was a bug in v1.0).
        Note: 'CONFIRMED-bias' DOES trigger 'CONFIRMED' — this is correct.
        Hyphen is a regex word boundary, so 'CONFIRMED' appears as a complete
        word token before the hyphen. This is expected behaviour.
        """
        tweet = make_tweet(text="The data is breakingly good news for vaccine coverage.")
        result = score_tweet(tweet)
        assert result['keyword_hit_count'] == 0, (
            f"'breakingly' must NOT match 'BREAKING'. Got {result['keyword_hit_count']} hits. "
            f"Word-boundary matching regression — check scorer.py _phrase_match()"
        )


# ── SIGNAL 5: DOMAIN BLOCKLIST ────────────────────────────────────────────────

class TestSignalDomain:
    def test_blocklisted_domain_scores_plus_15(self):
        """naturalnews.com is on the blocklist — should add +15."""
        tweet = make_tweet(url_domain='naturalnews.com')
        result = score_tweet(tweet)
        assert result['risk_score'] == 15
        assert 'bad_domain(naturalnews.com,+15)' in result['signal_summary']
        assert result['has_low_credibility_domain'] == 1

    def test_clean_domain_does_not_score(self):
        for domain in ['bbc.com', 'reuters.com', 'nejm.org', 'who.int']:
            tweet = make_tweet(url_domain=domain)
            result = score_tweet(tweet)
            assert result['risk_score'] == 0, f"{domain} incorrectly scored {result['risk_score']}"

    def test_none_domain_does_not_score(self):
        """Tweet with no URL should not trigger domain signal."""
        tweet = make_tweet(url_domain=None)
        result = score_tweet(tweet)
        assert 'bad_domain' not in result['signal_summary']

    def test_empty_string_domain_does_not_score(self):
        tweet = make_tweet(url_domain='')
        result = score_tweet(tweet)
        assert 'bad_domain' not in result['signal_summary']

    def test_blocklist_loads_without_error(self):
        """Blocklist should load and be non-empty."""
        blocklist = load_blocklist()
        assert isinstance(blocklist, set)
        assert len(blocklist) > 0
        assert 'naturalnews.com' in blocklist

    def test_graceful_degradation_with_missing_blocklist(self):
        """If blocklist file is missing, scorer should return empty set (not crash)."""
        blocklist = load_blocklist('/nonexistent/path.txt')
        assert blocklist == set()


# ── SIGNAL 6: RETWEET VELOCITY ────────────────────────────────────────────────

class TestSignalRetweetVelocity:
    def test_ratio_above_10x_scores_plus_20(self):
        """10 followers, 200 retweets = 20x ratio → +20."""
        tweet = make_tweet(followers_count=10, retweet_count=200)
        result = score_tweet(tweet)
        assert 'rt_velocity(ratio=' in result['signal_summary']
        # Should include +20 from ratio signal
        assert result['risk_score'] >= 20

    def test_absolute_over_500_scores_plus_15_when_ratio_under_10(self):
        """Large account (10000 followers), 600 retweets: ratio=0.06 (<10), absolute>500."""
        tweet = make_tweet(followers_count=10000, retweet_count=600)
        result = score_tweet(tweet)
        assert 'rt_velocity(abs>500,+15)' in result['signal_summary']

    def test_absolute_over_100_scores_plus_5(self):
        """5000 followers, 150 retweets: ratio=0.03 (<10), absolute 100-500."""
        tweet = make_tweet(followers_count=5000, retweet_count=150)
        result = score_tweet(tweet)
        assert 'rt_velocity(abs>100,+5)' in result['signal_summary']

    def test_low_retweet_count_does_not_score(self):
        tweet = make_tweet(followers_count=1000, retweet_count=50)
        result = score_tweet(tweet)
        assert 'rt_velocity' not in result['signal_summary']

    def test_zero_followers_does_not_cause_division_by_zero(self):
        """0 followers with any retweets: ratio should be safe (uses max(followers,1))."""
        tweet = make_tweet(followers_count=0, retweet_count=50)
        result = score_tweet(tweet)
        # Should not raise ZeroDivisionError and should fire ratio signal
        assert 'rt_velocity(ratio=' in result['signal_summary']


# ── SCORE COMBINATIONS ────────────────────────────────────────────────────────

class TestScoreCombinations:
    """
    Test that multi-signal combinations produce expected totals.
    These are the combinations that actually determine triage decisions.
    """

    def test_new_user_problem_combination(self):
        """
        Signal 1 (<30d: +20) + Signal 2 (<10f: +15) + Signal 3 (no photo: +10) = 45.
        A brand new legitimate user hits 45 → auto-hold.
        This is the documented 'New User Problem' false positive.
        """
        tweet = make_tweet(
            account_age_days=15,
            followers_count=5,
            has_profile_photo=0,
            text="Just joined Twitter. Excited to share ideas."
        )
        result = score_tweet(tweet)
        assert result['risk_score'] == 45
        assert triage_decision(45) == 'auto-hold'

    def test_minimum_escalation_combination(self):
        """
        Verify the minimum score required to reach escalate (61) is achievable.
        new<30(+20) + <10f(+15) + no_photo(+10) + 2+keywords(+20) = 65.
        """
        tweet = make_tweet(
            account_age_days=5,
            followers_count=3,
            has_profile_photo=0,
            text="BREAKING: CONFIRMED government hiding deaths. WAKE UP everyone."
        )
        result = score_tweet(tweet)
        assert result['risk_score'] >= 61
        assert triage_decision(result['risk_score']) == 'escalate'

    def test_single_signal_cannot_escalate(self):
        """
        No single signal (max weight 20) should be able to reach the escalate
        threshold alone (61). This is by design.
        """
        single_signal_tweets = [
            make_tweet(account_age_days=5),                         # Signal 1 only: 20
            make_tweet(followers_count=3),                          # Signal 2 only: 15
            make_tweet(has_profile_photo=0),                        # Signal 3 only: 10
            make_tweet(text="BREAKING CONFIRMED data released."),   # Signal 4 only: 20
            make_tweet(url_domain='naturalnews.com'),               # Signal 5 only: 15
            make_tweet(followers_count=5, retweet_count=200),       # Signal 6 only: 20+15
        ]
        for tweet in single_signal_tweets:
            result = score_tweet(tweet)
            assert result['risk_score'] < 61, (
                f"Single signal tweet reached escalation with score {result['risk_score']}. "
                f"Signals: {result['signal_summary']}"
            )

    def test_score_is_capped_at_100(self):
        """All signals firing simultaneously should not exceed 100."""
        tweet = make_tweet(
            account_age_days=2,
            followers_count=1,
            has_profile_photo=0,
            url_domain='naturalnews.com',
            retweet_count=5000,
            text="BREAKING CONFIRMED CENSORED BANNED VIDEO WAKE UP SHARE BEFORE DELETED."
        )
        result = score_tweet(tweet)
        assert result['risk_score'] <= 100

    def test_journalism_trap(self):
        """
        A journalist tweeting 'BREAKING: Government CONFIRMS irregularities'
        picks up Signal 4 (2 keywords: +20). With an established account,
        this stays below the auto-hold threshold (36).
        But if the journalist has a newer account, they land in auto-hold.
        This is the documented Journalism Trap false positive.
        """
        # Established journalist: score should stay low
        established = make_tweet(
            account_age_days=2000,
            followers_count=50000,
            text="BREAKING: Government CONFIRMS new investigation into election irregularities — Reuters"
        )
        result_est = score_tweet(established)
        assert result_est['risk_score'] == 20  # Only keyword signal fires
        assert triage_decision(result_est['risk_score']) == 'auto-pass'

        # Newer journalist or legitimate user: may land in auto-hold
        newer = make_tweet(
            account_age_days=45,
            followers_count=200,
            text="BREAKING: Government CONFIRMS new investigation — this is big news."
        )
        result_new = score_tweet(newer)
        # 45-day account (+10) + 2 keywords (+20) = 30 — still auto-pass
        assert result_new['risk_score'] == 30
        assert triage_decision(result_new['risk_score']) == 'auto-pass'


# ── OUTPUT FIELDS ─────────────────────────────────────────────────────────────

class TestOutputFields:
    def test_score_tweet_returns_risk_score(self):
        tweet = make_tweet()
        result = score_tweet(tweet)
        assert 'risk_score' in result
        assert isinstance(result['risk_score'], int)

    def test_score_tweet_returns_signal_summary(self):
        tweet = make_tweet()
        result = score_tweet(tweet)
        assert 'signal_summary' in result
        assert isinstance(result['signal_summary'], str)

    def test_score_tweet_returns_keyword_hit_count(self):
        tweet = make_tweet()
        result = score_tweet(tweet)
        assert 'keyword_hit_count' in result
        assert isinstance(result['keyword_hit_count'], int)

    def test_score_tweet_returns_has_keyword_signal(self):
        tweet = make_tweet()
        result = score_tweet(tweet)
        assert 'has_keyword_signal' in result

    def test_score_tweet_sets_has_low_credibility_domain(self):
        """Scorer should update has_low_credibility_domain when domain is on blocklist."""
        tweet = make_tweet(url_domain='naturalnews.com')
        result = score_tweet(tweet)
        assert result['has_low_credibility_domain'] == 1

    def test_score_is_always_non_negative(self):
        for _ in range(20):
            import random
            tweet = make_tweet(
                account_age_days=random.randint(0, 3000),
                followers_count=random.randint(0, 100000),
                retweet_count=random.randint(0, 5000),
            )
            result = score_tweet(tweet)
            assert result['risk_score'] >= 0


# ── TRIAGE DECISIONS ──────────────────────────────────────────────────────────

class TestTriageDecision:
    def test_score_0_routes_auto_pass(self):
        assert triage_decision(0) == 'auto-pass'

    def test_score_35_routes_auto_pass(self):
        assert triage_decision(35) == 'auto-pass'

    def test_score_36_routes_auto_hold(self):
        assert triage_decision(36) == 'auto-hold'

    def test_score_60_routes_auto_hold(self):
        assert triage_decision(60) == 'auto-hold'

    def test_score_61_routes_escalate(self):
        assert triage_decision(61) == 'escalate'

    def test_score_100_routes_escalate(self):
        assert triage_decision(100) == 'escalate'

    def test_custom_thresholds_work(self):
        """Threshold overrides (used by dashboard sliders) should work correctly."""
        assert triage_decision(40, hold_threshold=50, escalate_threshold=70) == 'auto-pass'
        assert triage_decision(55, hold_threshold=50, escalate_threshold=70) == 'auto-hold'
        assert triage_decision(75, hold_threshold=50, escalate_threshold=70) == 'escalate'

    def test_default_thresholds_match_documented_values(self):
        """Thresholds in triage.py must match what SCORING_RATIONALE.md documents."""
        assert DEFAULT_HOLD_THRESHOLD == 36
        assert DEFAULT_ESCALATE_THRESHOLD == 61
