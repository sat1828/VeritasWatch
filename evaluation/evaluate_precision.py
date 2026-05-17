"""
evaluate_precision.py — Calculate escalation bucket precision.

Run this AFTER you have manually labelled the escalated tweets.
The labelling protocol is in EVALUATION.md.

Usage:
  python evaluation/evaluate_precision.py

Input:
  evaluation/labelled_escalate_sample.csv
  (Columns: tweet_id, text, risk_score, signal_summary,
   account_age_days, followers_count, retweet_count,
   url_domain, human_label [0 or 1], rationale)

Output:
  Precision number, confusion matrix, top false positive patterns.
  This output must match what is displayed in the README exactly.

WHAT PRECISION MEASURES (and what it does not):
  Precision = TP / (TP + FP) in the escalate bucket.
  "Of all posts the system escalated, what fraction were genuinely
  high-risk according to a human reviewer?"

  Precision does NOT measure recall.
  Recall = TP / (TP + FN), where FN is high-risk content that
  the system MISSED (scored below the escalation threshold).
  We cannot measure recall without labelling a random sample of
  auto-passed tweets — which this project does not do.
  This limitation is documented in EVALUATION.md.

HONEST EXPECTATION FOR A RULE-BASED SYSTEM:
  60–70%: Many false positives. Common. Document honestly.
  70–80%: Reasonable. This is the target range.
  80%+:   Unlikely for a keyword-based system unless your keyword
          set is very precise and journalism is rare in your corpus.

  If you get 65%, report 65%. Do not adjust thresholds to inflate.
  An honest 65% with clear false-positive analysis is more valuable
  in an interview than a manipulated 82%.
"""

import pandas as pd
import sys
import os

LABEL_CSV = os.path.join(os.path.dirname(__file__), 'labelled_escalate_sample.csv')


def run_evaluation():
    # ── Load labelled data ──────────────────────────────────────────────────────
    if not os.path.exists(LABEL_CSV):
        print(f"ERROR: Label file not found at {LABEL_CSV}")
        print("Export escalated tweets first: python evaluation/export_for_labelling.py")
        print("Then label them in the CSV and re-run this script.")
        sys.exit(1)

    df = pd.read_csv(LABEL_CSV)

    # ── Validate ────────────────────────────────────────────────────────────────
    required_cols = ['tweet_id', 'text', 'risk_score', 'human_label']
    for col in required_cols:
        if col not in df.columns:
            print(f"ERROR: Column '{col}' missing from label file.")
            print(f"Expected columns: {required_cols}")
            sys.exit(1)

    # Only count rows that have been labelled
    labelled = df[df['human_label'].notna()].copy()
    labelled['human_label'] = labelled['human_label'].astype(int)

    if len(labelled) == 0:
        print("ERROR: No labelled rows found (human_label column is all empty).")
        print("Fill in the human_label column (0 or 1) before running evaluation.")
        sys.exit(1)

    # ── Calculate precision ─────────────────────────────────────────────────────
    total_labelled = len(labelled)
    true_positives  = int((labelled['human_label'] == 1).sum())
    false_positives = int((labelled['human_label'] == 0).sum())

    if total_labelled == 0:
        print("ERROR: Division by zero — no labelled rows.")
        sys.exit(1)

    precision = true_positives / total_labelled * 100

    # ── Output ──────────────────────────────────────────────────────────────────
    print("=" * 60)
    print("VeritasWatch — Escalation Bucket Precision Evaluation")
    print("=" * 60)
    print()
    print(f"Total escalated posts labelled: {total_labelled}")
    print(f"True positives  (label=1, genuinely high-risk): {true_positives}")
    print(f"False positives (label=0, incorrectly escalated): {false_positives}")
    print()
    print(f"  Escalation Bucket Precision: {precision:.1f}%")
    print()
    print("-" * 60)
    print("Confusion matrix (escalate bucket only):")
    print(f"  TP = {true_positives} | FP = {false_positives}")
    print(f"  FN = not measured (see EVALUATION.md)")
    print(f"  TN = not measured (see EVALUATION.md)")
    print()

    # ── False positive patterns ─────────────────────────────────────────────────
    if 'rationale' in labelled.columns:
        fp_rows = labelled[labelled['human_label'] == 0]
        if len(fp_rows) > 0:
            print("Top false positive rationales (why the system was wrong):")
            print("-" * 60)
            for i, (_, row) in enumerate(fp_rows.iterrows(), 1):
                rationale = row.get('rationale', '(no rationale provided)')
                score = row.get('risk_score', '?')
                print(f"  FP #{i}: Score={score} | {rationale}")
                if i >= 10:
                    print(f"  ... and {len(fp_rows) - 10} more.")
                    break
        else:
            print("No false positives found. Check your labels are honest.")
    else:
        print("No 'rationale' column found. Add a rationale column for each label=0 row.")

    print()
    print("=" * 60)
    print(f"PUT THIS IN YOUR README: Escalation bucket precision: {precision:.1f}%")
    print(f"Based on manual review of {total_labelled} escalated posts.")
    print("=" * 60)


if __name__ == '__main__':
    run_evaluation()
