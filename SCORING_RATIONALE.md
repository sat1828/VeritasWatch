# SCORING_RATIONALE.md
# VeritasWatch — Scoring Signal Rationale

This document explains **why** each signal has the weight it has.  
A score without a rationale is a number. A score with a rationale is a policy.

---

## Signal Table

| # | Signal | Condition | Weight | Max Points |
|---|--------|-----------|--------|-----------|
| 1 | Account age | Created < 30 days ago | +20 | 20 |
| 1b | Account age (partial) | Created 30–90 days ago | +10 | — |
| 2 | Follower count | < 10 followers | +15 | 15 |
| 2b | Follower count (partial) | < 50 followers | +5 | — |
| 3 | Profile photo absent | Default or missing avatar | +10 | 10 |
| 4 | Keyword signals | 2+ high-risk phrases in text | +20 | 20 |
| 4b | Keyword signals (partial) | 1 high-risk phrase | +10 | — |
| 5 | Low-credibility domain | URL from blocklist | +15 | 15 |
| 6 | Retweet velocity | RT count > 10× follower count | +20 | 20 |
| 6b | Retweet velocity (absolute) | > 500 retweets | +15 | — |
| 6c | Retweet velocity (absolute) | > 100 retweets | +5 | — |

**Maximum possible score: 100 (score is capped at 100)**

---

## Threshold Calibration

| Score Range | Decision | Rationale |
|-------------|----------|-----------|
| 0–35 | auto-pass | No combination of signals reached meaningful threshold. Cost of error: a low-risk piece of content is not reviewed. Acceptable at this range. |
| 36–60 | auto-hold | Some signals fired. Content goes to secondary human review. Not urgent. No SLA. |
| 61–100 | escalate | Multiple strong signals fired together. Priority human review. Still NOT automatic action. |

**The 35/60 boundaries were chosen so that:**
- A single high-weight signal (max 20 pts) cannot escalate a post alone
- Escalation requires at least 3 meaningful signals firing together
- At the auto-hold threshold (36 pts), at least two signals have fired
- This reduces single-signal false positives

---

## Signal-by-Signal Rationale

### Signal 1 — Account Age (< 30 days: +20, 30–90 days: +10)

**Why account age matters:**  
New accounts are disproportionately associated with coordinated inauthentic behaviour (CIB) and automated bot activity. Research consistently identifies account age as one of the highest-predictive features in social bot detection.

**Research basis:**  
Cresci, S. (2020). "A Decade of Social Bot Detection." *Communications of the ACM*, 63(10), 72–83.  
Also: Ferrara et al. (2016). "The Rise of Social Bots." *Communications of the ACM*, 59(7), 96–104.

**Real T&S equivalent:**  
New account signal in Meta's Coordinated Inauthentic Behaviour detection.  
**Critical difference:** Meta analyses account creation *networks* — accounts created in batch at the same time with shared infrastructure. We analyse one account's age in isolation. Sophisticated CIB networks use old, established accounts. Our signal is blind to that.

**Known false positive:**  
Every legitimate new user who just joined X also scores +20 here. This is the primary driver of false positives on new legitimate accounts. This is why Signal 1 alone (20 pts) cannot reach the escalation threshold. Two additional signals must fire.

**Weight justification:**  
Highest weight alongside Keywords and RT Velocity because account age has the strongest empirical correlation with inauthentic behaviour in the literature.

---

### Signal 2 — Follower Count (< 10: +15, < 50: +5)

**Why follower count matters:**  
Accounts with near-zero followers have no organic audience. They frequently function as disposable amplification accounts in coordinated campaigns — accounts created solely to retweet and amplify content, then abandoned.

**Limitation:**  
This signal is weak in isolation. A new legitimate user also has 0 followers. The signal's value comes from combination with Signal 1 and Signal 3 (the "New User Problem" below). A 3-year-old account with 8 followers is more suspicious than a 3-day-old account with 8 followers — but this signal doesn't distinguish between them.

**Weight justification:**  
Lower than Signal 1 (15 vs 20) because follower count is a weaker predictor than account age when examined alone.

---

### Signal 3 — Profile Photo Absent (+10)

**Why a missing profile photo matters:**  
Default-avatar accounts are strongly associated with newly created, unverified, or automated accounts. Default photos require no user action — setting a custom photo is a signal of investment in the account.

**Limitation:**  
Many legitimate inactive users retain their default photo for years. This signal is low-diagnostic in isolation — it adds risk points only when combined with account age and follower signals.

**Weight justification:**  
Lowest weight (10 pts) because it is the weakest individual predictor. A single-signal score of 10 keeps the tweet firmly in auto-pass.

---

### Signal 4 — Keyword Signals (2+ phrases: +20, 1 phrase: +10)

**Why keyword patterns matter:**  
Certain phrases appear disproportionately in misinformation content. The phrase list was compiled from content moderation literature on misinformation markers, focusing on "alarm" language that is common in false claims and uncommon in verifiable reporting.

**CRITICAL LIMITATION — The Journalism Trap:**  
This is a pattern match, not content understanding. The scoring engine cannot distinguish:
- "BREAKING: Vaccines CONFIRMED to cause autism — new study" (misinformation)
- "BREAKING: Government CONFIRMS election irregularities — Reuters reports" (verifiable news)
- "WAKE UP: The claim that vaccines cause autism has been CONFIRMED false 47 times" (debunking)

All three texts score similarly on Signal 4. Stance detection (NLP that classifies whether a post endorses or refutes a claim) is the production solution. We do not have it.

In the ground truth evaluation, the Journalism Trap is expected to be the primary source of false positives. This is documented in EVALUATION.md.

**Weight justification:**  
High weight (20 pts) because keyword patterns are a strong signal when combined with account signals. The high weight is appropriate *only because* escalation requires multiple signals to fire.

---

### Signal 5 — Low-Credibility Domain Link (+15)

**Why domain credibility matters:**  
Links to known misinformation sources are one of the strongest individual signals of harmful content at the post level. If a tweet's primary claim is sourced to a domain classified as conspiracy-pseudoscience, the claim is unlikely to be verified.

**Blocklist source:**  
Documented in `data/low_credibility_domains.txt`. Compiled from MediaBiasFactCheck.com "Conspiracy-Pseudoscience" category and NewsGuard red-rated domains referenced in published academic research.

**CRITICAL LIMITATION — Static List:**  
The blocklist is static and manually maintained. New misinformation domains emerge continuously. A domain that begins publishing misinformation tomorrow will not appear on this list. Production systems use dynamic credibility scoring trained on domain link graphs (CrediBench, 2024) that update continuously. Our list requires manual curation.

**Weight justification:**  
15 pts — meaningful but not the highest because a domain match could represent the tweet *debunking* the domain's content. "Why you should not trust naturalnews.com — a thread" would score +15 from Signal 5 despite being counter-speech. Without content understanding, we cannot distinguish citation from refutation.

---

### Signal 6 — Retweet Velocity (ratio > 10×: +20, absolute > 500: +15, > 100: +5)

**Why retweet velocity matters:**  
Disproportionate virality relative to an account's follower base is a signal of artificial amplification. A tweet from a 5-follower account with 200 retweets cannot have organically reached 200 shares through that account's own network — someone else is amplifying it.

**Implementation honesty:**  
True velocity requires tracking the *same tweet across multiple time windows* to measure rate of change (Δretweet_count / Δtime). In batch-collected data (our replay mode), we use the ratio of retweet_count to followers_count as a static proxy. This is a degraded approximation of velocity.

In a streaming architecture with tweet_id tracking across collection windows, you would compute:
```
velocity = (rt_count_now - rt_count_15min_ago) / 15
```
We don't do this. The ratio proxy catches extreme cases but misses moderate viral acceleration.

**Weight justification:**  
High weight (20 pts) because the ratio > 10× condition is a strong anomaly signal when it fires. Very few organic posts from small accounts achieve this ratio.

---

## Signal Interaction Awareness

### Interaction 1 — The New User Problem

Signals 1 + 2 + 3 can fire simultaneously for a brand-new legitimate user:  
- Signal 1: account < 30 days → +20  
- Signal 2: < 10 followers → +15  
- Signal 3: no profile photo → +10  
- **Total: 45 → auto-hold**

A new legitimate user with no keywords, no bad domains, and no viral content will still land in auto-hold. This is a structural false positive driver.

**Mitigation in this system:** Auto-hold sends them to *secondary human review*, not escalation. A human reviewer will quickly clear them. The damage is a wasted review slot, not a false accusation.

**Mitigation in production:** New accounts with high-quality content are downweighted after surviving the initial review period. Some platforms whitelist accounts that pass initial human review. We don't have either mechanism.

---

### Interaction 2 — The Journalism Trap

A journalist tweeting: `"BREAKING: Government CONFIRMS election irregularities — new investigation"`  
- Signal 4: "BREAKING" + "CONFIRMS" = 2 phrase hits → +20  
- Total (assuming established account): 20 → auto-pass if no other signals  
- Total (if newer account, few followers): potentially 55+ → auto-hold

This is expected behaviour at auto-hold. The journalist's content goes to secondary review, where a human quickly passes it. The damage: one wasted human review. In production, verified accounts and trusted news domains are whitelisted from keyword scoring. We lack that whitelist.

---

### Interaction 3 — The Dormant Account Problem (Most Dangerous Failure Mode)

A sophisticated misinformation actor who:
- Uses a 4-year-old account (Signal 1 = 0 pts)
- Has 15,000 followers (Signal 2 = 0 pts)
- Has a profile photo (Signal 3 = 0 pts)
- Uses clean language without alarm phrases (Signal 4 = 0 pts)
- Links to a domain not on the blocklist (Signal 5 = 0 pts)
- Has organic-looking engagement (Signal 6 = 0 pts)

**Score: 0 → auto-pass. The system is completely blind to this actor.**

This is not a hypothetical edge case. It represents how sophisticated coordinated inauthentic behaviour actually operates. High-value influence operations avoid obvious signals by design.

Platforms like Meta address this through graph-based CIB detection: analysing *networks* of accounts that post the same content in the same time window, accounts that consistently retweet each other, accounts created in batches with shared infrastructure. None of that is detectable from a single post's metadata.

**VeritasWatch has no equivalent.** This is documented as Limitation 1 in README.md because it is the most serious and fundamental limitation of any rule-based single-post triage system.

---

## What a Production Scoring System Looks Like

For context, here is what replaces a rule-based scorer in a production Trust & Safety system:

1. **ML classifier (BERT/RoBERTa fine-tuned on hate speech / misinformation corpora):** Replaces keyword matching with semantic understanding. Can distinguish endorsement from refutation. Requires millions of labelled training examples.

2. **Graph-based signals:** Accounts in a detected CIB network receive elevated scores regardless of individual post signals. Requires maintaining a persistent graph of account co-activity.

3. **Temporal velocity tracking:** Real streaming architecture tracks the same tweet_id across time windows. Delta retweet rate, not absolute count.

4. **Dynamic domain credibility scoring:** Trained model on domain link graphs (CrediBench, 2024). Updates automatically as new misinformation domains emerge.

5. **Geographic context signals:** Content that is harmless in one context may be harmful election interference in a specific country during a specific week. Requires geo-signal integration.

6. **Active learning pipeline:** Moderator decisions feed back into model retraining. The system improves as it processes more content.

VeritasWatch implements none of these. It models the *reasoning structure* of a production system, not its technical infrastructure.
