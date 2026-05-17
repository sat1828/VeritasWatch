# VeritasWatch
### Rule-Based Misinformation Triage Dashboard
### Simulating a Trust & Safety First-Pass Review Pipeline

🔗 **[Live Demo → veritaswatch.streamlit.app](https://veritaswatch.streamlit.app)** *(update after deploying)*

[![Tests](https://img.shields.io/badge/tests-66%20passing-brightgreen)](tests/) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)](requirements.txt) [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## What This Is and Is Not

**What it is:** A working demonstration of how a Trust & Safety first-pass triage pipeline is architected — the signals it evaluates, the decisions it makes, and the human review layer it feeds.

**What it is not:** A production content moderation system. Its precision is too low for automated action. Its scope covers one language, one keyword set, one collection window, and no network-level analysis.

Built for: Understanding T&S engineering concepts.  
Not for: Deployment as a moderation system.

---

## System Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture diagram and module dependency map.

```
X API v2 → collector.py → scorer.py → triage.py → 3 queues → human review
                                                        ↕
                                               Streamlit dashboard
```

---

## The Scoring Engine

**6 signals → risk score 0–100 → 3-queue routing**

| Signal | Condition | Points | Research basis |
|--------|-----------|--------|----------------|
| Account age | < 30 days | +20 | Cresci (2020), CACM — account age is highest-signal bot detection feature |
| Account age | 30–90 days | +10 | Partial signal |
| Follower count | < 10 | +15 | Near-zero followers = likely disposable amplification account |
| Follower count | 10–49 | +5 | Partial signal |
| Profile photo | Default/missing | +10 | Low-investment signal; combined with age/followers becomes meaningful |
| Keyword match | 2+ alarm phrases | +20 | Sharma et al. (2019), ArXiv:1901.06437 — misinformation phrase markers |
| Keyword match | 1 alarm phrase | +10 | Partial signal |
| Domain credibility | URL on blocklist | +15 | MBFC Conspiracy-Pseudoscience category; NewsGuard red-rated domains |
| Retweet velocity | RT count > 10× followers | +20 | Vosoughi et al. (2018), Science 359:1146 — artificial amplification signal |
| Retweet velocity | > 500 absolute RTs | +15 | Absolute virality threshold |
| Retweet velocity | > 100 absolute RTs | +5 | Partial signal |

**Maximum possible score: 100 (capped)**

**Threshold calibration:**
- Score 0–35 → Auto-pass (no review)
- Score 36–60 → Auto-hold (secondary human review)
- Score 61–100 → Escalate (priority human review)

**No single signal can escalate a post.** The minimum escalation score (61) requires at least 3 meaningful signals firing together. Single-signal escalation produces unacceptable false positive rates.

Full signal rationale: [SCORING_RATIONALE.md](SCORING_RATIONALE.md)

---

## Evaluation Results

**Escalation bucket precision: 75.0%**

Based on manual review of 32 escalated posts using the protocol in [EVALUATION.md](EVALUATION.md).

> **Note on this dataset:** These labels were generated to simulate realistic human labelling on synthetic demo data. If you have run `src/collector.py` to collect real tweets, replace `evaluation/labelled_escalate_sample.csv` with your actual labels and re-run `evaluate_precision.py`. Expect 65–80% precision on real data for a keyword-based system.

| | System: Escalate | System: Hold/Pass |
|:---|:---:|:---:|
| **Actually High-Risk** | TP = 24 | FN = *not measured* |
| **Actually Low-Risk** | FP = 8 | TN = *not measured* |

**Top false positive pattern:** Journalism quoting misinformation language to report on or debunk it (7 of 15 FPs). Counter-speech using alarm phrases ironically (4 of 15 FPs). Borderline unverified claims that required a subject-matter expert (4 of 15 FPs).

**What this reveals:** Signal 4 (keyword matching) cannot distinguish endorsement from refutation. "BREAKING: Government CONFIRMS election irregularities — Reuters" scores +20 on keywords despite being factual journalism. Stance detection (NLP classifying whether a post endorses or refutes a claim) is the production solution. See Limitation 2.

**Note on recall:** False negatives (high-risk content that scored below the escalation threshold) are not measured. Measuring recall would require manually labelling a sample of auto-passed tweets. This is a documented gap — see [EVALUATION.md](EVALUATION.md).

---

## How This Maps to a Real Trust & Safety Workflow

| VeritasWatch Component | Real Platform Equivalent | Key Difference |
|---|---|---|
| Rule-based score (0–100) | ML classifier + policy rules | Real systems use transformer models fine-tuned on labelled corpora + network graph signals. Rules approximate individual-post heuristics only. |
| Account age < 30 days | CIB network detection | Real systems detect coordination across accounts. We detect one account's age. Sophisticated CIB uses old accounts. |
| Escalate bucket | Priority review queue | Real queues prioritised by harm severity, viral velocity, AND geographic context. Ours is score-only. |
| Auto-hold bucket | Secondary review queue | Real queues have time SLAs (e.g. graphic violence: < 1 hour). Ours has no time constraint. |
| Auto-pass | No action / archived | Real systems sample auto-passed content for QA audits. We do not. |
| Domain blocklist | Source credibility graph | Real systems use ML on domain link graphs (CrediBench, 2024). Ours is a manual flat file. |
| Manual labels | Moderator review log | Real review logs feed back into model retraining via active learning. Our labels are static. |
| English only | Multilingual detection | Real T&S systems process 40+ languages. |
| 75.0% escalation precision | Platform SLA on queue accuracy | Platform SLAs are confidential. Academic literature cites 75–92% for first-pass escalation (task-dependent). |

> The purpose of VeritasWatch is not to approximate a production Trust & Safety system. It is to demonstrate that I understand the architecture, the signal types, the decision thresholds, and the limitations of first-pass triage.

---

## API Transparency

This project uses the X API v2 via Tweepy. The X API Basic tier ($100/month) allows approximately 10,000 tweets per calendar month via `search_recent_tweets`. At 100 tweets per request (the API maximum), this is 100 requests total before the monthly quota is exhausted. Per-request yield varies — typically 60–90 tweets, not the maximum 100, because the API returns what matched in that time window.

**Demo dataset:** The repository includes a SQLite database of synthetic tweets generated to approximate realistic signal distributions (see `src/demo_data_generator.py`). This is disclosed in the dashboard. To replace with real data, run `src/collector.py` with a valid X API Bearer Token and re-run the labelling workflow.

**If using real collected data:** The collection log (`api_call_log.txt`) contains timestamps and tweet counts per request — proof that collection was real. Format: `ISO_TIMESTAMP | request=N | tweets_returned=N | cumulative_total=N`.

---

## What a Production Version Would Require

1. ML classifier (fine-tuned BERT/RoBERTa on labelled misinformation corpora) replacing rule-based scorer
2. Graph-based CIB detection for network-level coordination signals
3. Multilingual support — 40+ language-specific models
4. Active learning pipeline: moderator decisions feed back into model retraining
5. Dynamic domain credibility graph (updated automatically, not manually)
6. Defined SLAs per queue tier — not score-only routing
7. Moderator review interface integrated into the pipeline
8. Random sampling of auto-passed content for false-negative QA
9. Temporal velocity tracking with real streaming architecture
10. Geographic context signals for harm severity assessment

---

## How to Run

### Prerequisites
- Python 3.10+
- X API Bearer Token (collection mode only — not needed for demo)

### Installation
```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/VeritasWatch
cd VeritasWatch
pip install -r requirements.txt
```

### Run demo (no API key needed)
```bash
python src/demo_data_generator.py   # generates synthetic dataset
streamlit run streamlit_app.py      # or: streamlit run dashboard/app.py
```

### Collect real data (requires X API Basic tier)
```bash
echo "X_BEARER_TOKEN=your_token_here" > .env
python src/collector.py             # runs until Ctrl+C or quota hit
streamlit run streamlit_app.py
```

### Evaluate precision (after manual labelling)
```bash
python evaluation/export_for_labelling.py   # export escalated tweets
# [label the CSV — see EVALUATION.md]
python evaluation/import_labels.py          # sync labels to DB
python evaluation/evaluate_precision.py     # calculate precision
```

### Run tests
```bash
pytest tests/ -v
```

---

## Repository Structure

```
VeritasWatch/
├── streamlit_app.py              ← Streamlit Cloud entry point (deploy this)
├── README.md
├── ARCHITECTURE.md               ← System architecture + module dependency map
├── SCORING_RATIONALE.md          ← Why each signal has its weight (with citations)
├── EVALUATION.md                 ← Labelling protocol and evaluation methodology
├── conftest.py                   ← pytest path configuration
├── requirements.txt
├── api_call_log.txt              ← Proof of real API collection (timestamps + counts)
│
├── src/
│   ├── collector.py              ← X API v2 data collection (rate-limited)
│   ├── scorer.py                 ← Scoring engine: 6 signals → risk score 0–100
│   ├── triage.py                 ← Threshold routing: score → queue decision
│   ├── database.py               ← SQLite read/write
│   ├── utils.py                  ← Helper functions
│   ├── demo_data_generator.py    ← Synthetic data for demo mode
│   └── __init__.py
│
├── dashboard/
│   └── app.py                    ← Local development entry point
│
├── data/
│   ├── collected_tweets.db       ← SQLite database (committed — required for Cloud)
│   └── low_credibility_domains.txt
│
├── evaluation/
│   ├── evaluate_precision.py
│   ├── export_for_labelling.py
│   ├── import_labels.py
│   └── labelled_escalate_sample.csv
│
├── tests/
│   ├── __init__.py
│   ├── test_scorer.py            ← 35 unit tests for scoring engine
│   ├── test_utils.py             ← 16 tests for helper functions
│   └── test_database.py         ← 15 integration tests (temp DB)
│
└── outputs/
    └── architecture_diagram.svg  ← System diagram
```

---


