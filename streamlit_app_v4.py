import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Bitwise EMEA | Lead Tracker",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# RUHIGES, MINIMALISTISCHES DESIGN
st.markdown("""
<style>
    /* Haupt-Hintergrund - sehr hell, fast weiß */
    .stApp { 
        background: #fafafa; 
    }
    
    /* Typography - clean, großzügig */
    h1 { 
        color: #1a1a1a; 
        font-size: 1.75rem; 
        font-weight: 500;
        letter-spacing: -0.02em;
        margin-bottom: 1.5rem;
    }
    h2 { 
        color: #333; 
        font-size: 1.125rem; 
        font-weight: 500;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    h3 {
        color: #444;
        font-size: 0.9375rem;
        font-weight: 500;
    }
    
    /* Sidebar - hellgrau, dezent */
    section[data-testid="stSidebar"] { 
        background: #f5f5f5;
        border-right: 1px solid #e5e5e5;
    }
    section[data-testid="stSidebar"] .stMarkdown {
        color: #666;
    }
    
    /* Metric Cards - weiß, subtiler Schatten */
    .metric-container { 
        background: white; 
        border: 1px solid #e8e8e8; 
        border-radius: 8px; 
        padding: 1.25rem;
        transition: box-shadow 0.2s;
    }
    .metric-container:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .metric-value { 
        font-size: 1.5rem; 
        font-weight: 600; 
        color: #1a1a1a; 
        letter-spacing: -0.02em;
    }
    .metric-label { 
        font-size: 0.8125rem; 
        color: #737373; 
        margin-top: 0.25rem;
    }
    
    /* Primary Button - dezentes Blau */
    .stButton > button[type="primary"] { 
        background: #2563eb; 
        color: white; 
        border: none; 
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button[type="primary"]:hover {
        background: #1d4ed8;
    }
    
    /* Secondary Buttons */
    .stButton > button:not([type="primary"]) {
        background: white;
        border: 1px solid #d4d4d4;
        color: #525252;
        border-radius: 6px;
    }
    
    /* DataFrames - clean */
    .stDataFrame {
        border: 1px solid #e5e5e5;
        border-radius: 8px;
    }
    
    /* Tabs - minimal */
    .stTabs [data-baseweb="tab"] { 
        background: transparent;
        color: #737373;
        border-bottom: 2px solid transparent;
    }
    .stTabs [aria-selected="true"] { 
        background: transparent !important;
        color: #1a1a1a !important;
        border-bottom: 2px solid #2563eb !important;
        font-weight: 500;
    }
    
    /* Inputs - clean */
    .stTextInput input, .stSelectbox select, .stTextArea textarea {
        border-color: #d4d4d4 !important;
        border-radius: 6px !important;
    }
    .stTextInput input:focus, .stSelectbox select:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
    }
    
    /* Dividers */
    hr {
        border-color: #e5e5e5;
        margin: 1.5rem 0;
    }
    
    /* Expander - clean */
    .streamlit-expanderHeader {
        background: white;
        border: 1px solid #e5e5e5;
        border-radius: 6px;
    }
    
    /* Caption */
    .stCaption {
        color: #a3a3a3 !important;
    }
    
    /* Status badges */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .badge-qual { background: #dcfce7; color: #166534; }
    .badge-prob { background: #dbeafe; color: #1e40af; }
    .badge-poss { background: #fef3c7; color: #92400e; }
    .badge-unq { background: #f3f4f6; color: #6b7280; }
</style>
""", unsafe_allow_html=True)

# Initialize
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database
from task_manager import TaskManager, populate_default_tasks
from models import Lead, MEDDPICCScore, Region, Tier, Stage

db = Database()
task_manager = TaskManager()

# Populate tasks if empty
try:
    with task_manager.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            populate_default_tasks()
except:
    pass

leads = db.get_all_leads()

# Load leads DataFrame
def load_leads_df():
    if not leads:
        return pd.DataFrame()
    data = []
    for lead in leads:
        meddpicc = db.get_meddpicc_score(lead.id)
        data.append({
            'ID': lead.id,
            'Company': lead.company,
            'Region': str(lead.region),
            'Industry': lead.industry,
            'Stage': str(lead.stage),
            'MEDDPICC': meddpicc.total_score if meddpicc else 0,
            'Readiness': lead.staking_readiness,
        })
    return pd.DataFrame(data)

df = load_leads_df()

# ==================== ERWEITERTE SIDEBAR ====================
with st.sidebar:
    # Logo/Header
    st.markdown("### ◆ Bitwise EMEA")
    st.markdown("<span style='color: #737373; font-size: 0.8125rem;'>Onchain Solutions</span>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Navigation
    st.markdown("**Navigation**")
    page = st.radio("", [
        "Übersicht",
        "Pipeline",
        "Tasks",
        "Import",
        "MEDDPICC",
        "Neuer Lead"
    ], label_visibility="collapsed")
    
    st.markdown("---")
    
    # Quick Stats in Sidebar
    st.markdown("**Kurzübersicht**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div style='font-size: 1.25rem; font-weight: 600;'>{len(leads):,}</div>", unsafe_allow_html=True)
        st.markdown("<span style='color: #737373; font-size: 0.75rem;'>Leads</span>", unsafe_allow_html=True)
    with col2:
        qualified = len(df[df['MEDDPICC'] >= 50]) if not df.empty else 0
        st.markdown(f"<div style='font-size: 1.25rem; font-weight: 600;'>{qualified}</div>", unsafe_allow_html=True)
        st.markdown("<span style='color: #737373; font-size: 0.75rem;'>Qualifiziert</span>", unsafe_allow_html=True)
    
    st.markdown("")
    
    col3, col4 = st.columns(2)
    with col3:
        todo = len([t for t in task_manager.get_tasks(status='todo')])
        st.markdown(f"<div style='font-size: 1.25rem; font-weight: 600;'>{todo}</div>", unsafe_allow_html=True)
        st.markdown("<span style='color: #737373; font-size: 0.75rem;'>Offene Tasks</span>", unsafe_allow_html=True)
    with col4:
        p1 = len([t for t in task_manager.get_tasks(status='todo') if t.priority == 'P1'])
        st.markdown(f"<div style='font-size: 1.25rem; font-weight: 600; color: #dc2626;'>{p1}</div>", unsafe_allow_html=True)
        st.markdown("<span style='color: #737373; font-size: 0.75rem;'>P1 Kritisch</span>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Pipeline by Region (Mini-Chart)
    if not df.empty:
        st.markdown("**Verteilung nach Region**")
        region_counts = df['Region'].value_counts()
        for region, count in region_counts.head(5).items():
            pct = count / len(df) * 100
            st.markdown(f"""
            <div style='margin-bottom: 0.5rem;'>
                <div style='display: flex; justify-content: space-between; font-size: 0.8125rem;'>
                    <span>{region}</span>
                    <span style='color: #737373;'>{count} ({pct:.0f}%)</span>
                </div>
                <div style='background: #e5e5e5; height: 4px; border-radius: 2px; margin-top: 2px;'>
                    <div style='background: #737373; height: 4px; border-radius: 2px; width: {pct}%;'></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
    
    # Recent Activity (Top Qualifizierte)
    st.markdown("**Top Qualifizierte**")
    if not df.empty:
        top_qualified = df[df['MEDDPICC'] >= 50].nlargest(3, 'MEDDPICC')
        for _, lead in top_qualified.iterrows():
            st.markdown(f"""
            <div style='font-size: 0.8125rem; margin-bottom: 0.5rem;'>
                <div style='font-weight: 500;'>{lead['Company']}</div>
                <div style='color: #737373;'>{lead['MEDDPICC']}/80 • {lead['Region']}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Footer
    st.markdown("<span style='color: #a3a3a3; font-size: 0.75rem;'>v2.0 • {}</span>".format(datetime.now().strftime('%d.%m.%Y')), unsafe_allow_html=True)

# ==================== PAGES ====================

if page == "Übersicht":
    st.markdown("# Übersicht")
    
    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'''<div class="metric-container">
            <div class="metric-value">{len(df):,}</div>
            <div class="metric-label">Gesamte Leads</div>
        </div>''', unsafe_allow_html=True)
    with col2:
        qualified = len(df[df['MEDDPICC'] >= 50]) if not df.empty else 0
        st.markdown(f'''<div class="metric-container">
            <div class="metric-value">{qualified}</div>
            <div class="metric-label">Qualifiziert</div>
        </div>''', unsafe_allow_html=True)
    with col3:
        todo = len([t for t in task_manager.get_tasks(status='todo')])
        st.markdown(f'''<div class="metric-container">
            <div class="metric-value">{todo}</div>
            <div class="metric-label">Offene Tasks</div>
        </div>''', unsafe_allow_html=True)
    with col4:
        p1 = len([t for t in task_manager.get_tasks(status='todo') if t.priority == 'P1'])
        st.markdown(f'''<div class="metric-container">
            <div class="metric-value" style="color: #dc2626;">{p1}</div>
            <div class="metric-label">P1 Kritisch</div>
        </div>''', unsafe_allow_html=True)
    
    st.markdown("---")
    
    if df.empty:
        st.info("Noch keine Leads vorhanden. Gehe zu **Import** um Daten hinzuzufügen.")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Leads nach Region")
            region_data = df.groupby('Region').size().reset_index(name='Count')
            
            # Ruhiges Farbschema - Graublautöne
            colors = ['#525252', '#737373', '#a3a3a3', '#d4d4d4']
            
            fig = px.pie(region_data, values='Count', names='Region', 
                        color_discrete_sequence=colors,
                        hole=0.4)
            fig.update_layout(
                height=280, 
                paper_bgcolor='rgba(0,0,0,0)', 
                font_color='#525252',
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                margin=dict(t=20, b=40, l=20, r=20)
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### MEDDPICC Verteilung")
            if len(df) > 0:
                bins = pd.cut(df['MEDDPICC'], bins=[0, 30, 50, 70, 80], 
                             labels=['Ungenügend', 'Möglich', 'Wahrscheinlich', 'Qualifiziert'])
                score_data = df.groupby(bins).size().reset_index(name='Count')
                score_data = score_data[score_data['Count'] > 0]
                
                # Ruhige Farben
                color_map = {
                    'Ungenügend': '#d4d4d4',
                    'Möglich': '#fca5a5', 
                    'Wahrscheinlich': '#93c5fd',
                    'Qualifiziert': '#86efac'
                }
                
                fig = px.bar(score_data, x='MEDDPICC', y='Count', 
                            color='MEDDPICC',
                            color_discrete_map=color_map)
                fig.update_layout(
                    height=280, 
                    paper_bgcolor='rgba(0,0,0,0)', 
                    font_color='#525252',
                    showlegend=False,
                    xaxis_title=None,
                    yaxis_title=None,
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=20, b=40, l=20, r=20)
                )
                fig.update_xaxes(showgrid=False)
                fig.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
                st.plotly_chart(fig, use_container_width=True)
        
        # Recent Leads Table
        st.markdown("---")
        st.markdown("### Neueste Leads")
        recent = df.sort_values('ID', ascending=False).head(10)
        st.dataframe(recent[['Company', 'Region', 'Industry', 'Stage', 'MEDDPICC']], 
                    use_container_width=True, hide_index=True)

elif page == "Pipeline":
    st.markdown("# Pipeline")
    
    if df.empty:
        st.info("Keine Leads verfügbar.")
    else:
        # Filters in Expander
        with st.expander("Filter", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                region_filter = st.multiselect("Region", df['Region'].unique().tolist())
            with col2:
                stage_filter = st.multiselect("Stage", df['Stage'].unique().tolist())
            with col3:
                min_meddpicc = st.slider("Min. MEDDPICC", 0, 80, 0)
        
        filtered = df.copy()
        if region_filter:
            filtered = filtered[filtered['Region'].isin(region_filter)]
        if stage_filter:
            filtered = filtered[filtered['Stage'].isin(stage_filter)]
        if min_meddpicc > 0:
            filtered = filtered[filtered['MEDDPICC'] >= min_meddpicc]
        
        st.markdown(f"**{len(filtered)} von {len(df)} Leads**")
        
        # Styled table
        st.dataframe(
            filtered[['Company', 'Region', 'Industry', 'Stage', 'MEDDPICC', 'Readiness']], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                'MEDDPICC': st.column_config.ProgressColumn(
                    "MEDDPICC",
                    format="%d/80",
                    min_value=0,
                    max_value=80,
                ),
            }
        )

elif page == "Tasks":
    st.markdown("# Tasks & Targets")
    
    stats = task_manager.get_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gesamt", stats['total'])
    col2.metric("Offen", stats['todo'])
    col3.metric("In Arbeit", stats['in_progress'])
    col4.metric("Erledigt", stats['done'])
    
    st.markdown("---")
    
    with st.expander("Neue Task erstellen"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Titel")
            desc = st.text_area("Beschreibung")
            company = st.text_input("Unternehmen (optional)")
        with col2:
            priority = st.selectbox("Priorität", ["P1", "P2", "P3", "P4"])
            category = st.selectbox("Kategorie", ["UAE", "GERMANY", "SWITZERLAND", "UK", "OUTREACH", "CONTENT", "RESEARCH"])
        
        if st.button("Task erstellen", type="primary"):
            from models import Task
            task = Task(None, title, desc, "todo", priority, category, company if company else None)
            task_manager.create_task(task)
            st.success("Erstellt!")
            st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["Zu erledigen", "In Arbeit", "Erledigt"])
    
    with tab1:
        for task in task_manager.get_tasks(status='todo'):
            col1, col2, col3 = st.columns([0.05, 0.75, 0.2])
            with col1:
                if st.checkbox("", key=f"td_{task.id}", label_visibility="collapsed"):
                    task_manager.update_task_status(task.id, 'done')
                    st.rerun()
            with col2:
                priority_dot = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🟢"}
                st.markdown(f"**{task.title}** {priority_dot.get(task.priority, '')}")
                if task.description:
                    st.caption(task.description)
                if task.target_company:
                    st.caption(f"🏢 {task.target_company}")
            with col3:
                if st.button("Starten", key=f"start_{task.id}"):
                    task_manager.update_task_status(task.id, 'in_progress')
                    st.rerun()
    
    with tab2:
        for task in task_manager.get_tasks(status='in_progress'):
            col1, col2, col3 = st.columns([0.05, 0.75, 0.2])
            with col1:
                if st.checkbox("", key=f"ip_{task.id}", label_visibility="collapsed"):
                    task_manager.update_task_status(task.id, 'done')
                    st.rerun()
            with col2:
                st.markdown(f"**{task.title}**")
            with col3:
                if st.button("Pausieren", key=f"pause_{task.id}"):
                    task_manager.update_task_status(task.id, 'todo')
                    st.rerun()
    
    with tab3:
        tasks = task_manager.get_tasks(status='done')
        st.success(f"{len(tasks)} erledigt")
        for task in tasks:
            st.markdown(f"~~{task.title}~~")

elif page == "Import":
    st.markdown("# Import")
    st.info("CSV mit Chorus One Prospects hochladen")
    
    uploaded = st.file_uploader("CSV auswählen", type=['csv'])
    if uploaded:
        df_import = pd.read_csv(uploaded)
        st.write(f"{len(df_import)} Zeilen gefunden")
        st.dataframe(df_import.head(), use_container_width=True)
        
        if st.button("Importieren", type="primary"):
            count = 0
            for _, row in df_import.iterrows():
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
            st.success(f"{count} Leads importiert!")

elif page == "MEDDPICC":
    st.markdown("# MEDDPICC Scoring")
    
    if df.empty:
        st.info("Keine Leads verfügbar.")
    else:
        company = st.selectbox("Unternehmen auswählen", df['Company'].tolist())
        
        if company:
            lead_row = df[df['Company'] == company].iloc[0]
            current = db.get_meddpicc_score(lead_row['ID'])
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("### Elemente bewerten")
                
                cols = st.columns(2)
                with cols[0]:
                    metrics = st.slider("Metrics", 0, 10, current.metrics if current else 0)
                    economic = st.slider("Economic Buyer", 0, 10, current.economic_buyer if current else 0)
                    process = st.slider("Decision Process", 0, 10, current.decision_process if current else 0)
                    criteria = st.slider("Decision Criteria", 0, 10, current.decision_criteria if current else 0)
                with cols[1]:
                    paper = st.slider("Paper Process", 0, 10, current.paper_process if current else 0)
                    pain = st.slider("Pain", 0, 10, current.pain if current else 0)
                    champion = st.slider("Champion", 0, 10, current.champion if current else 0)
                    competition = st.slider("Competition", 0, 10, current.competition if current else 0)
                
                total = metrics + economic + process + criteria + paper + pain + champion + competition
                status = "QUALIFIED" if total >= 70 else "PROBABLE" if total >= 50 else "POSSIBLE" if total >= 30 else "UNQUALIFIED"
                
                if st.button("Speichern", type="primary"):
                    new_score = MEDDPICCScore(
                        lead_id=lead_row['ID'], metrics=metrics, economic_buyer=economic,
                        decision_process=process, decision_criteria=criteria,
                        paper_process=paper, pain=pain, champion=champion, competition=competition
                    )
                    db.set_meddpicc_score(lead_row['ID'], new_score)
                    st.success(f"Gespeichert! {total}/80")
            
            with col2:
                st.markdown("### Ergebnis")
                
                fig = go.Figure(go.Indicator(
                    mode="gauge+number", 
                    value=total,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': f"MEDDPICC<br><span style='font-size:0.7em; color:#666'>{status}</span>"},
                    gauge={
                        'axis': {'range': [None, 80]}, 
                        'bar': {'color': "#2563eb"},
                        'steps': [
                            {'range': [0, 30], 'color': "#f3f4f6"}, 
                            {'range': [30, 50], 'color': "#fee2e2"},
                            {'range': [50, 70], 'color': "#dbeafe"}, 
                            {'range': [70, 80], 'color': "#dcfce7"}
                        ]
                    }
                ))
                fig.update_layout(
                    height=250, 
                    paper_bgcolor='rgba(0,0,0,0)', 
                    font_color='#525252',
                    margin=dict(t=40, b=20, l=20, r=20)
                )
                st.plotly_chart(fig, use_container_width=True)

elif page == "Neuer Lead":
    st.markdown("# Neuer Lead")
    
    with st.form("add_lead"):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("Unternehmen *")
            region = st.selectbox("Region", ['DE', 'CH', 'UK', 'UAE'])
            contact = st.text_input("Kontakt Name")
        with col2:
            title = st.text_input("Titel")
            linkedin = st.text_input("LinkedIn URL")
            stage = st.selectbox("Stage", ['prospecting', 'discovery', 'solutioning', 'validation'])
        
        if st.form_submit_button("Lead erstellen", type="primary"):
            if company:
                lead = Lead(
                    id=None, company=company, region=Region(region), tier=Tier(2),
                    aum_estimate_millions=0, contact_person=contact, title=title,
                    linkedin=linkedin if linkedin else None, stage=Stage(stage)
                )
                lid = db.create_lead(lead)
                db.set_meddpicc_score(lid, MEDDPICCScore(lead_id=lid))
                st.success(f"Erstellt: {company}")
            else:
                st.error("Unternehmen ist erforderlich")
