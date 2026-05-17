"""
export_for_labelling.py — Export escalated tweets for manual human labelling.

This is Step 1 of the evaluation workflow.
After running this, open the CSV in Google Sheets or Excel and fill in
the human_label column (0 or 1) for each row.

Then run: python evaluation/evaluate_precision.py

See EVALUATION.md for the full labelling protocol.
"""

import sqlite3
import pandas as pd
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'collected_tweets.db')
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'labelled_escalate_sample.csv')


def export():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Run collector.py or demo_data_generator.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT
            tweet_id,
            text,
            risk_score,
            signal_summary,
            account_age_days,
            followers_count,
            retweet_count,
            url_domain,
            NULL as human_label,
            CAST(NULL as TEXT) as rationale
        FROM tweets
        WHERE triage_decision = 'escalate'
        ORDER BY risk_score DESC
        """,
        conn
    )
    conn.close()

    if df.empty:
        print("No escalated tweets found. Check your database or lower the escalation threshold.")
        sys.exit(1)

    # Add instructions as column headers make clear
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Exported {len(df)} escalated tweets to: {OUTPUT_CSV}")
    print()
    print("LABELLING INSTRUCTIONS:")
    print("  Open the CSV in Google Sheets or Excel.")
    print("  Fill in 'human_label' for EACH row:")
    print("    1 = HIGH-RISK: tweet is spreading a false claim or appears")
    print("        to be coordinated inauthentic behaviour. A moderator should see this.")
    print("    0 = LOW-RISK: tweet does NOT appear to be misinformation despite")
    print("        triggering signals (journalism quoting false claims, debunking,")
    print("        satire, legitimate alarm phrases used non-deceptively).")
    print()
    print("  Fill in 'rationale' for EVERY label=0 row (false positives).")
    print("  These explain your system's weaknesses. They are the most important rows.")
    print()
    print("  Label in sessions of 50 rows. Take breaks. Be honest.")
    print()
    print("After labelling, run: python evaluation/evaluate_precision.py")


if __name__ == '__main__':
    export()
