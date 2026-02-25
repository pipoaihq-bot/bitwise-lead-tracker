import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# Page config
st.set_page_config(
    page_title="Bitwise EMEA | Lead Tracker",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean, Professional CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    /* Main Background */
    .stApp {
        background: #0f172a;
    }
    
    /* Headers */
    h1 {
        color: #f8fafc;
        font-weight: 700;
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: #e2e8f0;
        font-weight: 600;
        font-size: 1.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.5rem;
    }
    
    h3 {
        color: #cbd5e1;
        font-weight: 600;
        font-size: 1.1rem;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
        border-right: 1px solid #334155;
    }
    
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.5rem;
    }
    
    /* Radio buttons */
    .stRadio > div {
        background: transparent;
    }
    
    .stRadio > div > label {
        color: #e2e8f0 !important;
        padding: 0.6rem 1rem;
        margin: 0.2rem 0;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .stRadio > div > label:hover {
        background: rgba(26, 156, 156, 0.2);
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
    }
    
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #14b8a6;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #94a3b8;
        margin-top: 0.25rem;
    }
    
    /* Buttons */
    .stButton > button {
        background: #14b8a6;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        background: #0d9488;
        transform: translateY(-1px);
    }
    
    /* DataFrames */
    .stDataFrame {
        background: #1e293b;
        border-radius: 8px;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #1e293b !important;
        border: 1px solid #334155;
        border-radius: 8px;
        color: #e2e8f0 !important;
    }
    
    .streamlit-expanderContent {
        background: #0f172a !important;
        border: 1px solid #334155;
        border-top: none;
        border-radius: 0 0 8px 8px;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: #1e293b;
        border-radius: 8px 8px 0 0;
        color: #94a3b8;
        border: none;
        padding: 0.75rem 1rem;
    }
    
    .stTabs [aria-selected="true"] {
        background: #14b8a6 !important;
        color: white !important;
    }
    
    /* Task Cards */
    .task-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    
    .task-title {
        font-weight: 600;
        color: #f1f5f9;
        font-size: 0.95rem;
    }
    
    .task-meta {
        color: #94a3b8;
        font-size: 0.8rem;
        margin-top: 0.25rem;
    }
    
    /* Form Elements */
    .stTextInput > div > div, .stSelectbox > div > div, .stMultiselect > div > div {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px;
        color: #f1f5f9 !important;
    }
    
    .stSlider > div > div > div {
        background: #14b8a6 !important;
    }
    
    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .badge-p1 { background: #dc2626; color: white; }
    .badge-p2 { background: #ea580c; color: white; }
    .badge-p3 { background: #ca8a04; color: white; }
    .badge-p4 { background: #16a34a; color: white; }
    
    .badge-todo { background: #475569; color: white; }
    .badge-progress { background: #2563eb; color: white; }
    .badge-done { background: #16a34a; color: white; }
</style>
""", unsafe_allow_html=True)

# Initialize
from database import Database
from task_manager import TaskManager, populate_default_tasks

db = Database()
task_manager = TaskManager()

# Check and populate tasks
with task_manager.get_connection() as conn:
    task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if task_count == 0:
        populate_default_tasks()

leads = db.get_all_leads()

# Helper functions
def load_leads_df():
    if not leads:
        return pd.DataFrame()
    
    data = []
    for lead in leads:
        meddpicc = db.get_meddpicc_score(lead.id)
        data.append({
            'ID': lead.id,
            'Company': lead.company,
            'Region': lead.region.value if hasattr(lead.region, 'value') else str(lead.region),
            'Industry': getattr(lead, 'industry', '') or '',
            'Stage': lead.stage.value if hasattr(lead.stage, 'value') else str(lead.stage),
            'MEDDPICC': meddpicc.total_score if meddpicc else 0,
            'Readiness': getattr(lead, 'staking_readiness', '') or '',
        })
    return pd.DataFrame(data)

# Sidebar
with st.sidebar:
    st.markdown("### 🔷 Bitwise")
    st.markdown("**EMEA Onchain Solutions**")
    st.markdown("---")
    
    page = st.radio("", [
        "📊 Dashboard",
        "📋 Pipeline",
        "🎯 Tasks",
        "📁 Import",
        "🎯 MEDDPICC",
        "➕ Add Lead"
    ], label_visibility="collapsed")
    
    st.markdown("---")
    st.markdown(f"**{len(leads):,} Leads**")
    st.markdown(f"**{task_count} Tasks**")
    st.caption(f"v1.0 • {datetime.now().strftime('%Y-%m-%d')}")

# ==================== PAGES ====================

# DASHBOARD
if page == "📊 Dashboard":
    st.markdown("# 📊 Dashboard")
    
    df = load_leads_df()
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{len(df):,}</div><div class="metric-label">Total Leads</div></div>', unsafe_allow_html=True)
    with col2:
        qualified = len(df[df['MEDDPICC'] >= 50]) if not df.empty else 0
        st.markdown(f'<div class="metric-card"><div class="metric-value">{qualified}</div><div class="metric-label">Qualified</div></div>', unsafe_allow_html=True)
    with col3:
        todo_tasks = len([t for t in task_manager.get_tasks(status='todo')])
        st.markdown(f'<div class="metric-card"><div class="metric-value">{todo_tasks}</div><div class="metric-label">Tasks To Do</div></div>', unsafe_allow_html=True)
    with col4:
        p1_tasks = len([t for t in task_manager.get_tasks(status='todo') if t.priority.value == 'P1'])
        st.markdown(f'<div class="metric-card"><div class="metric-value">{p1_tasks}</div><div class="metric-label">P1 Critical</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    if df.empty:
        st.info("📋 No leads yet. Go to **📁 Import** to add data.")
    else:
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Leads by Region")
            region_data = df.groupby('Region').size().reset_index(name='Count')
            fig = px.pie(region_data, values='Count', names='Region', 
                        color_discrete_sequence=['#14b8a6', '#0d9488', '#0f766e', '#115e59', '#134e4a'])
            fig.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', font_color='#e2e8f0')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### MEDDPICC Distribution")
            score_data = df.groupby(pd.cut(df['MEDDPICC'], bins=[0, 30, 50, 70, 80], labels=['Low', 'Medium', 'High', 'Qualified'])).size().reset_index(name='Count')
            score_data = score_data[score_data['Count'] > 0]
            fig = px.bar(score_data, x='MEDDPICC', y='Count', color='MEDDPICC',
                        color_discrete_sequence=['#dc2626', '#ea580c', '#14b8a6', '#16a34a'])
            fig.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', font_color='#e2e8f0', showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

# PIPELINE
elif page == "📋 Pipeline":
    st.markdown("# 📋 Lead Pipeline")
    
    df = load_leads_df()
    
    if df.empty:
        st.info("📋 No leads available.")
    else:
        # Filters
        with st.expander("🔍 Filters", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                region_filter = st.multiselect("Region", df['Region'].unique().tolist())
            with col2:
                if 'Industry' in df.columns:
                    industries = [i for i in df['Industry'].unique() if i]
                    industry_filter = st.multiselect("Industry", industries)
                else:
                    industry_filter = []
            with col3:
                min_meddpicc = st.slider("Min MEDDPICC", 0, 80, 0)
        
        # Apply filters
        filtered = df.copy()
        if region_filter:
            filtered = filtered[filtered['Region'].isin(region_filter)]
        if industry_filter and 'Industry' in filtered.columns:
            filtered = filtered[filtered['Industry'].isin(industry_filter)]
        if min_meddpicc > 0:
            filtered = filtered[filtered['MEDDPICC'] >= min_meddpicc]
        
        st.markdown(f"**Showing {len(filtered)} of {len(df)} leads**")
        
        # Table
        display_cols = ['Company', 'Region', 'Industry', 'Stage', 'MEDDPICC', 'Readiness']
        display_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

# TASKS
elif page == "🎯 Tasks":
    st.markdown("# 🎯 Tasks & Targets")
    
    # Stats
    stats = task_manager.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", stats['total'])
    col2.metric("To Do", stats['todo'])
    col3.metric("In Progress", stats['in_progress'])
    col4.metric("Done", stats['done'])
    
    st.markdown("---")
    
    # Create Task
    with st.expander("➕ New Task"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Title")
            desc = st.text_area("Description")
            company = st.text_input("Company (optional)")
        with col2:
            priority = st.selectbox("Priority", ["P1", "P2", "P3", "P4"])
            category = st.selectbox("Category", ["UAE", "GERMANY", "SWITZERLAND", "UK", "OUTREACH", "CONTENT", "RESEARCH"])
        
        if st.button("Create Task", type="primary"):
            from task_manager import Task, TaskStatus, TaskPriority, TaskCategory
            task = Task(None, title, desc, TaskStatus.TODO, TaskPriority(priority), TaskCategory(category), company if company else None)
            task_manager.create_task(task)
            st.success("✅ Created!")
            st.rerun()
    
    # Task Board
    tab1, tab2, tab3 = st.tabs(["📋 To Do", "⚡ In Progress", "✅ Done"])
    
    with tab1:
        tasks = task_manager.get_tasks(status='todo')
        for task in tasks:
            with st.container():
                col1, col2, col3 = st.columns([0.1, 0.7, 0.2])
                with col1:
                    if st.checkbox("", key=f"td_{task.id}"):
                        task_manager.update_task_status(task.id, 'done')
                        st.rerun()
                with col2:
                    priority_colors = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🟢"}
                    st.markdown(f"{priority_colors[task.priority.value]} **{task.title}**")
                    if task.description:
                        st.caption(task.description)
                    if task.target_company:
                        st.caption(f"🏢 {task.target_company}")
                with col3:
                    if st.button("▶️ Start", key=f"start_{task.id}"):
                        task_manager.update_task_status(task.id, 'in_progress')
                        st.rerun()
    
    with tab2:
        tasks = task_manager.get_tasks(status='in_progress')
        for task in tasks:
            with st.container():
                col1, col2, col3 = st.columns([0.1, 0.7, 0.2])
                with col1:
                    if st.checkbox("", key=f"ip_{task.id}", value=False):
                        task_manager.update_task_status(task.id, 'done')
                        st.rerun()
                with col2:
                    st.markdown(f"⚡ **{task.title}**")
                with col3:
                    if st.button("⏸️ Pause", key=f"pause_{task.id}"):
                        task_manager.update_task_status(task.id, 'todo')
                        st.rerun()
    
    with tab3:
        tasks = task_manager.get_tasks(status='done')
        st.success(f"🎉 {len(tasks)} completed!")
        for task in tasks:
            st.markdown(f"✅ ~~{task.title}~~")

# IMPORT
elif page == "📁 Import":
    st.markdown("# 📁 Import Data")
    st.info("Upload CSV with Chorus One prospects")
    
    uploaded = st.file_uploader("Choose CSV", type=['csv'])
    if uploaded:
        import pandas as pd
        df = pd.read_csv(uploaded)
        st.write(f"📊 {len(df)} rows found")
        st.dataframe(df.head())
        
        if st.button("🚀 Import", type="primary"):
            from models import Lead, Region, Tier, Stage, MEDDPICCScore
            count = 0
            for _, row in df.iterrows():
                try:
                    lead = Lead(
                        id=None,
                        company=str(row.get('Account Name', '')),
                        region=Region('DE'),
                        tier=Tier(2),
                        aum_estimate_millions=0,
                        contact_person='',
                        title='',
                        email=None,
                        linkedin=str(row.get('LinkedIn', '')) if pd.notna(row.get('LinkedIn')) else None,
                        stage=Stage.PROSPECTING,
                        pain_points=str(row.get('Account Type', '')),
                        expected_deal_size_millions=0,
                        expected_yield=0
                    )
                    lid = db.create_lead(lead)
                    db.set_meddpicc_score(lid, MEDDPICCScore(lead_id=lid))
                    count += 1
                except:
                    pass
            st.success(f"✅ Imported {count} leads!")
            st.balloons()

# MEDDPICC
elif page == "🎯 MEDDPICC":
    st.markdown("# 🎯 MEDDPICC Scoring")
    
    df = load_leads_df()
    
    if df.empty:
        st.info("No leads available.")
    else:
        company = st.selectbox("Select Company", df['Company'].tolist())
        
        if company:
            lead_row = df[df['Company'] == company].iloc[0]
            current = db.get_meddpicc_score(lead_row['ID'])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Score Elements")
                metrics = st.slider("Metrics", 0, 10, current.metrics if current else 0)
                economic = st.slider("Economic Buyer", 0, 10, current.economic_buyer if current else 0)
                process = st.slider("Decision Process", 0, 10, current.decision_process if current else 0)
                criteria = st.slider("Decision Criteria", 0, 10, current.decision_criteria if current else 0)
                pain = st.slider("Pain", 0, 10, current.pain if current else 0)
                champion = st.slider("Champion", 0, 10, current.champion if current else 0)
            
            with col2:
                st.markdown("### Result")
                total = metrics + economic + process + criteria + pain + champion + (current.competition if current else 0)
                status = "QUALIFIED" if total >= 70 else "PROBABLE" if total >= 50 else "POSSIBLE" if total >= 30 else "UNQUALIFIED"
                
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=total,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': f"MEDDPICC<br><span style='font-size:0.8em;color:gray'>{status}</span>"},
                    gauge={'axis': {'range': [None, 80]}, 'bar': {'color': "#14b8a6"},
                           'steps': [{'range': [0, 30], 'color': "#7f1d1d"},
                                    {'range': [30, 50], 'color': "#92400e"},
                                    {'range': [50, 70], 'color': "#1e40af"},
                                    {'range': [70, 80], 'color': "#14532d"}]}
                ))
                fig.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', font_color='#e2e8f0')
                st.plotly_chart(fig, use_container_width=True)
                
                if st.button("💾 Save Score", type="primary"):
                    from models import MEDDPICCScore
                    new_score = MEDDPICCScore(
                        lead_id=lead_row['ID'],
                        metrics=metrics, economic_buyer=economic,
                        decision_process=process, decision_criteria=criteria,
                        paper_process=0, pain=pain, champion=champion, competition=0
                    )
                    db.set_meddpicc_score(lead_row['ID'], new_score)
                    st.success("Saved!")

# ADD LEAD
elif page == "➕ Add Lead":
    st.markdown("# ➕ Add New Lead")
    
    with st.form("add_lead"):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("Company Name *")
            region = st.selectbox("Region", ['DE', 'CH', 'UK', 'UAE'])
            contact = st.text_input("Contact Name")
        with col2:
            title = st.text_input("Title")
            linkedin = st.text_input("LinkedIn URL")
            stage = st.selectbox("Stage", ['prospecting', 'discovery', 'solutioning', 'validation'])
        
        if st.form_submit_button("✨ Create Lead", type="primary"):
            from models import Lead, Region as R, Tier, Stage as S, MEDDPICCScore
            lead = Lead(
                id=None, company=company, region=R(region), tier=Tier(2),
                aum_estimate_millions=0, contact_person=contact, title=title,
                linkedin=linkedin if linkedin else None, stage=S(stage)
            )
            lid = db.create_lead(lead)
            db.set_meddpicc_score(lid, MEDDPICCScore(lead_id=lid))
            st.success(f"✅ Created: {company}")
