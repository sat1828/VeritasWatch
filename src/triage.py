"""
triage.py — Triage routing logic for VeritasWatch.

THIS FILE IS DELIBERATELY SIMPLE.
Complexity belongs in the scoring engine (scorer.py),
not in the routing logic. A threshold is a policy decision.
It should be readable in plain English by a non-engineer.

AUDIT NOTES:

  THRESHOLD RATIONALE (do not change without documentation):
    35 / 60 were chosen so that:
      - A single high-weight signal (max 20 pts) cannot escalate alone
      - Escalation requires 3+ meaningful signals firing together
      - Auto-hold catches "borderline" posts that need a human look
        but are not urgent enough for priority review
      - At 35+, at least two signals have fired (minimum meaningful combination)

    Example that just reaches auto-hold (36 pts):
      Signal 1 (new account < 30d) = +20
      Signal 3 (no profile photo)  = +10
      Signal 2 (< 50 followers)    = + 5
      Signal 4 (1 keyword hit)     = +10
                               Total = 45 → auto-hold  ← correct

    Example that just reaches escalate (61 pts):
      Signal 1 (new account < 30d) = +20
      Signal 2 (< 10 followers)    = +15
      Signal 3 (no profile photo)  = +10
      Signal 4 (2+ keyword hits)   = +20
                               Total = 65 → escalate   ← correct

  CRITICAL: "escalate" does NOT mean "remove".
    All triage decisions route to human review.
    No content is actioned automatically.
    The escalate queue means "priority human review".
    The auto-hold queue means "secondary human review".
    The auto-pass queue means "no review unless sampled for QA".
    This distinction must be clear in all dashboard labels.

  THRESHOLD OVERRIDE:
    The Streamlit dashboard exposes sidebar sliders that allow
    live threshold adjustment. This is intentional — it demonstrates
    that thresholds are policy decisions, not mathematical constants.
    A T&S policy team adjusts thresholds based on:
      - Queue volume vs. moderator capacity
      - Time-sensitive events (elections, health emergencies)
      - Observed false positive / false negative rates from QA
    The slider makes this visible to a recruiter in a live demo.
"""


DEFAULT_HOLD_THRESHOLD = 36      # Score >= this → auto-hold (not auto-pass)
DEFAULT_ESCALATE_THRESHOLD = 61  # Score >= this → escalate (not auto-hold)


def triage_decision(
    score: int,
    hold_threshold: int = DEFAULT_HOLD_THRESHOLD,
    escalate_threshold: int = DEFAULT_ESCALATE_THRESHOLD
) -> str:
    """
    Route a tweet to one of three review queues based on risk score.

    Args:
        score: Integer 0–100 from scorer.py
        hold_threshold: Minimum score for auto-hold (default 36)
        escalate_threshold: Minimum score for escalate (default 61)

    Returns:
        One of: 'auto-pass', 'auto-hold', 'escalate'

    NOTE: Thresholds are parametric so the dashboard can override them
    live via sidebar sliders. The pipeline itself never hardcodes them.
    """
    if score >= escalate_threshold:
        return "escalate"
        # Priority human review.
        # Multiple strong signals fired together.
        # Still NOT automatic action — a senior moderator reviews first.

    elif score >= hold_threshold:
        return "auto-hold"
        # Secondary human review.
        # Some signals fired but not at highest combined intensity.
        # Not urgent — no time SLA in this demo system.
        # LIMITATION: Production queues have defined SLAs per tier
        # (e.g. graphic violence: < 1 hour regardless of score).
        # We do not implement SLAs.

    else:
        return "auto-pass"
        # No significant signal combination detected.
        # Content is not reviewed.
        # LIMITATION: Production systems sample auto-passed content
        # for QA audits to catch false negatives over time.
        # We do not implement sampling.
        # The dormant account problem lives here — sophisticated actors
        # using old accounts with clean language will auto-pass.
        # This is documented as Limitation 1 in README.md.


def describe_decision(decision: str) -> str:
    """
    Return a plain-English description of a triage decision.
    Used in dashboard captions and signal_summary display.
    """
    descriptions = {
        'auto-pass':  "No significant risk signals detected. No review required.",
        'auto-hold':  "Some risk signals detected. Queued for secondary human review.",
        'escalate':   "Multiple strong risk signals detected. Priority human review required.",
    }
    return descriptions.get(decision, "Unknown decision.")
