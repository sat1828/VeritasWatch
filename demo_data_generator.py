"""
demo_data_generator.py — Synthetic tweet generator for VeritasWatch demo mode.

v2.0 — Complete rewrite. Previous version had 31 unique texts / 500 tweets (16x repetition).

CRITICAL HONESTY NOTICE:
  All data produced by this script is SYNTHETIC.
  The dashboard banner states this clearly.
  If you have real data from collector.py, delete the DB and use that instead.

DESIGN: Score-range targeting.
  Each tweet is engineered by choosing which signals fire, then running
  the real scorer.py. We control inputs, scorer controls outputs.
  This ensures the distribution matches what real data would produce.

TARGET DISTRIBUTION:
  ~65% auto-pass  (clean accounts, debunking content, journalism)
  ~22% auto-hold  (moderate signal combinations, alarm language)
  ~11% escalate   (new accounts, alarm language, bad domains, high RT ratio)

TEXT DIVERSITY TARGET: < 3x repetition ratio (v1 was 16x).

RESEARCH BASIS FOR TEXT SELECTION:
  Sharma et al. (2019) ArXiv:1901.06437 — misinformation pattern taxonomy
  Wardle (2017) First Draft — seven types of mis/disinformation
  Vosoughi et al. (2018) Science 359:1146 — spread of true vs false news
  Roozenbeek et al. (2020) Royal Society Open Science — COVID misinfo susceptibility
"""

import random
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from database import initialise_db, insert_tweet, get_total_count
from scorer import score_tweet
from triage import triage_decision
from utils import now_iso

random.seed(7)

# ── POOL A: Auto-pass content ─────────────────────────────────────────────────

POOL_A_DEBUNKING = [
    "No, mRNA vaccines do not alter your DNA. Here is the actual mechanism — a thread.",
    "Fact-check: The claim that 5G towers spread COVID has been tested and refuted repeatedly.",
    "The peer-reviewed evidence on vaccine myocarditis risk: rare, mild, and lower than from COVID itself.",
    "I keep seeing this naturalnews.com article shared. Let me walk through why it misrepresents the study.",
    "The COVID lab leak hypothesis is scientifically plausible and under active investigation. It is not 'confirmed'.",
    "A useful thread on how to evaluate a health claim you see online before sharing it.",
    "The WHO investigation report on COVID origins is 120 pages. Here are the actual findings, not the headline.",
    "Media literacy: when a headline says 'study shows', always click through to the actual study.",
    "The VAERS reporting system is frequently misrepresented online. Here is what it actually measures.",
    "Reading the Cochrane review on ivermectin and COVID. Methodology matters more than conclusions.",
    "Excess mortality analysis for 2021-2022: here is the actual ONS data and how to read it.",
    "Three common misreadings of vaccine efficacy data and what the numbers actually mean.",
    "This 'suppressed study' has not been suppressed — it is on PubMed. It also doesn't say what the tweet claims.",
    "The difference between relative risk reduction and absolute risk reduction in vaccine trials.",
    "Correction: I was wrong about the booster timing data I shared last week. Here is the update.",
    "If you are reading a health claim on social media, here are five questions to ask before sharing.",
    "Why this viral 5G tower map is completely wrong — a brief explainer.",
    "The graphene oxide claim was debunked by five independent labs. Here are the papers.",
    "Spike protein toxicity: what the research actually shows vs what is being claimed.",
    "Thread: How misinformation narratives evolve after fact-checks — the COVID vaccine case study.",
    "No, the Pfizer trial data that was released does not show what viral posts claim it shows.",
    "The 'died suddenly' narrative: what the actual excess mortality data does and does not support.",
    "Honest assessment: where vaccine safety monitoring failed and where it worked.",
    "Thread on how to read a vaccine safety data sheet properly.",
    "Reuters fact-check: the viral 5G causes cancer clip is from 2019 and was debunked then.",
    "Published peer review does not work the way conspiracy theories assume it does.",
    "The actual Pfizer trial protocol is publicly available. Here is what it shows.",
    "Moderna preclinical safety data was published before EUA. Links below.",
    "The MHRA yellow card system explained: what it measures and what it does not.",
    "Cross-referencing ONS excess mortality data with vaccination rates by region.",
    "Academic read on why the lab leak hypothesis is scientifically discussable.",
    "Why doing your own research online usually means confirmation bias in practice.",
    "The difference between a preprint and a peer-reviewed publication — with examples.",
    "This graph has been shared 100k times with a misleading axis. Here is the corrected version.",
]

POOL_A_JOURNALISM = [
    "BREAKING: FDA approves updated COVID booster formulation — Reuters",
    "New NEJM paper on long COVID biomarkers — significant if it replicates.",
    "Government confirms investigation into COVID origins will continue — full statement here.",
    "Health ministers from G7 nations agree on pandemic preparedness framework — AP",
    "BREAKING: CDC updates mask guidance for healthcare settings — here is what changed.",
    "Reuters: Major study on vaccine effectiveness against new variants published today.",
    "Nature Medicine: Long-term cardiac outcomes in vaccinated vs unvaccinated COVID patients.",
    "CONFIRMED: FDA clears new antiviral for high-risk patients — clinical trial data here.",
    "BBC: Countries with high vaccine coverage saw lower excess mortality in 2021-22.",
    "AP Exclusive: Inside the lab leak investigation — what investigators found and didn't.",
    "The Guardian: 5G infrastructure rollout timeline and rural connectivity implications.",
    "Science: Researchers identify mechanism by which SARS-CoV-2 evades early immune response.",
    "BREAKING: UK MHRA publishes updated Yellow Card analysis for all COVID vaccines.",
    "AP: WHO declares end of COVID-19 global health emergency — what that means practically.",
    "CONFIRMED: Large Danish study on vaccine effectiveness at 12 months published in Lancet.",
    "Reuters: Pfizer posts Q3 results — Paxlovid revenue below analyst expectations.",
    "Nature: New research on T-cell immunity and its role in COVID protection.",
    "BREAKING: European Medicines Agency approves adapted booster for new subvariants.",
    "CONFIRMED: JAMA study on bivalent booster effectiveness against hospitalisation published.",
    "AP: EU regulators approve updated mRNA vaccine formulation for 2024-25 season.",
    "Reuters: First large-scale study on COVID reinfection rates in vaccinated population released.",
    "BREAKING: NIH releases new guidance on long COVID research priorities and funding.",
    "Science: Meta-analysis of 47 studies on mask effectiveness — findings and methodology.",
    "AP: Five years of 5G deployment data — no evidence of adverse health effects per WHO review.",
    "BMJ investigation: How health misinformation spreads faster than corrections on social media.",
    "CONFIRMED: FDA advisory committee votes to update COVID vaccine composition annually.",
    "Reuters: Global excess mortality study covering 74 countries published in Lancet.",
]

POOL_A_GENERAL = [
    "Genuinely not sure what to think about the lab leak hypothesis at this point.",
    "My doctor answered all my vaccine questions. If you have concerns, talk to yours.",
    "Public health communication has been a disaster in many countries. Worth examining honestly.",
    "The problem with 'just trust the science' is that science is a process, not an oracle.",
    "Vaccine hesitancy has structural roots, not just individual misinformation exposure.",
    "I've been reading about the history of 5G conspiracy theories — the timeline is fascinating.",
    "Both uncritical vaccine promotion AND anti-vaccine fearmongering can coexist in the same news cycle.",
    "Something I found interesting in the latest CDC surveillance report on breakthrough infections.",
    "Sharing this paper on information hazards and how researchers think about what to publish.",
    "Long thread on the history of pharmaceutical regulation — more complicated than most think.",
    "My experience getting the vaccine was uneventful. Not saying that's everyone's experience.",
    "The COVAX rollout and what went wrong — a long thread on equity and IP waiver politics.",
    "It is entirely possible to support vaccination programs while also holding institutions accountable.",
    "Reading about the ACE2 receptor binding mechanism. The structural biology here is genuinely interesting.",
    "Thoughts on why science communication failed during COVID — and what could be done differently.",
    "Thread on how to read a forest plot — for anyone trying to evaluate meta-analyses themselves.",
    "The difference between statistical significance and clinical significance, with COVID vaccine examples.",
    "Pre-pandemic, most people had no opinion on mRNA technology. The science itself is over 30 years old.",
    "Why excess mortality is a better metric than reported COVID deaths, and its limitations.",

    "Cross-referencing four different COVID data sources. They mostly agree where you'd expect them to.",
    "The challenge of communicating probabilistic risk to a general audience — COVID examples.",
    "Why the herd immunity threshold is a range, not a fixed number, and why that matters.",
    "Thread: what an immunologist actually does all day and why it is not like social media suggests.",
    "On the ethics of open science in pandemic research — sharing too fast vs sharing too slow.",
    "Reading the actual SAGE minutes on COVID policy. More uncertainty than headlines suggested.",
    "Why I changed my mind on vaccine mandates — and what changed it back.",
    "The long COVID registry data is becoming clearer. Here is what I take from it so far.",
    "Interesting disagreement between two well-credentialed researchers on aerosol transmission.",
    "On the difference between what a study found and what the press release said it found.",
    "Why health journalists and scientists often miscommunicate — a structural problem.",
    "Thread: the history of how mRNA technology went from obscure to household name in two years.",
    "My notes from the latest ISAC conference on immune response to repeated antigen exposure.",
    "Reading Offit on original antigenic sin — useful framework for thinking about booster design.",
    "The regulatory approval pathway for vaccines compared to other biologics — a breakdown.",
]

# Extended pool used by borderline pass profiles
POOL_A_EXTENDED2 = [
    "Why the precautionary principle cuts both ways in vaccine policy decisions.",
    "The statistical concept of number needed to treat — explained with COVID vaccine data.",
    "Comparing myocarditis rates: COVID infection vs mRNA vaccine, by age group.",
    "Thread: what the immunobridging study design means for variant-specific boosters.",
    "Reading the Brighton Collaboration criteria for adverse event categorisation.",
    "On base rates: why rare side effects look different depending on your reference class.",
    "The COVID origins question as a case study in how science handles genuine uncertainty.",
    "Why seroprevalence surveys and vaccination records often give different numbers.",
    "Thread on the history of adjuvants in vaccines and what they actually do.",
    "Comparing excess mortality methodology across five major studies — they mostly agree.",
    "On the question of vaccine effectiveness waning vs immune imprinting — current evidence.",
    "Reading Roozenbeek et al. on pre-bunking as a misinformation inoculation strategy.",
    "Thread: the evolution of COVID variant nomenclature and why some names stick.",
    "Why the precautionary principle is not a get-out-of-jail-free card for either side.",
    "Statistical concept: number needed to vaccinate — explained with COVID booster data.",
    "The COVID origins question as a case study in how science handles genuine uncertainty.",
    "Why seroprevalence surveys and vaccination records often give different population estimates.",
    "Thread on the history of adjuvants in vaccines and what they actually do at the cellular level.",
    "On base rates: why rare side effects look different depending on your reference population.",
    "Reading the Brighton Collaboration criteria for adverse event categorisation — useful.",
    "The challenge of ascribing causation in post-market surveillance — COVID vaccine examples.",
    "Why P-hacking is a bigger threat to vaccine safety science than most people realise.",
    "Thread: Bayesian thinking and why it changes how you should interpret safety signals.",
    "My reading notes on the history of how FDA review processes have changed since 1962.",
]

# Extended pool to reduce text repetition in large synthetic datasets
POOL_A_EXTENDED = [
    "Sharing this Lancet study on hybrid immunity — the combination of infection plus vaccination shows strongest protection.",
    "The ACE2 receptor binding domain research is genuinely fascinating. Structural biology people: here is a thread.",
    "Pre-pandemic, most people had no opinion on mRNA technology. The science itself is 30+ years old.",
    "Why excess mortality is a better COVID metric than reported deaths — and its own limitations.",
    "Thread on how to read a forest plot, for anyone trying to evaluate meta-analyses themselves.",
    "The difference between statistical significance and clinical significance, with vaccine trial examples.",
    "Something worth understanding: why the Pfizer trial had a 95% efficacy figure but real-world was lower.",
    "Reading Hotez et al on vaccine hesitancy. The root causes are structural, not just informational.",
    "Public health messaging has failed in specific ways. That is worth examining honestly, not defensively.",
    "Science is a process, not an answer. Uncertainty is honest, not suspicious.",
    "Good thread on how to identify a preprint vs a peer-reviewed paper and why it matters.",
    "The reason COVID variants get named after Greek letters — and what that system was designed to communicate.",
    "Thread: how does mRNA actually get into cells? The lipid nanoparticle mechanism explained clearly.",
    "ONS excess mortality data is publicly available. Here is how to download and read it yourself.",
    "Genuinely complex question: what is the right benchmark for vaccine trial placebo design?",
    "Reading about the ACE2 receptor binding mechanism. The structural biology here is genuinely interesting.",
    "Why I think the lab leak debate got so tribal, and why that's bad for epistemics on both sides.",
    "If you see a health claim that sounds alarming, here is a quick three-step check before you share.",
    "The measles vaccine comparison is often used in vaccine debates — here is what it does and doesn't prove.",
    "My experience: asking my GP hard vaccine questions. She answered all of them without defensiveness.",
    "Thread: the history of VAERS and how it was designed vs how it is currently being misused.",
    "On the question of natural immunity duration vs vaccine immunity duration — what the evidence shows.",
    "The boosters controversy explained: what the trials actually showed vs what was claimed by both sides.",
    "Understanding why excess mortality fluctuates year to year even without pandemics.",
    "The spike protein biodistribution question: what the actual pharmacokinetic data shows.",
]

# ── POOL B: Auto-hold content ─────────────────────────────────────────────────

POOL_B_ALARM = [
    "BREAKING: New data suggests vaccine efficacy drops faster than reported. Share widely.",
    "Why is mainstream media ignoring the latest adverse event reports? Someone explain this.",
    "MUST READ: Doctor raises concerns about long-term mRNA effects. They won't cover this.",
    "Going viral: Study links boosters to increased COVID susceptibility at 3 months.",
    "CONFIRMED: Excess mortality in 2022 exceeds pre-pandemic baseline. What explains this?",
    "They don't want you asking questions about what was in the COVID vaccines. So ask them.",
    "WAKE UP: The Pfizer trial data they tried to keep sealed for 75 years is now public. Read it.",
    "SHARE: Former FDA advisor raises questions about booster approval process.",
    "What mainstream media won't report: natural immunity data that doesn't fit the narrative.",
    "BREAKING: Multiple European countries pause vaccine rollout for certain age groups.",
    "The COVID death counts were manipulated. Not all of them. But some. Here is evidence.",
    "MUST WATCH: Virologist who worked on mRNA technology raises concerns about long-term safety.",
    "They're hiding the full VAERS data. What's been released doesn't match my FOIA queries.",
    "GOING VIRAL: Leaked hospital document contradicts official COVID death counting methodology.",
    "Do your own research on what the CDC changed in its counting guidelines in October 2021.",
    "SHARE BEFORE DELETED: Parliamentary testimony that mainstream outlets aren't covering.",
    "What they're not telling you about the relationship between spike protein and heart inflammation.",
    "BREAKING CONFIRMED: Whistleblower claims data was altered in a major vaccine trial.",
    "The numbers being reported on COVID deaths in 2022 are inconsistent across government sources.",
    "Something is going on with the 5G rollout timing and COVID wave timing. Not making claims.",
    "MUST WATCH: Doctor lost hospital privileges after speaking out about adverse event reporting.",
    "The FDA approved this in record time. I'm not against vaccines. I'm asking questions.",
    "Mainstream media covered the Pfizer profits. They're not covering the injury reports at the same rate.",
    "GOING VIRAL: Internal emails show CDC knew about myocarditis risk earlier than publicly stated.",
    "WAKE UP: The relationship between pharmaceutical lobbying and regulatory decisions is real.",
    "BREAKING: Confidential documents from FDA advisory meeting leaked. No mainstream coverage.",
    "Do your own research on what spike protein does to vascular endothelium over time.",
    "MUST WATCH: Senator asks pointed questions about gain-of-function research. No coverage.",
    "They have been caught changing the definition of vaccine. Look at Merriam-Webster archive.",
    "GOING VIRAL: European cardiologist warns against boosters for under-40 males. Press silent.",
    "Why are embalmers across multiple countries reporting the same unusual findings? No coverage.",
    "CONFIRMED: Insurance actuaries report unusual rise in working-age mortality. What explains it?",
    "The signal in the VAERS database is real. Epidemiologists are afraid to say it publicly.",
    "WAKE UP: Why did New Zealand release vaccine death data only after a court order? Think about it.",
    "They switched from IFR to CFR calculations in 2021. Look at who benefited from that change.",
    "MUST READ: Pathologist presents findings at European Parliament. Zero coverage in major press.",
    "SHARE: Former WHO pandemic advisor says the next pandemic is already being planned. See docs.",
    "What the companies knew about spike protein toxicity before Phase 3 trials were completed.",
    "GOING VIRAL: Hospital staff told not to attribute certain deaths to vaccines. Whistleblower.",
    "The Cochrane review on mask effectiveness was buried for 18 months. Follow the funding.",
    "BREAKING: Regulatory capture at the FDA explained by former insider. Share this.",
    "CONFIRMED: Drug company knew about myocarditis signal early 2021. Approved August. Connect dots.",
    "Why are mainstream scientists refusing to debate the lab-leak scientists in a public forum?",
    "MUST WATCH: Epidemiologist who predicted the COVID wave pattern given no mainstream platform.",
]


POOL_B_CREDULOUS = [
    "My friend's cousin is a nurse and says hospitals look nothing like what's officially reported.",
    "I know three people who had serious vaccine reactions. The plural of anecdote is not data but still.",
    "Something about the 5G rollout speed feels off to me. Too coordinated for coincidence.",
    "Interesting thread I found. Can't fully verify it but claims are specific enough to investigate.",
    "This doctor lost hospital privileges for speaking out. Doesn't that seem strange to anyone?",
    "Not saying I believe this but worth discussing: why did Pfizer want 75 years of data secrecy?",
    "My mum is very healthy and had a bad reaction. The doctor said unrelated. I have doubts.",
    "The way anyone questioning vaccine policy is immediately called antivaxx is a red flag to me.",
    "Going around in some communities I'm in. Hasn't hit mainstream yet. Thoughts?",
    "The official story keeps changing. I'm not saying that means anything. But it used to.",
    "I asked my GP about this and she got very defensive. That's not how doctors usually act.",
    "Three people in my street were hospitalised after the booster. Cannot prove causation.",
    "I'm double-vaccinated. Not antivaxx. But some injury reports are worth taking seriously.",
    "Whatever happened to the Great Barrington Declaration scientists? They've gone very quiet.",
    "This FOIA request result is very strange. Why would that information be redacted?",
    "Not saying it's proof of anything. But the timing is odd and deserves an explanation.",
    "I work in healthcare. Something has changed in the last two years. Not allowed to say what.",
    "The FDA approval timeline was unusually short. Not saying that's wrong. But it's a fact.",
    "Interesting: countries with lowest vaccine uptake did not see the highest excess mortality.",
    "My brother had a cardiac event two weeks after his booster. Doctors say unrelated. I question it.",
    "I've been trying to get a straight answer from my GP about this for three months. Still waiting.",
    "I do not have a theory. I just have questions that nobody will answer on the record.",
    "My employer mandated the booster. Three colleagues had adverse reactions. HR said: coincidence.",
    "Something changed in my health after the second dose. No doctor can find an explanation.",
    "Both my vaccinated parents got COVID. Both unvaccinated neighbours did not. Anecdote, I know.",
    "I do not think the vaccines are dangerous. I think the data transparency has been inadequate.",
    "The demographic most vaccine-hesitant happens to be the most credentialed. Make of that what you will.",
    "I do not align with conspiracies. But I do not think every question has a satisfactory answer yet.",
]

# ── POOL C: Escalate content ──────────────────────────────────────────────────

# Partitioned sub-pools — prevents borderline/hold profiles competing for same texts
POOL_B_ALARM_MILD   = POOL_B_ALARM[:22]   # low-key alarm; for borderline auto-pass
POOL_B_ALARM_STRONG = POOL_B_ALARM[22:]   # explicit alarm; for hold profiles only

POOL_C_HIGH_RISK = [
    "BREAKING CONFIRMED: Government statistics SUPPRESSED — vaccines killing 1 in 500. SHARE BEFORE DELETED.",
    "THEY DON'T WANT YOU TO KNOW: 5G towers activate graphene oxide in vaccines. WAKE UP. Share now.",
    "MUST WATCH BANNED VIDEO: Doctor CONFIRMS mRNA changes your DNA permanently. Media hiding this.",
    "SHARE BEFORE THEY DELETE: Whistleblower from Pfizer CONFIRMS trial data was falsified. Going viral.",
    "BREAKING: Doctors who spoke out about vaccine deaths being SILENCED. What they're hiding will shock you.",
    "CONFIRMED SUPPRESSED: Lab leak documents PROVE COVID was engineered bioweapon. Share everywhere.",
    "THEY DON'T WANT THIS OUT: Excess deaths in 2022 are 40% above baseline. Government covering it up.",
    "MUST SHARE NOW: Hospital recording CONFIRMS patients killed by ventilators for financial incentives.",
    "BANNED VIDEO: Nobel Prize winner explains why mRNA vaccines cause immune system collapse. CENSORED.",
    "BREAKING CONFIRMED: Vaccine nanoparticles collect biometric data and transmit via 5G towers.",
    "SHARE BEFORE DELETED: Internal CDC document shows they KNEW about massive myocarditis scale.",
    "GOING VIRAL: They're hiding that COVID was never real — the PCR test was deliberately miscalibrated.",
    "CONFIRMED: VAERS reports show 50,000 vaccine deaths in US alone. Real number estimated 100x higher.",
    "WAKE UP EVERYONE: Flu disappeared in 2020 because hospitals were counting flu deaths as COVID. CONFIRMED.",
    "THEY DON'T WANT YOU KNOWING: Former Pfizer executive says vaccines designed to reduce fertility.",
    "MUST WATCH CENSORED: Nurse CONFIRMS she was told not to report adverse events. Going viral everywhere.",
    "BREAKING SUPPRESSED: New study CONFIRMS spike protein permanently integrates into cellular DNA.",
    "SHARE NOW BEFORE IT'S DELETED: Leaked Moderna documents show they knew about cardiac risks in 2020.",
    "WAKE UP CONFIRMED: 5G towers are being used for mass mind control. MUST WATCH before BANNED.",
    "THEY DON'T WANT YOU KNOWING: Ivermectin CONFIRMED to cure COVID — SUPPRESSED by pharma lobby.",
    "SHARE BEFORE DELETED: Government CONFIRMS plan to use vaccines for population reduction. WAKE UP.",
    "BREAKING BANNED VIDEO: Funeral director CONFIRMS seeing unusual clots in vaccinated bodies only.",
    "CONFIRMED GOING VIRAL: Electromagnetic fields from vaccinated people detected by magnets. SHARE.",
    "MUST WATCH CENSORED: Patent documents CONFIRM COVID was engineered and vaccine was pre-planned.",
    "THEY'RE HIDING: VAERS whistleblower CONFIRMS death data deleted before public release. WAKE UP.",
    "BREAKING SHARE NOW: Lab CONFIRMS graphene oxide in all COVID vaccines. MAINSTREAM MEDIA WON'T REPORT.",
    "SUPPRESSED CONFIRMED: Former WHO scientist CONFIRMS pandemic was manufactured. SHARE BEFORE DELETED.",
    "WAKE UP GOING VIRAL: 5G activates vaccine payload on signal from satellite. MUST WATCH NOW.",
]


LOW_CRED_DOMAINS = [
    "naturalnews.com", "infowars.com", "globalresearch.ca",
    "beforeitsnews.com", "activistpost.com", "brighteon.com",
    "newstarget.com", "healthimpactnews.com", "zerohedge.com",
    "newspunch.com", "thegatewaypundit.com", "revolver.news",
    "rumble.com", "nationalfile.com", "dcclothesline.com",
]

CLEAN_DOMAINS = [
    "reuters.com", "reuters.com", "bbc.com", "apnews.com",
    "nejm.org", "who.int", "cdc.gov", "nature.com",
    "pubmed.ncbi.nlm.nih.gov", "theguardian.com",
    "washingtonpost.com", "sciencemag.org", "bmj.com",
]


def _rand_ts(days_back_max=7):
    offset = timedelta(minutes=random.randint(1, days_back_max * 24 * 60))
    return (datetime.now(timezone.utc) - offset).isoformat()


def _pick(pool: list, counts: dict) -> str:
    """
    Pick the least-used text from pool.
    Guarantees max repetition = ceil(total_draws / pool_size).
    Uses a Counter (dict) instead of a set so we track usage counts,
    not binary used/unused — eliminates the unlimited-fallback problem.
    """
    min_count = min(counts.get(t, 0) for t in pool)
    candidates = [t for t in pool if counts.get(t, 0) == min_count]
    choice = random.choice(candidates)
    counts[choice] = counts.get(choice, 0) + 1
    return choice


def _base(tweet_id, text, age, followers, photo, domain, rt, like=None, reply=None):
    return {
        'tweet_id': tweet_id, 'text': text,
        'created_at': _rand_ts(), 'author_id': f'u_{tweet_id}',
        'account_age_days': age, 'followers_count': followers,
        'following_count': min(random.randint(max(1, followers//4), max(followers//4+1, min(followers*2, 4999))), 5000),
        'has_profile_photo': photo, 'is_verified': 0,
        'retweet_count': rt,
        'like_count': like if like is not None else random.randint(rt//3+1, rt*3+5),
        'reply_count': reply if reply is not None else random.randint(1, max(2, rt//5)),
        'contains_url': 1 if domain else 0, 'url_domain': domain,
        'has_low_credibility_domain': 0, 'has_keyword_signal': 0,
        'keyword_hit_count': 0, 'signal_summary': '', 'collected_at': now_iso(),
        'risk_score': 0, 'triage_decision': 'unscored', 'ground_truth_label': None,
    }


def build_pass_clean(tid, counts):
    pool = POOL_A_DEBUNKING + POOL_A_JOURNALISM + POOL_A_GENERAL + POOL_A_EXTENDED + POOL_A_EXTENDED2
    text = _pick(pool, counts)
    age = random.randint(200, 4000)
    followers = random.randint(200, 80000)
    domain = random.choice(CLEAN_DOMAINS + [None, None])
    is_verified = 1 if followers > 10000 and random.random() < 0.3 else 0
    t = _base(tid, text, age, followers, 1, domain, random.randint(0, 80))
    t['is_verified'] = is_verified
    return t


def build_pass_borderline(tid, counts):
    """Newer account or one mild keyword — still passes."""
    profile = random.randint(1, 5)
    if profile == 1:     # Age 30-89d, clean → score ~10
        text = _pick(POOL_A_GENERAL + POOL_A_EXTENDED, counts)
        return _base(tid, text, random.randint(30, 89), random.randint(100, 2000),
                     1, random.choice(CLEAN_DOMAINS + [None]), random.randint(0, 40))
    elif profile == 2:   # Established, 1 keyword → score ~10
        text = _pick(POOL_B_CREDULOUS, counts)
        return _base(tid, text, random.randint(400, 3000), random.randint(200, 8000),
                     1, None, random.randint(0, 30))
    elif profile == 3:   # New-ish, few followers, has photo → score ~20
        text = _pick(POOL_A_GENERAL + POOL_A_EXTENDED + POOL_A_EXTENDED2 + POOL_B_CREDULOUS, counts)
        return _base(tid, text, random.randint(30, 89), random.randint(60, 300),
                     1, None, random.randint(0, 25))
    elif profile == 4:   # Established account, no photo (inactive type) → score ~10
        text = _pick(POOL_A_DEBUNKING + POOL_A_GENERAL, counts)
        return _base(tid, text, random.randint(500, 3000), random.randint(20, 500),
                     0, random.choice(CLEAN_DOMAINS), random.randint(0, 20))
    else:                # New-ish, 1 keyword, clean domain → score ~20
        text = _pick(POOL_B_ALARM_MILD, counts)
        return _base(tid, text, random.randint(30, 89), random.randint(100, 1000),
                     1, random.choice(CLEAN_DOMAINS), random.randint(5, 50))


def build_hold(tid, counts):
    """
    2-3 medium signals. Target: score 36-60.
    All profiles verified empirically against scorer.py:
    P1: age<90(+10)+<50f(+5)+no_photo(+10)+bad_domain(+15)+1kw(+10) = 50
    P2: age<90(+10)+<10f(+15)+bad_domain(+15)+1kw(+10)              = 50
    P3: no_photo(+10)+bad_domain(+15)+rt>100(+5)+1kw(+10)           = 40
    P4: age<90(+10)+no_photo(+10)+1kw(+10)+bad_domain(+15)          = 45
    P5: age<90(+10)+<10f(+15)+no_photo(+10)+bad_domain(+15) no kw   = 50
    """
    # Text selection happens INSIDE profile to avoid wasting a STRONG slot on profile 5
    profile = random.randint(1, 5)
    if profile == 5:
        # Profile 5: credulous/anecdotal text — no keyword signal needed
        text = _pick(POOL_B_CREDULOUS, counts)
        return _base(tid, text, random.randint(35, 89), random.randint(2, 9),
                     0, random.choice(LOW_CRED_DOMAINS), random.randint(5, 50))
    else:
        # Profiles 1-4: alarm text with exactly 1 keyword
        text = _pick(POOL_B_ALARM_STRONG, counts)
        if profile == 1:   # 50 pts: age<90 + <50f + no_photo + bad_domain + 1kw
            return _base(tid, text, random.randint(35, 89), random.randint(10, 45),
                         0, random.choice(LOW_CRED_DOMAINS), random.randint(10, 80))
        elif profile == 2: # 50 pts: age<90 + <10f + bad_domain + 1kw
            return _base(tid, text, random.randint(35, 89), random.randint(2, 9),
                         1, random.choice(LOW_CRED_DOMAINS), random.randint(5, 60))
        elif profile == 3: # 40 pts: older account, no_photo + bad_domain + rt>100 + 1kw
            return _base(tid, text, random.randint(200, 1500), random.randint(100, 3000),
                         0, random.choice(LOW_CRED_DOMAINS), random.randint(105, 400))
        else:              # 45 pts: age<90 + no_photo + bad_domain + 1kw
            return _base(tid, text, random.randint(35, 89), random.randint(50, 500),
                         0, random.choice(LOW_CRED_DOMAINS), random.randint(10, 60))


def build_escalate(tid, counts):
    """3+ strong signals. Target: score 61-100."""
    text = _pick(POOL_C_HIGH_RISK, counts)
    followers = random.randint(1, 8)
    profile = random.randint(1, 3)
    if profile == 1:   # new<30(+20) + <10f(+15) + no_photo(+10) + 2kw(+20) = 65+
        return _base(tid, text, random.randint(2, 25), followers,
                     0, None, random.randint(20, 300))
    elif profile == 2: # new<30(+20) + <10f(+15) + 2kw(+20) + bad_domain(+15) = 70+
        return _base(tid, text, random.randint(2, 25), followers,
                     random.choice([0, 1]), random.choice(LOW_CRED_DOMAINS),
                     random.randint(50, 600))
    else:              # new<30(+20) + <10f(+15) + no_photo(+10) + bad_domain(+15) + rt_ratio>10(+20) = 80+
        rt = followers * random.randint(15, 400)
        return _base(tid, text, random.randint(2, 25), followers, 0,
                     random.choice(LOW_CRED_DOMAINS), rt)


def generate_demo_dataset(n_clean=120, n_borderline=80, n_hold=70, n_escalate=30):
    initialise_db()
    counts: dict = {}
    tweets = []
    ctr = [0]

    def nid(p):
        ctr[0] += 1
        return f"synth_{p}_{ctr[0]:05d}"

    for _ in range(n_clean):      tweets.append(build_pass_clean(nid("pc"), counts))
    for _ in range(n_borderline): tweets.append(build_pass_borderline(nid("pb"), counts))
    for _ in range(n_hold):       tweets.append(build_hold(nid("hold"), counts))
    for _ in range(n_escalate):   tweets.append(build_escalate(nid("esc"), counts))

    random.shuffle(tweets)

    dist = {'auto-pass': 0, 'auto-hold': 0, 'escalate': 0}
    for t in tweets:
        t = score_tweet(t)
        t['triage_decision'] = triage_decision(t['risk_score'])
        insert_tweet(t)
        dist[t['triage_decision']] += 1

    total = sum(dist.values())
    print("=" * 62)
    print("VeritasWatch — Synthetic Demo Data Generator v2.0")
    print("=" * 62)
    print(f"\nWARNING: All {total} tweets are SYNTHETIC. Dashboard discloses this.\n")
    print(f"Unique text templates used: {len(counts)}")
    print(f"Repetition ratio: {total/max(len(counts),1):.1f}x  (target: <3x)\n")
    print("Distribution:")
    for d, c in dist.items():
        pct = c / total * 100
        bar = '█' * int(pct / 2)
        print(f"  {d:<12}: {c:>4} ({pct:5.1f}%) {bar}")
    print("\nRun: streamlit run dashboard/app.py")
    print("=" * 62)


if __name__ == '__main__':
    generate_demo_dataset()
