"""
evaluation/import_labels.py — Import human labels from CSV into SQLite.

After labelling the CSV exported by export_for_labelling.py,
run this script to sync the labels back into the database.
The dashboard reads ground_truth_label from SQLite — this is required
for the precision metric to appear in the dashboard.

WORKFLOW:
  1. python evaluation/export_for_labelling.py
  2. [label the CSV manually — see EVALUATION.md]
  3. python evaluation/import_labels.py          ← this script
  4. python evaluation/evaluate_precision.py     ← calculate precision
  5. streamlit run dashboard/app.py              ← precision appears in dashboard
"""

import csv
import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from database import get_connection

LABEL_CSV = os.path.join(os.path.dirname(__file__), 'labelled_escalate_sample.csv')


def import_labels():
    if not os.path.exists(LABEL_CSV):
        print(f"ERROR: {LABEL_CSV} not found.")
        print("Run export_for_labelling.py first, then label the CSV.")
        sys.exit(1)

    with open(LABEL_CSV, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    labelled = [r for r in rows if r.get('human_label') not in ('', None)]
    unlabelled = len(rows) - len(labelled)

    if not labelled:
        print("No labelled rows found (human_label column is all empty).")
        print("Fill in the human_label column (0 or 1) before running this script.")
        sys.exit(1)

    conn = get_connection()
    cursor = conn.cursor()
    updated = 0

    for row in labelled:
        try:
            label = int(float(row['human_label']))
            cursor.execute(
                "UPDATE tweets SET ground_truth_label = ? WHERE tweet_id = ?",
                (label, row['tweet_id'])
            )
            if cursor.rowcount > 0:
                updated += 1
        except (ValueError, KeyError) as e:
            print(f"  WARNING: Could not parse label for tweet_id={row.get('tweet_id')}: {e}")

    conn.commit()
    conn.close()

    print(f"Labels imported successfully.")
    print(f"  Rows in CSV:    {len(rows)}")
    print(f"  Labels found:   {len(labelled)}")
    print(f"  Unlabelled:     {unlabelled}")
    print(f"  DB rows updated: {updated}")
    print()
    print("Next steps:")
    print("  python evaluation/evaluate_precision.py")
    print("  streamlit run dashboard/app.py")


if __name__ == '__main__':
    import_labels()
