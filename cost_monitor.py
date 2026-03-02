#!/usr/bin/env python3
"""
cost_monitor.py — Pipo API Cost Monitor
========================================
Zeigt Verbrauch und Kosten aller integrierten APIs (Anthropic, EXA, Supabase, LinkedIn).
Starten: . ./.env && streamlit run cost_monitor.py --server.port 8502
"""

import streamlit as st
import os, re, json
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
import urllib.request, urllib.parse

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
BOT_LOG      = Path("/tmp/pipo_bot.log")

# Pricing (USD, Stand 2026 — ggf. anpassen)
HAIKU_IN_PER_1M    = 0.80   # claude-haiku-4-5 input
HAIKU_OUT_PER_1M   = 4.00   # claude-haiku-4-5 output
SONNET_IN_PER_1M   = 3.00   # claude-sonnet-4-6 input
SONNET_OUT_PER_1M  = 15.00  # claude-sonnet-4-6 output
EXA_PER_SEARCH     = 0.01   # neural search

# Geschätzte Tokens pro Call-Typ
T_INTENT    = {"in": 500,  "out": 80}    # claude_route_intent (Haiku)
T_ANALYSIS  = {"in": 600,  "out": 200}   # claude_quick_analysis (Haiku)
T_BATTLECARD= {"in": 8000, "out": 2000}  # generate_battlecard (Sonnet, via subprocess)

# Monatliche Fixkosten (manuell gepflegt)
FIXED_COSTS = {
    "LinkedIn Sales Navigator": {"eur": 100, "note": "manuell"},
    "Streamlit Cloud":          {"eur": 0,   "note": "Free Tier"},
    "GitHub":                   {"eur": 0,   "note": "Free / Public"},
    "Telegram Bot API":         {"eur": 0,   "note": "kostenlos"},
}

EUR_PER_USD = 0.92  # Näherungswert

# ── Streamlit Setup ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Pipo Cost Monitor",
    page_icon="💰",
    layout="wide",
)
st.markdown("""
<style>
.stApp { background: #0d1520; color: #e2e8f0; }
[data-testid="stMetricValue"] { color: #60a5fa; font-size: 1.6rem; font-weight: 600; }
[data-testid="stMetricLabel"] { color: #94a3b8; }
[data-testid="stMetricDelta"] { font-size: 0.85rem; }
h1,h2,h3 { color: #e2e8f0; }
.metric-card {
    background: #1e293b; border: 1px solid #334155;
    border-radius: 10px; padding: 1.2rem 1.5rem; margin: 0.3rem 0;
}
.cost-green  { color: #4ade80; font-weight: 600; }
.cost-yellow { color: #facc15; font-weight: 600; }
.cost-red    { color: #f87171; font-weight: 600; }
.small-note  { color: #64748b; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ── Helper: Supabase ──────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def sb_count(table, filter_=""):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=id&{filter_}"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "count=exact",
            "Range": "0-0",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            content_range = r.headers.get("Content-Range", "*/0")
            total = content_range.split("/")[-1]
            return int(total) if total.isdigit() else None
    except Exception:
        return None

@st.cache_data(ttl=300)
def sb_get(path, params=""):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/{path}{'?' + params if params else ''}"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return []

# ── Helper: Log-Analyse ───────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def parse_log(log_path: str, month_str: str):
    """Parst den Bot-Log und zählt API-Calls für den aktuellen Monat."""
    counts = {
        "intent_calls":    0,   # claude_route_intent (Haiku)
        "analysis_calls":  0,   # claude_quick_analysis (Haiku)
        "battlecard_calls":0,   # Battle Card runs (Sonnet via subprocess)
        "li_profile_calls":0,   # LinkedIn get_profile
        "li_search_calls": 0,   # LinkedIn search_people
        "sb_gets":         0,   # Supabase GET-Anfragen
        "sb_posts":        0,   # Supabase POST (Inserts)
        "sb_errors":       0,   # Supabase 4xx Fehler
        "total_messages":  0,   # Telegram-Nachrichten verarbeitet
        "errors":          0,   # Beliebige Fehler
    }
    log_lines = []
    p = Path(log_path)
    if not p.exists():
        return counts, []
    with open(p, "r", errors="replace") as f:
        for line in f:
            # Nur aktueller Monat
            if month_str not in line:
                continue
            log_lines.append(line.rstrip())
            ll = line.lower()
            if "claude_route:" in ll:
                counts["intent_calls"] += 1
            elif "claude_quick_analysis" in ll and "error" not in ll:
                counts["analysis_calls"] += 1
            elif "battle card" in ll or "pipo_battlecard" in ll or "starte battle card" in ll:
                counts["battlecard_calls"] += 1
            elif "linkedin profile error" in ll or "get_profile" in ll:
                counts["li_profile_calls"] += 1
            elif "search_people" in ll or "handle_find_contacts" in ll:
                counts["li_search_calls"] += 1
            elif "sb_post" in ll and "http" in ll:
                if "400" in ll or "401" in ll or "403" in ll or "5" in ll:
                    counts["sb_errors"] += 1
                counts["sb_posts"] += 1
            elif "message:" in ll:
                counts["total_messages"] += 1
            if "error" in ll:
                counts["errors"] += 1
    return counts, log_lines[-50:]  # letzte 50 Zeilen

# ── Cost Calculator ───────────────────────────────────────────────────────────
def calc_anthropic_cost(counts):
    haiku_in  = (counts["intent_calls"] * T_INTENT["in"] +
                 counts["analysis_calls"] * T_ANALYSIS["in"]) / 1_000_000
    haiku_out = (counts["intent_calls"] * T_INTENT["out"] +
                 counts["analysis_calls"] * T_ANALYSIS["out"]) / 1_000_000
    sonnet_in  = counts["battlecard_calls"] * T_BATTLECARD["in"]  / 1_000_000
    sonnet_out = counts["battlecard_calls"] * T_BATTLECARD["out"] / 1_000_000
    haiku_cost  = haiku_in  * HAIKU_IN_PER_1M + haiku_out  * HAIKU_OUT_PER_1M
    sonnet_cost = sonnet_in * SONNET_IN_PER_1M + sonnet_out * SONNET_OUT_PER_1M
    return {
        "haiku_cost":  haiku_cost,
        "sonnet_cost": sonnet_cost,
        "total":       haiku_cost + sonnet_cost,
        "haiku_calls": counts["intent_calls"] + counts["analysis_calls"],
        "sonnet_calls":counts["battlecard_calls"],
    }

def color_cost(usd):
    if usd < 5:    return "cost-green"
    elif usd < 20: return "cost-yellow"
    return "cost-red"

# ── Main ──────────────────────────────────────────────────────────────────────
now       = datetime.now(timezone.utc)
month_str = now.strftime("%m")   # z.B. "03" für März
month_label = now.strftime("%B %Y")

st.title("💰 Pipo API Cost Monitor")
st.caption(f"Bitwise EMEA · {month_label} · Daten aus Log + Supabase · Refresh alle 60s")

counts, log_lines = parse_log(str(BOT_LOG), month_str)
anthropic = calc_anthropic_cost(counts)

# EXA: Kosten über Battle Cards schätzen (jede Battle Card ≈ 5 EXA-Suchanfragen)
exa_searches_est = counts["battlecard_calls"] * 5
exa_cost_est     = exa_searches_est * EXA_PER_SEARCH

# Supabase
total_leads   = sb_count("leads") or 0
total_meddpicc= sb_count("meddpicc_scores") or 0

total_variable_usd = anthropic["total"] + exa_cost_est
total_fixed_eur    = sum(v["eur"] for v in FIXED_COSTS.values())

# ── KPI Row ───────────────────────────────────────────────────────────────────
st.markdown("---")
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.metric("🤖 Claude Calls", f"{anthropic['haiku_calls'] + anthropic['sonnet_calls']}")
with k2:
    st.metric("💵 Anthropic", f"${anthropic['total']:.3f}")
with k3:
    st.metric("🔍 EXA Searches ~", f"{exa_searches_est}")
with k4:
    st.metric("💵 EXA ~", f"${exa_cost_est:.2f}")
with k5:
    st.metric("📊 Leads in DB", f"{total_leads:,}")

st.markdown("---")

# ── Anthropic Section ─────────────────────────────────────────────────────────
col_a, col_b = st.columns([2, 1])
with col_a:
    st.subheader("🤖 Anthropic API")
    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">Intent Router</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{counts['intent_calls']}</div>
        <div class="small-note">Claude Haiku · ~{counts['intent_calls']*T_INTENT['in']//1000}k tokens</div>
        </div>""", unsafe_allow_html=True)
    with a2:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">Lead Analysis</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{counts['analysis_calls']}</div>
        <div class="small-note">Claude Haiku · ~{counts['analysis_calls']*T_ANALYSIS['in']//1000}k tokens</div>
        </div>""", unsafe_allow_html=True)
    with a3:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">Battle Cards</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{counts['battlecard_calls']}</div>
        <div class="small-note">Claude Sonnet · ~{counts['battlecard_calls']*T_BATTLECARD['in']//1000}k tokens</div>
        </div>""", unsafe_allow_html=True)

with col_b:
    cc = color_cost(anthropic["total"])
    st.markdown(f"""<div class="metric-card" style="height:100%">
    <div style="color:#94a3b8;font-size:.85rem">Geschätzte Kosten ({month_label})</div>
    <div style="font-size:2rem;font-weight:700" class="{cc}">${anthropic['total']:.3f}</div>
    <div class="small-note">Haiku: ${anthropic['haiku_cost']:.3f}</div>
    <div class="small-note">Sonnet: ${anthropic['sonnet_cost']:.3f}</div>
    <div class="small-note" style="margin-top:.5rem">≈ €{anthropic['total']*EUR_PER_USD:.2f}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── EXA Section ──────────────────────────────────────────────────────────────
col_e, col_ef = st.columns([2, 1])
with col_e:
    st.subheader("🔍 EXA Web Search")
    e1, e2 = st.columns(2)
    with e1:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">Battle Cards generiert</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{counts['battlecard_calls']}</div>
        <div class="small-note">≈ {exa_searches_est} Suchanfragen geschätzt (5/Card)</div>
        </div>""", unsafe_allow_html=True)
    with e2:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">Preis pro Suche</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">$0.010</div>
        <div class="small-note">Neural Search · exa.ai Pricing</div>
        </div>""", unsafe_allow_html=True)
with col_ef:
    cc = color_cost(exa_cost_est)
    st.markdown(f"""<div class="metric-card" style="height:100%">
    <div style="color:#94a3b8;font-size:.85rem">Geschätzte Kosten ({month_label})</div>
    <div style="font-size:2rem;font-weight:700" class="{cc}">${exa_cost_est:.2f}</div>
    <div class="small-note">~{exa_searches_est} Suchanfragen</div>
    <div class="small-note" style="margin-top:.5rem">≈ €{exa_cost_est*EUR_PER_USD:.2f}</div>
    <div class="small-note" style="color:#fbbf24">⚠️ Schätzung — echte Zahl im EXA Dashboard</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Supabase Section ──────────────────────────────────────────────────────────
col_s, col_sf = st.columns([2, 1])
with col_s:
    st.subheader("🗄️ Supabase")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">Leads gesamt</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{total_leads:,}</div>
        <div class="small-note">leads Tabelle</div>
        </div>""", unsafe_allow_html=True)
    with s2:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">MEDDPICC Scores</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{total_meddpicc:,}</div>
        <div class="small-note">meddpicc_scores Tabelle</div>
        </div>""", unsafe_allow_html=True)
    with s3:
        sb_posts = counts.get("sb_posts", 0)
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">Bot DB-Inserts</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{sb_posts}</div>
        <div class="small-note">{counts.get('sb_errors',0)} Fehler</div>
        </div>""", unsafe_allow_html=True)
with col_sf:
    st.markdown(f"""<div class="metric-card" style="height:100%">
    <div style="color:#94a3b8;font-size:.85rem">Plan & Kosten</div>
    <div style="font-size:2rem;font-weight:700;color:#4ade80">Free</div>
    <div class="small-note">500 MB DB · 2 GB Bandwidth</div>
    <div class="small-note">50K Monthly Active Users</div>
    <div class="small-note" style="margin-top:.5rem;color:#4ade80">✅ Innerhalb Free Tier</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── LinkedIn Section ──────────────────────────────────────────────────────────
col_l, col_lf = st.columns([2, 1])
with col_l:
    st.subheader("💼 LinkedIn Sales Navigator")
    l1, l2 = st.columns(2)
    with l1:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">Profile Lookups (Bot)</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{counts['li_profile_calls']}</div>
        <div class="small-note">get_profile Aufrufe</div>
        </div>""", unsafe_allow_html=True)
    with l2:
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.85rem">People Searches</div>
        <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{counts['li_search_calls']}</div>
        <div class="small-note">search_people Aufrufe</div>
        </div>""", unsafe_allow_html=True)
with col_lf:
    st.markdown(f"""<div class="metric-card" style="height:100%">
    <div style="color:#94a3b8;font-size:.85rem">Monatliche Kosten</div>
    <div style="font-size:2rem;font-weight:700;color:#facc15">€100</div>
    <div class="small-note">Sales Navigator Advanced</div>
    <div class="small-note">manuell · kein API-Tracking</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Fixkosten Übersicht ───────────────────────────────────────────────────────
st.subheader("📋 Fixkosten & Subscriptions")
fix_cols = st.columns(len(FIXED_COSTS))
for i, (name, info) in enumerate(FIXED_COSTS.items()):
    with fix_cols[i]:
        color = "color:#4ade80" if info["eur"] == 0 else "color:#facc15"
        label = "kostenlos" if info["eur"] == 0 else f"€{info['eur']}/Mo"
        st.markdown(f"""<div class="metric-card">
        <div style="color:#94a3b8;font-size:.8rem">{name}</div>
        <div style="font-size:1.2rem;font-weight:600;{color}">{label}</div>
        <div class="small-note">{info['note']}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Gesamtkosten ──────────────────────────────────────────────────────────────
total_eur = total_variable_usd * EUR_PER_USD + total_fixed_eur
st.subheader(f"💰 Gesamtkosten {month_label}")
t1, t2, t3, t4 = st.columns(4)
with t1:
    st.metric("Variable (API-Nutzung)", f"${total_variable_usd:.2f}", f"≈ €{total_variable_usd*EUR_PER_USD:.2f}")
with t2:
    st.metric("Fix (Subscriptions)", f"€{total_fixed_eur}", "")
with t3:
    st.metric("Gesamt ~", f"€{total_eur:.0f}", "")
with t4:
    cc_total = color_cost(total_variable_usd)
    st.markdown(f"""<div class="metric-card">
    <div style="color:#94a3b8;font-size:.85rem">Bot-Nachrichten ({month_label})</div>
    <div style="font-size:1.6rem;font-weight:600;color:#60a5fa">{counts['total_messages']}</div>
    <div class="small-note">{counts['errors']} Fehler im Log</div>
    </div>""", unsafe_allow_html=True)

# ── Telegram-Log Viewer ───────────────────────────────────────────────────────
with st.expander("📜 Bot-Log (letzte 50 Zeilen diesen Monat)"):
    if log_lines:
        st.code("\n".join(log_lines), language=None)
    else:
        st.info(f"Log-Datei {BOT_LOG} nicht gefunden oder leer.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.caption(
    f"Alle Kosten sind Schätzungen basierend auf Log-Analyse. "
    f"Anthropic: console.anthropic.com · EXA: dashboard.exa.ai · "
    f"Supabase: app.supabase.com · Letztes Update: {now.strftime('%H:%M:%S UTC')}"
)
