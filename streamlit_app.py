"""
StakeStream Command Center v8
Bitwise EMEA | Lead Tracker
Features: Pipo Chat, Lead Detail, Kanban, Search, Bulk Actions
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os, json
from datetime import datetime

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StakeStream | Bitwise EMEA",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': 'StakeStream — Bitwise EMEA'}
)

# ── Bitwise Brand CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=Inter:wght@300;400;500;600&display=swap');

/* ── Base ── */
.stApp {
    background: #0d1520;
    color: #d4dbe8;
    background-image:
        linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
    background-size: 40px 40px;
}
.main .block-container { max-width: 1400px; padding: 1.5rem 1.5rem 3rem; }

/* ── Typography ── */
h1, h2, h3 { font-family: 'Cormorant Garamond', 'Georgia', serif; color: #ffffff; font-weight: 300; letter-spacing: -0.01em; }
h1 { font-size: clamp(1.5rem, 5vw, 2.25rem); font-style: italic; margin-bottom: 0.25rem; }
h2 { font-size: clamp(1rem, 3.5vw, 1.35rem); margin-top: 1.5rem; color: #c8d4e8; }
h3 { font-size: clamp(0.9rem, 3vw, 1.1rem); color: #a0b0c8; }
p, span, div, label { font-family: 'Inter', -apple-system, sans-serif; }

/* ── Header Brand Bar ── */
.bw-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.75rem 0 1.25rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 1.5rem;
}
.bw-logo {
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.5rem; font-weight: 400; color: #fff; letter-spacing: 0.01em;
}
.bw-logo span { color: #22c55e; }
.bw-subtitle { font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #4a6080; text-transform: uppercase; letter-spacing: 0.15em; margin-top: 2px; }
.bw-date { font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #4a6080; text-align: right; }

/* ── Metric Cards ── */
.metric-card {
    background: #0f1c2e;
    border: 1px solid rgba(255,255,255,0.07);
    border-top: 2px solid #22c55e;
    border-radius: 4px;
    padding: 1.25rem 1rem;
    text-align: center;
    margin-bottom: 0.5rem;
    transition: border-color 0.2s;
}
.metric-card:hover { border-color: #22c55e; border-top-color: #22c55e; }
.metric-card.alert { border-top-color: #ef4444; }
.metric-card.warn  { border-top-color: #f59e0b; }
.metric-card.purple { border-top-color: #6366f1; }
.metric-val { font-family: 'Cormorant Garamond', serif; font-size: clamp(1.75rem, 6vw, 2.5rem); font-weight: 300; color: #fff; line-height: 1; }
.metric-lbl { font-size: 0.65rem; color: #4a6080; margin-top: 0.375rem; text-transform: uppercase; letter-spacing: 0.12em; }

/* ── Lead Cards ── */
.lead-row {
    background: #0f1c2e;
    border: 1px solid rgba(255,255,255,0.07);
    border-left: 3px solid #22c55e;
    border-radius: 4px;
    padding: 0.875rem 1rem;
    margin-bottom: 0.5rem;
    transition: border-color 0.2s;
}
.lead-row:hover { border-color: #22c55e; }
.lead-row.tier1 { border-left-color: #22c55e; }
.lead-row.tier2 { border-left-color: #6366f1; }
.lead-row.tier3 { border-left-color: #334155; }
.lead-company { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.9375rem; color: #e8f0ff; }
.lead-meta { font-size: 0.75rem; color: #4a6080; margin-top: 0.25rem; }

/* ── Alert Cards ── */
.alert-card { background: #0f1c2e; border-radius: 4px; padding: 1rem; margin-bottom: 0.75rem; border-left: 3px solid #ef4444; }
.alert-card.warning { border-left-color: #f59e0b; }
.alert-card.info    { border-left-color: #6366f1; }
.alert-card.success { border-left-color: #22c55e; }
.alert-title { font-size: 0.9375rem; font-weight: 600; color: #e8f0ff; }
.alert-sub   { font-size: 0.8rem; color: #4a6080; margin-top: 0.25rem; }

/* ── Badges ── */
.score-badge { background: #1a2840; border-radius: 3px; padding: 0.2rem 0.5rem; font-size: 0.7rem; font-weight: 600; color: #6b7fa0; white-space: nowrap; font-family: 'Inter', sans-serif; letter-spacing: 0.05em; }
.score-badge.qualified { background: #052e16; color: #22c55e; border: 1px solid #166534; }
.score-badge.probable  { background: #1e1b4b; color: #818cf8; border: 1px solid #3730a3; }
.score-badge.possible  { background: #1c1917; color: #d4a660; border: 1px solid #78350f; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 2px; font-size: 0.65rem; font-weight: 600; letter-spacing: 0.05em; }
.pill-green  { background: #052e16; color: #22c55e; }
.pill-yellow { background: #1c1917; color: #d4a660; }
.pill-red    { background: #1f0909; color: #f87171; }
.pill-blue   { background: #0c1a3a; color: #6366f1; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { background: #0a1624; border-radius: 4px; padding: 3px; gap: 1px; border: 1px solid rgba(255,255,255,0.06); }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: #4a6080 !important; border-radius: 3px !important; font-size: clamp(0.7rem, 2.2vw, 0.8rem) !important; padding: 0.4rem 0.7rem !important; font-family: 'Inter', sans-serif !important; letter-spacing: 0.03em !important; }
.stTabs [aria-selected="true"] { background: #0f1c2e !important; color: #22c55e !important; border: 1px solid rgba(34,197,94,0.2) !important; }

/* ── Buttons ── */
.stButton > button { border-radius: 3px !important; font-weight: 500 !important; font-family: 'Inter', sans-serif !important; font-size: 0.8rem !important; letter-spacing: 0.05em !important; text-transform: uppercase !important; }
.stButton > button[kind="primary"] { background: #22c55e !important; color: #052e16 !important; border: none !important; }
.stButton > button:not([kind="primary"]) { background: #0f1c2e !important; color: #6b8ab0 !important; border: 1px solid rgba(255,255,255,0.08) !important; }

/* ── Inputs ── */
.stTextInput input, .stSelectbox select, .stTextArea textarea { background: #0a1624 !important; border: 1px solid rgba(255,255,255,0.08) !important; border-radius: 3px !important; color: #d4dbe8 !important; font-family: 'Inter', sans-serif !important; }
.stSelectbox > div > div { background: #0a1624 !important; border-color: rgba(255,255,255,0.08) !important; color: #d4dbe8 !important; }
.streamlit-expanderHeader { background: #0f1c2e !important; border: 1px solid rgba(255,255,255,0.07) !important; border-radius: 4px !important; color: #d4dbe8 !important; }

/* ── Misc ── */
section[data-testid="stSidebar"] { background: #0a1624; border-right: 1px solid rgba(255,255,255,0.06); }
.stDataFrame { border: 1px solid rgba(255,255,255,0.07) !important; border-radius: 4px !important; }
footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }
hr { border-color: rgba(255,255,255,0.06) !important; margin: 1.25rem 0 !important; }
.bw-footer { font-size: 0.6rem; color: #1e3050; text-transform: uppercase; letter-spacing: 0.1em; text-align: center; padding: 1rem 0 0; border-top: 1px solid rgba(255,255,255,0.04); margin-top: 2rem; }
@media (max-width: 768px) { .main .block-container { padding: 0.75rem !important; } }
</style>
""", unsafe_allow_html=True)

# ── Supabase Connection ────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase Verbindung fehlgeschlagen: {e}")
        return None

sb = get_supabase()

# ── Data Loading ────────────────────────────────────────────────────────────────
def qualify(score):
    if score >= 70: return "QUALIFIED", "qualified"
    if score >= 50: return "PROBABLE", "probable"
    if score >= 30: return "POSSIBLE", "possible"
    return "UNQUALIFIED", "unqualified"

def activity_pill(days):
    if days <= 2: return "<span class='pill pill-green'>Aktiv</span>"
    if days <= 7: return f"<span class='pill pill-yellow'>{days}d</span>"
    return f"<span class='pill pill-red'>{days}d 🚨</span>"

def days_ago(dt_str):
    if not dt_str: return 999
    try:
        dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        return max(0, (datetime.now() - dt.replace(tzinfo=None)).days)
    except: return 999

@st.cache_data(ttl=60)
def load_data():
    if not sb:
        return pd.DataFrame(), {}
    try:
        # Load leads with meddpicc scores via join (paginated, alle Records)
        all_data = []
        page_size = 1000
        offset = 0
        while True:
            resp = sb.table("leads").select(
                "*, meddpicc_scores(total_score, qualification_status, metrics, economic_buyer, "
                "decision_process, decision_criteria, paper_process, pain, champion, competition)"
            ).range(offset, offset + page_size - 1).execute()
            if not resp.data:
                break
            all_data.extend(resp.data)
            if len(resp.data) < page_size:
                break
            offset += page_size

        if not all_data:
            return pd.DataFrame(), {}
        # Alias for compatibility
        class _R:
            def __init__(self, data): self.data = data
        resp = _R(all_data)

        rows = []
        for lead in resp.data:
            score_data = lead.pop("meddpicc_scores", None)
            if isinstance(score_data, list):
                score_data = score_data[0] if score_data else None
            meddpicc = score_data.get("total_score", 0) if score_data else 0
            qual = score_data.get("qualification_status", "UNQUALIFIED") if score_data else "UNQUALIFIED"
            rows.append({
                **lead,
                "meddpicc": meddpicc or 0,
                "qualification": qual or "UNQUALIFIED",
                "m_metrics": score_data.get("metrics", 0) if score_data else 0,
                "m_economic": score_data.get("economic_buyer", 0) if score_data else 0,
                "m_process": score_data.get("decision_process", 0) if score_data else 0,
                "m_criteria": score_data.get("decision_criteria", 0) if score_data else 0,
                "m_paper": score_data.get("paper_process", 0) if score_data else 0,
                "m_pain": score_data.get("pain", 0) if score_data else 0,
                "m_champion": score_data.get("champion", 0) if score_data else 0,
                "m_competition": score_data.get("competition", 0) if score_data else 0,
            })

        df = pd.DataFrame(rows)
        df["days_inactive"] = df["updated_at"].apply(days_ago)
        df["qual_class"] = df["meddpicc"].apply(lambda s: qualify(s)[1])
        df["meddpicc"] = df["meddpicc"].fillna(0).astype(int)
        df["deal_size"] = df["expected_deal_size_millions"].fillna(0)
        df["region"] = df["region"].fillna("DE")
        df["stage"] = df["stage"].fillna("prospecting")
        df["industry"] = df["industry"].fillna("Institutional")

        active = df[~df["stage"].isin(["closed_won", "closed_lost"])]
        stats = {
            "total": len(df),
            "qualified": int((active["meddpicc"] >= 50).sum()),
            "stale": int((active["days_inactive"] >= 7).sum()),
            "critical": int(((active["meddpicc"] >= 60) & (active["days_inactive"] >= 3)).sum()),
            "pipeline": float(active["deal_size"].sum()),
        }
        return df, stats
    except Exception as e:
        st.error(f"Daten konnten nicht geladen werden: {e}")
        return pd.DataFrame(), {}

@st.cache_data(ttl=60)
def load_tasks():
    if not sb: return pd.DataFrame()
    try:
        resp = sb.table("tasks").select("*").order("created_at", desc=True).execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except:
        return pd.DataFrame()

def get_pipo_daily_picks(df, n=5):
    """Pipo's daily top picks — same algorithm as morning_briefing.py"""
    if df.empty:
        return pd.DataFrame()

    STAGE_WEIGHTS = {
        'negotiation': 1.0, 'validation': 0.9, 'solutioning': 0.8,
        'discovery': 0.6, 'prospecting': 0.4, 'closed_won': 0.0, 'closed_lost': 0.0
    }
    REGION_PRIORITY = {'UAE': 1.1, 'DE': 1.0, 'CH': 1.0, 'UK': 0.95, 'NORDICS': 0.9}

    active = df[~df["stage"].isin(["closed_won", "closed_lost"])].copy()

    def _score(row):
        meddpicc = int(row["meddpicc"])
        deal_size = float(row.get("deal_size") or 0)
        days = int(row.get("days_inactive") or 0)
        stage = str(row.get("stage") or "prospecting").lower()
        region = str(row.get("region") or "DE").upper()

        meddpicc_c = (meddpicc / 80) * 40
        if deal_size >= 50:   deal_c = 25
        elif deal_size >= 20: deal_c = 20
        elif deal_size >= 10: deal_c = 15
        elif deal_size >= 5:  deal_c = 10
        else: deal_c = min(5, deal_size) if deal_size else 2

        if days <= 2:    act_c = 5
        elif days <= 5:  act_c = 15
        elif days <= 10: act_c = 20
        elif days <= 21: act_c = 15
        else:            act_c = 10

        stage_c = STAGE_WEIGHTS.get(stage, 0.5) * 10
        strat_c = REGION_PRIORITY.get(region, 0.9) * 5
        return round(meddpicc_c + deal_c + act_c + stage_c + strat_c, 1)

    def _action(row):
        stage = str(row.get("stage") or "prospecting").lower()
        days = int(row.get("days_inactive") or 0)
        meddpicc = int(row["meddpicc"])
        if days > 10 and meddpicc >= 50:
            return "🔥 Dringend reaktivieren"
        return {
            'prospecting':  "📧 Cold Email / LinkedIn",
            'discovery':    "📞 Discovery Call buchen",
            'solutioning':  "📊 Solution Presentation",
            'validation':   "✅ POC Timeline",
            'negotiation':  "🤝 Deal closing",
        }.get(stage, "📞 Follow-up")

    active["priority_score"] = active.apply(_score, axis=1)
    active["suggested_action"] = active.apply(_action, axis=1)
    return active.nlargest(n, "priority_score")

def pipo_chat(messages, df_stats):
    """Send message to Claude API as Pipo with Bitwise context."""
    try:
        import anthropic
        api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "⚠️ ANTHROPIC_API_KEY nicht gesetzt. Bitte in Streamlit Cloud → Secrets hinzufügen."
        client = anthropic.Anthropic(api_key=api_key)
        system = f"""Du bist Pipo, der autonome Pre-Sales Chief of Staff von Philipp Sandor (HEAD of EMEA, Bitwise Asset Management, Dubai).

BITWISE FAKTEN (für Pitches):
- $15B+ AUM weltweit | 40+ Produkte | 4.000+ institutionelle Clients | Est. 2017
- Bitwise Onchain Solutions (ETH Staking): ~$5B gestaked | ZERO Slashings seit Genesis | 99.984% Uptime 2025
- Staking APR: 3.170% vs Benchmark 3.015% (+0.155% Outperformance)
- MiCA-konform | Institutional Reporting | Custody-Integration

LIVE DATENBANK (heute):
- Gesamt Leads: {df_stats.get('total', '?'):,}
- Qualifiziert (MEDDPICC≥60): {df_stats.get('qualified', '?')}
- Pipeline: €{df_stats.get('pipeline', 0):.0f}M
- Inaktiv >7 Tage: {df_stats.get('stale', '?')}
- Q1 Ziel: €500M Pipeline (aktuell: ~28%)

PHILIPPS FOKUS: ETH Staking für institutionelle EMEA-Kunden (DE > CH > UAE > UK > NORDICS)

Antworte präzise, datenbasiert, kein Smalltalk. Auf Deutsch. Max. 300 Wörter außer bei Email-Drafts."""

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=messages
        )
        return resp.content[0].text
    except ImportError:
        return "⚠️ 'anthropic' Package fehlt. Bitte requirements.txt updaten."
    except Exception as e:
        return f"⚠️ Fehler: {str(e)[:200]}"

# ── Load ───────────────────────────────────────────────────────────────────────
if not sb:
    st.error("⚠️ Supabase nicht konfiguriert. Bitte Secrets in Streamlit Cloud setzen.")
    st.code("""
# Streamlit Cloud → App Settings → Secrets → hinzufügen:
SUPABASE_URL = "https://cxrhqzggukuqxpsausrd.supabase.co"
SUPABASE_KEY = "dein-anon-key"
""")
    st.stop()

df, stats = load_data()
tasks_df = load_tasks()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:0.5rem 0 1rem;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:1rem;'>
        <div style='font-family:Cormorant Garamond,Georgia,serif;font-size:1.1rem;color:#fff;font-weight:300;'>
            <span style='color:#22c55e;'>■</span> StakeStream
        </div>
        <div style='font-size:0.6rem;color:#1e3050;text-transform:uppercase;letter-spacing:0.15em;margin-top:3px;'>
            Bitwise Onchain Solutions · EMEA
        </div>
    </div>
    """, unsafe_allow_html=True)
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div style='font-family:Cormorant Garamond,serif;font-size:1.75rem;font-weight:300;color:#fff;'>{stats['total']:,}</div><div style='font-size:0.6rem;color:#4a6080;text-transform:uppercase;letter-spacing:0.1em;'>Leads</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='font-family:Cormorant Garamond,serif;font-size:1.75rem;font-weight:300;color:#fff;'>€{stats['pipeline']:.0f}M</div><div style='font-size:0.6rem;color:#4a6080;text-transform:uppercase;letter-spacing:0.1em;'>Pipeline</div>", unsafe_allow_html=True)
        if stats['critical'] > 0:
            st.markdown(f"<div style='background:#1f0909;color:#f87171;padding:0.4rem 0.75rem;border-radius:3px;border:1px solid #7f1d1d;font-size:0.75rem;margin-top:0.75rem;font-weight:600;letter-spacing:0.05em;text-transform:uppercase;'>⚠ {stats['critical']} DRINGEND</div>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color:rgba(255,255,255,0.05);margin:1rem 0;'>", unsafe_allow_html=True)
    if st.button("↻  Aktualisieren"):
        st.cache_data.clear()
        st.rerun()
    st.markdown(f"<div style='font-size:0.6rem;color:#1e3050;text-transform:uppercase;letter-spacing:0.08em;margin-top:0.5rem;'>Supabase Cloud · {datetime.now().strftime('%d.%m %H:%M')}</div>", unsafe_allow_html=True)

# ── Navigation ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "🏠 Home", "🚨 Alerts", "📊 Pipeline",
    "✅ Tasks", "📥 Import", "⚙️ Score", "➕ Lead", "🤖 Pipo"
])

# ══════════════════════════════════════════════════════════════
# TAB 1: DASHBOARD
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown(f"""
    <div class='bw-header'>
        <div>
            <div class='bw-logo'><span>■</span> StakeStream</div>
            <div class='bw-subtitle'>Bitwise Onchain Solutions · EMEA</div>
        </div>
        <div class='bw-date'>
            {datetime.now().strftime('%A, %d. %b %Y')}<br>
            <span style='color:#22c55e;font-size:0.65rem;'>● LIVE</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.warning("Keine Daten. Leads müssen erst in Supabase migriert werden.")
    else:
        # ── Metric Row ──────────────────────────────────────────
        active = df[~df["stage"].isin(["closed_won", "closed_lost"])]
        avg_meddpicc = int(active["meddpicc"].mean()) if not active.empty else 0
        qual_rate = int(stats['qualified'] / max(stats['total'], 1) * 100)

        c1, c2, c3, c4, c5 = st.columns(5)
        metric_cards = [
            (c1, f"{stats['total']:,}",       "Leads gesamt",    "#22c55e", ""),
            (c2, str(stats['qualified']),       "Qualifiziert",    "#6366f1", "purple"),
            (c3, f"{qual_rate}%",               "Qual.-Rate",      "#06b6d4", "purple"),
            (c4, str(avg_meddpicc) + "/80",     "Ø MEDDPICC",     "#d4a660", "warn"),
            (c5, str(stats['stale']),           "Inaktiv >7T",
             "#ef4444" if stats['stale'] > 0 else "#4a6080",
             "alert" if stats['stale'] > 0 else ""),
        ]
        for col, val, label, color, cls in metric_cards:
            with col:
                st.markdown(f"""<div class="metric-card {cls}">
                    <div class="metric-val" style="color:{color};">{val}</div>
                    <div class="metric-lbl">{label}</div>
                </div>""", unsafe_allow_html=True)

        # ── Pipo's Daily Picks ──────────────────────────────────
        st.markdown("---")
        st.markdown("""
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.75rem;">
            <div style="font-family:'Cormorant Garamond',serif;font-size:1.2rem;color:#fff;font-weight:300;">
                🤖 Pipo's Picks für heute
            </div>
            <div style="font-size:0.6rem;color:#22c55e;text-transform:uppercase;letter-spacing:0.12em;
                         background:#052e16;border:1px solid #166534;padding:2px 8px;border-radius:2px;">
                Live · Morning Briefing Algo
            </div>
        </div>
        <div style="font-size:0.72rem;color:#4a6080;margin-bottom:1rem;">
            Top 5 Leads nach MEDDPICC · Deal Size · Inaktivität · Stage · Region
        </div>
        """, unsafe_allow_html=True)

        picks = get_pipo_daily_picks(df, n=5)
        if not picks.empty:
            pick_cols = st.columns(len(picks))
            rank_emojis = ["🥇", "🥈", "🥉", "4.", "5."]
            for i, (_, p) in enumerate(picks.iterrows()):
                _, qc = qualify(int(p["meddpicc"]))
                days = int(p.get("days_inactive") or 0)
                urgency_color = "#22c55e" if days <= 3 else "#d4a660" if days <= 7 else "#ef4444"
                deal_str = f"€{float(p.get('deal_size') or 0):.0f}M" if float(p.get('deal_size') or 0) >= 0.5 else "TBD"
                li_link = f"<a href='{p['linkedin']}' target='_blank' style='color:#6366f1;font-size:0.65rem;'>↗ LinkedIn</a>" if p.get("linkedin") else ""
                with pick_cols[i]:
                    st.markdown(f"""
                    <div style="background:#0f1c2e;border:1px solid rgba(34,197,94,0.18);
                                border-top:2px solid #22c55e;border-radius:4px;
                                padding:0.875rem 0.75rem;height:100%;position:relative;">
                        <div style="font-size:0.65rem;color:#22c55e;letter-spacing:0.1em;
                                     text-transform:uppercase;margin-bottom:0.4rem;">{rank_emojis[i]}</div>
                        <div style="font-weight:600;font-size:0.85rem;color:#e8f0ff;
                                     white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                                     margin-bottom:0.25rem;">{p['company'][:20]}</div>
                        <div style="font-size:0.65rem;color:#4a6080;margin-bottom:0.5rem;">
                            {p['region']} · T{int(p.get('tier',2) if p.get('tier') else 2)} · {p['stage']}
                        </div>
                        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:0.5rem;">
                            <span class="score-badge {qc}" style="font-size:0.6rem;">{int(p['meddpicc'])}/80</span>
                            <span style="font-size:0.65rem;color:{urgency_color};background:rgba(0,0,0,0.3);
                                          padding:1px 6px;border-radius:2px;">{days}d</span>
                        </div>
                        <div style="font-size:0.7rem;color:#d4a660;margin-bottom:0.25rem;">{deal_str}</div>
                        <div style="font-size:0.68rem;color:#a0b0c8;line-height:1.4;margin-bottom:0.4rem;">
                            {p.get('suggested_action','📞 Follow-up')}
                        </div>
                        <div style="font-size:0.6rem;color:#1e3050;margin-bottom:0.25rem;">{li_link}</div>
                        <div style="font-size:0.58rem;color:#1e3050;text-align:right;
                                     position:absolute;bottom:6px;right:8px;">
                            Score {p.get('priority_score','?')}
                        </div>
                    </div>""", unsafe_allow_html=True)
        else:
            st.info("Keine Picks verfügbar — Leads werden geladen...")

        # ── Charts Row ──────────────────────────────────────────
        st.markdown("---")
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            st.markdown("### Region")
            reg = df.groupby("region").size().reset_index(name="Count")
            fig = px.pie(reg, values="Count", names="region",
                         color_discrete_sequence=["#22c55e","#6366f1","#06b6d4","#a78bfa","#d4a660","#3b82f6","#f87171"], hole=0.55)
            fig.update_layout(height=220, paper_bgcolor="rgba(0,0,0,0)", font_color="#d4dbe8",
                              legend=dict(orientation="h", y=-0.35, font_size=9, font_color="#4a6080"),
                              margin=dict(t=5, b=55, l=5, r=5))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### MEDDPICC")
            order = ["QUALIFIED","PROBABLE","POSSIBLE","UNQUALIFIED"]
            qc_vals = df["qualification"].value_counts()
            fig = go.Figure(go.Bar(
                x=order, y=[qc_vals.get(o, 0) for o in order],
                marker_color=["#22c55e","#6366f1","#d4a660","#1e3050"],
                text=[qc_vals.get(o, 0) for o in order], textposition="outside",
                textfont=dict(color="#e5e5e5", size=10)
            ))
            fig.update_layout(height=220, paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", font_color="#d4dbe8",
                              showlegend=False,
                              xaxis=dict(showgrid=False, tickfont_size=9),
                              yaxis=dict(showgrid=True, gridcolor="#111", showticklabels=False),
                              margin=dict(t=10, b=5, l=5, r=5))
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            st.markdown("### Pipeline Funnel")
            stage_order = ["prospecting","discovery","solutioning","validation","negotiation","closed_won"]
            stage_labels = ["Prospecting","Discovery","Solutioning","Validation","Negotiation","Closed Won"]
            stage_colors = ["#22c55e","#06b6d4","#6366f1","#d4a660","#f87171","#22c55e"]
            stage_counts = [len(df[df["stage"] == s]) for s in stage_order]
            fig = go.Figure(go.Bar(
                y=stage_labels[::-1], x=stage_counts[::-1],
                orientation='h',
                marker_color=stage_colors[::-1],
                text=[f"{c:,}" for c in stage_counts[::-1]],
                textposition="outside",
                textfont=dict(color="#e5e5e5", size=10),
            ))
            fig.update_layout(height=220, paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", font_color="#d4dbe8",
                              showlegend=False,
                              xaxis=dict(showgrid=False, showticklabels=False),
                              yaxis=dict(showgrid=False, tickfont=dict(size=9, color="#6b8ab0")),
                              margin=dict(t=5, b=5, l=5, r=40))
            st.plotly_chart(fig, use_container_width=True)

        # ── Critical Alerts ──────────────────────────────────────
        hot = active[(active["meddpicc"] >= 50) & (active["days_inactive"] >= 3)].sort_values(
            ["meddpicc", "days_inactive"], ascending=[False, False]).head(3)
        if not hot.empty:
            st.markdown("---")
            st.markdown("### 🔥 Sofort-Prioritäten")
            for _, r in hot.iterrows():
                _, qc = qualify(int(r["meddpicc"]))
                li = f"&nbsp;·&nbsp;<a href='{r['linkedin']}' target='_blank' style='color:#6366f1;'>LinkedIn ↗</a>" if r.get("linkedin") else ""
                st.markdown(f"""
                <div class="alert-card">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <div class="alert-title">{r['company']} <span class="score-badge {qc}">{int(r['meddpicc'])}/80</span></div>
                            <div class="alert-sub">👤 {r.get('contact_person') or 'N/A'} · {r['region']} · {r['stage']} · {int(r['days_inactive'])}d inaktiv{li}</div>
                        </div>
                        <div style="font-size:0.7rem;color:#ef4444;white-space:nowrap;margin-left:0.5rem;">
                            🔥 Jetzt handeln
                        </div>
                    </div>
                </div>""", unsafe_allow_html=True)

        # ── Neueste Leads ────────────────────────────────────────
        st.markdown("---")
        st.markdown("### Neueste Leads")
        recent = df.sort_values("created_at", ascending=False).head(8) if "created_at" in df.columns else df.head(8)
        for _, r in recent.iterrows():
            _, qc = qualify(int(r["meddpicc"]))
            li = f"<a href='{r['linkedin']}' target='_blank' style='color:#6366f1;font-size:0.7rem;'>↗ LinkedIn</a>" if r.get("linkedin") else ""
            em = f"<a href='mailto:{r['email']}' style='color:#22c55e;font-size:0.7rem;'>✉</a>" if r.get("email") else ""
            days = int(r.get("days_inactive") or 0)
            urgency_color = "#22c55e" if days <= 3 else "#d4a660" if days <= 7 else "#ef4444"
            st.markdown(f"""
            <div class="lead-row">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
                    <div style="flex:1;min-width:0;">
                        <div class="lead-company">{r['company']}</div>
                        <div class="lead-meta">
                            {r['region']} · {r.get('industry','')} · {r['stage']}
                            &nbsp;{li}&nbsp;{em}
                        </div>
                    </div>
                    <div style="text-align:right;flex-shrink:0;">
                        <span class="score-badge {qc}">{int(r['meddpicc'])}/80</span>
                        <div style="font-size:0.6rem;color:{urgency_color};margin-top:3px;">{days}d</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB 2: PRIORITÄTEN
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown("# 🚨 Prioritäten")
    if df.empty:
        st.info("Keine Daten.")
    else:
        active = df[~df["stage"].isin(["closed_won","closed_lost"])]
        st.markdown("### 🔥 Kritisch — MEDDPICC ≥60 & inaktiv")
        crit = active[(active["meddpicc"] >= 60) & (active["days_inactive"] >= 3)].sort_values(["meddpicc","days_inactive"], ascending=[False,False])
        if crit.empty:
            st.success("✅ Keine kritischen Leads!")
        else:
            for _, r in crit.iterrows():
                _, qc = qualify(int(r["meddpicc"]))
                st.markdown(f"""
                <div class="alert-card">
                    <div class="alert-title">🔥 {r['company']} ({r['region']})</div>
                    <div class="alert-sub">👤 {r.get('contact_person') or 'N/A'} | {r.get('title') or ''} | {r['stage']}</div>
                    <div style="margin-top:0.5rem;"><span class="score-badge {qc}">{int(r['meddpicc'])}/80</span>
                    <span style="color:#a3a3a3;font-size:0.75rem;margin-left:0.5rem;">{int(r['days_inactive'])} Tage inaktiv</span></div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 😴 Schlummernde Deals (MEDDPICC ≥50, >7 Tage)")
        stale = active[(active["meddpicc"] >= 50) & (active["days_inactive"] >= 7)].sort_values("days_inactive", ascending=False)
        if stale.empty:
            st.info("Keine schlummernden Deals!")
        else:
            for _, r in stale.iterrows():
                _, qc = qualify(int(r["meddpicc"]))
                st.markdown(f"""
                <div class="alert-card warning">
                    <div class="alert-title">⚠️ {r['company']} ({r['region']})</div>
                    <div class="alert-sub">👤 {r.get('contact_person') or 'N/A'} | {r['stage']}</div>
                    <div style="margin-top:0.5rem;"><span class="score-badge {qc}">{int(r['meddpicc'])}/80</span>
                    <span style="color:#a3a3a3;font-size:0.75rem;margin-left:0.5rem;">{int(r['days_inactive'])} Tage</span></div>
                </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB 3: PIPELINE (Search + Kanban + Lead Detail)
# ══════════════════════════════════════════════════════════════
with tab3:
    if df.empty:
        st.info("Keine Daten.")
    else:
        # ── Global Search ──────────────────────────────────────
        search_q = st.text_input("🔍 Suche nach Firma, Kontakt, Industrie, Region...",
                                  placeholder="z.B. Deutsche Bank, Asset Management, UAE, C-Suite...",
                                  key="pipeline_search")

        # ── Filters Row ────────────────────────────────────────
        with st.expander("⚙️ Filter", expanded=False):
            fc1, fc2, fc3, fc4 = st.columns(4)
            with fc1: sel_region = st.selectbox("Region", ["Alle"] + sorted(df["region"].dropna().unique().tolist()))
            with fc2: sel_stage  = st.selectbox("Stage",  ["Alle"] + sorted(df["stage"].dropna().unique().tolist()))
            with fc3: sel_tier   = st.selectbox("Tier",   ["Alle", "1", "2", "3"])
            with fc4: act_filter = st.selectbox("Aktivität", ["Alle","Aktiv (<3T)","Warm (3-7T)","Inaktiv (>7T)"])
            min_medd = st.slider("Min. MEDDPICC Score", 0, 80, 0)

        # ── Apply Filters ──────────────────────────────────────
        filt = df.copy()
        if search_q:
            q = search_q.lower()
            filt = filt[
                filt["company"].str.lower().str.contains(q, na=False) |
                filt["contact_person"].str.lower().str.contains(q, na=False) |
                filt["industry"].str.lower().str.contains(q, na=False) |
                filt["region"].str.lower().str.contains(q, na=False) |
                filt["title"].str.lower().str.contains(q, na=False)
            ]
        if sel_region != "Alle": filt = filt[filt["region"] == sel_region]
        if sel_stage  != "Alle": filt = filt[filt["stage"]  == sel_stage]
        if sel_tier   != "Alle": filt = filt[filt["tier"]   == int(sel_tier)]
        if min_medd   >  0:      filt = filt[filt["meddpicc"] >= min_medd]
        if act_filter == "Aktiv (<3T)":   filt = filt[filt["days_inactive"] < 3]
        elif act_filter == "Warm (3-7T)": filt = filt[(filt["days_inactive"] >= 3) & (filt["days_inactive"] <= 7)]
        elif act_filter == "Inaktiv (>7T)": filt = filt[filt["days_inactive"] > 7]

        # ── Stats Bar ──────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#22c55e;'>{len(filt):,}</div><div class='metric-lbl'>Leads</div></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card purple'><div class='metric-val' style='color:#6366f1;'>{len(filt[filt['tier']==1])}</div><div class='metric-lbl'>Tier 1</div></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#22c55e;'>€{filt['deal_size'].sum():.0f}M</div><div class='metric-lbl'>Pipeline</div></div>", unsafe_allow_html=True)
        m4.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#d4a660;'>{len(filt[filt['days_inactive']>7])}</div><div class='metric-lbl'>Inaktiv >7T</div></div>", unsafe_allow_html=True)

        st.markdown("<div style='margin:0.75rem 0;'></div>", unsafe_allow_html=True)

        # ── View Toggle: List / Kanban ──────────────────────────
        view_mode = st.radio("Ansicht", ["📋 Liste", "🗂️ Kanban"], horizontal=True, label_visibility="collapsed")

        if view_mode == "🗂️ Kanban":
            # ── KANBAN BOARD ───────────────────────────────────
            st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)
            stages = ["prospecting","discovery","solutioning","validation","negotiation","closed_won"]
            stage_labels = {"prospecting":"Prospecting","discovery":"Discovery","solutioning":"Solutioning",
                           "validation":"Validation","negotiation":"Negotiation","closed_won":"Closed Won"}
            stage_colors = {"prospecting":"#22c55e","discovery":"#6366f1","solutioning":"#06b6d4",
                           "validation":"#d4a660","negotiation":"#f87171","closed_won":"#22c55e"}
            cols = st.columns(len(stages))
            for i, stage in enumerate(stages):
                with cols[i]:
                    stage_leads = filt[filt["stage"] == stage]
                    cnt = len(stage_leads)
                    pipe = stage_leads["deal_size"].sum()
                    color = stage_colors[stage]
                    st.markdown(f"""
                    <div style='border-top:2px solid {color};background:#0a1624;border-radius:4px;
                                padding:0.6rem 0.5rem;margin-bottom:0.5rem;text-align:center;'>
                        <div style='font-size:0.65rem;color:#4a6080;text-transform:uppercase;letter-spacing:0.1em;'>{stage_labels[stage]}</div>
                        <div style='font-size:1.1rem;font-weight:600;color:#fff;margin-top:2px;'>{cnt}</div>
                        <div style='font-size:0.65rem;color:{color};'>€{pipe:.0f}M</div>
                    </div>""", unsafe_allow_html=True)
                    for _, r in stage_leads.head(8).iterrows():
                        _, qc = qualify(int(r["meddpicc"]))
                        t_color = "#22c55e" if r["tier"]==1 else "#6366f1" if r["tier"]==2 else "#334155"
                        st.markdown(f"""
                        <div style='background:#0f1c2e;border:1px solid rgba(255,255,255,0.06);
                                    border-left:2px solid {t_color};border-radius:3px;
                                    padding:0.5rem 0.6rem;margin-bottom:0.375rem;'>
                            <div style='font-size:0.78rem;font-weight:600;color:#e8f0ff;white-space:nowrap;
                                        overflow:hidden;text-overflow:ellipsis;'>{r['company'][:22]}</div>
                            <div style='font-size:0.65rem;color:#4a6080;margin-top:2px;'>
                                {r['region']} · T{int(r['tier']) if r.get('tier') else '?'}
                            </div>
                            <div style='margin-top:4px;'>
                                <span class='score-badge {qc}' style='font-size:0.6rem;'>{int(r['meddpicc'])}</span>
                            </div>
                        </div>""", unsafe_allow_html=True)
                    if cnt > 8:
                        st.markdown(f"<div style='font-size:0.65rem;color:#4a6080;text-align:center;'>+{cnt-8} weitere</div>", unsafe_allow_html=True)
        else:
            # ── LIST VIEW ──────────────────────────────────────
            # Lead Detail State
            if "selected_lead_id" not in st.session_state:
                st.session_state.selected_lead_id = None

            for _, r in filt.head(100).iterrows():
                _, qc = qualify(int(r["meddpicc"]))
                t_color = "#22c55e" if r.get("tier")==1 else "#6366f1" if r.get("tier")==2 else "#334155"
                li = f"<a href='{r['linkedin']}' target='_blank' style='color:#6366f1;font-size:0.7rem;margin-left:6px;'>↗ LinkedIn</a>" if r.get("linkedin") else ""
                em = f"<a href='mailto:{r['email']}' style='color:#22c55e;font-size:0.7rem;margin-left:6px;'>✉ Email</a>" if r.get("email") else ""

                col_lead, col_btn = st.columns([10, 1])
                with col_lead:
                    st.markdown(f"""
                    <div class="lead-row tier{int(r.get('tier',3))}">
                        <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
                            <div style="flex:1;min-width:0;">
                                <div class="lead-company">{r['company']}</div>
                                <div class="lead-meta">
                                    {r.get('contact_person') or '—'} · {r.get('title') or ''}{li}{em}
                                </div>
                                <div class="lead-meta" style="margin-top:3px;">
                                    <span class='pill pill-blue' style='font-size:0.6rem;'>{r['region']}</span>
                                    <span style='margin:0 4px;color:#1e3050;'>·</span>
                                    {r.get('industry') or ''}
                                    <span style='margin:0 4px;color:#1e3050;'>·</span>
                                    {r['stage']}
                                </div>
                            </div>
                            <div style="text-align:right;flex-shrink:0;">
                                <span class="score-badge {qc}">{int(r['meddpicc'])}/80</span><br>
                                <span style="display:inline-block;margin-top:3px;">{activity_pill(int(r['days_inactive']))}</span>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)
                with col_btn:
                    if st.button("▼", key=f"detail_{r['id']}", help="Details anzeigen"):
                        if st.session_state.selected_lead_id == r["id"]:
                            st.session_state.selected_lead_id = None
                        else:
                            st.session_state.selected_lead_id = r["id"]

                # ── LEAD DETAIL CARD ──────────────────────────
                if st.session_state.selected_lead_id == r["id"]:
                    with st.container():
                        st.markdown(f"""
                        <div style='background:#071120;border:1px solid rgba(34,197,94,0.2);
                                    border-left:3px solid #22c55e;border-radius:4px;
                                    padding:1.25rem 1.25rem 0.75rem;margin:-0.25rem 0 0.75rem 0;'>
                            <div style='font-size:0.6rem;color:#22c55e;text-transform:uppercase;
                                        letter-spacing:0.15em;margin-bottom:0.75rem;'>
                                ■ LEAD DETAIL — {r['company'].upper()}
                            </div>
                        </div>""", unsafe_allow_html=True)

                        d1, d2, d3 = st.columns(3)
                        with d1:
                            st.markdown("**Kontakt**")
                            st.markdown(f"👤 {r.get('contact_person') or '—'}")
                            st.markdown(f"💼 {r.get('title') or '—'}")
                            if r.get("email"):
                                st.markdown(f"✉️ {r['email']}")
                            if r.get("linkedin"):
                                st.markdown(f"[↗ LinkedIn]({r['linkedin']})")
                        with d2:
                            st.markdown("**Deal Info**")
                            st.markdown(f"📍 {r['region']} · {r.get('sub_region') or '—'}")
                            st.markdown(f"🏢 {r.get('industry') or '—'} · Tier {int(r.get('tier',3))}")
                            st.markdown(f"📊 Stage: **{r['stage']}**")
                            st.markdown(f"💰 €{float(r.get('deal_size') or 0):.1f}M")
                        with d3:
                            st.markdown("**MEDDPICC**")
                            total_m = int(r["meddpicc"])
                            ql_m, qc_m = qualify(total_m)
                            fig_m = go.Figure(go.Indicator(
                                mode="gauge+number", value=total_m,
                                number={"font":{"color":"#22c55e","size":28}},
                                gauge={"axis":{"range":[0,80],"tickcolor":"#4a6080"},
                                       "bar":{"color":"#22c55e"},"bgcolor":"#0a1624",
                                       "steps":[{"range":[0,30],"color":"#071120"},
                                                {"range":[30,50],"color":"#1c1917"},
                                                {"range":[50,64],"color":"#1e1b4b"},
                                                {"range":[64,80],"color":"#052e16"}]}))
                            fig_m.update_layout(height=140, paper_bgcolor="rgba(0,0,0,0)",
                                              font_color="#d4dbe8", margin=dict(t=20,b=5,l=5,r=5))
                            st.plotly_chart(fig_m, use_container_width=True)

                        if r.get("pain_points") or r.get("use_case"):
                            st.markdown("**Notizen**")
                            if r.get("use_case"): st.caption(f"Use Case: {r['use_case']}")
                            if r.get("pain_points"): st.caption(f"Pain Points: {r['pain_points']}")

                        st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
                        ea1, ea2, ea3, ea4 = st.columns(4)
                        with ea1:
                            new_stage = st.selectbox("Stage ändern", ["—","prospecting","discovery","solutioning","validation","negotiation","closed_won","closed_lost"],
                                                     key=f"stg_{r['id']}")
                        with ea2:
                            new_notes = st.text_input("Notiz hinzufügen", key=f"note_{r['id']}", placeholder="z.B. Call gebucht...")
                        with ea3:
                            new_deal = st.number_input("Deal Size (Mio €)", min_value=0.0, value=float(r.get("deal_size") or 0), key=f"ds_{r['id']}")
                        with ea4:
                            st.markdown("<div style='margin-top:1.7rem;'></div>", unsafe_allow_html=True)
                            if st.button("💾 Update", key=f"save_{r['id']}", type="primary") and sb:
                                try:
                                    upd = {"updated_at": datetime.now().isoformat()}
                                    if new_stage != "—": upd["stage"] = new_stage
                                    if new_notes: upd["use_case"] = (r.get("use_case") or "") + f"\n[{datetime.now().strftime('%d.%m')}] {new_notes}"
                                    if new_deal != float(r.get("deal_size") or 0): upd["expected_deal_size_millions"] = new_deal
                                    sb.table("leads").update(upd).eq("id", int(r["id"])).execute()
                                    st.success("✅ Gespeichert!")
                                    st.cache_data.clear(); st.rerun()
                                except Exception as e:
                                    st.error(f"Fehler: {e}")
                        st.markdown("---")

            if len(filt) > 100:
                st.caption(f"Zeige 100 von {len(filt):,} Leads. Filter oder Suche nutzen.")

# ══════════════════════════════════════════════════════════════
# TAB 4: TASKS
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown("# ✅ Tasks")
    if not tasks_df.empty:
        todo = tasks_df[tasks_df["status"]=="todo"] if "status" in tasks_df else pd.DataFrame()
        inprog = tasks_df[tasks_df["status"]=="in_progress"] if "status" in tasks_df else pd.DataFrame()
        done = tasks_df[tasks_df["status"]=="done"] if "status" in tasks_df else pd.DataFrame()
        c1,c2,c3,c4 = st.columns(4)
        for col, val, lbl in [(c1,len(tasks_df),"Gesamt"),(c2,len(todo),"Offen"),(c3,len(inprog),"Aktiv"),(c4,len(done),"Erledigt")]:
            with col:
                st.markdown(f"""<div class="metric-card"><div class="metric-val">{val}</div><div class="metric-lbl">{lbl}</div></div>""", unsafe_allow_html=True)
        st.markdown("---")
        s1,s2,s3 = st.tabs(["Offen","In Arbeit","Erledigt"])
        PI = {"P1":"🔴","P2":"🟠","P3":"🟡","P4":"🟢"}
        def rtasks(tdf):
            if tdf.empty: st.info("Nichts hier!"); return
            for _, t in tdf.iterrows():
                pi = PI.get(str(t.get("priority","P2")),"⚪")
                co = f" | 🏢 {t['target_company']}" if t.get("target_company") else ""
                desc = str(t.get("description",""))[:100]
                st.markdown(f"""<div class="alert-card info"><div class="alert-title">{pi} {t['title']}</div><div class="alert-sub">{desc}{co}</div></div>""", unsafe_allow_html=True)
        with s1: rtasks(todo)
        with s2: rtasks(inprog)
        with s3: rtasks(done)

    st.markdown("---")
    with st.expander("➕ Neue Task"):
        with st.form("new_task_v7"):
            title = st.text_input("Titel *")
            desc = st.text_area("Beschreibung", height=80)
            c1,c2 = st.columns(2)
            with c1:
                priority = st.selectbox("Priorität", ["P1","P2","P3","P4"])
                category = st.selectbox("Kategorie", ["OUTREACH","UAE","GERMANY","SWITZERLAND","UK","RESEARCH","CONTENT"])
            with c2:
                company = st.text_input("Unternehmen")
                due = st.text_input("Fällig (YYYY-MM-DD)")
            if st.form_submit_button("Erstellen", type="primary"):
                if title and sb:
                    sb.table("tasks").insert({"title":title,"description":desc,"status":"todo","priority":priority,"category":category,"target_company":company or None,"due_date":due or None}).execute()
                    st.success(f"✅ {title}")
                    st.cache_data.clear(); st.rerun()

# ══════════════════════════════════════════════════════════════
# TAB 5: IMPORT
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown("# 📥 Import")
    st.markdown("CSV oder XLSX hochladen — wird direkt in Supabase gespeichert")

    uploaded = st.file_uploader("Datei auswählen", type=["csv","xlsx"])
    if uploaded:
        import tempfile, pathlib
        suffix = pathlib.Path(uploaded.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        try:
            preview = pd.read_csv(tmp_path, nrows=5) if suffix==".csv" else pd.read_excel(tmp_path, nrows=5)
            st.markdown(f"**{uploaded.name}** — Vorschau:")
            st.dataframe(preview, use_container_width=True, hide_index=True)
        except: pass

        source_tag = st.text_input("Quelle", value=uploaded.name.split(".")[0])
        dry_run = st.checkbox("Nur analysieren", value=True)

        if st.button("🚀 Importieren", type="primary"):
            with st.spinner("Importiere nach Supabase..."):
                try:
                    import sys, os, importlib.util
                    spec = importlib.util.spec_from_file_location(
                        "csv_importer",
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv_importer.py")
                    )
                    imp = importlib.util.load_from_spec(spec)
                    spec.loader.exec_module(imp)

                    # Import to local SQLite first (for Supabase we'd need direct connection)
                    # For now, import to temp SQLite and then sync to Supabase
                    import sqlite3
                    tmp_db = "/tmp/stakestream_import.db"

                    # Create minimal schema in temp DB
                    tconn = sqlite3.connect(tmp_db)
                    tconn.execute("""CREATE TABLE IF NOT EXISTS leads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL,
                        region TEXT DEFAULT 'DE', tier INTEGER DEFAULT 2,
                        aum_estimate_millions REAL DEFAULT 0, contact_person TEXT, title TEXT,
                        email TEXT, linkedin TEXT, stage TEXT DEFAULT 'prospecting',
                        pain_points TEXT, use_case TEXT, expected_deal_size_millions REAL DEFAULT 0,
                        expected_yield REAL DEFAULT 0, industry TEXT, staking_readiness TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                    tconn.execute("CREATE TABLE IF NOT EXISTS meddpicc_scores (id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER UNIQUE)")
                    tconn.commit()
                    tconn.close()

                    result = imp.import_file(tmp_path, source_tag=source_tag, dry_run=dry_run, db_path=tmp_db)

                    if not dry_run and result["imported"] > 0:
                        # Sync new leads from tmp_db to Supabase
                        tconn = sqlite3.connect(tmp_db)
                        tconn.row_factory = sqlite3.Row
                        new_leads = tconn.execute("SELECT * FROM leads").fetchall()
                        tconn.close()

                        batch = []
                        for row in new_leads:
                            d = dict(row)
                            batch.append({k: v for k, v in {
                                "company": d["company"],
                                "region": d.get("region","DE"),
                                "tier": d.get("tier", 2),
                                "contact_person": d.get("contact_person"),
                                "title": d.get("title"),
                                "email": d.get("email"),
                                "linkedin": d.get("linkedin"),
                                "stage": d.get("stage","prospecting"),
                                "industry": d.get("industry","Institutional"),
                                "use_case": d.get("use_case",""),
                                "staking_readiness": d.get("staking_readiness","Unknown"),
                                "expected_deal_size_millions": d.get("expected_deal_size_millions",0),
                                "aum_estimate_millions": d.get("aum_estimate_millions",0),
                            }.items() if v is not None})

                        if batch:
                            sb.table("leads").insert(batch).execute()
                        os.unlink(tmp_db)

                        st.success(f"✅ **{result['imported']} neue Leads** direkt in Supabase gespeichert!")
                        st.cache_data.clear(); st.rerun()
                    else:
                        st.info(f"**DRY RUN** — {result['imported']} würden importiert, {result['skipped_dup']} Duplikate")
                except Exception as e:
                    st.error(f"Fehler: {e}")
                    import traceback; st.code(traceback.format_exc())
                finally:
                    try: os.unlink(tmp_path)
                    except: pass

    st.markdown("---")
    st.markdown("**DB Status:**")
    try:
        count = sb.table("leads").select("id", count="exact").execute()
        by_region = sb.table("leads").select("region").execute()
        if by_region.data:
            reg_df = pd.DataFrame(by_region.data)["region"].value_counts()
            st.markdown(f"**{count.count:,} Leads** in Supabase")
            cols = st.columns(min(len(reg_df), 5))
            for i, (region, cnt) in enumerate(reg_df.items()):
                with cols[i % len(cols)]:
                    st.markdown(f"""<div class="metric-card"><div class="metric-val" style="font-size:1.25rem;">{cnt:,}</div><div class="metric-lbl">{region}</div></div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Status Fehler: {e}")

# ══════════════════════════════════════════════════════════════
# TAB 6: MEDDPICC
# ══════════════════════════════════════════════════════════════
with tab6:
    st.markdown("# ⚙️ MEDDPICC Scoring")
    if df.empty:
        st.info("Keine Daten.")
    else:
        search = st.text_input("🔍 Suchen", placeholder="z.B. Bitvavo, Deutsche Bank...")
        matches = df[df["company"].str.lower().str.contains(search.lower(), na=False)] if search else df.head(50)
        if matches.empty:
            st.warning(f"Kein Treffer für '{search}'")
        else:
            sel = st.selectbox("Unternehmen", matches["company"].tolist())
            r = matches[matches["company"]==sel].iloc[0]
            _, qc = qualify(int(r["meddpicc"]))
            st.markdown(f"""<div class="alert-card info"><div class="alert-title">{r['company']}</div>
            <div class="alert-sub">👤 {r.get('contact_person') or 'N/A'} | {r['region']} | {r['stage']} | Aktuell: <strong>{int(r['meddpicc'])}/80</strong></div></div>""", unsafe_allow_html=True)
            cl, cr = st.columns([3,2])
            with cl:
                st.markdown("### Bewertung")
                ll, lr = st.columns(2)
                with ll:
                    s_m = st.slider("📏 Metrics", 0, 10, int(r["m_metrics"]))
                    s_e = st.slider("💼 Economic Buyer", 0, 10, int(r["m_economic"]))
                    s_p = st.slider("🔄 Decision Process", 0, 10, int(r["m_process"]))
                    s_c = st.slider("📋 Decision Criteria", 0, 10, int(r["m_criteria"]))
                with lr:
                    s_pp = st.slider("📄 Paper Process", 0, 10, int(r["m_paper"]))
                    s_pa = st.slider("🩹 Pain", 0, 10, int(r["m_pain"]))
                    s_ch = st.slider("🏆 Champion", 0, 10, int(r["m_champion"]))
                    s_co = st.slider("⚔️ Competition", 0, 10, int(r["m_competition"]))
                total = s_m+s_e+s_p+s_c+s_pp+s_pa+s_ch+s_co
                ql, qc2 = qualify(total)
                st.markdown(f"""<div style="padding:1rem;background:#1a1a1a;border-radius:8px;text-align:center;">
                    <div style="font-size:2rem;font-weight:700;">{total}/80</div>
                    <span class="score-badge {qc2}">{ql}</span></div>""", unsafe_allow_html=True)
            with cr:
                fig = go.Figure(go.Indicator(mode="gauge+number", value=total,
                    title={"text":f"<b>{ql}</b>","font":{"color":"#e5e5e5","size":13}},
                    number={"font":{"color":"#e5e5e5","size":34}},
                    gauge={"axis":{"range":[0,80],"tickcolor":"#4a6080"},"bar":{"color":"#22c55e"},
                           "bgcolor":"#2a2a2a","steps":[{"range":[0,30],"color":"#1a1a1a"},
                           {"range":[30,50],"color":"#7f1d1d"},{"range":[50,70],"color":"#1e3a8a"},
                           {"range":[70,80],"color":"#166534"}]}))
                fig.update_layout(height=220, paper_bgcolor="rgba(0,0,0,0)", font_color="#d4dbe8", margin=dict(t=30,b=10,l=10,r=10))
                st.plotly_chart(fig, use_container_width=True)
            if st.button("💾 Speichern", type="primary") and sb:
                try:
                    lead_id = int(r["id"])
                    score_data = {"metrics":s_m,"economic_buyer":s_e,"decision_process":s_p,"decision_criteria":s_c,
                                  "paper_process":s_pp,"pain":s_pa,"champion":s_ch,"competition":s_co,
                                  "total_score":total,"qualification_status":ql}
                    existing = sb.table("meddpicc_scores").select("id").eq("lead_id",lead_id).execute()
                    if existing.data:
                        sb.table("meddpicc_scores").update(score_data).eq("lead_id",lead_id).execute()
                    else:
                        sb.table("meddpicc_scores").insert({"lead_id":lead_id,**score_data}).execute()
                    st.success(f"✅ {total}/80 ({ql}) gespeichert!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Fehler: {e}")

# ══════════════════════════════════════════════════════════════
# TAB 7: NEUER LEAD
# ══════════════════════════════════════════════════════════════
with tab7:
    st.markdown("# ➕ Neuer Lead")
    with st.form("new_lead_v7"):
        c1,c2 = st.columns(2)
        with c1:
            company = st.text_input("Unternehmen *")
            region = st.selectbox("Region", ["DE","CH","UK","UAE","NORDICS"])
            industry = st.selectbox("Industrie", ["Institutional","Asset Management","Bank","Insurance","Family Office","Pension Fund","Foundation","Custodian","Hedge Fund","Real Estate","Other"])
            aum = st.number_input("AUM (Mio €)", min_value=0.0, value=0.0)
        with c2:
            contact = st.text_input("Kontakt")
            title = st.text_input("Titel")
            email = st.text_input("Email")
            linkedin = st.text_input("LinkedIn URL")
        c3,c4 = st.columns(2)
        with c3:
            stage = st.selectbox("Stage", ["prospecting","discovery","solutioning","validation","negotiation"])
            tier = st.selectbox("Tier", [1,2,3,4])
        with c4:
            deal_size = st.number_input("Deal Size (Mio €)", min_value=0.0, value=0.0)
            notes = st.text_area("Notizen", height=80)
        if st.form_submit_button("✅ Lead erstellen", type="primary"):
            if company and sb:
                try:
                    resp = sb.table("leads").insert({
                        "company":company,"region":region,"tier":tier,
                        "contact_person":contact,"title":title,
                        "email":email or None,"linkedin":linkedin or None,
                        "stage":stage,"industry":industry,
                        "use_case":notes or "ETH Staking | Manual Entry",
                        "aum_estimate_millions":aum,
                        "expected_deal_size_millions":deal_size,
                        "staking_readiness":"Unknown"
                    }).execute()
                    new_id = resp.data[0]["id"]
                    sb.table("meddpicc_scores").insert({"lead_id":new_id,"total_score":0,"qualification_status":"UNQUALIFIED"}).execute()
                    st.success(f"✅ **{company}** erstellt!")
                    st.cache_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Fehler: {e}")
            else:
                st.error("Unternehmen ist erforderlich")

# ══════════════════════════════════════════════════════════════
# TAB 8: PIPO CHAT
# ══════════════════════════════════════════════════════════════
with tab8:
    st.markdown("""
    <div class='bw-header'>
        <div>
            <div class='bw-logo'><span>■</span> Pipo</div>
            <div class='bw-subtitle'>Dein autonomer Pre-Sales Chief of Staff</div>
        </div>
        <div class='bw-date'>
            <span style='color:#22c55e;font-size:0.75rem;'>● Claude-Haiku</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Quick Action Prompts ──────────────────────────────────
    st.markdown("<div style='margin-bottom:0.75rem;font-size:0.7rem;color:#4a6080;text-transform:uppercase;letter-spacing:0.1em;'>Quick Actions</div>", unsafe_allow_html=True)
    qa_cols = st.columns(4)
    quick_actions = [
        ("🎯 Top 5 Leads heute", "Welche 5 Leads sollte ich heute zuerst kontaktieren? Begründe kurz mit MEDDPICC und Inaktivität."),
        ("✉️ Email-Draft DE", "Schreib mir einen kurzen Cold-Email-Draft auf Deutsch für einen deutschen Asset Manager mit >1B AUM, der ETH noch nicht stakt. Spezifisch, kein Buzzword-Bingo."),
        ("📊 Pipeline-Check", "Wie sieht meine aktuelle Pipeline aus? Was sind die größten Risiken und wo muss ich diese Woche handeln?"),
        ("⚔️ Einwand-Coaching", "Ich habe gleich ein Call mit einem Prospect der sagt 'Wir machen Staking lieber selbst in-house'. Wie antworte ich als Bitwise BOS?"),
    ]
    for i, (label, prompt) in enumerate(quick_actions):
        with qa_cols[i]:
            if st.button(label, key=f"qa_{i}", use_container_width=True):
                st.session_state.pipo_input = prompt

    st.markdown("<div style='margin:0.75rem 0;'></div>", unsafe_allow_html=True)

    # ── Chat History ──────────────────────────────────────────
    if "pipo_messages" not in st.session_state:
        st.session_state.pipo_messages = []

    # Display chat history
    chat_container = st.container()
    with chat_container:
        if not st.session_state.pipo_messages:
            st.markdown("""
            <div style='background:#0f1c2e;border:1px solid rgba(255,255,255,0.06);border-radius:8px;
                        padding:1.5rem;text-align:center;color:#4a6080;margin-bottom:1rem;'>
                <div style='font-family:Cormorant Garamond,serif;font-size:1.1rem;color:#6b8ab0;font-style:italic;margin-bottom:0.5rem;'>
                    Bereit für deinen nächsten Deal.
                </div>
                <div style='font-size:0.75rem;'>
                    Frag mich zu Leads, Email-Drafts, Einwand-Coaching oder Pipeline-Strategie.
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            for msg in st.session_state.pipo_messages:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    st.markdown(f"""
                    <div style='display:flex;justify-content:flex-end;margin-bottom:0.75rem;'>
                        <div style='background:#0c1a3a;border:1px solid rgba(99,102,241,0.25);border-radius:8px 8px 2px 8px;
                                    padding:0.75rem 1rem;max-width:80%;font-size:0.875rem;color:#c8d4e8;'>
                            {content}
                        </div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style='display:flex;justify-content:flex-start;margin-bottom:0.75rem;'>
                        <div style='background:#0f1c2e;border:1px solid rgba(34,197,94,0.15);border-radius:8px 8px 8px 2px;
                                    padding:0.75rem 1rem;max-width:85%;font-size:0.875rem;color:#d4dbe8;line-height:1.6;'>
                            <span style='font-size:0.65rem;color:#22c55e;text-transform:uppercase;letter-spacing:0.1em;
                                         font-family:Inter,sans-serif;display:block;margin-bottom:0.4rem;'>■ Pipo</span>
                            {content.replace(chr(10), "<br>")}
                        </div>
                    </div>""", unsafe_allow_html=True)

    # ── Input ─────────────────────────────────────────────────
    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
    col_inp, col_send, col_clear = st.columns([8, 1, 1])
    with col_inp:
        default_val = st.session_state.pop("pipo_input", "")
        user_input = st.text_input(
            "Nachricht",
            value=default_val,
            placeholder="Frag Pipo — Leads, Emails, Strategie, Einwände...",
            label_visibility="collapsed",
            key="pipo_text_input"
        )
    with col_send:
        send_btn = st.button("→", type="primary", use_container_width=True, key="pipo_send")
    with col_clear:
        if st.button("✕", use_container_width=True, key="pipo_clear"):
            st.session_state.pipo_messages = []
            st.rerun()

    if (send_btn or (user_input and user_input.endswith("\n"))) and user_input.strip():
        user_msg = user_input.strip()
        st.session_state.pipo_messages.append({"role": "user", "content": user_msg})
        with st.spinner("Pipo denkt..."):
            reply = pipo_chat(
                [{"role": m["role"], "content": m["content"]} for m in st.session_state.pipo_messages],
                stats
            )
        st.session_state.pipo_messages.append({"role": "assistant", "content": reply})
        st.rerun()

    # ── Context Info ──────────────────────────────────────────
    with st.expander("ℹ️ Pipo's Kontext", expanded=False):
        st.markdown(f"""
        **Live Datenbank:**
        - {stats.get('total', 0):,} Leads total
        - {stats.get('qualified', 0)} qualifiziert (MEDDPICC ≥60)
        - €{stats.get('pipeline', 0):.0f}M Pipeline
        - {stats.get('stale', 0)} inaktiv >7 Tage

        **Bitwise Kernfakten:**
        - $15B+ AUM | 40+ Produkte | 4.000+ institutionelle Clients
        - BOS: ~$5B ETH gestaked | Zero Slashings seit Genesis (Sep 2022)
        - Uptime 2025: 99.984% | APR: 3.170% (+0.155% vs Benchmark)
        - MiCA-konform | Institutional-grade Reporting

        **Philipps Fokus:** EMEA (DE > CH > UAE > UK > NORDICS)
        """)
    if not (st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        st.warning("⚠️ **ANTHROPIC_API_KEY** nicht gesetzt. Bitte in Streamlit Cloud → App Settings → Secrets hinzufügen: `ANTHROPIC_API_KEY = \"sk-ant-...\"`")

    st.markdown("---")

    # ── Pipo Evaluate Status ──────────────────────────────────
    st.markdown("### 🔍 Pipo Lead-Evaluierung")
    st.markdown("<div style='font-size:0.8rem;color:#4a6080;margin-bottom:1rem;'>Pipo bewertet alle Leads automatisch mit geschätzten MEDDPICC-Scores basierend auf Titel, Industry, Region und AUM. Das Script läuft auf deinem Mac mini.</div>", unsafe_allow_html=True)

    if not df.empty:
        scored_count = int((df["meddpicc"] > 0).sum())
        unscored_count = int((df["meddpicc"] == 0).sum())
        total_count = len(df)
        pct = int(scored_count / total_count * 100) if total_count > 0 else 0

        ec1, ec2, ec3 = st.columns(3)
        ec1.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#22c55e;font-size:1.5rem;'>{scored_count:,}</div><div class='metric-lbl'>Gescored</div></div>", unsafe_allow_html=True)
        ec2.markdown(f"<div class='metric-card alert'><div class='metric-val' style='color:#ef4444;font-size:1.5rem;'>{unscored_count:,}</div><div class='metric-lbl'>Unbewertet</div></div>", unsafe_allow_html=True)
        ec3.markdown(f"<div class='metric-card purple'><div class='metric-val' style='color:#6366f1;font-size:1.5rem;'>{pct}%</div><div class='metric-lbl'>Coverage</div></div>", unsafe_allow_html=True)

        # Progress bar
        st.markdown(f"""
        <div style='margin:1rem 0 0.25rem;font-size:0.65rem;color:#4a6080;text-transform:uppercase;letter-spacing:0.1em;'>Evaluierungs-Fortschritt</div>
        <div style='background:#0a1624;border-radius:4px;height:8px;overflow:hidden;border:1px solid rgba(255,255,255,0.06);'>
            <div style='background:linear-gradient(90deg,#22c55e,#6366f1);height:100%;width:{pct}%;border-radius:4px;transition:width 0.5s;'></div>
        </div>
        <div style='font-size:0.7rem;color:#4a6080;margin-top:4px;'>{scored_count:,} von {total_count:,} Leads bewertet</div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:1.25rem;'></div>", unsafe_allow_html=True)

        # Command to run
        with st.expander("▶ Script starten (auf Mac mini)", expanded=unscored_count > 0):
            st.markdown("**1. Environment vorbereiten:**")
            st.code("""export SUPABASE_URL="https://cxrhqzggukuqxpsausrd.supabase.co"
export SUPABASE_KEY="dein-anon-key"
export ANTHROPIC_API_KEY="sk-ant-..."
""", language="bash")
            st.markdown("**2. Alle ungescoredeten Leads bewerten:**")
            st.code("cd ~/openclaw/workspace/bitwise/leadtracker\npython3 pipo_evaluate.py", language="bash")

            st.markdown("**Optionen:**")
            st.code("""# Nur Deutschland:
python3 pipo_evaluate.py --region DE

# Nur erste 50 testen:
python3 pipo_evaluate.py --limit 50

# Dry-Run (nichts speichern):
python3 pipo_evaluate.py --dry-run

# Alle neu bewerten (auch bestehende):
python3 pipo_evaluate.py --force
""", language="bash")

            st.markdown(f"**Schätzung:** {unscored_count:,} Leads × {BATCH_SIZE if False else 20} Leads/Batch = ~{unscored_count//20 + 1} API-Calls — ca. **{unscored_count * 0.001:.1f}–{unscored_count * 0.003:.1f} USD** (Haiku-Preise)")

    # Qualification breakdown (only scored)
    scored_df = df[df["meddpicc"] > 0] if not df.empty else pd.DataFrame()
    if not scored_df.empty:
        st.markdown("<div style='margin-top:1rem;font-size:0.7rem;color:#4a6080;text-transform:uppercase;letter-spacing:0.1em;'>Ergebnis der bewerteten Leads</div>", unsafe_allow_html=True)
        ql_counts = scored_df["qualification"].value_counts()
        qcols = st.columns(4)
        ql_config = [
            ("QUALIFIED",   "#22c55e", "✅"),
            ("PROBABLE",    "#6366f1", "🔵"),
            ("POSSIBLE",    "#d4a660", "🟡"),
            ("UNQUALIFIED", "#4a6080", "⚪"),
        ]
        for col, (ql, color, icon) in zip(qcols, ql_config):
            cnt = ql_counts.get(ql, 0)
            pct_ql = int(cnt / len(scored_df) * 100) if len(scored_df) > 0 else 0
            col.markdown(f"""<div class='metric-card' style='border-top-color:{color};'>
                <div class='metric-val' style='color:{color};font-size:1.35rem;'>{cnt:,}</div>
                <div class='metric-lbl'>{icon} {ql} ({pct_ql}%)</div>
            </div>""", unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='bw-footer'>
    StakeStream · Bitwise Onchain Solutions · EMEA · Powered by Pipo
</div>""", unsafe_allow_html=True)
