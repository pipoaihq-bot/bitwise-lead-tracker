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

# ── Dark Mobile CSS (same as v6) ───────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background: #0f0f0f; color: #e5e5e5; }
h1, h2, h3 { color: #ffffff; letter-spacing: -0.02em; }
h1 { font-size: clamp(1.4rem, 5vw, 2rem); font-weight: 600; margin-bottom: 1rem; }
h2 { font-size: clamp(1rem, 4vw, 1.25rem); font-weight: 500; margin-top: 1.5rem; }
section[data-testid="stSidebar"] { background: #1a1a1a; border-right: 1px solid #2a2a2a; }
.metric-card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px; padding: 1rem; text-align: center; margin-bottom: 0.5rem; }
.metric-card:hover { border-color: #3b82f6; }
.metric-val { font-size: clamp(1.5rem, 6vw, 2rem); font-weight: 700; color: #fff; }
.metric-lbl { font-size: 0.75rem; color: #737373; margin-top: 0.125rem; text-transform: uppercase; letter-spacing: 0.05em; }
.alert-card { background: #1a1a1a; border-radius: 10px; padding: 1rem; margin-bottom: 0.75rem; border-left: 4px solid #ef4444; }
.alert-card.warning { border-left-color: #f59e0b; }
.alert-card.info { border-left-color: #3b82f6; }
.alert-title { font-size: 1rem; font-weight: 600; color: #fff; }
.alert-sub { font-size: 0.8125rem; color: #a3a3a3; margin-top: 0.25rem; }
.lead-row { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px; padding: 0.875rem 1rem; margin-bottom: 0.5rem; }
.lead-row:hover { border-color: #3b82f6; }
.lead-company { font-weight: 600; font-size: 0.9375rem; }
.lead-meta { font-size: 0.75rem; color: #737373; margin-top: 0.125rem; }
.score-badge { background: #2a2a2a; border-radius: 6px; padding: 0.25rem 0.5rem; font-size: 0.75rem; font-weight: 600; color: #e5e5e5; white-space: nowrap; }
.score-badge.qualified { background: #166534; color: #86efac; }
.score-badge.probable { background: #1e3a8a; color: #93c5fd; }
.score-badge.possible { background: #713f12; color: #fde68a; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.6875rem; font-weight: 600; }
.pill-green { background: #166534; color: #86efac; }
.pill-yellow { background: #713f12; color: #fde68a; }
.pill-red { background: #7f1d1d; color: #fca5a5; }
.stButton > button { border-radius: 8px !important; font-weight: 500 !important; }
.stButton > button[kind="primary"] { background: #3b82f6 !important; color: white !important; border: none !important; }
.stTabs [data-baseweb="tab-list"] { background: #1a1a1a; border-radius: 8px; padding: 4px; gap: 2px; }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: #737373 !important; border-radius: 6px !important; font-size: clamp(0.75rem, 2.5vw, 0.875rem) !important; padding: 0.4rem 0.75rem !important; }
.stTabs [aria-selected="true"] { background: #2a2a2a !important; color: #fff !important; }
.stDataFrame { border: 1px solid #2a2a2a !important; border-radius: 8px !important; }
.stTextInput input, .stSelectbox select, .stTextArea textarea { background: #1a1a1a !important; border: 1px solid #2a2a2a !important; border-radius: 8px !important; color: #e5e5e5 !important; }
.streamlit-expanderHeader { background: #1a1a1a !important; border: 1px solid #2a2a2a !important; border-radius: 8px !important; color: #e5e5e5 !important; }
.stSelectbox > div > div { background: #1a1a1a !important; border-color: #2a2a2a !important; color: #e5e5e5 !important; }
footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }
hr { border-color: #2a2a2a !important; margin: 1rem 0 !important; }
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
        # Load leads with meddpicc scores via join
        resp = sb.table("leads").select(
            "*, meddpicc_scores(total_score, qualification_status, metrics, economic_buyer, "
            "decision_process, decision_criteria, paper_process, pain, champion, competition)"
        ).execute()

        if not resp.data:
            return pd.DataFrame(), {}

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
    st.markdown("## ◆ StakeStream")
    st.markdown("<span style='color:#737373;font-size:0.8125rem;'>Bitwise EMEA Command Center</span>", unsafe_allow_html=True)
    st.markdown("---")
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div style='font-size:1.5rem;font-weight:700;'>{stats['total']:,}</div><div style='font-size:0.75rem;color:#737373;'>Leads</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='font-size:1.5rem;font-weight:700;'>€{stats['pipeline']:.0f}M</div><div style='font-size:0.75rem;color:#737373;'>Pipeline</div>", unsafe_allow_html=True)
        if stats['critical'] > 0:
            st.markdown(f"<div style='background:#7f1d1d;color:#fca5a5;padding:0.4rem 0.75rem;border-radius:8px;font-size:0.8125rem;margin-top:0.5rem;font-weight:600;'>🚨 {stats['critical']} Dringend</div>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("🔄 Aktualisieren"):
        st.cache_data.clear()
        st.rerun()
    st.markdown(f"<span style='color:#3a3a3a;font-size:0.75rem;'>v7.0 Supabase • {datetime.now().strftime('%d.%m %H:%M')}</span>", unsafe_allow_html=True)

# ── Navigation ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏠 Dashboard", "🚨 Prioritäten", "📊 Pipeline",
    "✅ Tasks", "📥 Import", "⚙️ MEDDPICC", "➕ Neuer Lead"
])

# ══════════════════════════════════════════════════════════════
# TAB 1: DASHBOARD
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown("# ◆ StakeStream")
    st.markdown(f"<span style='color:#737373;'>Bitwise EMEA • {datetime.now().strftime('%a, %d. %b %Y')}</span>", unsafe_allow_html=True)

    if df.empty:
        st.warning("Keine Daten. Leads müssen erst in Supabase migriert werden.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        for col, val, label, alert in [
            (c1, f"{stats['total']:,}", "Leads gesamt", False),
            (c2, str(stats['qualified']), "Qualifiziert", False),
            (c3, f"⚠️ {stats['stale']}" if stats['stale'] else "0", "Inaktiv >7T", stats['stale'] > 0),
            (c4, f"€{stats['pipeline']:.0f}M", "Pipeline", False),
        ]:
            with col:
                color = "#ef4444" if alert else "#fff"
                st.markdown(f"""<div class="metric-card">
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
                         color_discrete_sequence=["#3b82f6","#8b5cf6","#06b6d4","#10b981","#f59e0b"], hole=0.5)
            fig.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)", font_color="#e5e5e5",
                              legend=dict(orientation="h", y=-0.3, font_size=11),
                              margin=dict(t=10, b=50, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### MEDDPICC Verteilung")
            order = ["QUALIFIED","PROBABLE","POSSIBLE","UNQUALIFIED"]
            qc = df["qualification"].value_counts()
            fig = go.Figure(go.Bar(
                x=order, y=[qc.get(o, 0) for o in order],
                marker_color=["#86efac","#93c5fd","#fde68a","#525252"],
                text=[qc.get(o, 0) for o in order], textposition="outside",
                textfont=dict(color="#e5e5e5")
            ))
            fig.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", font_color="#e5e5e5",
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
                    gauge={"axis":{"range":[0,80],"tickcolor":"#e5e5e5"},"bar":{"color":"#3b82f6"},
                           "bgcolor":"#2a2a2a","steps":[{"range":[0,30],"color":"#1a1a1a"},
                           {"range":[30,50],"color":"#7f1d1d"},{"range":[50,70],"color":"#1e3a8a"},
                           {"range":[70,80],"color":"#166534"}]}))
                fig.update_layout(height=220, paper_bgcolor="rgba(0,0,0,0)", font_color="#e5e5e5", margin=dict(t=30,b=10,l=10,r=10))
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
