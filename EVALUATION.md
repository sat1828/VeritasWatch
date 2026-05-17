# EVALUATION.md
# VeritasWatch — Evaluation Methodology

This document describes how the precision number in the README was calculated,
what it measures, and what it does **not** measure.

---

## What We Are Measuring

**Metric: Escalation Bucket Precision**

Precision = TP / (TP + FP) in the escalate queue only.

In plain English: *Of all posts that VeritasWatch sent to the escalate queue,
what fraction were genuinely concerning according to a human reviewer?*

**What we are NOT measuring:**

- **Recall:** We cannot measure recall (how much high-risk content the system
  *missed*) without manually labelling a random sample of auto-passed tweets.
  That was not done in this project. This is a documented limitation.
  
- **Precision of the auto-hold bucket:** The auto-hold bucket was not manually
  labelled. Only escalated tweets were evaluated.

- **System-level accuracy:** The system as a whole has no single accuracy number.
  A system that escalates everything would have 100% recall and terrible precision.
  A system that escalates nothing would have 0% recall and undefined precision.
  Precision on one bucket is a partial metric, not a complete evaluation.

---

## Labelling Protocol

### Step 1 — Export escalated tweets

```bash
python evaluation/export_for_labelling.py
```

This generates `evaluation/labelled_escalate_sample.csv` with all escalated tweets.

### Step 2 — Manual labelling

Open the CSV in Google Sheets or Excel. Fill in the `human_label` column:

| Label | Meaning |
|-------|---------|
| **1** | HIGH-RISK: This tweet is spreading a false claim, amplifying dangerous misinformation, or appears to be coordinated inauthentic behaviour. A human moderator should review this. |
| **0** | LOW-RISK: This tweet does NOT appear to be misinformation despite triggering signals. This includes journalism quoting false claims, debunking content, satire, genuine alarm phrases used non-deceptively. |

**For every label=0 (false positive), write a rationale in the `rationale` column.**  
One sentence explaining why the system was wrong. These rationales are the most
analytically valuable output of the evaluation process.

### Step 3 — Label calibration rules

Apply these rules consistently:

- **Journalism quoting misinformation to report or debunk it → label=0.** The trigger
  was the keyword, not the claim. The tweet is not spreading misinformation.

- **Counter-speech mocking conspiracy language → label=0.** Same signal, opposite intent.
  The system cannot distinguish this. Document it as a false positive.

- **New account with clean content → label=0.** The trigger was the account signal,
  not the content. A new user's tweet is not misinformation.

- **Tweet containing an unverified claim presented as fact, even without alarm phrases
  → label=1.** The absence of alarm phrases does not mean the tweet is safe. Trust your
  judgment as the human reviewer.

- **Tweets you cannot determine the veracity of → do not label.** Leave `human_label`
  blank. Do not guess. Uncertain labels corrupt the precision calculation.

### Step 4 — Calculate precision

```bash
python evaluation/evaluate_precision.py
```

This outputs the precision number, confusion matrix, and top false positive patterns.

---

## Expected Results for a Rule-Based System

| Precision | Interpretation |
|-----------|---------------|
| 60–70% | Many false positives from journalism and counter-speech. Common for keyword-based systems. Document honestly. |
| 70–80% | Reasonable for this approach. Report this range without inflating. |
| 80%+ | Unlikely without a whitelist of trusted news domains. If you get this, check your labelling for confirmation bias. |

**Do not adjust thresholds to inflate the precision number.**

If the real precision is 65%, report 65% and explain:  
*"The keyword-based scoring produces significant false positives from journalistic content
that quotes or debunks misinformation using alarm-phrase language. Precision would improve
with a whitelist of trusted news domains and stance detection."*

That analysis is worth more in an interview than a manipulated 82%.

---

## Known Evaluation Limitations

### Limitation A — Recall Is Unmeasured

We have no estimate of false negatives — high-risk content that scored below the
escalation threshold. This is the most dangerous unknown. A dormant account posting
sophisticated misinformation with clean language scores zero and auto-passes. We have
no count of how many such posts exist in our dataset.

**To measure recall:** Take a random stratified sample of auto-passed tweets and label them.
If the false negative rate in auto-pass is low, the system is performing well overall.
If it is high, precision alone is a misleading metric. This is future work.

### Limitation B — Labeller Bias

The same person who built the scoring engine is labelling the tweets. This creates
confirmation bias risk — a tendency to label borderline cases as true positives to
validate the system's decisions. Mitigation: label sessions should be separated in time,
rationales should be written before recording the label, and borderline cases should
be recorded as uncertain rather than forced into a category.

In a production system, labels would come from professional moderators with documented
guidelines and inter-rater reliability checks. We have one labeller and no IRR score.

### Limitation C — Label Decay

The labels reflect the labeller's judgement at the time of labelling. A tweet that appeared
low-risk in January may appear high-risk in March if new evidence about the claim emerges.
The ground truth CSV is a snapshot, not a living document.

### Limitation D — Dataset Representativeness

The evaluated dataset consists only of tweets matching a specific keyword set
(e.g. "vaccine deaths" OR "5G dangers") collected during a specific 48-hour window.
Precision on this dataset may not generalise to:
- Different misinformation topics
- Different time periods
- Different languages
- Different platforms

---

## How to Use the Labelled Dataset

After labelling, save the completed CSV as `data/ground_truth_labels.csv`.

This file is itself a secondary deliverable: **a small annotated dataset of
misinformation-adjacent tweets with human labels and false positive rationales.**

In the README, describe it as:  
*"The ground truth dataset consists of [N] manually labelled tweets from the escalation
bucket. Labels were assigned using the documented protocol in EVALUATION.md. This dataset
is the foundation for a future supervised classifier — the next evolutionary step beyond
the rule-based scoring engine."*

That sentence signals that you understand the full ML pipeline trajectory, even though
you built only one stage of it.
