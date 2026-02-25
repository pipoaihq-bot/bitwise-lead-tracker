import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Page config
st.set_page_config(
    page_title="Bitwise EMEA | Lead Tracker",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# RUHIGES, MINIMALISTISCHES DESIGN + ALERT STYLES
st.markdown("""
<style>
    .stApp { background: #fafafa; }
    
    h1 { color: #1a1a1a; font-size: 1.75rem; font-weight: 500; letter-spacing: -0.02em; margin-bottom: 1.5rem; }
    h2 { color: #333; font-size: 1.125rem; font-weight: 500; margin-top: 2rem; margin-bottom: 1rem; }
    h3 { color: #444; font-size: 0.9375rem; font-weight: 500; }
    
    section[data-testid="stSidebar"] { background: #f5f5f5; border-right: 1px solid #e5e5e5; }
    section[data-testid="stSidebar"] .stMarkdown { color: #666; }
    
    .metric-container { background: white; border: 1px solid #e8e8e8; border-radius: 8px; padding: 1.25rem; transition: box-shadow 0.2s; }
    .metric-container:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
    .metric-value { font-size: 1.5rem; font-weight: 600; color: #1a1a1a; letter-spacing: -0.02em; }
    .metric-label { font-size: 0.8125rem; color: #737373; margin-top: 0.25rem; }
    
    .alert-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
        margin-left: 8px;
    }
    .alert-critical { background: #fee2e2; color: #dc2626; }
    .alert-warning { background: #fef3c7; color: #d97706; }
    
    .priority-card {
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        border-left: 3px solid #dc2626;
        transition: all 0.2s;
    }
    .priority-card:hover {
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border-left-width: 4px;
    }
    .priority-card.warning { border-left-color: #f59e0b; }
    
    .stale-indicator {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.6875rem;
        font-weight: 500;
    }
    .stale-hot { background: #fee2e2; color: #dc2626; }
    .stale-warm { background: #fef3c7; color: #d97706; }
    .stale-cold { background: #f3f4f6; color: #6b7280; }
    
    .stButton > button[type="primary"] { background: #2563eb; color: white; border: none; border-radius: 6px; font-weight: 500; transition: all 0.2s; }
    .stButton > button[type="primary"]:hover { background: #1d4ed8; }
    
    .stButton > button:not([type="primary"]) { background: white; border: 1px solid #d4d4d4; color: #525252; border-radius: 6px; }
    
    .stDataFrame { border: 1px solid #e5e5e5; border-radius: 8px; }
    
    .stTabs [data-baseweb="tab"] { background: transparent; color: #737373; border-bottom: 2px solid transparent; }
    .stTabs [aria-selected="true"] { background: transparent !important; color: #1a1a1a !important; border-bottom: 2px solid #2563eb !important; font-weight: 500; }
    
    .stTextInput input, .stSelectbox select, .stTextArea textarea { border-color: #d4d4d4 !important; border-radius: 6px !important; }
    .stTextInput input:focus, .stSelectbox select:focus { border-color: #2563eb !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important; }
    
    hr { border-color: #e5e5e5; margin: 1.5rem 0; }
    
    .streamlit-expanderHeader { background: white; border: 1px solid #e5e5e5; border-radius: 6px; }
    
    .stCaption { color: #a3a3a3 !important; }
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

# ============================================
# ALERT SYSTEM FUNCTIONS
# ============================================

def get_leads_with_activity_df():
    """Enhanced DataFrame with last activity info"""
    if not leads:
        return pd.DataFrame()
    
    data = []
    with db.get_connection() as conn:
        for lead in leads:
            meddpicc = db.get_meddpicc_score(lead.id)
            
            # Get last activity
            activity_row = conn.execute("""
                SELECT activity_type, created_at 
                FROM activities 
                WHERE lead_id = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (lead.id,)).fetchone()
            
            if activity_row:
                last_activity = activity_row['created_at']
                last_activity_type = activity_row['activity_type']
            else:
                last_activity = lead.updated_at or lead.created_at
                last_activity_type = 'No Activity'
            
            # Parse datetime
            if isinstance(last_activity, str):
                try:
                    last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                except:
                    last_activity = datetime.now()
            
            days_since = (datetime.now() - last_activity).days if last_activity else 999
            
            # Determine status
            if days_since <= 2:
                activity_status = 'recent'
                status_label = 'Aktiv'
            elif days_since <= 7:
                activity_status = 'warm'
                status_label = f'{days_since} Tage'
            else:
                activity_status = 'stale'
                status_label = f'{days_since} Tage 🚨' if days_since > 14 else f'{days_since} Tage'
            
            data.append({
                'ID': lead.id,
                'Company': lead.company,
                'Region': str(lead.region),
                'Industry': lead.industry,
                'Stage': str(lead.stage),
                'MEDDPICC': meddpicc.total_score if meddpicc else 0,
                'Qualification': meddpicc.qualification_status if meddpicc else 'UNQUALIFIED',
                'Readiness': lead.staking_readiness,
                'Last Activity': last_activity_type,
                'Days Inactive': days_since,
                'Activity Status': activity_status,
                'Status Label': status_label,
                'Contact': lead.contact_person,
                'LinkedIn': lead.linkedin,
                'Deal Size': lead.expected_deal_size_millions,
            })
    
    return pd.DataFrame(data)

def get_priority_alerts(df):
    """Get high priority leads needing attention"""
    if df.empty:
        return []
    
    alerts = []
    
    # High MEDDPICC + Stale
    high_score_stale = df[
        (df['MEDDPICC'] >= 60) & 
        (df['Days Inactive'] >= 3) &
        (~df['Stage'].isin(['closed_won', 'closed_lost']))
    ].sort_values(['MEDDPICC', 'Days Inactive'], ascending=[False, False])
    
    for _, lead in high_score_stale.head(3).iterrows():
        alerts.append({
            'type': 'critical',
            'company': lead['Company'],
            'region': lead['Region'],
            'meddpicc': lead['MEDDPICC'],
            'days': lead['Days Inactive'],
            'stage': lead['Stage'],
            'contact': lead['Contact'],
            'message': f"MEDDPICC {lead['MEDDPICC']}/80 aber {lead['Days Inactive']} Tage inaktiv"
        })
    
    # Churn risks
    churn_risks = df[
        (df['MEDDPICC'] >= 50) & 
        (df['Days Inactive'] >= 7) &
        (~df['Stage'].isin(['closed_won', 'closed_lost']))
    ].sort_values('Days Inactive', ascending=False)
    
    for _, lead in churn_risks.head(2).iterrows():
        if lead['Company'] not in [a['company'] for a in alerts]:
            alerts.append({
                'type': 'warning',
                'company': lead['Company'],
                'region': lead['Region'],
                'meddpicc': lead['MEDDPICC'],
                'days': lead['Days Inactive'],
                'stage': lead['Stage'],
                'contact': lead['Contact'],
                'message': f"Churn Risk: {lead['Days Inactive']} Tage keine Activity"
            })
    
    return alerts

def get_stats_with_alerts(df):
    """Get stats including alert counts"""
    if df.empty:
        return {'total': 0, 'qualified': 0, 'stale': 0, 'critical': 0, 'pipeline': 0}
    
    qualified = len(df[(df['MEDDPICC'] >= 50) & (~df['Stage'].isin(['closed_won', 'closed_lost']))])
    stale = len(df[df['Days Inactive'] >= 7])
    critical = len(df[
        (df['MEDDPICC'] >= 60) & 
        (df['Days Inactive'] >= 3) &
        (~df['Stage'].isin(['closed_won', 'closed_lost']))
    ])
    
    pipeline = df[~df['Stage'].isin(['closed_won', 'closed_lost'])]['Deal Size'].sum()
    
    return {
        'total': len(df),
        'qualified': qualified,
        'stale': stale,
        'critical': critical,
        'pipeline': pipeline
    }

# Load enhanced data
df = get_leads_with_activity_df()
alerts = get_priority_alerts(df)
stats = get_stats_with_alerts(df)

# ============================================
# SIDEBAR MIT ALERT BADGES
# ============================================

with st.sidebar:
    st.markdown("### ◆ Bitwise EMEA")
    st.markdown("<span style='color: #737373; font-size: 0.8125rem;'>Onchain Solutions</span>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Navigation mit Alert-Indikatoren
    st.markdown("**Navigation**")
    
    # Alert Badge anzeigen wenn es Prioritäten gibt
    alert_indicator = f" 🔴 {stats['critical']}" if stats['critical'] > 0 else ""
    
    page = st.radio("", [
        f"Übersicht",
        f"Prioritäten{alert_indicator}",
        "Pipeline",
        "Tasks",
        "Import",
        "MEDDPICC",
        "Neuer Lead"
    ], label_visibility="collapsed")
    
    st.markdown("---")
    
    # Quick Stats
    st.markdown("**Kurzübersicht**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div style='font-size: 1.25rem; font-weight: 600;'>{stats['total']:,}</div>", unsafe_allow_html=True)
        st.markdown("<span style='color: #737373; font-size: 0.75rem;'>Leads</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='font-size: 1.25rem; font-weight: 600;'>{stats['qualified']}</div>", unsafe_allow_html=True)
        st.markdown("<span style='color: #737373; font-size: 0.75rem;'>Qualifiziert</span>", unsafe_allow_html=True)
    
    st.markdown("")
    
    # ALERT BADGES
    if stats['critical'] > 0:
        st.markdown(f"""
        <div class='alert-badge alert-critical'>
            🚨 {stats['critical']} Dringend
        </div>
        """, unsafe_allow_html=True)
    
    if stats['stale'] > 0:
        st.markdown(f"""
        <div class='alert-badge alert-warning'>
            😴 {stats['stale']} Inaktiv
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("")
    
    col3, col4 = st.columns(2)
    with col3:
        todo = len([t for t in task_manager.get_tasks(status='todo')])
        st.markdown(f"<div style='font-size: 1.25rem; font-weight: 600;'>{todo}</div>", unsafe_allow_html=True)
        st.markdown("<span style='color: #737373; font-size: 0.75rem;'>Offene Tasks</span>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div style='font-size: 1.25rem; font-weight: 600;'>€{stats['pipeline']:.0f}M</div>", unsafe_allow_html=True)
        st.markdown("<span style='color: #737373; font-size: 0.75rem;'>Pipeline</span>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Recent Top Qualified
    st.markdown("**Top Qualifizierte**")
    if not df.empty:
        top_qualified = df[df['MEDDPICC'] >= 50].nlargest(3, 'MEDDPICC')
        for _, lead in top_qualified.iterrows():
            stale_icon = "🚨" if lead['Days Inactive'] >= 7 else ""
            st.markdown(f"""
            <div style='font-size: 0.8125rem; margin-bottom: 0.5rem;'>
                <div style='font-weight: 500;'>{lead['Company']} {stale_icon}</div>
                <div style='color: #737373;'>{lead['MEDDPICC']}/80 • {lead['Region']} • {lead['Status Label']}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("<span style='color: #a3a3a3; font-size: 0.75rem;'>v2.1 • {}</span>".format(datetime.now().strftime('%d.%m.%Y')), unsafe_allow_html=True)

# Rest des Codes... (gekürzt für Übersichtlichkeit)
# ============================================
# PAGES
# ============================================

if page.startswith("Übersicht"):
    st.markdown("# Übersicht")
    
    # Quick Alert Banner
    if alerts:
        with st.container():
            st.markdown("### 🚨 Heute priorisieren")
            for alert in alerts[:2]:
                color_class = "priority-card" if alert['type'] == 'critical' else "priority-card warning"
                st.markdown(f"""
                <div class='{color_class}'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div>
                            <strong>{alert['company']}</strong> ({alert['region']})<br/>
                            <span style='color: #737373; font-size: 0.8125rem;'>{alert['message']}</span>
                        </div>
                        <div style='text-align: right;'>
                            <span style='font-size: 1.25rem;'>{alert['meddpicc']}/80</span><br/>
                            <span style='color: #737373; font-size: 0.75rem;'>MEDDPICC</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            if len(alerts) > 2:
                st.caption(f"... und {len(alerts) - 2} weitere Prioritäten im 'Prioritäten' Tab")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'''<div class="metric-container">
            <div class="metric-value">{stats['total']:,}</div>
            <div class="metric-label">Gesamte Leads</div>
        </div>''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''<div class="metric-container">
            <div class="metric-value">{stats['qualified']}</div>
            <div class="metric-label">Qualifiziert</div>
        </div>''', unsafe_allow_html=True)
    with col3:
        stale_display = f"{stats['stale']}" if stats['stale'] == 0 else f"⚠️ {stats['stale']}"
        st.markdown(f'''<div class="metric-container">
            <div class="metric-value" style="{'color: #dc2626;' if stats['stale'] > 0 else ''}">{stale_display}</div>
            <div class="metric-label">Inaktiv (>7 Tage)</div>
        </div>''', unsafe_allow_html=True)
    with col4:
        st.markdown(f'''<div class="metric-container">
            <div class="metric-value">€{stats['pipeline']:.0f}M</div>
            <div class="metric-label">Pipeline Value</div>
        </div>''', unsafe_allow_html=True)
    
    st.markdown("---")
    
    if df.empty:
        st.info("Noch keine Leads vorhanden. Gehe zu **Import** um Daten hinzuzufügen.")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Leads nach Region")
            region_data = df.groupby('Region').size().reset_index(name='Count')
            colors = ['#525252', '#737373', '#a3a3a3', '#d4d4d4']
            fig = px.pie(region_data, values='Count', names='Region', color_discrete_sequence=colors, hole=0.4)
            fig.update_layout(height=280, paper_bgcolor='rgba(0,0,0,0)', font_color='#525252', showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2), margin=dict(t=20, b=40, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### MEDDPICC Verteilung")
            score_data = df['Qualification'].value_counts().reset_index()
            score_data.columns = ['Status', 'Count']
            color_map = {'UNQUALIFIED': '#d4d4d4', 'POSSIBLE': '#fca5a5', 'PROBABLE': '#93c5fd', 'QUALIFIED': '#86efac'}
            fig = px.bar(score_data, x='Status', y='Count', color='Status', color_discrete_map=color_map)
            fig.update_layout(height=280, paper_bgcolor='rgba(0,0,0,0)', font_color='#525252', showlegend=False, xaxis_title=None, yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=20, b=40, l=20, r=20))
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
            st.plotly_chart(fig, use_container_width=True)
        
        # Recent with activity status
        st.markdown("---")
        st.markdown("### Neueste Leads")
        recent = df.sort_values('ID', ascending=False).head(10)
        
        display_df = recent[['Company', 'Region', 'Industry', 'Stage', 'MEDDPICC', 'Status Label']].copy()
        display_df.columns = ['Unternehmen', 'Region', 'Branche', 'Stage', 'MEDDPICC', 'Aktivität']
        st.dataframe(display_df, use_container_width=True, hide_index=True)

elif page.startswith("Prioritäten"):
    st.markdown("# 🚨 Prioritäten")
    st.markdown("Leads die sofortige Attention brauchen")
    
    if not alerts:
        st.success("✅ Keine dringenden Prioritäten! Alle qualifizierten Leads sind aktiv.")
    else:
        st.markdown(f"**{len(alerts)} Lead(s) brauchen Action:**")
        
        for alert in alerts:
            color_class = "priority-card" if alert['type'] == 'critical' else "priority-card warning"
            emoji = "🔥" if alert['type'] == 'critical' else "⚠️"
            
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"""
                    <div class='{color_class}'>
                        <div style='font-size: 1.125rem; font-weight: 600;'>
                            {emoji} {alert['company']} ({alert['region']})
                        </div>
                        <div style='color: #737373; margin-top: 0.25rem;'>
                            👤 {alert['contact']} | Stage: {alert['stage']}
                        </div>
                        <div style='color: #525252; margin-top: 0.5rem; font-size: 0.9375rem;'>
                            {alert['message']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with col2:
                    st.metric("MEDDPICC", f"{alert['meddpicc']}/80")
                with col3:
                    if st.button("Aktion", key=f"act_{alert['company']}"):
                        st.info(f"Empfohlene Aktion: Kontaktiere {alert['contact']}")
        
        # Churn Risk Section
        st.markdown("---")
        st.markdown("### 😴 Schlummernde Deals")
        st.markdown("Qualifizierte Leads (>50 MEDDPICC) ohne Activity seit 7+ Tagen")
        
        churn_df = df[
            (df['MEDDPICC'] >= 50) & 
            (df['Days Inactive'] >= 7) &
            (~df['Stage'].isin(['closed_won', 'closed_lost']))
        ].sort_values('Days Inactive', ascending=False)
        
        if churn_df.empty:
            st.info("Keine schlummernden Deals – alle qualifizierten Leads sind aktiv!")
        else:
            st.dataframe(
                churn_df[['Company', 'Region', 'MEDDPICC', 'Days Inactive', 'Stage', 'Contact']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Days Inactive': st.column_config.NumberColumn("Tage inaktiv", help="Tage seit letzter Activity"),
                    'MEDDPICC': st.column_config.ProgressColumn("MEDDPICC", format="%d", min_value=0, max_value=80),
                }
            )

elif page == "Pipeline":
    st.markdown("# Pipeline")
    
    if df.empty:
        st.info("Keine Leads verfügbar.")
    else:
        # Quick Filters
        st.markdown("**Schnellfilter:**")
        
        col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
        
        with col1:
            show_stale = st.checkbox("🚨 Nur Inaktive", key="filter_stale")
        with col2:
            show_qualified = st.checkbox("✅ Nur Qualifizierte", key="filter_qualified")
        with col3:
            show_hot = st.checkbox("🔥 Top MEDDPICC", key="filter_hot")
        
        # Apply filters
        filtered = df.copy()
        
        if show_stale:
            filtered = filtered[filtered['Days Inactive'] >= 7]
        if show_qualified:
            filtered = filtered[filtered['MEDDPICC'] >= 50]
        if show_hot:
            filtered = filtered.nlargest(10, 'MEDDPICC')
        
        # Manual filters
        with st.expander("🔍 Erweiterte Filter"):
            col1, col2, col3 = st.columns(3)
            with col1:
                region_filter = st.multiselect("Region", df['Region'].unique().tolist())
            with col2:
                stage_filter = st.multiselect("Stage", df['Stage'].unique().tolist())
            with col3:
                min_meddpicc = st.slider("Min. MEDDPICC", 0, 80, 0)
        
        if region_filter:
            filtered = filtered[filtered['Region'].isin(region_filter)]
        if stage_filter:
            filtered = filtered[filtered['Stage'].isin(stage_filter)]
        if min_meddpicc > 0:
            filtered = filtered[filtered['MEDDPICC'] >= min_meddpicc]
        
        # Activity filter dropdown
        activity_filter = st.selectbox(
            "Aktivitäts-Filter",
            ["Alle", "🟢 Aktiv (<3 Tage)", "🟡 Warm (3-7 Tage)", "🔴 Inaktiv (>7 Tage)"],
            label_visibility="collapsed"
        )
        
        if activity_filter == "🟢 Aktiv (<3 Tage)":
            filtered = filtered[filtered['Days Inactive'] < 3]
        elif activity_filter == "🟡 Warm (3-7 Tage)":
            filtered = filtered[(filtered['Days Inactive'] >= 3) & (filtered['Days Inactive'] <= 7)]
        elif activity_filter == "🔴 Inaktiv (>7 Tage)":
            filtered = filtered[filtered['Days Inactive'] > 7]
        
        st.markdown(f"**{len(filtered)} von {len(df)} Leads**")
        
        # Display with activity indicators
        display_cols = ['Company', 'Region', 'Industry', 'Stage', 'MEDDPICC', 'Status Label', 'Last Activity']
        display_df = filtered[display_cols].copy()
        display_df.columns = ['Unternehmen', 'Region', 'Branche', 'Stage', 'MEDDPICC', 'Inaktiv', 'Letzte Activity']
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                'MEDDPICC': st.column_config.ProgressColumn("MEDDPICC", format="%d/80", min_value=0, max_value=80),
                'Inaktiv': st.column_config.Column("Inaktivität", help="Tage seit letzter Activity"),
            }
        )

elif page == "Tasks":
    st.markdown("# Tasks")
    
    stats_task = task_manager.get_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gesamt", stats_task['total'])
    col2.metric("Offen", stats_task['todo'])
    col3.metric("In Arbeit", stats_task['in_progress'])
    col4.metric("Erledigt", stats_task['done'])

# Weitere Pages... (gekürzt für diesen Output)
