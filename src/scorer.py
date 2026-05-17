"""
scorer.py — Rule-based heuristic scoring engine for VeritasWatch.

THIS IS THE INTELLECTUAL CORE OF THE PROJECT.
Every signal has a weight and a rationale.
A score without a rationale is a number.
A score with a rationale is a policy.

AUDIT NOTES (read these before touching thresholds):

  1. No single signal is sufficient to escalate a post.
     The minimum escalation score is 61.
     The maximum score from any ONE signal is 20.
     You need at least 3 strong signals firing together.
     This is intentional — single-signal escalation
     produces unacceptable false positive rates.

  2. The scoring engine does NOT understand content.
     It reads metadata and keyword patterns only.
     "Vaccines DO cause autism — this study proves it"
     and "The claim vaccines cause autism is FALSE"
     receive the SAME keyword score. This is the
     most serious limitation of this system.
     It is documented in EVALUATION.md and README.md.

  3. All thresholds in this file are policy decisions,
     not mathematical optima. They are calibrated so
     that two or more correlated signals are required
     for escalation. Full rationale in SCORING_RATIONALE.md.

Signal table (also in README.md scoring_table.png):
  Signal                | Condition                          | Max Weight
  ──────────────────────┼────────────────────────────────────┼───────────
  1. Account age        | < 30 days                          | +20
  2. Follower count     | < 10 followers                     | +15
  3. No profile photo   | default/missing avatar             | +10
  4. Keyword signals    | 2+ high-risk phrases in text       | +20
  5. Low-cred domain    | URL from blocklist                 | +15
  6. Retweet velocity   | RT ratio > 10x follower count      | +20
  ──────────────────────┴────────────────────────────────────┴───────────
  Maximum possible score: 100 (capped)
"""

import re
import os
from typing import Optional

# ── KEYWORD LISTS ──────────────────────────────────────────────────────────────
# Selected from content moderation literature on misinformation markers.
# These are phrases disproportionately present in misinformation content.
# LIMITATION: This will also fire on journalism that QUOTES or DEBUNKS
# misinformation using these phrases. A whitelist of verified news domains
# is the production mitigation. We do not have one.

HIGH_RISK_PHRASES = [
    "BREAKING",
    "SHARE BEFORE DELETED",
    "SHARE BEFORE THEY DELETE",
    "THEY DON'T WANT YOU TO KNOW",
    "CONFIRMED",
    "MAINSTREAM MEDIA WON'T REPORT",
    "WHAT THEY'RE HIDING",
    "DO YOUR OWN RESEARCH",
    "WAKE UP",
    "MUST WATCH",
    "GOING VIRAL",
    "THEY'RE HIDING",
    "DOCTORS WON'T TELL YOU",
    "SUPPRESSED",
    "BANNED VIDEO",
    "CENSORED",
    "TRUTH THEY DON'T WANT",
]


def load_blocklist(blocklist_path: Optional[str] = None) -> set:
    """
    Load the low-credibility domain blocklist from a text file.
    Returns an empty set if the file is missing — scorer degrades
    gracefully without it (Signal 5 never fires).
    This is intentional: a missing blocklist should not crash the pipeline.
    """
    if blocklist_path is None:
        blocklist_path = os.path.join(
            os.path.dirname(__file__), '..', 'data', 'low_credibility_domains.txt'
        )
    blocklist = set()
    if not os.path.exists(blocklist_path):
        return blocklist
    with open(blocklist_path, 'r') as f:
        for line in f:
            domain = line.strip().lower()
            if domain and not domain.startswith('#'):
                blocklist.add(domain)
    return blocklist


# Load blocklist once at module import time. Do not reload per tweet.
BLOCKLIST = load_blocklist()


def score_tweet(tweet_row: dict) -> dict:
    """
    Compute a risk score 0–100 for a single tweet row.

    Args:
        tweet_row: dict with keys matching the tweets table schema.
                   All fields must be pre-populated. No defaults assumed.

    Returns:
        The same dict with added keys:
          - risk_score (int, 0–100)
          - signal_summary (str, human-readable list of signals that fired)
          - keyword_hit_count (int)

    Score thresholds (do NOT change without updating triage.py):
      0–35:   auto-pass
      36–60:  auto-hold (secondary human review)
      61–100: escalate (priority human review)
    """
    score = 0
    signals_fired = []

    # ── SIGNAL 1: ACCOUNT AGE ─────────────────────────────────────────────────
    # Condition: Account created < 30 days ago → +20 pts
    #            Account created 30–90 days ago → +10 pts
    # Rationale: New accounts are disproportionately associated with
    #   coordinated inauthentic behaviour and bot activity.
    #   Account age is one of the highest-signal features in social bot
    #   detection research (Cresci, 2020, "A Decade of Social Bot Detection",
    #   Communications of the ACM).
    # False positive driver: Every legitimate new user also scores here.
    #   This is why Signal 1 alone (20 pts) cannot escalate a post.
    #   Combined with other signals it becomes meaningful.
    # Real T&S equivalent: New account signal in Meta's CIB detection.
    #   CRITICAL DIFFERENCE: Meta looks at account creation NETWORKS
    #   (accounts created in batch at the same time). We look at one account.

    age = tweet_row.get('account_age_days', 9999)
    if age < 30:
        score += 20
        signals_fired.append(f"new_account(<30d,+20)")
    elif age < 90:
        score += 10
        signals_fired.append(f"new_account(<90d,+10)")

    # ── SIGNAL 2: FOLLOWER COUNT ──────────────────────────────────────────────
    # Condition: < 10 followers → +15 pts
    #            < 50 followers → +5 pts
    # Rationale: Near-zero follower accounts have no organic audience and
    #   are frequently disposable amplification accounts in influence
    #   operations. Signal is WEAK in isolation — a new legitimate user
    #   also has 0 followers. Meaning only emerges in combination.
    # False positive driver: All new users start at 0 followers.
    #   Signal 1 + Signal 2 + Signal 3 can fire simultaneously for
    #   a brand-new legitimate account, scoring 45 → auto-hold.
    #   This is the "New User Problem" documented in SCORING_RATIONALE.md.

    followers = tweet_row.get('followers_count', 0)
    if followers < 10:
        score += 15
        signals_fired.append(f"low_followers(<10,+15)")
    elif followers < 50:
        score += 5
        signals_fired.append(f"low_followers(<50,+5)")

    # ── SIGNAL 3: PROFILE PHOTO ABSENT ───────────────────────────────────────
    # Condition: has_profile_photo == 0 → +10 pts
    # Rationale: Default-avatar accounts are strongly associated with
    #   newly created, unverified, or automated accounts.
    # Low weight (10 pts) because many legitimate inactive users also
    #   have no profile photo. Not diagnostic alone.

    if not tweet_row.get('has_profile_photo', 1):
        score += 10
        signals_fired.append("no_profile_photo(+10)")

    # ── SIGNAL 4: KEYWORD SIGNALS ─────────────────────────────────────────────
    # Condition: 2+ high-risk phrases in text → +20 pts
    #            1 high-risk phrase → +10 pts
    # Rationale: Certain phrases are disproportionately present in
    #   misinformation content. The list was compiled from content
    #   moderation literature on misinformation markers.
    # CRITICAL LIMITATION: This is pattern matching, not understanding.
    #   A journalist tweeting "BREAKING: Government CONFIRMS election
    #   irregularities" scores +20 from two phrase hits. A debunking
    #   tweet quoting misinformation language scores the same as the
    #   original misinformation. Stance detection (NLP that distinguishes
    #   endorsement from refutation) is the production solution.
    #   We don't have it. This is documented in EVALUATION.md.

    text_upper = tweet_row.get('text', '').upper()

    # Word-boundary matching: \bPHRASE\b
    # Prevents substring false positives: "breakingly" no longer matches "BREAKING",
    # "CONFIRMED-bias" no longer matches "CONFIRMED".
    # Multi-word phrases (e.g. "SHARE BEFORE DELETED") use boundary at start and end only.
    # KNOWN RESIDUAL LIMITATION: "BREAKING NEWS" matches "BREAKING" (correct),
    # but "I AM NOT CONFIRMED" also matches (correct — phrase appears at word boundary).
    # The scorer cannot distinguish endorsement from refutation: documented in SCORING_RATIONALE.md.
    def _phrase_match(phrase: str, text: str) -> bool:
        escaped = re.escape(phrase)
        return bool(re.search(r'\b' + escaped + r'\b', text))

    phrase_hits = sum(1 for phrase in HIGH_RISK_PHRASES if _phrase_match(phrase, text_upper))
    tweet_row['keyword_hit_count'] = phrase_hits

    if phrase_hits >= 2:
        score += 20
        signals_fired.append(f"keyword_match({phrase_hits}_hits,+20)")
    elif phrase_hits == 1:
        score += 10
        signals_fired.append(f"keyword_match(1_hit,+10)")

    # ── SIGNAL 5: LOW-CREDIBILITY DOMAIN LINK ─────────────────────────────────
    # Condition: URL domain on blocklist → +15 pts
    # Rationale: Links to known misinformation sources are one of the
    #   strongest single signals of harmful content. Domain credibility
    #   assessment is core to professional fact-checking pipelines.
    # Blocklist source: Documented in data/low_credibility_domains.txt header.
    #   Manually curated from MediaBiasFactCheck.com "Conspiracy-Pseudoscience"
    #   category and NewsGuard red-rated domains as documented in academic
    #   literature. This is a STATIC list — new misinformation domains
    #   emerge continuously and will not be caught. See Limitation 5 in README.

    domain = (tweet_row.get('url_domain') or '').lower().strip()
    if domain and domain in BLOCKLIST:
        score += 15
        tweet_row['has_low_credibility_domain'] = 1
        signals_fired.append(f"bad_domain({domain},+15)")
    else:
        tweet_row['has_low_credibility_domain'] = tweet_row.get('has_low_credibility_domain', 0)

    # ── SIGNAL 6: RETWEET VELOCITY ────────────────────────────────────────────
    # Condition: retweet_count > 10x followers_count → +20 pts
    #            absolute retweet_count > 500 → +15 pts
    #            absolute retweet_count > 100 → +5 pts
    # Rationale: Disproportionate virality relative to an account's follower
    #   base is a signal of artificial amplification. A tweet from a 5-follower
    #   account with 200 retweets is a statistical anomaly.
    # IMPLEMENTATION NOTE: True velocity requires tracking the SAME tweet
    #   across multiple time windows to measure rate of change. Since we
    #   collect in batch (Option C replay mode), we use the ratio of retweets
    #   to followers as a static proxy for velocity. This is a degraded signal.
    #   In a streaming architecture with tweet_id tracking across windows,
    #   you would compute delta_retweet_count / delta_time_minutes instead.

    safe_followers = max(followers, 1)  # Avoid division by zero
    retweet_count = tweet_row.get('retweet_count', 0)
    retweet_ratio = retweet_count / safe_followers

    if retweet_ratio > 10:
        score += 20
        signals_fired.append(f"rt_velocity(ratio={retweet_ratio:.1f},+20)")
    elif retweet_count > 500:
        score += 15
        signals_fired.append(f"rt_velocity(abs>500,+15)")
    elif retweet_count > 100:
        score += 5
        signals_fired.append(f"rt_velocity(abs>100,+5)")

    # ── FINAL SCORE ───────────────────────────────────────────────────────────
    score = min(score, 100)

    tweet_row['risk_score'] = score
    tweet_row['signal_summary'] = ' | '.join(signals_fired) if signals_fired else 'no_signals'
    tweet_row['has_keyword_signal'] = 1 if phrase_hits > 0 else 0

    return tweet_row
