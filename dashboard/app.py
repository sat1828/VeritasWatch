"""
dashboard/app.py — VeritasWatch Streamlit Dashboard with live replay mode.

TWO OPERATING MODES:
  1. STATIC VIEW: See all tweets at once. Default on load.
  2. LIVE REPLAY: Simulates tweets arriving one at a time.
     Press "▶ Start Replay" in sidebar. Press "⏹ Stop" to halt.
     Replay speed controlled by sidebar slider.

AUDIT NOTES:
  - Dashboard reads from SQLite only. Zero write operations.
  - Threshold sliders re-route existing scored data. No re-scoring.
  - "Escalate" = priority human review queue. Not automatic removal.
  - All displayed content is clearly marked synthetic if using demo data.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'collected_tweets.db')

# ── PAGE CONFIG ─────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="VeritasWatch — Misinformation Triage",
    page_icon="⚠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ──────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.auto-pass {
    background-color: #162a1d;
    border-left: 4px solid #27ae60;
    padding: 10px 14px; margin: 5px 0;
    border-radius: 4px; font-size: 13px; line-height: 1.6;
}
.auto-hold {
    background-color: #2e2010;
    border-left: 4px solid #f39c12;
    padding: 10px 14px; margin: 5px 0;
    border-radius: 4px; font-size: 13px; line-height: 1.6;
}
.escalate {
    background-color: #2e1010;
    border-left: 4px solid #e74c3c;
    padding: 10px 14px; margin: 5px 0;
    border-radius: 4px; font-size: 13px; line-height: 1.6;
}
.score-pill {
    display: inline-block;
    font-weight: 700; font-size: 11px;
    padding: 2px 7px; border-radius: 10px;
    margin-right: 6px;
}
.banner {
    background: #0f1629;
    border: 1px solid #2a3560;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 12px; color: #8899cc;
    margin-bottom: 14px;
}
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ────────────────────────────────────────────────────────────────

if 'replay_running' not in st.session_state:
    st.session_state.replay_running = False
if 'replay_index' not in st.session_state:
    st.session_state.replay_index = 0
if 'displayed_ids' not in st.session_state:
    st.session_state.displayed_ids = set()

# ── DATA LOADING ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_all_tweets():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM tweets ORDER BY collected_at ASC", conn
    )
    conn.close()
    return df


def apply_thresholds(df, hold_t, esc_t):
    """Re-route display decisions using current threshold slider values."""
    if df.empty:
        return df
    df = df.copy()
    df['triage_display'] = df['risk_score'].apply(
        lambda s: 'escalate' if s >= esc_t
        else ('auto-hold' if s >= hold_t else 'auto-pass')
    )
    return df


# ── SIDEBAR ──────────────────────────────────────────────────────────────────────

st.sidebar.title("⚠️ VeritasWatch")
st.sidebar.caption("Trust & Safety Triage Demo")

st.sidebar.markdown("---")
st.sidebar.subheader("🎬 Replay Mode")
st.sidebar.caption(
    "Simulate tweets arriving live through the pipeline. "
    "Each tick adds one tweet to the display."
)

replay_speed = st.sidebar.slider(
    "Tweets per second", min_value=0.2, max_value=3.0, value=0.5, step=0.1
)

col_start, col_stop = st.sidebar.columns(2)
with col_start:
    if st.button("▶ Start", use_container_width=True, disabled=st.session_state.replay_running):
        st.session_state.replay_running = True
        st.session_state.replay_index = 0
        st.session_state.displayed_ids = set()
        st.rerun()
with col_stop:
    if st.button("⏹ Stop", use_container_width=True, disabled=not st.session_state.replay_running):
        st.session_state.replay_running = False
        st.rerun()

if st.sidebar.button("↺ Reset to Full View", use_container_width=True):
    st.session_state.replay_running = False
    st.session_state.replay_index = 0
    st.session_state.displayed_ids = set()
    load_all_tweets.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Threshold Override")
st.sidebar.caption(
    "Adjust thresholds live. Shows how policy decisions affect queue volumes — "
    "a core T&S calibration activity."
)

hold_threshold = st.sidebar.slider(
    "Hold threshold (score ≥ X)", min_value=20, max_value=60, value=36
)
escalate_threshold = st.sidebar.slider(
    "Escalate threshold (score ≥ X)", min_value=40, max_value=85, value=61
)

if escalate_threshold <= hold_threshold:
    st.sidebar.error("Escalate must be above Hold threshold.")

st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ About")
st.sidebar.info(
    "Rule-based scoring engine: 6 signals → risk score 0–100 → 3-queue routing. "
    "No content is actioned automatically. All escalated posts go to human review. "
    "\n\n**Not a production moderation system.**"
)
st.sidebar.markdown("[GitHub](https://github.com/yourusername/VeritasWatch) · "
                    "[SCORING_RATIONALE.md](https://github.com/yourusername/VeritasWatch/blob/main/SCORING_RATIONALE.md)")

# ── MAIN HEADER ──────────────────────────────────────────────────────────────────

st.title("⚠️ VeritasWatch")
st.markdown("**Rule-Based Misinformation Triage Dashboard** · Trust & Safety First-Pass Pipeline Demo")

st.markdown("""
<div class="banner">
<b>DEMO MODE</b> — Pre-collected dataset replayed through the triage pipeline. No live API calls.
No content is removed, labelled, or actioned automatically.
Escalated posts require <b>human moderator review</b> before any action.
All scoring is heuristic — see <a href="#known-limitations">Known Limitations</a>.
<br>
Dataset: SYNTHETIC tweets (generated by <code>src/demo_data_generator.py</code>).
Replace with real data via <code>src/collector.py</code>.
</div>
""", unsafe_allow_html=True)

# ── LOAD AND FILTER DATA ─────────────────────────────────────────────────────────

df_all = load_all_tweets()

if df_all.empty:
    st.error(
        "No data found. Run: `python src/demo_data_generator.py`  "
        "then refresh this page."
    )
    st.stop()

# In replay mode, only show tweets up to current index
if st.session_state.replay_running or st.session_state.replay_index > 0:
    idx = min(st.session_state.replay_index, len(df_all))
    df_view = df_all.iloc[:idx].copy()
else:
    df_view = df_all.copy()

if df_view.empty:
    st.info("Replay started. Tweets will appear momentarily...")
    time.sleep(1 / replay_speed)
    st.session_state.replay_index += 1
    st.rerun()

df = apply_thresholds(df_view, hold_threshold, escalate_threshold)

df_pass = df[df['triage_display'] == 'auto-pass']
df_hold = df[df['triage_display'] == 'auto-hold']
df_esc  = df[df['triage_display'] == 'escalate']
total   = len(df)

# ── REPLAY ENGINE ────────────────────────────────────────────────────────────────

if st.session_state.replay_running:
    if st.session_state.replay_index < len(df_all):
        time.sleep(1 / replay_speed)
        st.session_state.replay_index += 1
        st.rerun()
    else:
        st.session_state.replay_running = False
        st.toast("✅ Replay complete — all tweets processed.", icon="✅")

# Replay progress bar
if st.session_state.replay_index > 0 and st.session_state.replay_index < len(df_all):
    progress = st.session_state.replay_index / len(df_all)
    st.progress(progress, text=f"Replay: {st.session_state.replay_index}/{len(df_all)} tweets processed")

# ── PANEL 1: METRICS ─────────────────────────────────────────────────────────────

st.markdown("---")
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("Processed", f"{total:,}")
with m2:
    pass_pct = len(df_pass)/total*100 if total else 0
    st.metric("✅ Auto-Pass", f"{len(df_pass):,}", delta=f"{pass_pct:.1f}%")
with m3:
    hold_pct = len(df_hold)/total*100 if total else 0
    st.metric("⚠️ Auto-Hold", f"{len(df_hold):,}", delta=f"{hold_pct:.1f}%")
with m4:
    esc_pct = len(df_esc)/total*100 if total else 0
    st.metric("🚨 Escalated", f"{len(df_esc):,}", delta=f"{esc_pct:.1f}%")

# ── PANEL 2: THREE QUEUE DISPLAY ─────────────────────────────────────────────────

st.markdown("---")
st.subheader("Review Queues")
st.caption(
    "Content is **routed to queues, not actioned**. "
    f"Thresholds: Hold ≥ {hold_threshold} · Escalate ≥ {escalate_threshold}. "
    "Adjust thresholds in sidebar to see live policy calibration."
)

N = 5  # Cards per queue
q1, q2, q3 = st.columns(3)

COLOR_MAP = {'auto-pass': '#27ae60', 'auto-hold': '#f39c12', 'escalate': '#e74c3c'}

def tweet_card(row, css_class, color):
    score = row['risk_score']
    signals = row.get('signal_summary', 'no_signals') or 'no_signals'
    text = row['text']
    preview = text[:140] + ('…' if len(text) > 140 else '')
    age = row.get('account_age_days', '?')
    followers = row.get('followers_count', '?')
    rt = row.get('retweet_count', '?')
    return (
        f'<div class="{css_class}">'
        f'<span class="score-pill" style="background:{color}22;color:{color}">SCORE {score}</span>'
        f'<span style="font-size:11px;color:#888">acct:{age}d · {followers}f · {rt}RT</span><br>'
        f'<span style="font-size:11px;color:#aaa">{signals}</span><br>'
        f'<span style="color:#ddd">{preview}</span>'
        f'</div>'
    )

with q1:
    st.markdown(f"### ✅ Auto-Pass ({len(df_pass):,})")
    st.caption(f"Score < {hold_threshold} · No significant risk signals · No review")
    if df_pass.empty:
        st.caption("No tweets yet.")
    else:
        for _, row in df_pass.tail(N).iterrows():
            st.markdown(tweet_card(row, 'auto-pass', '#27ae60'), unsafe_allow_html=True)

with q2:
    st.markdown(f"### ⚠️ Auto-Hold ({len(df_hold):,})")
    st.caption(f"Score {hold_threshold}–{escalate_threshold-1} · Secondary human review")
    if df_hold.empty:
        st.caption("No tweets yet.")
    else:
        for _, row in df_hold.tail(N).iterrows():
            st.markdown(tweet_card(row, 'auto-hold', '#f39c12'), unsafe_allow_html=True)

with q3:
    st.markdown(f"### 🚨 Escalate ({len(df_esc):,})")
    st.caption(f"Score ≥ {escalate_threshold} · Priority human review · NOT auto-removed")
    if df_esc.empty:
        st.caption("No tweets yet.")
    else:
        for _, row in df_esc.tail(N).iterrows():
            st.markdown(tweet_card(row, 'escalate', '#e74c3c'), unsafe_allow_html=True)

# ── PANEL 3: CHARTS ──────────────────────────────────────────────────────────────

st.markdown("---")
chart_left, chart_right = st.columns([3, 2])

with chart_left:
    st.subheader("Score Distribution")
    st.caption("Risk scores coloured by queue assignment. Threshold lines show current slider settings.")
    fig = px.histogram(
        df, x='risk_score', color='triage_display', nbins=20,
        color_discrete_map={'auto-pass':'#27ae60','auto-hold':'#f39c12','escalate':'#e74c3c'},
        category_orders={'triage_display':['auto-pass','auto-hold','escalate']},
        labels={'risk_score':'Risk Score (0–100)','triage_display':'Queue'},
    )
    fig.add_vline(x=hold_threshold, line_dash='dash', line_color='#f39c12',
                  annotation_text=f'Hold≥{hold_threshold}', annotation_position='top')
    fig.add_vline(x=escalate_threshold, line_dash='dash', line_color='#e74c3c',
                  annotation_text=f'Esc≥{escalate_threshold}', annotation_position='top right')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      xaxis=dict(range=[0,100]), height=290, margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig, use_container_width=True)

with chart_right:
    st.subheader("Signal Activation")
    st.caption("How many tweets triggered each scoring signal (current view).")
    if not df.empty:
        safe_followers = df['followers_count'].clip(lower=1)
        rt_ratio_fires = int((df['retweet_count'] / safe_followers > 10).sum())
        sigs = {
            'New acct\n(<30d)':    int((df['account_age_days'] < 30).sum()),
            'Low\nfollowers':      int((df['followers_count'] < 10).sum()),
            'No profile\nphoto':   int((df['has_profile_photo'] == 0).sum()),
            'Keyword\nmatch':      int((df['has_keyword_signal'] == 1).sum()),
            'Bad\ndomain':         int((df['has_low_credibility_domain'] == 1).sum()),
            'High RT\nratio':      rt_ratio_fires,
        }
        fig2 = px.bar(
            x=list(sigs.keys()), y=list(sigs.values()),
            color=list(sigs.values()), color_continuous_scale='RdYlGn_r',
            labels={'x':'Signal','y':'Count'},
        )
        fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                           showlegend=False, coloraxis_showscale=False,
                           height=290, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True)

# ── PANEL 4: KEYWORD TRACKER + SCATTER ──────────────────────────────────────────

st.markdown("---")
kw_col, scatter_col = st.columns([1, 2])

with kw_col:
    st.subheader("Top Keywords (Escalate Queue)")
    st.caption("Phrase frequency in escalate-bucket tweets")

    HIGH_RISK_PHRASES = [
        "BREAKING","SHARE BEFORE DELETED","SHARE BEFORE THEY DELETE",
        "THEY DON'T WANT YOU TO KNOW","CONFIRMED","MAINSTREAM MEDIA WON'T REPORT",
        "WHAT THEY'RE HIDING","DO YOUR OWN RESEARCH","WAKE UP","MUST WATCH",
        "GOING VIRAL","THEY'RE HIDING","SUPPRESSED","BANNED VIDEO","CENSORED",
    ]
    counter = Counter()
    for text in df_esc['text'].dropna():
        tu = text.upper()
        for phrase in HIGH_RISK_PHRASES:
            if phrase in tu:
                counter[phrase] += 1

    if counter:
        kw_df = pd.DataFrame(counter.most_common(10), columns=['Phrase', 'Count'])
        st.dataframe(kw_df, hide_index=True, use_container_width=True)
    else:
        st.caption("No escalated tweets yet.")

with scatter_col:
    st.subheader("Score vs. Retweet Count")
    st.caption(
        "High-score posts with high RT counts are the most suspicious. "
        "Low-follower accounts with high RTs = artificial amplification signal."
    )
    if not df.empty:
        df_plot = df.copy()
        df_plot['retweet_count_capped'] = df_plot['retweet_count'].clip(upper=2000)
        fig3 = px.scatter(
            df_plot, x='risk_score', y='retweet_count_capped',
            color='triage_display',
            color_discrete_map={'auto-pass':'#27ae60','auto-hold':'#f39c12','escalate':'#e74c3c'},
            opacity=0.55,
            labels={'risk_score':'Risk Score','retweet_count_capped':'Retweet Count (cap 2k)',
                    'triage_display':'Queue'},
            hover_data=['account_age_days','followers_count','signal_summary'],
        )
        fig3.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                           height=310, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig3, use_container_width=True)

# ── PANEL 5: PRECISION EVALUATION ────────────────────────────────────────────────

st.markdown("---")
st.subheader("Escalation Bucket Precision")
st.caption(
    "Precision = of all posts the system escalated, what fraction were genuinely high-risk? "
    "Measured on manually labelled ground truth. See EVALUATION.md for labelling protocol."
)

labelled = df_all[df_all['ground_truth_label'].notna()]
if labelled.empty:
    st.info(
        "**No labels yet.** Run `python evaluation/export_for_labelling.py`, "
        "fill in the human_label column (0/1) in the CSV, then run "
        "`python evaluation/evaluate_precision.py` to calculate precision. "
        "See [EVALUATION.md](https://github.com/yourusername/VeritasWatch/blob/main/EVALUATION.md) "
        "for the full labelling protocol."
    )
else:
    labelled_esc = labelled[labelled['triage_decision'] == 'escalate']
    n = len(labelled_esc)
    tp = int((labelled_esc['ground_truth_label'] == 1).sum())
    fp = int((labelled_esc['ground_truth_label'] == 0).sum())
    precision = tp / n * 100 if n > 0 else 0

    e1, e2, e3 = st.columns(3)
    with e1:
        st.metric("Escalation Precision", f"{precision:.1f}%",
                  help="TP/(TP+FP) in escalate bucket. Not recall — FN is unmeasured.")
    with e2:
        st.metric("Labelled Sample", f"{n}")
    with e3:
        st.metric("Confirmed High-Risk (TP)", f"{tp}")

    st.markdown(f"""
| | System: Escalate | System: Hold/Pass |
|:---|:---:|:---:|
| **Actually High-Risk** | TP = {tp} | FN = *not measured* |
| **Actually Low-Risk** | FP = {fp} | TN = *not measured* |

*Recall is not measured — would require labelling auto-passed tweets. See EVALUATION.md.*
    """)

# ── KNOWN LIMITATIONS ANCHOR ─────────────────────────────────────────────────────

st.markdown("---")
st.markdown("<a name='known-limitations'></a>", unsafe_allow_html=True)
st.subheader("Known Limitations")
with st.expander("Click to expand — read before discussing this project in an interview"):
    st.markdown("""
**Limitation 1 — The Dormant Account Problem (Most Dangerous)**  
A sophisticated actor using a 4-year-old account with 15,000 followers, clean language, and a domain not on the blocklist scores 0 and auto-passes. VeritasWatch has no equivalent of platform-level CIB network detection.

**Limitation 2 — The Journalism False Positive**  
Journalism quoting false claims to debunk them triggers the same keyword signals as the false claims themselves. No whitelist. No stance detection (NLP that distinguishes endorsement from refutation).

**Limitation 3 — English Only**  
`lang:en` filter in collection. Misinformation is multilingual. Not deployable at scale.

**Limitation 4 — No Content Understanding**  
"Vaccines DO cause autism — proven here" and "The claim vaccines cause autism has been proven false 47 times" receive the same keyword score. Pattern matching ≠ semantic understanding.

**Limitation 5 — Static Domain Blocklist**  
Manually curated. New misinformation domains appear daily. Production systems use dynamic domain credibility graphs.

**Limitation 6 — Recall Is Unmeasured**  
We measure precision (of what we escalated, how much was correct). We do not measure recall (of all the high-risk content, how much did we catch). Labelling auto-passed tweets was out of scope.

**Limitation 7 — Batch/Replay Mode Only**  
X API Basic tier ($100/month) caps at ~10,000 tweets/month. True real-time streaming requires Pro tier ($5,000/month). This dashboard replays pre-collected data.
    """)

# ── FOOTER ───────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    "VeritasWatch · Rule-based misinformation triage demo · "
    "Python 3.10 · Tweepy · SQLite · Streamlit · Plotly · "
    "Not a production moderation system · No content is automatically actioned"
)
