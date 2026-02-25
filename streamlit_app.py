import streamlit as st

st.set_page_config(page_title="Bitwise Test", layout="wide")

st.title("🔷 Bitwise EMEA - Test Page")

st.success("If you see this, the app is working!")

st.markdown("### Testing Components:")

# Test 1: Basic imports
try:
    import pandas as pd
    st.write("✅ Pandas OK")
except Exception as e:
    st.error(f"❌ Pandas: {e}")

try:
    import plotly.express as px
    st.write("✅ Plotly OK")
except Exception as e:
    st.error(f"❌ Plotly: {e}")

# Test 2: Database
try:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from database import Database
    db = Database()
    leads = db.get_all_leads()
    st.write(f"✅ Database OK - {len(leads)} leads found")
except Exception as e:
    st.error(f"❌ Database: {e}")

# Test 3: Task Manager
try:
    from task_manager import TaskManager
    tm = TaskManager()
    st.write("✅ Task Manager OK")
except Exception as e:
    st.error(f"❌ Task Manager: {e}")

# Test 4: Charts
try:
    import plotly.graph_objects as go
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=50,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Test"}
    ))
    st.plotly_chart(fig, use_container_width=True)
    st.write("✅ Charts OK")
except Exception as e:
    st.error(f"❌ Charts: {e}")

st.markdown("---")
st.info("If all checks above show ✅, the main app should work.")

if st.button("Go to Full App"):
    st.switch_page("streamlit_app_full.py")
