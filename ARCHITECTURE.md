# ARCHITECTURE.md
# VeritasWatch — System Architecture

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA INGESTION                                                   │
│                                                                             │
│  [X API v2 (Tweepy)]                                                        │
│       │                                                                     │
│       │  search_recent_tweets()                                             │
│       │  · 1 request / 15 minutes (rate limit buffer)                      │
│       │  · 100 tweets / request (API maximum)                              │
│       │  · lang:en -is:retweet (filter)                                    │
│       │  · Monthly cap: ~10,000 tweets (Basic tier)                        │
│       ▼                                                                     │
│  [JSON Response — Tweet + User objects]                                     │
│       │                                                                     │
│       │  Field extraction + normalisation (collector.py)                   │
│       ▼                                                                     │
│  [SQLite — collected_tweets.db]                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — SCORING AND ROUTING                                              │
│                                                                             │
│  [scorer.py]                                                                │
│  · Signal 1: Account age (max +20)                                         │
│  · Signal 2: Follower count (max +15)                                      │
│  · Signal 3: Profile photo (max +10)                                       │
│  · Signal 4: Keyword patterns (max +20)                                    │
│  · Signal 5: Domain blocklist (max +15)                                    │
│  · Signal 6: Retweet velocity (max +20)                                    │
│  · Output: risk_score (0–100), signal_summary                              │
│       │                                                                     │
│       ▼                                                                     │
│  [triage.py]                                                                │
│  · score < 36  → "auto-pass"                                               │
│  · score 36–60 → "auto-hold"                                               │
│  · score 61+   → "escalate"                                                │
│  · Thresholds are policy decisions, parametric                             │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — REVIEW QUEUES                                                    │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │  AUTO-PASS       │  │  AUTO-HOLD       │  │  ESCALATE        │            │
│  │  Score < 36      │  │  Score 36–60     │  │  Score 61+       │            │
│  │  No review       │  │  Secondary review│  │  Priority review │            │
│  │  (archived)      │  │  (not urgent)    │  │  (senior mod)    │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  ⚠️  NO AUTOMATED ACTION OCCURS IN THIS LAYER.                      │    │
│  │      ALL CONTENT ROUTES TO HUMAN REVIEW.                           │    │
│  │      "ESCALATE" MEANS PRIORITY QUEUE, NOT REMOVAL.                 │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — HUMAN REVIEW                                                     │
│                                                                             │
│  [Human Moderator Review]                                                   │
│  · Reviews content in queue order (escalate first)                         │
│  · Applies platform policy (not automated rules)                           │
│  · Makes final decision:                                                    │
│      No action / Warning / Label / Removal / Escalation to legal           │
│                                                                             │
│  NOTE: This layer exists outside this codebase.                            │
│  VeritasWatch produces the queue. The decision is the moderator's.         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 5 — MONITORING (parallel to all layers)                              │
│                                                                             │
│  [Streamlit Dashboard — dashboard/app.py]                                   │
│  · Reads from SQLite (no write operations)                                  │
│  · Displays queue counts, score distribution, signal activation            │
│  · Exposes threshold sliders (policy calibration demo)                     │
│  · Shows precision evaluation results from ground truth labels             │
│  · Deployed at: your-url.streamlit.app                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Dependency Map

```
collector.py
    ├── database.py    (write: INSERT tweet)
    ├── scorer.py      (compute risk_score)
    ├── triage.py      (compute triage_decision)
    └── utils.py       (field extraction helpers)

dashboard/app.py
    └── database.py    (read: SELECT tweets)

evaluation/evaluate_precision.py
    └── (reads CSV — no database dependency)

evaluation/export_for_labelling.py
    └── database.py    (read: SELECT escalated tweets)

src/demo_data_generator.py
    ├── database.py    (write: INSERT synthetic tweets)
    ├── scorer.py      (score synthetic tweets)
    └── triage.py      (route synthetic tweets)
```

---

## Data Flow: What Happens to One Tweet

1. **Collection:** `collector.py` calls `search_recent_tweets()`.  
   Tweet JSON arrives with author expansion data.

2. **Extraction:** `process_tweet()` in `collector.py` flattens the nested JSON
   into a flat dict matching the `tweets` table schema.
   Fields computed at this stage: `account_age_days`, `has_profile_photo`, 
   `url_domain`, `contains_url`.

3. **Scoring:** `scorer.score_tweet(tweet_dict)` evaluates all 6 signals.
   Adds `risk_score`, `signal_summary`, `keyword_hit_count`, 
   `has_low_credibility_domain`, `has_keyword_signal` to the dict.

4. **Routing:** `triage.triage_decision(risk_score)` returns one of 
   `auto-pass`, `auto-hold`, `escalate`. Added to dict as `triage_decision`.

5. **Storage:** `database.insert_tweet(tweet_dict)` executes INSERT OR IGNORE.
   Duplicate tweet_ids are silently dropped.

6. **Dashboard reads:** `dashboard/app.py` reads from SQLite using `SELECT * FROM tweets`.
   No modification to stored data.

7. **Evaluation:** Human labels are added to `evaluation/labelled_escalate_sample.csv`
   manually. `evaluate_precision.py` reads this CSV directly — no database interaction.

---

## Demo Mode Architecture (Option C Replay)

Since the X API Basic tier caps collection at 10,000 tweets/month, the dashboard
operates in replay mode using pre-collected data:

```
[Pre-collected SQLite DB]
        │
        │  st.cache_data(ttl=30) — reads every 30 seconds
        ▼
[Streamlit Dashboard]
        │
        │  Displays all stored tweets as if arriving live
        │  Threshold sliders re-filter existing data (no re-scoring)
        ▼
[User sees triage pipeline in motion]
```

This is not a limitation to hide — it is an architectural decision worth explaining.
See Section 0 of the project specification for the full rationale.

---

## What This Architecture Cannot Do

| Missing Capability | Why It Matters | Production Solution |
|---|---|---|
| Network graph analysis | Cannot detect coordinated accounts | Graph database (Neo4j) with co-activity tracking |
| Cross-tweet velocity | RT velocity is a static ratio, not a rate | Streaming architecture with tweet_id time-series |
| Multilingual processing | English only | Language-specific models (40+ languages on major platforms) |
| Content understanding | Cannot distinguish endorsement from refutation | Fine-tuned BERT/RoBERTa with stance detection |
| Dynamic domain scoring | Blocklist is static | ML on domain link graphs (CrediBench 2024) |
| Active learning loop | Labels don't improve the model | Moderator review feeding back into training data |
| SLA-based prioritisation | No time constraints on queues | Queue management system with per-tier SLAs |
| Auto-pass QA sampling | False negatives are undetected | Random sampling of auto-passed content for audit |

None of these are design oversights — they are deliberate scope decisions for a
portfolio demonstration project. Each represents a real engineering problem that
production T&S systems have solved.
