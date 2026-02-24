# Bitwise EMEA Lead Tracker

MEDDPICC-aligned sales pipeline dashboard for Bitwise Onchain Solutions EMEA.

**Live URL:** https://bitwise-leads.streamlit.app (nach Deployment)

## Features

- 📊 Interactive Dashboard (Pipeline Funnel, MEDDPICC Distribution)
- 📋 Lead Management with Filters
- 🎯 MEDDPICC Scoring with Gauge Charts
- ➕ Add New Leads via Form
- 📝 Activity Tracking

## Local Development

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy to Streamlit Cloud

### Step 1: Push to GitHub

```bash
cd ~/.openclaw/workspace/bitwise/leadtracker

git init
git add .
git commit -m "Initial commit"

# Create GitHub repo (via gh CLI or manually)
gh repo create bitwise-lead-tracker --public --source=. --push
```

### Step 2: Connect to Streamlit Cloud

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click "New app"
4. Select repository: `philippsandor/bitwise-lead-tracker`
5. Main file path: `streamlit_app.py`
6. Click "Deploy"

### Step 3: Access Your Dashboard

- URL will be: `https://bitwise-leads.streamlit.app`
- Or custom: `https://yourusername-bitwise-leads.streamlit.app`

## Data Persistence

On Streamlit Cloud:
- Data persists for the session
- For permanent storage, use Streamlit's `st.secrets` + external DB (Supabase, etc.)
- Or export regularly via Export feature

## File Structure

```
├── streamlit_app.py      # Main Streamlit app (Cloud version)
├── dashboard.py          # Local dashboard (optional)
├── main.py               # CLI entry point
├── commands.py           # CLI commands
├── database.py           # SQLite operations
├── models.py             # Data classes
├── requirements.txt      # Dependencies
└── README.md
```

## Environment Variables

Optional for Streamlit Cloud:
```bashn# .streamlit/secrets.toml (not committed)
[database]
url = "your_external_db_url"
```

## Team Access

Streamlit Cloud apps are public by default. To restrict access:
- Share the URL privately
- Or use Streamlit's private apps (Teams plan)

## Support

Philipp Sandor - Head of EMEA Onchain Solutions
