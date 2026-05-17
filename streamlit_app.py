"""
streamlit_app.py — Root entry point for Streamlit Community Cloud deployment.

WHY THIS FILE EXISTS:
  Streamlit Cloud looks for streamlit_app.py or app.py in the repository root.
  It cannot use dynamic delegation — it needs real Streamlit
  code in the entry file itself.

  This file is the authoritative copy for deployment.
  For local development, you can also run: streamlit run dashboard/app.py

DEPLOYMENT:
  1. Push repository to GitHub (commit data/collected_tweets.db)
  2. share.streamlit.io → New app → set Main file path: streamlit_app.py
  3. No API credentials needed for demo mode.

WHAT THIS DOES:
  Adds src/ to sys.path then runs the dashboard inline.
  dashboard/app.py is the development copy — kept for local workflows.
"""

import sys
import os

# Make src/ importable — must happen before any local imports
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "src"))

# ── All imports from here are identical to dashboard/app.py ──────────────────
import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import time
from collections import Counter

DB_PATH = os.path.join(_ROOT, "data", "collected_tweets.db")

st.set_page_config(
    page_title="VeritasWatch — Misinformation Triage",
    page_icon="⚠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.auto-pass {
    background-color: #162a1d; border-left: 4px solid #27ae60;
    padding: 10px 14px; margin: 5px 0; border-radius: 4px;
    font-size: 13px; line-height: 1.6;
}
.auto-hold {
    background-color: #2e2010; border-left: 4px solid #f39c12;
    padding: 10px 14px; margin: 5px 0; border-radius: 4px;
    font-size: 13px; line-height: 1.6;
}
.escalate {
    background-color: #2e1010; border-left: 4px solid #e74c3c;
    padding: 10px 14px; margin: 5px 0; border-radius: 4px;
    font-size: 13px; line-height: 1.6;
}
.banner {
    background: #0f1629; border: 1px solid #2a3560; border-radius: 6px;
    padding: 10px 14px; font-size: 12px; color: #8899cc; margin-bottom: 14px;
}
</style>
""", unsafe_allow_html=True)

if "replay_running" not in st.session_state:
    st.session_state.replay_running = False
if "replay_index" not in st.session_state:
    st.session_state.replay_index = 0

@st.cache_data(ttl=60)
def load_all_tweets():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM tweets ORDER BY collected_at ASC", conn)
    conn.close()
    return df

def apply_thresholds(df, hold_t, esc_t):
    if df.empty:
        return df
    df = df.copy()
    df["triage_display"] = df["risk_score"].apply(
        lambda s: "escalate" if s >= esc_t else ("auto-hold" if s >= hold_t else "auto-pass")
    )
    return df

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.title("⚠️ VeritasWatch")
st.sidebar.caption("Trust & Safety Triage Demo")
st.sidebar.markdown("---")
st.sidebar.subheader("🎬 Replay Mode")
st.sidebar.caption("Simulate tweets arriving live through the pipeline.")

replay_speed = st.sidebar.slider("Tweets per second", 0.2, 3.0, 0.5, 0.1)

col_start, col_stop = st.sidebar.columns(2)
with col_start:
    if st.button("▶ Start", use_container_width=True,
                 disabled=st.session_state.replay_running):
        st.session_state.replay_running = True
        st.session_state.replay_index = 0
        st.rerun()
with col_stop:
    if st.button("⏹ Stop", use_container_width=True,
                 disabled=not st.session_state.replay_running):
        st.session_state.replay_running = False
        st.rerun()

if st.sidebar.button("↺ Reset to Full View", use_container_width=True):
    st.session_state.replay_running = False
    st.session_state.replay_index = 0
    load_all_tweets.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Threshold Override")
st.sidebar.caption(
    "Adjust thresholds live — demonstrates that these are policy decisions, "
    "not mathematical constants. Core T&S calibration activity."
)
hold_threshold = st.sidebar.slider("Hold threshold (score ≥ X)", 20, 60, 36)
escalate_threshold = st.sidebar.slider("Escalate threshold (score ≥ X)", 40, 85, 61)

if escalate_threshold <= hold_threshold:
    st.sidebar.error("Escalate must be above Hold threshold.")

st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ About")
st.sidebar.info(
    "6 rule-based signals → risk score 0–100 → 3-queue routing.\n\n"
    "No content is actioned automatically. All escalated posts go to human review.\n\n"
    "**Not a production moderation system.**"
)
st.sidebar.markdown(
    "[GitHub](https://github.com/yourusername/VeritasWatch) · "
    "[SCORING_RATIONALE.md](https://github.com/yourusername/VeritasWatch/blob/main/SCORING_RATIONALE.md)"
)

# ── MAIN CONTENT ─────────────────────────────────────────────────────────────
st.title("⚠️ VeritasWatch")
st.markdown("**Rule-Based Misinformation Triage Dashboard** · Trust & Safety First-Pass Pipeline Demo")

st.markdown("""
<div class="banner">
<b>DEMO MODE</b> — Pre-collected dataset replayed through the triage pipeline.
No live API calls. No content is removed, labelled, or actioned automatically.
Escalated posts require <b>human moderator review</b> before any action.
Dataset: SYNTHETIC tweets (<code>src/demo_data_generator.py</code>).
Replace with real data via <code>src/collector.py</code>.
</div>
""", unsafe_allow_html=True)

df_all = load_all_tweets()

if df_all.empty:
    st.error(
        "No data found. Run: `python src/demo_data_generator.py`  "
        "then refresh this page."
    )
    st.stop()

if st.session_state.replay_running or st.session_state.replay_index > 0:
    idx = min(st.session_state.replay_index, len(df_all))
    df_view = df_all.iloc[:idx].copy()
else:
    df_view = df_all.copy()

if df_view.empty:
    st.info("Replay started. First tweet arriving shortly…")
    time.sleep(1 / replay_speed)
    st.session_state.replay_index += 1
    st.rerun()

df = apply_thresholds(df_view, hold_threshold, escalate_threshold)
df_pass = df[df["triage_display"] == "auto-pass"]
df_hold = df[df["triage_display"] == "auto-hold"]
df_esc  = df[df["triage_display"] == "escalate"]
total   = len(df)

# Replay engine — runs AFTER rendering so user sees each frame
if st.session_state.replay_running:
    if st.session_state.replay_index < len(df_all):
        prog = st.session_state.replay_index / len(df_all)
        st.progress(prog, text=f"Replay: {st.session_state.replay_index}/{len(df_all)} tweets processed")
        time.sleep(1 / replay_speed)
        st.session_state.replay_index += 1
        st.rerun()
    else:
        st.session_state.replay_running = False
        st.toast("✅ Replay complete — all tweets processed.", icon="✅")

# ── PANEL 1: METRICS ─────────────────────────────────────────────────────────
st.markdown("---")
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Processed", f"{total:,}")
with m2:
    st.metric("✅ Auto-Pass", f"{len(df_pass):,}",
              delta=f"{len(df_pass)/total*100:.1f}%" if total else "0%")
with m3:
    st.metric("⚠️ Auto-Hold", f"{len(df_hold):,}",
              delta=f"{len(df_hold)/total*100:.1f}%" if total else "0%")
with m4:
    st.metric("🚨 Escalated", f"{len(df_esc):,}",
              delta=f"{len(df_esc)/total*100:.1f}%" if total else "0%")

# ── PANEL 2: THREE QUEUES ────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Review Queues")
st.caption(
    f"Content is **routed to queues, not actioned**. "
    f"Hold ≥ {hold_threshold} · Escalate ≥ {escalate_threshold}. "
    "Adjust thresholds in sidebar to see live policy calibration."
)

N = 5
COLOR_MAP = {"auto-pass": "#27ae60", "auto-hold": "#f39c12", "escalate": "#e74c3c"}

def tweet_card(row, css_class, color):
    score    = row["risk_score"]
    signals  = (row.get("signal_summary") or "no_signals")
    text     = row["text"]
    preview  = text[:140] + ("…" if len(text) > 140 else "")
    age      = row.get("account_age_days", "?")
    followers= row.get("followers_count", "?")
    rt       = row.get("retweet_count", "?")
    return (
        f'<div class="{css_class}">'
        f'<span style="background:{color}22;color:{color};font-weight:700;'
        f'font-size:11px;padding:2px 7px;border-radius:10px;margin-right:6px;">SCORE {score}</span>'
        f'<span style="font-size:11px;color:#888">acct:{age}d · {followers}f · {rt}RT</span><br>'
        f'<span style="font-size:11px;color:#aaa">{signals}</span><br>'
        f'<span style="color:#ddd">{preview}</span>'
        f'</div>'
    )

q1, q2, q3 = st.columns(3)
with q1:
    st.markdown(f"### ✅ Auto-Pass ({len(df_pass):,})")
    st.caption(f"Score < {hold_threshold} · No significant risk signals · No review")
    if df_pass.empty:
        st.caption("No tweets yet.")
    else:
        for _, row in df_pass.tail(N).iterrows():
            st.markdown(tweet_card(row, "auto-pass", "#27ae60"), unsafe_allow_html=True)

with q2:
    st.markdown(f"### ⚠️ Auto-Hold ({len(df_hold):,})")
    st.caption(f"Score {hold_threshold}–{escalate_threshold - 1} · Secondary human review")
    if df_hold.empty:
        st.caption("No tweets yet.")
    else:
        for _, row in df_hold.tail(N).iterrows():
            st.markdown(tweet_card(row, "auto-hold", "#f39c12"), unsafe_allow_html=True)

with q3:
    st.markdown(f"### 🚨 Escalate ({len(df_esc):,})")
    st.caption(f"Score ≥ {escalate_threshold} · Priority human review · NOT auto-removed")
    if df_esc.empty:
        st.caption("No tweets yet.")
    else:
        for _, row in df_esc.tail(N).iterrows():
            st.markdown(tweet_card(row, "escalate", "#e74c3c"), unsafe_allow_html=True)

# ── PANEL 3: CHARTS ──────────────────────────────────────────────────────────
st.markdown("---")
chart_left, chart_right = st.columns([3, 2])

with chart_left:
    st.subheader("Score Distribution")
    st.caption("Risk scores coloured by queue. Dashed lines = current threshold settings.")
    fig = px.histogram(
        df, x="risk_score", color="triage_display", nbins=20,
        color_discrete_map=COLOR_MAP,
        category_orders={"triage_display": ["auto-pass", "auto-hold", "escalate"]},
        labels={"risk_score": "Risk Score (0–100)", "triage_display": "Queue"},
    )
    fig.add_vline(x=hold_threshold, line_dash="dash", line_color="#f39c12",
                  annotation_text=f"Hold≥{hold_threshold}", annotation_position="top")
    fig.add_vline(x=escalate_threshold, line_dash="dash", line_color="#e74c3c",
                  annotation_text=f"Esc≥{escalate_threshold}", annotation_position="top right")
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(range=[0, 100]), height=290,
                      margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

with chart_right:
    st.subheader("Signal Activation")
    st.caption("How many tweets triggered each scoring signal")
    if not df.empty:
        safe_f = df["followers_count"].clip(lower=1)
        sigs = {
            "New acct\n(<30d)":   int((df["account_age_days"] < 30).sum()),
            "Low\nfollowers":     int((df["followers_count"] < 10).sum()),
            "No profile\nphoto":  int((df["has_profile_photo"] == 0).sum()),
            "Keyword\nmatch":     int((df["has_keyword_signal"] == 1).sum()),
            "Bad\ndomain":        int((df["has_low_credibility_domain"] == 1).sum()),
            "High RT\nratio":     int((df["retweet_count"] / safe_f > 10).sum()),
        }
        fig2 = px.bar(
            x=list(sigs.keys()), y=list(sigs.values()),
            color=list(sigs.values()), color_continuous_scale="RdYlGn_r",
            labels={"x": "Signal", "y": "Count"},
        )
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           showlegend=False, coloraxis_showscale=False,
                           height=290, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig2, use_container_width=True)

# ── PANEL 4: KEYWORD TRACKER + SCATTER ───────────────────────────────────────
st.markdown("---")
kw_col, scatter_col = st.columns([1, 2])

HIGH_RISK_PHRASES = [
    "BREAKING", "SHARE BEFORE DELETED", "SHARE BEFORE THEY DELETE",
    "THEY DON'T WANT YOU TO KNOW", "CONFIRMED", "MAINSTREAM MEDIA WON'T REPORT",
    "WHAT THEY'RE HIDING", "DO YOUR OWN RESEARCH", "WAKE UP", "MUST WATCH",
    "GOING VIRAL", "THEY'RE HIDING", "SUPPRESSED", "BANNED VIDEO", "CENSORED",
]

with kw_col:
    st.subheader("Top Keywords (Escalate Queue)")
    st.caption("Phrase frequency in escalate-bucket tweets")
    counter = Counter()
    for text in df_esc["text"].dropna():
        tu = text.upper()
        for phrase in HIGH_RISK_PHRASES:
            if phrase in tu:
                counter[phrase] += 1
    if counter:
        kw_df = pd.DataFrame(counter.most_common(10), columns=["Phrase", "Count"])
        st.dataframe(kw_df, hide_index=True, use_container_width=True)
    else:
        st.caption("No escalated tweets yet.")

with scatter_col:
    st.subheader("Score vs. Retweet Count")
    st.caption(
        "High-score posts with high RT counts are most suspicious. "
        "Low-follower accounts with high RTs = artificial amplification signal."
    )
    if not df.empty:
        df_plot = df.copy()
        df_plot["retweet_count_capped"] = df_plot["retweet_count"].clip(upper=2000)
        fig3 = px.scatter(
            df_plot, x="risk_score", y="retweet_count_capped",
            color="triage_display", color_discrete_map=COLOR_MAP, opacity=0.55,
            labels={"risk_score": "Risk Score", "retweet_count_capped": "Retweet Count (cap 2k)",
                    "triage_display": "Queue"},
            hover_data=["account_age_days", "followers_count", "signal_summary"],
        )
        fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           height=310, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig3, use_container_width=True)

# ── PANEL 5: PRECISION EVALUATION ────────────────────────────────────────────
st.markdown("---")
st.subheader("Escalation Bucket Precision")
st.caption(
    "Precision = of all posts the system escalated, what fraction were genuinely high-risk? "
    "Measured on manually labelled ground truth. See EVALUATION.md for protocol."
)

labelled = df_all[df_all["ground_truth_label"].notna()].copy()
if labelled.empty:
    st.info(
        "**No labels yet.** Run `python evaluation/export_for_labelling.py`, "
        "fill in the human_label column (0/1) in the CSV, then run "
        "`python evaluation/import_labels.py` and "
        "`python evaluation/evaluate_precision.py` to calculate precision."
    )
else:
    labelled_esc = labelled[labelled["triage_decision"] == "escalate"]
    n = len(labelled_esc)
    tp = int((labelled_esc["ground_truth_label"] == 1).sum())
    fp = int((labelled_esc["ground_truth_label"] == 0).sum())
    precision = tp / n * 100 if n > 0 else 0

    e1, e2, e3 = st.columns(3)
    with e1:
        st.metric("Escalation Precision", f"{precision:.1f}%",
                  help="TP/(TP+FP) in escalate bucket. Recall not measured — see EVALUATION.md.")
    with e2:
        st.metric("Labelled Sample", f"{n} posts")
    with e3:
        st.metric("Confirmed High-Risk (TP)", f"{tp}")

    st.markdown(f"""
| | System: Escalate | System: Hold/Pass |
|:---|:---:|:---:|
| **Actually High-Risk** | TP = {tp} | FN = *not measured* |
| **Actually Low-Risk** | FP = {fp} | TN = *not measured* |

*False negatives (high-risk content that auto-passed) are not measured — would require labelling auto-passed tweets. See EVALUATION.md.*
    """)

# ── KNOWN LIMITATIONS ────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("⚠️ Known Limitations — read before discussing this project in an interview"):
    st.markdown("""
**Limitation 1 — The Dormant Account Problem (most dangerous)**
A sophisticated actor using a 4-year-old account with 15,000 followers, clean language, and a domain not on the blocklist scores **0** and auto-passes. VeritasWatch has no equivalent of graph-based CIB network detection.

**Limitation 2 — The Journalism False Positive**
Journalism quoting false claims to debunk them triggers the same keyword signals as the false claims themselves. No whitelist. No stance detection.

**Limitation 3 — Word-boundary keyword matching**
Phrases are matched with `\\b` word boundaries (fixed in v1.1). Substring matches like "breakingly" no longer falsely trigger "BREAKING". Documented in scorer.py.

**Limitation 4 — English only**
`lang:en` filter. Misinformation is multilingual.

**Limitation 5 — No content understanding**
"Vaccines DO cause autism" and "The claim vaccines cause autism is false" score identically on Signal 4.

**Limitation 6 — Static domain blocklist**
New misinformation domains not caught automatically.

**Limitation 7 — Recall is unmeasured**
Precision only. FN rate on auto-passed content is unknown.

**Limitation 8 — Batch/replay only**
X API Basic tier ($100/month) caps at ~10,000 tweets/month. True real-time streaming requires Pro ($5,000/month).
    """)

# ── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "VeritasWatch · Rule-based misinformation triage demo · "
    "Python 3.10 · Tweepy · SQLite · Streamlit · Plotly · "
    "Not a production moderation system · No content is automatically actioned"
)
