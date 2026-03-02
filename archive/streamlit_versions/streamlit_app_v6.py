"""
StakeStream Command Center v6
Bitwise EMEA | Lead Tracker
Mobile-first, Bug-free, Production-ready
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import sqlite3
from datetime import datetime, timedelta

# ── Path Setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Page Config (must be first Streamlit call) ──────────────────────────────────
st.set_page_config(
    page_title="StakeStream | Bitwise EMEA",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",   # collapsed by default on mobile
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': 'StakeStream — Bitwise EMEA Command Center'
    }
)

# ── Mobile-first CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
.stApp { background: #0f0f0f; color: #e5e5e5; }

/* ── Typography ── */
h1, h2, h3 { color: #ffffff; letter-spacing: -0.02em; }
h1 { font-size: clamp(1.4rem, 5vw, 2rem); font-weight: 600; margin-bottom: 1rem; }
h2 { font-size: clamp(1rem, 4vw, 1.25rem); font-weight: 500; margin-top: 1.5rem; }
h3 { font-size: clamp(0.875rem, 3vw, 1rem); font-weight: 500; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #1a1a1a;
    border-right: 1px solid #2a2a2a;
}
section[data-testid="stSidebar"] .stMarkdown { color: #a3a3a3; }

/* ── Cards ── */
.metric-card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
    margin-bottom: 0.5rem;
}
.metric-card:hover { border-color: #3b82f6; }
.metric-val { font-size: clamp(1.5rem, 6vw, 2rem); font-weight: 700; color: #fff; }
.metric-lbl { font-size: 0.75rem; color: #737373; margin-top: 0.125rem; text-transform: uppercase; letter-spacing: 0.05em; }

/* ── Alert Cards ── */
.alert-card {
    background: #1a1a1a;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    border-left: 4px solid #ef4444;
}
.alert-card.warning { border-left-color: #f59e0b; }
.alert-card.info { border-left-color: #3b82f6; }
.alert-title { font-size: 1rem; font-weight: 600; color: #fff; }
.alert-sub { font-size: 0.8125rem; color: #a3a3a3; margin-top: 0.25rem; }

/* ── Lead Row ── */
.lead-row {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 0.875rem 1rem;
    margin-bottom: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.lead-row:hover { border-color: #3b82f6; }
.lead-company { font-weight: 600; font-size: 0.9375rem; }
.lead-meta { font-size: 0.75rem; color: #737373; margin-top: 0.125rem; }
.score-badge {
    background: #2a2a2a;
    border-radius: 6px;
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: #e5e5e5;
    white-space: nowrap;
}
.score-badge.qualified { background: #166534; color: #86efac; }
.score-badge.probable { background: #1e3a8a; color: #93c5fd; }
.score-badge.possible { background: #713f12; color: #fde68a; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.15s !important;
}
.stButton > button[kind="primary"] {
    background: #3b82f6 !important;
    color: white !important;
    border: none !important;
}
.stButton > button[kind="primary"]:hover { background: #2563eb !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #1a1a1a;
    border-radius: 8px;
    padding: 4px;
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #737373 !important;
    border-radius: 6px !important;
    font-size: clamp(0.75rem, 2.5vw, 0.875rem) !important;
    padding: 0.4rem 0.75rem !important;
}
.stTabs [aria-selected="true"] {
    background: #2a2a2a !important;
    color: #fff !important;
}

/* ── DataFrames ── */
.stDataFrame { border: 1px solid #2a2a2a !important; border-radius: 8px !important; }
.stDataFrame thead th { background: #1a1a1a !important; color: #a3a3a3 !important; }
.stDataFrame tbody td { background: #0f0f0f !important; color: #e5e5e5 !important; }

/* ── Inputs ── */
.stTextInput input, .stSelectbox select, .stTextArea textarea {
    background: #1a1a1a !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 8px !important;
    color: #e5e5e5 !important;
}
.stTextInput input:focus { border-color: #3b82f6 !important; }

/* ── Mobile-specific adjustments ── */
@media (max-width: 768px) {
    .main .block-container { padding: 0.75rem !important; }
    .stColumns { gap: 0.5rem !important; }
    .metric-card { padding: 0.75rem; }
    h1 { margin-bottom: 0.75rem; }
}

/* ── Navigation Tabs ── */
.nav-tab {
    display: inline-block;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    background: #1a1a1a;
    color: #a3a3a3;
    border: 1px solid #2a2a2a;
    text-decoration: none;
    margin: 0.25rem;
}
.nav-tab.active {
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
}

/* ── Status Pills ── */
.pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.6875rem;
    font-weight: 600;
}
.pill-green { background: #166534; color: #86efac; }
.pill-yellow { background: #713f12; color: #fde68a; }
.pill-red { background: #7f1d1d; color: #fca5a5; }
.pill-gray { background: #2a2a2a; color: #a3a3a3; }

/* ── Selectbox dark ── */
.stSelectbox > div > div {
    background: #1a1a1a !important;
    border-color: #2a2a2a !important;
    color: #e5e5e5 !important;
}

/* ── Slider dark ── */
.stSlider > div > div > div { background: #3b82f6 !important; }

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #1a1a1a !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 8px !important;
    color: #e5e5e5 !important;
}

/* ── Hide streamlit watermark ── */
footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }

/* ── Divider ── */
hr { border-color: #2a2a2a !important; margin: 1rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Database Connection ─────────────────────────────────────────────────────────

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "bitwise_leads.db")
)


def get_conn():
    """Get SQLite connection with Row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_leads_df() -> pd.DataFrame:
    """Load all leads with MEDDPICC scores into DataFrame"""
    try:
        with get_conn() as conn:
            df = pd.read_sql_query("""
                SELECT
                    l.id,
                    l.company,
                    l.region,
                    l.tier,
                    l.contact_person,
                    l.title,
                    l.email,
                    l.linkedin,
                    l.stage,
                    l.industry,
                    l.staking_readiness,
                    l.expected_deal_size_millions as deal_size,
                    l.aum_estimate_millions as aum,
                    l.use_case,
                    COALESCE(l.updated_at, l.created_at) as last_update,
                    COALESCE(
                        m.metrics + m.economic_buyer + m.decision_process +
                        m.decision_criteria + m.paper_process + m.pain +
                        m.champion + m.competition, 0
                    ) as meddpicc,
                    COALESCE(m.metrics, 0) as m_metrics,
                    COALESCE(m.economic_buyer, 0) as m_economic,
                    COALESCE(m.decision_process, 0) as m_process,
                    COALESCE(m.decision_criteria, 0) as m_criteria,
                    COALESCE(m.paper_process, 0) as m_paper,
                    COALESCE(m.pain, 0) as m_pain,
                    COALESCE(m.champion, 0) as m_champion,
                    COALESCE(m.competition, 0) as m_competition
                FROM leads l
                LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
                ORDER BY l.id DESC
            """, conn)
            return df
    except Exception as e:
        st.error(f"DB Fehler: {e}")
        return pd.DataFrame()


def get_tasks_df() -> pd.DataFrame:
    """Load tasks"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query(
                "SELECT * FROM tasks ORDER BY priority ASC, created_at DESC", conn
            )
    except:
        return pd.DataFrame()


def qualify(score: int) -> tuple:
    """Return (label, css_class) for MEDDPICC score"""
    if score >= 70:
        return "QUALIFIED", "qualified"
    if score >= 50:
        return "PROBABLE", "probable"
    if score >= 30:
        return "POSSIBLE", "possible"
    return "UNQUALIFIED", "unqualified"


def days_ago(dt_str) -> int:
    """Parse datetime string and return days since"""
    if not dt_str:
        return 999
    try:
        dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        return max(0, (datetime.now() - dt.replace(tzinfo=None)).days)
    except:
        return 999


def activity_pill(days: int) -> str:
    if days <= 2:
        return "<span class='pill pill-green'>Aktiv</span>"
    if days <= 7:
        return f"<span class='pill pill-yellow'>{days}d</span>"
    return f"<span class='pill pill-red'>{days}d 🚨</span>"


# ── Load Data ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)   # Cache 60 seconds — refreshes each minute
def load_data():
    df = get_leads_df()
    if df.empty:
        return df, {}

    df['days_inactive'] = df['last_update'].apply(days_ago)
    df['qualification'] = df['meddpicc'].apply(lambda s: qualify(s)[0])
    df['qual_class'] = df['meddpicc'].apply(lambda s: qualify(s)[1])
    df['region_str'] = df['region'].apply(lambda r: r.replace("Region.", "").replace("<", ""))
    df['stage_str'] = df['stage'].apply(lambda s: s.replace("Stage.", ""))

    active = df[~df['stage_str'].isin(['closed_won', 'closed_lost'])]
    stats = {
        'total': len(df),
        'qualified': int((active['meddpicc'] >= 50).sum()),
        'stale': int((active['days_inactive'] >= 7).sum()),
        'critical': int(((active['meddpicc'] >= 60) & (active['days_inactive'] >= 3)).sum()),
        'pipeline': float(active['deal_size'].fillna(0).sum()),
        'regions': df.groupby('region_str').size().to_dict(),
    }
    return df, stats


df, stats = load_data()

# ── Navigation ───────────────────────────────────────────────────────────────────
# Use tabs as main navigation (works well on mobile)
PAGES = ["🏠 Dashboard", "🚨 Prioritäten", "📊 Pipeline", "✅ Tasks", "📥 Import", "⚙️ MEDDPICC", "➕ Neuer Lead"]

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(PAGES)

# ── HEADER ── (shown on all pages via sidebar)
with st.sidebar:
    st.markdown("## ◆ StakeStream")
    st.markdown("<span style='color:#737373;font-size:0.8125rem;'>Bitwise EMEA Command Center</span>", unsafe_allow_html=True)
    st.markdown("---")

    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div style='font-size:1.5rem;font-weight:700;'>{stats['total']:,}</div><div style='font-size:0.75rem;color:#737373;'>Leads</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div style='font-size:1.5rem;font-weight:700;'>€{stats['pipeline']:.0f}M</div><div style='font-size:0.75rem;color:#737373;'>Pipeline</div>", unsafe_allow_html=True)

        if stats['critical'] > 0:
            st.markdown(f"<div style='background:#7f1d1d;color:#fca5a5;padding:0.4rem 0.75rem;border-radius:8px;font-size:0.8125rem;margin-top:0.5rem;font-weight:600;'>🚨 {stats['critical']} Dringend</div>", unsafe_allow_html=True)
        if stats['stale'] > 0:
            st.markdown(f"<div style='background:#713f12;color:#fde68a;padding:0.4rem 0.75rem;border-radius:8px;font-size:0.8125rem;margin-top:0.25rem;font-weight:600;'>😴 {stats['stale']} Inaktiv</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"<span style='color:#3a3a3a;font-size:0.75rem;'>v6.0 • {datetime.now().strftime('%d.%m.%Y %H:%M')}</span>", unsafe_allow_html=True)

    if st.button("🔄 Aktualisieren"):
        st.cache_data.clear()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("# ◆ StakeStream")
    st.markdown(f"<span style='color:#737373;'>Bitwise EMEA • {datetime.now().strftime('%a, %d. %b %Y')}</span>", unsafe_allow_html=True)

    if df.empty:
        st.warning("Keine Daten geladen. Gehe zu **Import** um Leads hinzuzufügen.")
    else:
        # ── KPI Row ──
        c1, c2, c3, c4 = st.columns(4)
        for col, val, label, highlight in [
            (c1, f"{stats['total']:,}", "Leads gesamt", False),
            (c2, str(stats['qualified']), "Qualifiziert", False),
            (c3, f"⚠️ {stats['stale']}" if stats['stale'] else "0", "Inaktiv >7T", stats['stale'] > 0),
            (c4, f"€{stats['pipeline']:.0f}M", "Pipeline", False),
        ]:
            color = "#ef4444" if highlight else "#fff"
            with col:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-val" style="color:{color};">{val}</div>
                    <div class="metric-lbl">{label}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # ── Critical Alerts (top 3) ──
        active = df[~df['stage_str'].isin(['closed_won', 'closed_lost'])]
        hot = active[(active['meddpicc'] >= 50) & (active['days_inactive'] >= 3)].sort_values(
            ['meddpicc', 'days_inactive'], ascending=[False, False]
        ).head(3)

        if not hot.empty:
            st.markdown("### 🔥 Sofort-Prioritäten")
            for _, r in hot.iterrows():
                qual_label, qual_class = qualify(int(r['meddpicc']))
                card_class = "alert-card" if int(r['days_inactive']) >= 7 else "alert-card warning"
                st.markdown(f"""
                <div class="{card_class}">
                    <div class="alert-title">{r['company']} <span class="score-badge {qual_class}">{int(r['meddpicc'])}/80</span></div>
                    <div class="alert-sub">
                        👤 {r['contact_person'] or 'N/A'} | {r['region_str']} | {r['stage_str']} | inaktiv seit {int(r['days_inactive'])} Tagen
                    </div>
                </div>""", unsafe_allow_html=True)

        # ── Charts ──
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Leads nach Region")
            reg = df.groupby('region_str').size().reset_index(name='Count')
            colors = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b']
            fig = px.pie(reg, values='Count', names='region_str',
                         color_discrete_sequence=colors, hole=0.5)
            fig.update_layout(
                height=260, paper_bgcolor='rgba(0,0,0,0)',
                font_color='#e5e5e5', showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, font_size=11),
                margin=dict(t=10, b=50, l=10, r=10)
            )
            fig.update_traces(textfont_color='white')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### MEDDPICC Verteilung")
            q_counts = df['qualification'].value_counts()
            order = ['QUALIFIED', 'PROBABLE', 'POSSIBLE', 'UNQUALIFIED']
            vals = [q_counts.get(o, 0) for o in order]
            colors_bar = ['#86efac', '#93c5fd', '#fde68a', '#525252']
            fig = go.Figure(go.Bar(
                x=order, y=vals,
                marker_color=colors_bar,
                text=vals, textposition='outside',
                textfont=dict(color='#e5e5e5')
            ))
            fig.update_layout(
                height=260, paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#e5e5e5', showlegend=False,
                xaxis=dict(showgrid=False, tickfont_size=11),
                yaxis=dict(showgrid=True, gridcolor='#2a2a2a'),
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Recent Leads ──
        st.markdown("---")
        st.markdown("### Zuletzt hinzugefügt")
        recent = df.head(8)
        for _, r in recent.iterrows():
            qual_label, qual_class = qualify(int(r['meddpicc']))
            st.markdown(f"""
            <div class="lead-row">
                <div>
                    <div class="lead-company">{r['company']}</div>
                    <div class="lead-meta">{r['region_str']} • {r['industry'] or 'Institutional'} • {r['stage_str']}</div>
                </div>
                <div>
                    <span class="score-badge {qual_class}">{int(r['meddpicc'])}/80</span>
                </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: PRIORITÄTEN
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("# 🚨 Prioritäten")

    if df.empty:
        st.info("Keine Daten.")
    else:
        active = df[~df['stage_str'].isin(['closed_won', 'closed_lost'])]

        st.markdown("### 🔥 Kritisch — Qualifiziert & Inaktiv")
        critical = active[
            (active['meddpicc'] >= 60) & (active['days_inactive'] >= 3)
        ].sort_values(['meddpicc', 'days_inactive'], ascending=[False, False])

        if critical.empty:
            st.success("✅ Keine kritischen Leads!")
        else:
            for _, r in critical.iterrows():
                qual_label, qual_class = qualify(int(r['meddpicc']))
                st.markdown(f"""
                <div class="alert-card">
                    <div class="alert-title">🔥 {r['company']} ({r['region_str']})</div>
                    <div class="alert-sub">👤 {r['contact_person'] or 'N/A'} | {r['title'] or ''} | {r['stage_str']}</div>
                    <div style="margin-top:0.5rem;display:flex;gap:0.5rem;align-items:center;">
                        <span class="score-badge {qual_class}">{int(r['meddpicc'])}/80 {qual_label}</span>
                        <span style="color:#a3a3a3;font-size:0.75rem;">Inaktiv seit {int(r['days_inactive'])} Tagen</span>
                    </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 😴 Schlummernde Deals (MEDDPICC ≥50, >7 Tage)")
        stale = active[
            (active['meddpicc'] >= 50) & (active['days_inactive'] >= 7)
        ].sort_values('days_inactive', ascending=False)

        if stale.empty:
            st.info("Keine schlummernden Deals!")
        else:
            for _, r in stale.iterrows():
                qual_label, qual_class = qualify(int(r['meddpicc']))
                st.markdown(f"""
                <div class="alert-card warning">
                    <div class="alert-title">⚠️ {r['company']} ({r['region_str']})</div>
                    <div class="alert-sub">👤 {r['contact_person'] or 'N/A'} | {r['stage_str']}</div>
                    <div style="margin-top:0.5rem;display:flex;gap:0.5rem;">
                        <span class="score-badge {qual_class}">{int(r['meddpicc'])}/80</span>
                        <span style="color:#a3a3a3;font-size:0.75rem;">{int(r['days_inactive'])} Tage inaktiv</span>
                    </div>
                </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("# 📊 Pipeline")

    if df.empty:
        st.info("Keine Daten.")
    else:
        # ── Filters (mobile-friendly) ──
        col1, col2 = st.columns(2)
        with col1:
            region_opts = ["Alle"] + sorted(df['region_str'].unique().tolist())
            sel_region = st.selectbox("Region", region_opts)
        with col2:
            stage_opts = ["Alle"] + sorted(df['stage_str'].unique().tolist())
            sel_stage = st.selectbox("Stage", stage_opts)

        col3, col4 = st.columns(2)
        with col3:
            min_medd = st.slider("Min. MEDDPICC", 0, 80, 0)
        with col4:
            show_filter = st.selectbox("Aktivität", ["Alle", "Aktiv (<3T)", "Warm (3-7T)", "Inaktiv (>7T)"])

        # Apply filters
        filtered = df.copy()
        if sel_region != "Alle":
            filtered = filtered[filtered['region_str'] == sel_region]
        if sel_stage != "Alle":
            filtered = filtered[filtered['stage_str'] == sel_stage]
        if min_medd > 0:
            filtered = filtered[filtered['meddpicc'] >= min_medd]
        if show_filter == "Aktiv (<3T)":
            filtered = filtered[filtered['days_inactive'] < 3]
        elif show_filter == "Warm (3-7T)":
            filtered = filtered[(filtered['days_inactive'] >= 3) & (filtered['days_inactive'] <= 7)]
        elif show_filter == "Inaktiv (>7T)":
            filtered = filtered[filtered['days_inactive'] > 7]

        st.markdown(f"**{len(filtered):,} von {len(df):,} Leads** | Pipeline: **€{filtered['deal_size'].fillna(0).sum():.0f}M**")
        st.markdown("---")

        # ── Lead Cards (Mobile) ──
        for _, r in filtered.head(50).iterrows():  # limit for performance
            qual_label, qual_class = qualify(int(r['meddpicc']))
            days = int(r['days_inactive'])
            act_html = activity_pill(days)

            linkedin_btn = f"<a href='{r['linkedin']}' target='_blank' style='color:#3b82f6;font-size:0.75rem;'>LinkedIn →</a>" if r['linkedin'] else ""

            st.markdown(f"""
            <div class="lead-row" style="display:block;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div>
                        <div class="lead-company">{r['company']}</div>
                        <div class="lead-meta">{r['contact_person'] or ''}{' | ' if r['contact_person'] else ''}{r['title'] or ''}</div>
                        <div class="lead-meta">{r['region_str']} • {r['industry'] or 'Institutional'} • {r['stage_str']}</div>
                    </div>
                    <div style="text-align:right;">
                        <span class="score-badge {qual_class}">{int(r['meddpicc'])}/80</span><br>
                        <span style="margin-top:0.25rem;display:inline-block;">{act_html}</span>
                    </div>
                </div>
                {f'<div style="margin-top:0.375rem;">{linkedin_btn}</div>' if linkedin_btn else ''}
            </div>""", unsafe_allow_html=True)

        if len(filtered) > 50:
            st.caption(f"... {len(filtered) - 50} weitere Leads. Nutze Filter zum Einschränken.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: TASKS
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("# ✅ Tasks")

    tasks_df = get_tasks_df()

    if tasks_df.empty:
        st.info("Keine Tasks vorhanden.")
    else:
        todo_df = tasks_df[tasks_df['status'] == 'todo'] if 'status' in tasks_df.columns else pd.DataFrame()
        inprog_df = tasks_df[tasks_df['status'] == 'in_progress'] if 'status' in tasks_df.columns else pd.DataFrame()
        done_df = tasks_df[tasks_df['status'] == 'done'] if 'status' in tasks_df.columns else pd.DataFrame()

        c1, c2, c3, c4 = st.columns(4)
        for col, val, label in [
            (c1, len(tasks_df), "Gesamt"), (c2, len(todo_df), "Offen"),
            (c3, len(inprog_df), "Aktiv"), (c4, len(done_df), "Erledigt")
        ]:
            with col:
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-val">{val}</div>
                    <div class="metric-lbl">{label}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")

        sub1, sub2, sub3 = st.tabs(["Zu erledigen", "In Arbeit", "Erledigt"])

        PRIORITY_ICONS = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🟢"}

        def render_tasks(task_df):
            if task_df.empty:
                st.info("Nichts hier!")
                return
            for _, t in task_df.iterrows():
                p_icon = PRIORITY_ICONS.get(str(t.get('priority', 'P2')), "⚪")
                company_str = f" | 🏢 {t['target_company']}" if t.get('target_company') else ""
                desc = str(t['description'])[:120] + "..." if len(str(t.get('description', ''))) > 120 else str(t.get('description', ''))
                st.markdown(f"""
                <div class="alert-card info">
                    <div class="alert-title">{p_icon} {t['title']}</div>
                    <div class="alert-sub">{desc}{company_str}</div>
                </div>""", unsafe_allow_html=True)

        with sub1: render_tasks(todo_df)
        with sub2: render_tasks(inprog_df)
        with sub3: render_tasks(done_df)

    # ── New Task Form ──
    st.markdown("---")
    with st.expander("➕ Neue Task erstellen"):
        with st.form("new_task"):
            title = st.text_input("Titel *")
            desc = st.text_area("Beschreibung", height=80)
            c1, c2 = st.columns(2)
            with c1:
                priority = st.selectbox("Priorität", ["P1", "P2", "P3", "P4"])
                category = st.selectbox("Kategorie", ["OUTREACH", "UAE", "GERMANY", "SWITZERLAND", "UK", "RESEARCH", "CONTENT"])
            with c2:
                company = st.text_input("Unternehmen (optional)")
                due = st.text_input("Fällig (YYYY-MM-DD, optional)")

            if st.form_submit_button("Task erstellen", type="primary"):
                if title:
                    try:
                        with get_conn() as conn:
                            conn.execute("""
                                INSERT INTO tasks (title, description, status, priority, category, target_company, due_date)
                                VALUES (?, ?, 'todo', ?, ?, ?, ?)
                            """, (title, desc, priority, category, company or None, due or None))
                            conn.commit()
                        st.success(f"✅ Task erstellt: {title}")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")
                else:
                    st.error("Titel ist erforderlich")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: IMPORT
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("# 📥 Import")
    st.markdown("CSV oder XLSX hochladen — alle Formate werden automatisch erkannt (Apollo, LinkedIn, Custom)")

    uploaded = st.file_uploader(
        "Datei auswählen (CSV oder XLSX)",
        type=['csv', 'xlsx'],
        help="Unterstützt: Apollo, LinkedIn, Notion, Custom XLSX mit beliebigen Spaltennamen"
    )

    if uploaded:
        # Save to temp
        import tempfile, pathlib
        suffix = pathlib.Path(uploaded.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        st.success(f"📎 Hochgeladen: **{uploaded.name}**")

        # Preview
        try:
            if suffix == '.csv':
                preview_df = pd.read_csv(tmp_path, encoding='utf-8-sig', nrows=5)
            else:
                preview_df = pd.read_excel(tmp_path, nrows=5)
            st.markdown("**Vorschau (erste 5 Zeilen):**")
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Preview fehler: {e}")

        # Import options
        col1, col2 = st.columns(2)
        with col1:
            source_tag = st.text_input("Quelle", value=uploaded.name.split('.')[0], help="z.B. Apollo, LinkedIn, Manual")
        with col2:
            dry_run = st.checkbox("Nur analysieren (kein Import)", value=True)

        if st.button("🚀 Import starten", type="primary"):
            with st.spinner("Importiere..."):
                try:
                    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(
                        "csv_importer",
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv_importer.py")
                    )
                    importer = importlib.util.load_from_spec(spec)
                    spec.loader.exec_module(importer)

                    stats_result = importer.import_file(
                        tmp_path,
                        source_tag=source_tag,
                        dry_run=dry_run,
                        db_path=DB_PATH
                    )

                    if dry_run:
                        st.info(f"**DRY RUN** — {stats_result['imported']} würden importiert, {stats_result['skipped_dup']} Duplikate, {stats_result['skipped_invalid']} ungültig")
                    else:
                        st.success(f"✅ **{stats_result['imported']} neue Leads importiert!** | {stats_result['skipped_dup']} Duplikate übersprungen")
                        st.cache_data.clear()
                        st.rerun()

                except Exception as e:
                    st.error(f"Import Fehler: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                finally:
                    os.unlink(tmp_path)

    st.markdown("---")
    st.markdown("**Aktueller DB-Status:**")
    try:
        with get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            by_region = conn.execute("SELECT region, COUNT(*) FROM leads GROUP BY region ORDER BY COUNT(*) DESC").fetchall()
        st.markdown(f"**{total:,} Leads** in StakeStream DB")
        cols = st.columns(len(by_region))
        for i, (region, count) in enumerate(by_region):
            with cols[i]:
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-val" style="font-size:1.25rem;">{count:,}</div>
                    <div class="metric-lbl">{region}</div>
                </div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"DB Status Fehler: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: MEDDPICC
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("# ⚙️ MEDDPICC Scoring")

    if df.empty:
        st.info("Keine Leads geladen.")
    else:
        # Search by company
        search = st.text_input("🔍 Unternehmen suchen", placeholder="z.B. Bitvavo, Deutsche Bank...")
        if search:
            matches = df[df['company'].str.lower().str.contains(search.lower(), na=False)]
        else:
            matches = df.head(50)

        if matches.empty:
            st.warning(f"Kein Treffer für '{search}'")
        else:
            company_options = matches['company'].tolist()
            selected_company = st.selectbox("Unternehmen auswählen", company_options)

            lead_row = matches[matches['company'] == selected_company].iloc[0]

            st.markdown(f"""
            <div class="alert-card info">
                <div class="alert-title">{lead_row['company']}</div>
                <div class="alert-sub">
                    👤 {lead_row['contact_person'] or 'N/A'} | {lead_row['region_str']} | {lead_row['stage_str']} |
                    Aktuell: <strong>{int(lead_row['meddpicc'])}/80</strong>
                </div>
            </div>""", unsafe_allow_html=True)

            col1, col2 = st.columns([3, 2])

            with col1:
                st.markdown("### Bewertung (0-10 je Kriterium)")
                c_l, c_r = st.columns(2)
                with c_l:
                    m_metrics = st.slider("📏 Metrics", 0, 10, int(lead_row['m_metrics']))
                    m_economic = st.slider("💼 Economic Buyer", 0, 10, int(lead_row['m_economic']))
                    m_process = st.slider("🔄 Decision Process", 0, 10, int(lead_row['m_process']))
                    m_criteria = st.slider("📋 Decision Criteria", 0, 10, int(lead_row['m_criteria']))
                with c_r:
                    m_paper = st.slider("📄 Paper Process", 0, 10, int(lead_row['m_paper']))
                    m_pain = st.slider("🩹 Pain", 0, 10, int(lead_row['m_pain']))
                    m_champion = st.slider("🏆 Champion", 0, 10, int(lead_row['m_champion']))
                    m_competition = st.slider("⚔️ Competition", 0, 10, int(lead_row['m_competition']))

                total = m_metrics + m_economic + m_process + m_criteria + m_paper + m_pain + m_champion + m_competition
                qual_label, qual_class = qualify(total)

                st.markdown(f"""
                <div style="margin-top:1rem;padding:1rem;background:#1a1a1a;border-radius:8px;text-align:center;">
                    <div style="font-size:2rem;font-weight:700;">{total}/80</div>
                    <div><span class="score-badge {qual_class}">{qual_label}</span></div>
                </div>""", unsafe_allow_html=True)

            with col2:
                st.markdown("### Score-Gauge")
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=total,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': f"<b>{qual_label}</b>", 'font': {'color': '#e5e5e5', 'size': 14}},
                    number={'font': {'color': '#e5e5e5', 'size': 36}},
                    gauge={
                        'axis': {'range': [0, 80], 'tickcolor': '#e5e5e5'},
                        'bar': {'color': "#3b82f6"},
                        'bgcolor': '#2a2a2a',
                        'steps': [
                            {'range': [0, 30], 'color': '#1a1a1a'},
                            {'range': [30, 50], 'color': '#7f1d1d'},
                            {'range': [50, 70], 'color': '#1e3a8a'},
                            {'range': [70, 80], 'color': '#166534'},
                        ],
                        'threshold': {
                            'line': {'color': '#fff', 'width': 2},
                            'thickness': 0.75, 'value': total
                        }
                    }
                ))
                fig.update_layout(
                    height=220,
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#e5e5e5',
                    margin=dict(t=30, b=10, l=20, r=20)
                )
                st.plotly_chart(fig, use_container_width=True)

            if st.button("💾 Score speichern", type="primary"):
                try:
                    with get_conn() as conn:
                        lead_id = int(lead_row['id'])
                        existing = conn.execute("SELECT id FROM meddpicc_scores WHERE lead_id = ?", (lead_id,)).fetchone()
                        if existing:
                            conn.execute("""
                                UPDATE meddpicc_scores SET
                                    metrics=?, economic_buyer=?, decision_process=?,
                                    decision_criteria=?, paper_process=?, pain=?,
                                    champion=?, competition=?, updated_at=CURRENT_TIMESTAMP
                                WHERE lead_id=?
                            """, (m_metrics, m_economic, m_process, m_criteria,
                                  m_paper, m_pain, m_champion, m_competition, lead_id))
                        else:
                            conn.execute("""
                                INSERT INTO meddpicc_scores
                                    (lead_id, metrics, economic_buyer, decision_process,
                                     decision_criteria, paper_process, pain, champion, competition)
                                VALUES (?,?,?,?,?,?,?,?,?)
                            """, (lead_id, m_metrics, m_economic, m_process,
                                  m_criteria, m_paper, m_pain, m_champion, m_competition))
                        conn.commit()
                    st.success(f"✅ Score gespeichert: {total}/80 ({qual_label})")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Fehler: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7: NEUER LEAD
# ══════════════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown("# ➕ Neuer Lead")

    with st.form("add_lead_v6"):
        c1, c2 = st.columns(2)
        with c1:
            company = st.text_input("Unternehmen *", placeholder="z.B. DWS Group")
            region = st.selectbox("Region", ['DE', 'CH', 'UK', 'UAE', 'NORDICS'])
            industry = st.selectbox("Industrie", [
                'Institutional', 'Asset Management', 'Bank', 'Insurance',
                'Family Office', 'Pension Fund', 'Foundation', 'Custodian',
                'Hedge Fund', 'Real Estate', 'Other'
            ])
            aum = st.number_input("AUM (Mio €, optional)", min_value=0.0, value=0.0)
        with c2:
            contact = st.text_input("Kontakt Name", placeholder="z.B. Max Müller")
            title = st.text_input("Titel", placeholder="z.B. CIO")
            email = st.text_input("Email (optional)")
            linkedin = st.text_input("LinkedIn URL (optional)")

        col3, col4 = st.columns(2)
        with col3:
            stage = st.selectbox("Stage", ['prospecting', 'discovery', 'solutioning', 'validation', 'negotiation'])
            tier = st.selectbox("Tier", [1, 2, 3, 4])
        with col4:
            deal_size = st.number_input("Expected Deal Size (Mio €)", min_value=0.0, value=0.0)
            notes = st.text_area("Notizen / Use Case", height=80)

        if st.form_submit_button("✅ Lead erstellen", type="primary"):
            if company:
                try:
                    with get_conn() as conn:
                        cursor = conn.execute("""
                            INSERT INTO leads (
                                company, region, tier, contact_person, title, email,
                                linkedin, stage, industry, use_case,
                                aum_estimate_millions, expected_deal_size_millions,
                                expected_yield, staking_readiness
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            company, region, tier, contact, title,
                            email or None, linkedin or None, stage, industry,
                            notes or f"ETH Staking | Manual Entry", aum, deal_size, 0.0,
                            "Unknown"
                        ))
                        lead_id = cursor.lastrowid
                        conn.execute("""
                            INSERT INTO meddpicc_scores (lead_id) VALUES (?)
                        """, (lead_id,))
                        conn.commit()
                    st.success(f"✅ **{company}** wurde erstellt! (ID: {lead_id})")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Fehler: {e}")
            else:
                st.error("Unternehmen ist erforderlich")
