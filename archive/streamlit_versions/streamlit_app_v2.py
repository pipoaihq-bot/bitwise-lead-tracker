import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os
import io

# Streamlit Cloud compatible paths
def get_database():
    """Initialize database - no caching to ensure fresh data"""
    from database import Database
    db_path = os.path.join(st.session_state.get('data_dir', '.'), 'bitwise_leads.db')
    return Database(db_path)

if 'data_dir' not in st.session_state:
    st.session_state.data_dir = '.'

# Page config
st.set_page_config(
    page_title="Bitwise EMEA | Lead Tracker",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean, Professional Bitwise Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Main container */
    .main {
        background-color: #fafbfc;
    }
    
    /* Headers */
    h1 {
        color: #0a2540;
        font-weight: 700;
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: #0a2540;
        font-weight: 600;
        font-size: 1.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e5e7eb;
    }
    
    h3 {
        color: #374151;
        font-weight: 600;
        font-size: 1.1rem;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
    
    /* Radio buttons in sidebar */
    .stRadio > div {
        background-color: transparent;
    }
    
    .stRadio > div > label {
        padding: 0.75rem 1rem;
        margin: 0.25rem 0;
        border-radius: 8px;
        transition: all 0.2s;
    }
    
    .stRadio > div > label:hover {
        background-color: #f3f4f6;
    }
    
    /* Metric cards */
    .metric-container {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e5e7eb;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #0a2540;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #6b7280;
        margin-top: 0.25rem;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #1a9c9c;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        background-color: #158a8a;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* DataFrames */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* Filter section */
    .filter-section {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid #e5e7eb;
    }
    
    /* Upload box */
    .upload-box {
        border: 2px dashed #1a9c9c;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        background: #f0fdfa;
    }
    
    /* Status badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .badge-high {
        background-color: #d1fae5;
        color: #065f46;
    }
    
    .badge-medium {
        background-color: #fef3c7;
        color: #92400e;
    }
    
    .badge-low {
        background-color: #fee2e2;
        color: #991b1b;
    }
    
    /* MEDDPICC colors */
    .meddpicc-high { color: #059669; font-weight: 600; }
    .meddpicc-medium { color: #d97706; font-weight: 600; }
    .meddpicc-low { color: #dc2626; font-weight: 600; }
    
    /* Divider */
    hr {
        border: none;
        border-top: 1px solid #e5e7eb;
        margin: 2rem 0;
    }
    
    /* Info boxes */
    .info-box {
        background-color: #f0fdfa;
        border-left: 4px solid #1a9c9c;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Select boxes */
    .stSelectbox > div > div {
        border-radius: 8px;
    }
    
    /* Multiselect */
    .stMultiSelect > div > div {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
db = get_database()

# Check data status
leads = db.get_all_leads()
lead_count = len(leads)
sample_lead = leads[0] if leads else None
has_enrichment = sample_lead and hasattr(sample_lead, 'industry') and sample_lead.industry

# ==================== SIDEBAR ====================
with st.sidebar:
    # Logo
    try:
        st.image("assets/bitwise_logo.png", width=60)
    except:
        st.markdown("## 🔷")
    
    st.markdown("### Bitwise")
    st.markdown("**EMEA Onchain Solutions**")
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "",
        ["📊 Dashboard", "📋 Pipeline", "📁 Import Data", "🎯 MEDDPICC", "➕ Add Lead"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Data Status
    st.markdown("**Data Status**")
    if lead_count == 0:
        st.error("❌ No leads")
    elif lead_count < 100:
        st.warning(f"⚠️ {lead_count} leads")
    else:
        st.success(f"✅ {lead_count:,} leads")
        
    if has_enrichment:
        st.info("📊 Enriched")
    
    st.markdown("---")
    
    # Footer
    try:
        st.image("assets/bitwise_wordmark.jpg", width=120)
    except:
        st.markdown("**Bitwise®**")
    
    st.caption(f"v1.0 • {datetime.now().strftime('%Y-%m-%d')}")

# ==================== HELPER FUNCTIONS ====================
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
    
    if not leads:
        return pd.DataFrame()
    
    data = []
    for lead in leads:
        meddpicc = db.get_meddpicc_score(lead.id)
        
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
            'MEDDPICC Score': meddpicc.total_score if meddpicc else 0,
            'Qualification': meddpicc.qualification_status if meddpicc else 'UNQUALIFIED',
        })
    
    return pd.DataFrame(data)

def process_uploaded_csv(uploaded_file):
    """Process uploaded CSV file"""
    try:
        df = pd.read_csv(uploaded_file)
        st.success(f"✅ CSV loaded: {len(df)} rows, {len(df.columns)} columns")
        
        # Show column mapping
        st.markdown("**Column Mapping**")
        required_cols = ['Account Name', 'LinkedIn', 'Account Type']
        found_cols = [col for col in required_cols if col in df.columns]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if found_cols:
            st.success(f"Found: {', '.join(found_cols)}")
        if missing_cols:
            st.warning(f"Missing: {', '.join(missing_cols)}")
        
        return df
    except Exception as e:
        st.error(f"❌ Error reading CSV: {e}")
        return None

# ==================== PAGES ====================

# DASHBOARD PAGE
if page == "📊 Dashboard":
    st.markdown("# Dashboard")
    st.markdown("### EMEA Lead Pipeline Overview")
    
    if df.empty:
        st.info("📋 No leads in the system yet. Go to **📁 Import Data** to get started!")
    else:
        df = load_leads_df()
        
        # KPI Row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">{len(df):,}</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Total Leads</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            pipeline_value = df[df['Stage'] != 'closed_lost']['Deal Size (M€)'].sum()
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">€{pipeline_value:.0f}M</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Pipeline Value</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            qualified = len(df[df['MEDDPICC Score'] >= 50])
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">{qualified}</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Qualified Deals</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            high_readiness = len(df[df['Staking Readiness'] == 'High']) if 'Staking Readiness' in df.columns else 0
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">{high_readiness}</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">High Readiness</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Pipeline by Stage")
            stage_data = df[df['Stage'] != 'closed_lost'].groupby('Stage').size().reset_index(name='Count')
            if not stage_data.empty:
                fig = px.bar(stage_data, x='Stage', y='Count', color='Stage',
                           color_discrete_sequence=['#1a9c9c', '#14b8a6', '#2dd4bf', '#5eead4'])
                fig.update_layout(showlegend=False, height=300)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### Leads by Region")
            region_data = df.groupby('Region').size().reset_index(name='Count')
            if not region_data.empty:
                fig = px.pie(region_data, values='Count', names='Region',
                           color_discrete_sequence=['#1a9c9c', '#14b8a6', '#2dd4bf', '#5eead4', '#99f6e4'])
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
        
        # Industry breakdown
        if 'Industry' in df.columns and df['Industry'].notna().any():
            st.markdown("#### Top Industries")
            industry_data = df[df['Industry'].notna()].groupby('Industry').size().reset_index(name='Count')
            industry_data = industry_data.sort_values('Count', ascending=False).head(8)
            
            col1, col2 = st.columns([2, 1])
            with col1:
                fig = px.bar(industry_data, x='Industry', y='Count', 
                           color='Industry', color_discrete_sequence=['#1a9c9c'])
                fig.update_layout(showlegend=False, height=250)
                st.plotly_chart(fig, use_container_width=True)

# PIPELINE PAGE
elif page == "📋 Pipeline":
    st.markdown("# Lead Pipeline")
    
    if df.empty:
        st.info("📋 No leads available. Import data first.")
    else:
        df = load_leads_df()
        
        # Filters
        with st.expander("🔍 Filters", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                region_filter = st.multiselect("Region", df['Region'].unique().tolist())
                industry_filter = st.multiselect("Industry", 
                                                df['Industry'].dropna().unique().tolist() if 'Industry' in df.columns else [])
            
            with col2:
                stage_filter = st.multiselect("Stage", df['Stage'].unique().tolist())
                readiness_filter = st.multiselect("Staking Readiness", 
                                                 df['Staking Readiness'].dropna().unique().tolist() if 'Staking Readiness' in df.columns else [])
            
            with col3:
                min_meddpicc = st.slider("Min MEDDPICC Score", 0, 80, 0)
                search_term = st.text_input("🔎 Search Company", placeholder="Type to search...")
        
        # Apply filters
        filtered_df = df.copy()
        if region_filter:
            filtered_df = filtered_df[filtered_df['Region'].isin(region_filter)]
        if industry_filter:
            filtered_df = filtered_df[filtered_df['Industry'].isin(industry_filter)]
        if stage_filter:
            filtered_df = filtered_df[filtered_df['Stage'].isin(stage_filter)]
        if readiness_filter:
            filtered_df = filtered_df[filtered_df['Staking Readiness'].isin(readiness_filter)]
        if min_meddpicc > 0:
            filtered_df = filtered_df[filtered_df['MEDDPICC Score'] >= min_meddpicc]
        if search_term:
            filtered_df = filtered_df[filtered_df['Company'].str.contains(search_term, case=False, na=False)]
        
        # Summary
        st.markdown(f"**Showing {len(filtered_df)} of {len(df)} leads**")
        
        # Table
        display_cols = ['Company', 'Region', 'Industry', 'Stage', 'MEDDPICC Score', 'Staking Readiness']
        display_cols = [col for col in display_cols if col in filtered_df.columns]
        
        st.dataframe(
            filtered_df[display_cols],
            use_container_width=True,
            height=500,
            column_config={
                'MEDDPICC Score': st.column_config.ProgressColumn(
                    "MEDDPICC",
                    format="%d/80",
                    min_value=0,
                    max_value=80,
                ),
            }
        )

# IMPORT DATA PAGE
elif page == "📁 Import Data":
    st.markdown("# Import Data")
    st.markdown("### Upload your prospects CSV")
    
    st.markdown("""
    <div class="info-box">
        Upload a CSV file with your prospects. The file should include columns like:
        <code>Account Name</code>, <code>LinkedIn</code>, <code>Account Type</code>, <code>Website</code>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Choose CSV file", type=['csv'])
    
    if uploaded_file is not None:
        df = process_uploaded_csv(uploaded_file)
        
        if df is not None:
            st.markdown("---")
            st.markdown("### Preview")
            st.dataframe(df.head(10), use_container_width=True)
            
            st.markdown("---")
            
            if st.button("🚀 Import All Prospects", type="primary"):
                with st.spinner("Importing... This may take a minute."):
                    # Import logic here
                    imported = 0
                    for _, row in df.iterrows():
                        try:
                            from models import Lead, Region, Tier, Stage, MEDDPICCScore
                            from database import Database
                            
                            # Determine region from LinkedIn/Website
                            linkedin = str(row.get('LinkedIn', ''))
                            website = str(row.get('Website', ''))
                            company = str(row.get('Account Name', ''))
                            account_type = str(row.get('Account Type', ''))
                            
                            # Simple region detection
                            region = 'DE'  # Default
                            if '.ch' in linkedin or '.ch' in website:
                                region = 'CH'
                            elif '.uk' in linkedin or '.uk' in website or 'london' in linkedin.lower():
                                region = 'UK'
                            elif '.ae' in linkedin or 'dubai' in linkedin.lower():
                                region = 'UAE'
                            
                            # Determine tier
                            tier = 4
                            if any(x in account_type.lower() for x in ['bank', 'asset manager']):
                                tier = 1
                            elif 'venture capital' in account_type.lower():
                                tier = 2
                            
                            new_lead = Lead(
                                id=None,
                                company=company,
                                region=Region(region),
                                tier=Tier(tier),
                                aum_estimate_millions=0,
                                contact_person='',
                                title='',
                                email=None,
                                linkedin=linkedin if linkedin != 'nan' else None,
                                stage=Stage.PROSPECTING,
                                pain_points=f"Type: {account_type}",
                                use_case='',
                                expected_deal_size_millions=0,
                                expected_yield=0
                            )
                            
                            lead_id = db.create_lead(new_lead)
                            score = MEDDPICCScore(lead_id=lead_id)
                            db.set_meddpicc_score(lead_id, score)
                            imported += 1
                            
                        except Exception as e:
                            continue
                    
                    st.success(f"✅ Successfully imported {imported} prospects!")
                    st.balloons()
                    
                    if st.button("🔄 Refresh Dashboard"):
                        st.rerun()

# MEDDPICC PAGE
elif page == "🎯 MEDDPICC":
    st.markdown("# MEDDPICC Scoring")
    
    if df.empty:
        st.info("📋 No leads available.")
    else:
        df = load_leads_df()
        
        selected_company = st.selectbox(
            "Select Company",
            df['Company'].tolist()
        )
        
        if selected_company:
            selected_row = df[df['Company'] == selected_company].iloc[0]
            selected_lead_id = selected_row['ID']
            current_score = db.get_meddpicc_score(selected_lead_id)
            
            st.markdown("---")
            st.markdown(f"### Scoring: {selected_company}")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("#### Score Each Element (0-10)")
                
                metrics = st.slider("Metrics (Quantified Business Case)", 0, 10,
                                   current_score.metrics if current_score else 0)
                economic_buyer = st.slider("Economic Buyer", 0, 10,
                                          current_score.economic_buyer if current_score else 0)
                decision_process = st.slider("Decision Process", 0, 10,
                                            current_score.decision_process if current_score else 0)
                decision_criteria = st.slider("Decision Criteria", 0, 10,
                                             current_score.decision_criteria if current_score else 0)
                pain = st.slider("Pain (Validated urgency)", 0, 10,
                               current_score.pain if current_score else 0)
                champion = st.slider("Champion (Internal advocate)", 0, 10,
                                   current_score.champion if current_score else 0)
            
            with col2:
                if current_score:
                    st.markdown("#### Current Score")
                    
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=current_score.total_score,
                        domain={'x': [0, 1], 'y': [0, 1]},
                        title={'text': "MEDDPICC"},
                        gauge={
                            'axis': {'range': [None, 80]},
                            'bar': {'color': "#1a9c9c"},
                            'steps': [
                                {'range': [0, 30], 'color': "#fee2e2"},
                                {'range': [30, 50], 'color': "#fef3c7"},
                                {'range': [50, 70], 'color': "#dbeafe"},
                                {'range': [70, 80], 'color': "#d1fae5"}
                            ],
                        }
                    ))
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    status = current_score.qualification_status
                    if status == "QUALIFIED":
                        st.success(f"✅ {status}")
                    elif status == "PROBABLE":
                        st.info(f"ℹ️ {status}")
                    elif status == "POSSIBLE":
                        st.warning(f"⚠️ {status}")
                    else:
                        st.error(f"❌ {status}")
                
                if st.button("💾 Save Score", type="primary"):
                    from models import MEDDPICCScore
                    new_score = MEDDPICCScore(
                        lead_id=selected_lead_id,
                        metrics=metrics,
                        economic_buyer=economic_buyer,
                        decision_process=decision_process,
                        decision_criteria=decision_criteria,
                        paper_process=0,
                        pain=pain,
                        champion=champion,
                        competition=0
                    )
                    db.set_meddpicc_score(selected_lead_id, new_score)
                    st.success("Score saved!")
                    st.rerun()

# ADD LEAD PAGE
elif page == "➕ Add Lead":
    st.markdown("# Add New Lead")
    
    with st.form("new_lead_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            company = st.text_input("Company Name *", placeholder="e.g., DWS Group")
            region = st.selectbox("Region *", ['DE', 'CH', 'UK', 'UAE', 'NORDICS'])
            tier = st.selectbox("Tier *", [1, 2, 3, 4],
                               format_func=lambda x: {1: "Tier 1 (€50B+)", 2: "Tier 2 (€10-50B)",
                                                     3: "Tier 3 (€1-10B)", 4: "Tier 4 (<€1B)"}.get(x))
            aum = st.number_input("AUM Estimate (M€)", min_value=0.0, value=0.0, step=10.0)
        
        with col2:
            contact = st.text_input("Contact Name *", placeholder="e.g., Max Mustermann")
            title = st.text_input("Contact Title *", placeholder="e.g., CIO Alternatives")
            email = st.text_input("Email", placeholder="email@company.com")
            linkedin = st.text_input("LinkedIn URL", placeholder="https://linkedin.com/in/...")
        
        stage = st.selectbox("Stage", ['prospecting', 'discovery', 'solutioning',
                                      'validation', 'negotiation', 'closed_won', 'closed_lost'])
        
        col1, col2 = st.columns(2)
        with col1:
            deal_size = st.number_input("Expected Deal Size (M€)", min_value=0.0, value=0.0, step=5.0)
        with col2:
            exp_yield = st.number_input("Expected Yield (%)", min_value=0.0, value=0.0, step=0.5)
        
        submitted = st.form_submit_button("✨ Create Lead", type="primary")
        
        if submitted:
            if not all([company, region, contact, title]):
                st.error("Please fill in all required fields (marked with *)")
            else:
                from models import Lead, Region, Tier, Stage, MEDDPICCScore
                
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
                    expected_deal_size_millions=deal_size,
                    expected_yield=exp_yield
                )
                
                lead_id = db.create_lead(new_lead)
                score = MEDDPICCScore(lead_id=lead_id)
                db.set_meddpicc_score(lead_id, score)
                
                st.success(f"✅ Lead created: {company} (ID: {lead_id})")
                st.info("Go to '🎯 MEDDPICC' to score this lead!")
