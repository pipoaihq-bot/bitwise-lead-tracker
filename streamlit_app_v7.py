"""
StakeStream Command Center v7
Bitwise EMEA | Lead Tracker
Supabase Cloud DB — Mobile-first, kein Tunnel, kein VPN
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
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
    except: return pd.DataFrame()

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏠 Dashboard", "🚨 Prioritäten", "📊 Pipeline",
    "✅ Tasks", "📥 Import", "⚙️ MEDDPICC", "➕ Neuer Lead"
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
        c1, c2, c3, c4 = st.columns(4)
        cards = [
            (c1, f"{stats['total']:,}", "Leads gesamt",  "#22c55e", ""),
            (c2, str(stats['qualified']), "Qualifiziert", "#6366f1", "purple"),
            (c3, str(stats['stale']),     "Inaktiv >7T",  "#ef4444" if stats['stale'] > 0 else "#4a6080", "alert" if stats['stale'] > 0 else ""),
            (c4, f"€{stats['pipeline']:.0f}M", "Pipeline", "#22c55e", ""),
        ]
        for col, val, label, color, cls in cards:
            with col:
                st.markdown(f"""<div class="metric-card {cls}">
                    <div class="metric-val" style="color:{color};">{val}</div>
                    <div class="metric-lbl">{label}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # Critical Alerts
        active = df[~df["stage"].isin(["closed_won", "closed_lost"])]
        hot = active[(active["meddpicc"] >= 50) & (active["days_inactive"] >= 3)].sort_values(
            ["meddpicc", "days_inactive"], ascending=[False, False]).head(3)

        if not hot.empty:
            st.markdown("### 🔥 Sofort-Prioritäten")
            for _, r in hot.iterrows():
                _, qc = qualify(int(r["meddpicc"]))
                st.markdown(f"""
                <div class="alert-card">
                    <div class="alert-title">{r['company']} <span class="score-badge {qc}">{int(r['meddpicc'])}/80</span></div>
                    <div class="alert-sub">👤 {r.get('contact_person') or 'N/A'} | {r['region']} | {r['stage']} | {int(r['days_inactive'])} Tage inaktiv</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Leads nach Region")
            reg = df.groupby("region").size().reset_index(name="Count")
            fig = px.pie(reg, values="Count", names="region",
                         color_discrete_sequence=["#22c55e","#6366f1","#06b6d4","#a78bfa","#d4a660","#3b82f6","#f87171"], hole=0.55)
            fig.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)", font_color="#d4dbe8",
                              legend=dict(orientation="h", y=-0.3, font_size=10, font_color="#4a6080"),
                              margin=dict(t=10, b=50, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### MEDDPICC Verteilung")
            order = ["QUALIFIED","PROBABLE","POSSIBLE","UNQUALIFIED"]
            qc = df["qualification"].value_counts()
            fig = go.Figure(go.Bar(
                x=order, y=[qc.get(o, 0) for o in order],
                marker_color=["#22c55e","#6366f1","#d4a660","#1e3050"],
                text=[qc.get(o, 0) for o in order], textposition="outside",
                textfont=dict(color="#e5e5e5")
            ))
            fig.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", font_color="#d4dbe8",
                              showlegend=False,
                              xaxis=dict(showgrid=False, tickfont_size=11),
                              yaxis=dict(showgrid=True, gridcolor="#2a2a2a"),
                              margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("### Zuletzt hinzugefügt")
        for _, r in df.head(8).iterrows():
            _, qc = qualify(int(r["meddpicc"]))
            li = f"<a href='{r['linkedin']}' target='_blank' style='color:#3b82f6;font-size:0.75rem;'>LinkedIn →</a>" if r.get("linkedin") else ""
            st.markdown(f"""
            <div class="lead-row">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div class="lead-company">{r['company']}</div>
                        <div class="lead-meta">{r['region']} • {r['industry']} • {r['stage']} {li}</div>
                    </div>
                    <span class="score-badge {qc}">{int(r['meddpicc'])}/80</span>
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
# TAB 3: PIPELINE
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown("# 📊 Pipeline")
    if df.empty:
        st.info("Keine Daten.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            sel_region = st.selectbox("Region", ["Alle"] + sorted(df["region"].unique().tolist()))
        with c2:
            sel_stage = st.selectbox("Stage", ["Alle"] + sorted(df["stage"].unique().tolist()))
        c3, c4 = st.columns(2)
        with c3:
            min_medd = st.slider("Min. MEDDPICC", 0, 80, 0)
        with c4:
            act_filter = st.selectbox("Aktivität", ["Alle","Aktiv (<3T)","Warm (3-7T)","Inaktiv (>7T)"])

        filt = df.copy()
        if sel_region != "Alle": filt = filt[filt["region"] == sel_region]
        if sel_stage != "Alle": filt = filt[filt["stage"] == sel_stage]
        if min_medd > 0: filt = filt[filt["meddpicc"] >= min_medd]
        if act_filter == "Aktiv (<3T)": filt = filt[filt["days_inactive"] < 3]
        elif act_filter == "Warm (3-7T)": filt = filt[(filt["days_inactive"] >= 3) & (filt["days_inactive"] <= 7)]
        elif act_filter == "Inaktiv (>7T)": filt = filt[filt["days_inactive"] > 7]

        st.markdown(f"**{len(filt):,} Leads** | Pipeline: **€{filt['deal_size'].sum():.0f}M**")
        st.markdown("---")

        for _, r in filt.head(50).iterrows():
            _, qc = qualify(int(r["meddpicc"]))
            li = f"<a href='{r['linkedin']}' target='_blank' style='color:#3b82f6;font-size:0.75rem;'>LinkedIn →</a>" if r.get("linkedin") else ""
            st.markdown(f"""
            <div class="lead-row">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div>
                        <div class="lead-company">{r['company']}</div>
                        <div class="lead-meta">{r.get('contact_person') or ''}{' | ' if r.get('contact_person') else ''}{r.get('title') or ''}</div>
                        <div class="lead-meta">{r['region']} • {r['industry']} • {r['stage']} {li}</div>
                    </div>
                    <div style="text-align:right;">
                        <span class="score-badge {qc}">{int(r['meddpicc'])}/80</span><br>
                        <span style="display:inline-block;margin-top:0.25rem;">{activity_pill(int(r['days_inactive']))}</span>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

        if len(filt) > 50:
            st.caption(f"... {len(filt)-50} weitere. Filter nutzen zum Einschränken.")

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
