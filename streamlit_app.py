import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

# Streamlit Cloud compatible paths
@st.cache_resource
def get_database():
    """Initialize database with Streamlit Cloud compatible path"""
    from database import Database
    
    # Use Streamlit's persistent storage
    db_path = os.path.join(st.session_state.get('data_dir', '.'), 'bitwise_leads.db')
    db = Database(db_path)
    
    # Verify enrichment data exists
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM leads WHERE industry IS NOT NULL")
        count = cursor.fetchone()[0]
        st.sidebar.text(f"DB: {count} leads with industry data")
    
    return db

# Ensure data directory exists in session state
if 'data_dir' not in st.session_state:
    st.session_state.data_dir = '.'

# Page config
st.set_page_config(
    page_title="Bitwise EMEA Lead Tracker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .meddpicc-high { color: #2ecc71; font-weight: bold; }
    .meddpicc-medium { color: #f39c12; font-weight: bold; }
    .meddpicc-low { color: #e74c3c; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Initialize database
db = get_database()

# Helper functions
def get_meddpicc_class(score):
    if score >= 70:
        return "meddpicc-high"
    elif score >= 50:
        return "meddpicc-medium"
    else:
        return "meddpicc-low"

def load_leads_df():
    """Load all leads as DataFrame with enriched data"""
    from models import Region, Tier, Stage
    
    leads = db.get_all_leads()
    if not leads:
        return pd.DataFrame()
    
    data = []
    for lead in leads:
        meddpicc = db.get_meddpicc_score(lead.id)
        
        # Get enriched fields (may not exist in old leads)
        industry = getattr(lead, 'industry', '') or ''
        employee_count = getattr(lead, 'employee_count', '') or ''
        company_type = getattr(lead, 'company_type', '') or ''
        staking_readiness = getattr(lead, 'staking_readiness', '') or ''
        tech_stack = getattr(lead, 'tech_stack', '') or ''
        sub_region = getattr(lead, 'sub_region', '') or ''
        
        data.append({
            'ID': lead.id,
            'Company': lead.company,
            'Region': lead.region.value if hasattr(lead.region, 'value') else lead.region,
            'Sub Region': sub_region,
            'Tier': lead.tier.value if hasattr(lead.tier, 'value') else lead.tier,
            'AUM (M€)': lead.aum_estimate_millions,
            'Contact': lead.contact_person,
            'Title': lead.title,
            'Email': lead.email or '',
            'LinkedIn': lead.linkedin or '',
            'Stage': lead.stage.value if hasattr(lead.stage, 'value') else lead.stage,
            'Deal Size (M€)': lead.expected_deal_size_millions,
            'Expected Yield %': lead.expected_yield,
            'Industry': industry,
            'Employee Count': employee_count,
            'Company Type': company_type,
            'Staking Readiness': staking_readiness,
            'Tech Stack': tech_stack,
            'Pain Points': lead.pain_points,
            'Use Case': lead.use_case,
            'MEDDPICC Score': meddpicc.total_score if meddpicc else 0,
            'Qualification': meddpicc.qualification_status if meddpicc else 'UNQUALIFIED',
            'Created': lead.created_at
        })
    return pd.DataFrame(data)

# Sidebar
st.sidebar.markdown("## 🎯 Bitwise EMEA")
st.sidebar.markdown("### Lead Tracker Dashboard")
st.sidebar.markdown("---")

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "📋 Lead Pipeline", "🎯 MEDDPICC Scoring", "➕ Add New Lead", "📝 Activities"]
)

# Load data
df = load_leads_df()

# DASHBOARD PAGE
if page == "📊 Dashboard":
    st.markdown('<p class="main-header">Bitwise EMEA Dashboard</p>', unsafe_allow_html=True)
    st.markdown("Head of Onchain Solutions — $1B Target Pipeline")
    st.markdown("---")
    
    if df.empty:
        st.info("No leads in the system yet. Go to 'Add New Lead' to get started!")
    else:
        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_leads = len(df)
            st.metric("Total Leads", total_leads)
        
        with col2:
            total_pipeline = df[df['Stage'] != 'closed_lost']['Deal Size (M€)'].sum()
            st.metric("Pipeline Value", f"€{total_pipeline:.0f}M")
        
        with col3:
            qualified_deals = len(df[df['MEDDPICC Score'] >= 50])
            st.metric("Qualified Deals", qualified_deals)
        
        with col4:
            avg_score = df['MEDDPICC Score'].mean() if len(df) > 0 else 0
            st.metric("Avg MEDDPICC", f"{avg_score:.0f}/80")
        
        st.markdown("---")
        
        # Charts Row 1
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Pipeline by Stage")
            stage_data = df[df['Stage'] != 'closed_lost'].groupby('Stage').agg({
                'Deal Size (M€)': 'sum',
                'ID': 'count'
            }).reset_index()
            stage_data.columns = ['Stage', 'Value', 'Count']
            
            if not stage_data.empty:
                fig = px.funnel(stage_data, x='Value', y='Stage', color='Stage',
                              title="Pipeline Value by Stage (€M)")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Pipeline by Region")
            region_data = df[df['Stage'] != 'closed_lost'].groupby('Region').agg({
                'Deal Size (M€)': 'sum',
                'ID': 'count'
            }).reset_index()
            region_data.columns = ['Region', 'Value', 'Count']
            
            if not region_data.empty:
                fig = px.pie(region_data, values='Value', names='Region',
                            title="Pipeline Distribution by Region")
                st.plotly_chart(fig, use_container_width=True)
        
        # Charts Row 2 - NEW: Industry breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Leads by Industry")
            if 'Industry' in df.columns:
                industry_data = df[df['Industry'].notna()].groupby('Industry').agg({
                    'ID': 'count'
                }).reset_index()
                industry_data.columns = ['Industry', 'Count']
                industry_data = industry_data.sort_values('Count', ascending=False).head(10)
                
                if not industry_data.empty:
                    fig = px.bar(industry_data, x='Industry', y='Count', 
                                color='Industry', title="Top 10 Industries")
                    st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Staking Readiness")
            if 'Staking Readiness' in df.columns:
                readiness_data = df[df['Staking Readiness'].notna()].groupby('Staking Readiness').agg({
                    'ID': 'count'
                }).reset_index()
                readiness_data.columns = ['Readiness', 'Count']
                
                if not readiness_data.empty:
                    colors = {'High': '#2ecc71', 'Medium': '#f39c12', 'Low': '#e74c3c'}
                    fig = px.pie(readiness_data, values='Count', names='Readiness',
                                color='Readiness', color_discrete_map=colors,
                                title="Staking Readiness Distribution")
                    st.plotly_chart(fig, use_container_width=True)
        
        # Charts Row 3
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("MEDDPICC Score Distribution")
            score_bins = pd.cut(df['MEDDPICC Score'], bins=[0, 30, 50, 70, 80], 
                               labels=['Unqualified', 'Possible', 'Probable', 'Qualified'])
            score_counts = score_bins.value_counts().reset_index()
            score_counts.columns = ['Status', 'Count']
            
            colors = {'Unqualified': '#e74c3c', 'Possible': '#f39c12', 
                     'Probable': '#3498db', 'Qualified': '#2ecc71'}
            
            fig = px.bar(score_counts, x='Status', y='Count', color='Status',
                        color_discrete_map=colors, title="Deal Qualification Status")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Deal Size vs MEDDPICC Score")
            fig = px.scatter(df, x='MEDDPICC Score', y='Deal Size (M€)', 
                           color='Region', size='AUM (M€)',
                           hover_data=['Company', 'Stage'],
                           title="Deal Quality vs Size")
            fig.add_hline(y=10, line_dash="dash", line_color="gray", 
                         annotation_text="€10M Threshold")
            fig.add_vline(x=50, line_dash="dash", line_color="gray",
                         annotation_text="Qualification Threshold")
            st.plotly_chart(fig, use_container_width=True)
        
        # Top Opportunities
        st.markdown("---")
        st.subheader("🏆 Top Opportunities (Qualified Deals)")
        
        qualified = df[df['MEDDPICC Score'] >= 50].sort_values('Deal Size (M€)', ascending=False)
        if not qualified.empty:
            display_cols = ['Company', 'Region', 'Industry', 'Stage', 'Deal Size (M€)', 
                           'MEDDPICC Score', 'Staking Readiness', 'Qualification']
            display_cols = [col for col in display_cols if col in qualified.columns]
            st.dataframe(qualified[display_cols].head(10),
                        use_container_width=True)
        else:
            st.info("No qualified deals yet. Update MEDDPICC scores to qualify deals.")

# PIPELINE PAGE
elif page == "📋 Lead Pipeline":
    st.markdown('<p class="main-header">Lead Pipeline</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    if df.empty:
        st.info("No leads in the system yet.")
    else:
        # Advanced Filters
        st.subheader("🔍 Filters")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            region_filter = st.multiselect("Region", df['Region'].unique().tolist())
            industry_filter = st.multiselect("Industry", 
                                            df['Industry'].dropna().unique().tolist() if 'Industry' in df.columns else [])
            stage_filter = st.multiselect("Stage", df['Stage'].unique().tolist())
        
        with col2:
            tier_filter = st.multiselect("Tier", df['Tier'].unique().tolist())
            employee_filter = st.multiselect("Employee Count", 
                                            df['Employee Count'].dropna().unique().tolist() if 'Employee Count' in df.columns else [])
            company_type_filter = st.multiselect("Company Type", 
                                               df['Company Type'].dropna().unique().tolist() if 'Company Type' in df.columns else [])
        
        with col3:
            min_meddpicc = st.slider("Min MEDDPICC Score", 0, 80, 0)
            staking_filter = st.multiselect("Staking Readiness", 
                                          df['Staking Readiness'].dropna().unique().tolist() if 'Staking Readiness' in df.columns else [])
            tech_filter = st.multiselect("Tech Stack", 
                                       df['Tech Stack'].dropna().unique().tolist() if 'Tech Stack' in df.columns else [])
        
        # Search box
        search_term = st.text_input("🔎 Search Companies", placeholder="Type company name...")
        
        # Apply filters
        filtered_df = df.copy()
        
        if region_filter:
            filtered_df = filtered_df[filtered_df['Region'].isin(region_filter)]
        if industry_filter:
            filtered_df = filtered_df[filtered_df['Industry'].isin(industry_filter)]
        if stage_filter:
            filtered_df = filtered_df[filtered_df['Stage'].isin(stage_filter)]
        if tier_filter:
            filtered_df = filtered_df[filtered_df['Tier'].isin(tier_filter)]
        if employee_filter:
            filtered_df = filtered_df[filtered_df['Employee Count'].isin(employee_filter)]
        if company_type_filter:
            filtered_df = filtered_df[filtered_df['Company Type'].isin(company_type_filter)]
        if staking_filter:
            filtered_df = filtered_df[filtered_df['Staking Readiness'].isin(staking_filter)]
        if tech_filter:
            filtered_df = filtered_df[filtered_df['Tech Stack'].isin(tech_filter)]
        if min_meddpicc > 0:
            filtered_df = filtered_df[filtered_df['MEDDPICC Score'] >= min_meddpicc]
        if search_term:
            filtered_df = filtered_df[filtered_df['Company'].str.contains(search_term, case=False, na=False)]
        
        # Summary stats
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Filtered Leads", len(filtered_df))
        with col2:
            st.metric("Pipeline Value", f"€{filtered_df['Deal Size (M€)'].sum():.0f}M")
        with col3:
            high_readiness = len(filtered_df[filtered_df['Staking Readiness'] == 'High']) if 'Staking Readiness' in filtered_df.columns else 0
            st.metric("High Readiness", high_readiness)
        with col4:
            qualified = len(filtered_df[filtered_df['MEDDPICC Score'] >= 50])
            st.metric("Qualified", qualified)
        
        st.markdown("---")
        
        # Display leads table
        display_cols = ['Company', 'Region', 'Industry', 'Tier', 'Stage', 'Deal Size (M€)', 
                       'MEDDPICC Score', 'Staking Readiness', 'Qualification']
        
        # Only show columns that exist
        display_cols = [col for col in display_cols if col in filtered_df.columns]
        
        display_df = filtered_df[display_cols].copy()
        
        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={
                'MEDDPICC Score': st.column_config.ProgressColumn(
                    "MEDDPICC",
                    help="MEDDPICC qualification score",
                    format="%d/80",
                    min_value=0,
                    max_value=80,
                ),
                'Deal Size (M€)': st.column_config.NumberColumn(format="€%.0fM"),
            }
        )

# MEDDPICC PAGE
elif page == "🎯 MEDDPICC Scoring":
    st.markdown('<p class="main-header">MEDDPICC Scoring</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    if df.empty:
        st.info("No leads in the system yet.")
    else:
        selected_lead_id = st.selectbox("Select Lead to Score", 
                                       df['ID'].tolist(),
                                       format_func=lambda x: f"{df[df['ID']==x]['Company'].values[0]} (ID: {x})")
        
        if selected_lead_id:
            lead_row = df[df['ID'] == selected_lead_id].iloc[0]
            current_score = db.get_meddpicc_score(selected_lead_id)
            
            st.markdown(f"### Scoring: {lead_row['Company']}")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("#### Score Each Element (0-10)")
                
                metrics = st.slider("Metrics (Quantified Business Case)", 0, 10, 
                                   current_score.metrics if current_score else 0)
                economic_buyer = st.slider("Economic Buyer (Access to decision maker)", 0, 10,
                                          current_score.economic_buyer if current_score else 0)
                decision_process = st.slider("Decision Process (Clear path)", 0, 10,
                                            current_score.decision_process if current_score else 0)
                decision_criteria = st.slider("Decision Criteria (Known requirements)", 0, 10,
                                             current_score.decision_criteria if current_score else 0)
                paper_process = st.slider("Paper Process (Contract clarity)", 0, 10,
                                         current_score.paper_process if current_score else 0)
                pain = st.slider("Pain (Validated urgency)", 0, 10,
                               current_score.pain if current_score else 0)
                champion = st.slider("Champion (Internal advocate)", 0, 10,
                                   current_score.champion if current_score else 0)
                competition = st.slider("Competition (Positioned to win)", 0, 10,
                                       current_score.competition if current_score else 0)
                
                if st.button("Save MEDDPICC Score", type="primary"):
                    from models import MEDDPICCScore
                    new_score = MEDDPICCScore(
                        lead_id=selected_lead_id,
                        metrics=metrics,
                        economic_buyer=economic_buyer,
                        decision_process=decision_process,
                        decision_criteria=decision_criteria,
                        paper_process=paper_process,
                        pain=pain,
                        champion=champion,
                        competition=competition
                    )
                    db.set_meddpicc_score(selected_lead_id, new_score)
                    st.success(f"MEDDPICC score saved! Total: {new_score.total_score}/80 ({new_score.qualification_status})")
                    st.rerun()
            
            with col2:
                if current_score:
                    total = current_score.total_score
                    st.markdown("### Current Score")
                    
                    fig = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = total,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': "MEDDPICC Score"},
                        gauge = {
                            'axis': {'range': [None, 80]},
                            'bar': {'color': "darkblue"},
                            'steps': [
                                {'range': [0, 30], 'color': "#e74c3c"},
                                {'range': [30, 50], 'color': "#f39c12"},
                                {'range': [50, 70], 'color': "#3498db"},
                                {'range': [70, 80], 'color': "#2ecc71"}
                            ],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': 50
                            }
                        }
                    ))
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)

# ADD LEAD PAGE
elif page == "➕ Add New Lead":
    st.markdown('<p class="main-header">Add New Lead</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    with st.form("new_lead_form"):
        from models import Region, Tier, Stage
        
        col1, col2 = st.columns(2)
        
        with col1:
            company = st.text_input("Company Name *", placeholder="DWS Group")
            region = st.selectbox("Region *", ['DE', 'CH', 'UK', 'UAE', 'NORDICS'])
            tier = st.selectbox("Tier *", [1, 2, 3, 4], 
                               format_func=lambda x: f"Tier {x}: {'€50B+' if x==1 else '€10-50B' if x==2 else '€1-10B' if x==3 else '<€1B'}")
            aum = st.number_input("AUM Estimate (M€) *", min_value=0.0, value=100.0, step=10.0)
        
        with col2:
            contact = st.text_input("Contact Name *", placeholder="Max Mustermann")
            title = st.text_input("Contact Title *", placeholder="CIO Alternatives")
            email = st.text_input("Email", placeholder="max@company.com")
            linkedin = st.text_input("LinkedIn URL", placeholder="https://linkedin.com/in/...")
        
        stage = st.selectbox("Initial Stage", 
                            ['prospecting', 'discovery', 'solutioning', 
                             'validation', 'negotiation', 'closed_won', 'closed_lost'])
        
        col1, col2 = st.columns(2)
        with col1:
            deal_size = st.number_input("Expected Deal Size (M€)", min_value=0.0, value=10.0, step=5.0)
        with col2:
            exp_yield = st.number_input("Expected Yield (%)", min_value=0.0, value=6.0, step=0.5)
        
        pain_points = st.text_area("Pain Points Identified", placeholder="Yield pressure, regulatory uncertainty...")
        use_case = st.text_area("Use Case / Opportunity", placeholder="Staking for treasury yield...")
        
        submitted = st.form_submit_button("Create Lead", type="primary")
        
        if submitted:
            if not all([company, region, contact, title]):
                st.error("Please fill in all required fields (marked with *)")
            else:
                new_lead = Lead(
                    id=None,
                    company=company,
                    region=Region(region),
                    tier=Tier(tier),
                    aum_estimate_millions=aum,
                    contact_person=contact,
                    title=title,
                    email=email or None,
                    linkedin=linkedin or None,
                    stage=Stage(stage),
                    pain_points=pain_points,
                    use_case=use_case,
                    expected_deal_size_millions=deal_size,
                    expected_yield=exp_yield
                )
                
                lead_id = db.create_lead(new_lead)
                
                from models import MEDDPICCScore
                score = MEDDPICCScore(lead_id=lead_id)
                db.set_meddpicc_score(lead_id, score)
                
                st.success(f"✅ Lead created: {company} (ID: {lead_id})")
                st.info("Go to 'MEDDPICC Scoring' to qualify this lead!")

# ACTIVITIES PAGE
elif page == "📝 Activities":
    st.markdown('<p class="main-header">Activity Tracking</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    if df.empty:
        st.info("No leads in the system yet.")
    else:
        selected_lead_id = st.selectbox("Select Lead", 
                                       df['ID'].tolist(),
                                       format_func=lambda x: f"{df[df['ID']==x]['Company'].values[0]} (ID: {x})")
        
        if selected_lead_id:
            lead_row = df[df['ID'] == selected_lead_id].iloc[0]
            st.markdown(f"### {lead_row['Company']}")
            
            activities = db.get_activities(selected_lead_id)
            
            if activities:
                st.markdown("#### Activity History")
                for act in activities:
                    with st.expander(f"{act.activity_type.upper()} — {act.created_at.strftime('%Y-%m-%d %H:%M') if act.created_at else 'N/A'}"):
                        st.markdown(f"**Outcome:** {act.outcome}")
                        st.markdown(f"**Notes:** {act.notes}")
                        if act.next_steps:
                            st.markdown(f"**Next Steps:** {act.next_steps}")
            else:
                st.info("No activities recorded yet.")
            
            st.markdown("---")
            st.markdown("#### Add New Activity")
            
            with st.form("new_activity_form"):
                activity_type = st.selectbox("Activity Type", 
                                           ['email', 'call', 'meeting', 'demo', 'proposal', 'linkedin', 'other'])
                notes = st.text_area("Notes", placeholder="What was discussed...")
                outcome = st.selectbox("Outcome", 
                                      ['positive', 'neutral', 'negative', 'scheduled', 'no_response'])
                next_steps = st.text_input("Next Steps", placeholder="Schedule follow-up...")
                
                submitted = st.form_submit_button("Add Activity", type="primary")
                
                if submitted and notes:
                    from models import Activity
                    new_activity = Activity(
                        id=None,
                        lead_id=selected_lead_id,
                        activity_type=activity_type,
                        notes=notes,
                        outcome=outcome,
                        next_steps=next_steps
                    )
                    db.add_activity(new_activity)
                    st.success("✅ Activity added!")
                    st.rerun()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Bitwise EMEA Lead Tracker v1.0**")
st.sidebar.markdown("Head of Onchain Solutions")
st.sidebar.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
