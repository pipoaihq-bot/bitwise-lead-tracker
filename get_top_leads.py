#!/usr/bin/env python3
"""
StakeStream — Top 10 Lead Selector
Holt die 10 besten Leads aus Supabase basierend auf Prioritäts-Algorithmus.
Output: JSON mit Lead-Details für Pipo's Daily Prospecting.

Usage:
  python3 get_top_leads.py            → Top 10, alle Regionen
  python3 get_top_leads.py --region DE → Nur DACH
  python3 get_top_leads.py --n 5      → Nur Top 5
"""

import json, urllib.request, urllib.error, sys, os
from datetime import datetime, timezone

SUPABASE_URL = "https://cxrhqzggukuqxpsausrd.supabase.co"
SERVICE_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4cmhxemdndWt1cXhwc2F1c3JkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjE4NTk4NiwiZXhwIjoyMDg3NzYxOTg2fQ.Xtq5UJtPWDgKvBVOBfU-nvBqFV_rf3UbHUBJCBsvalE"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

# Priorität der Regionen für Philipp (EMEA HEAD)
REGION_SCORE = {
    "DE": 25, "CH": 22, "UAE": 20, "UK": 18,
    "NORDICS": 15, "EUROPE": 10, "MIDEAST": 12,
    "USA": 5, "LATAM": 3, "OTHER": 2,
}

# Tier → Score
TIER_SCORE = {1: 35, 2: 20, 3: 8, 4: 2}

def fetch(path):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return []

def days_since(ts_str):
    if not ts_str:
        return 999
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - ts).days
    except:
        return 999

def score_lead(lead, meddpicc_map):
    """
    Prioritäts-Algorithmus:
    - Tier          (35%): Tier 1 = 35, Tier 2 = 20, Tier 3 = 8
    - Region        (25%): DE=25, CH=22, UAE=20, UK=18, ...
    - MEDDPICC      (20%): score / 64 * 20
    - Inaktivität   (15%): 1-7 Tage = 15, 8-30 = 10, >30 = 5, >90 = 1
    - Deal Size      (5%): >1M = 5, >0.5M = 3, sonst 1
    """
    tier      = lead.get("tier") or 3
    region    = lead.get("region") or "EUROPE"
    deal_size = float(lead.get("expected_deal_size_millions") or 0)
    days      = days_since(lead.get("updated_at"))
    lead_id   = lead.get("id")
    medd      = meddpicc_map.get(lead_id, {}).get("total_score", 0) or 0

    tier_pts   = TIER_SCORE.get(tier, 5)
    region_pts = REGION_SCORE.get(region, 5)
    medd_pts   = min(20, int(medd / 64 * 20))

    if days <= 7:   inact_pts = 15
    elif days <= 30: inact_pts = 10
    elif days <= 90: inact_pts = 5
    else:           inact_pts = 2

    if deal_size >= 1.0:   deal_pts = 5
    elif deal_size >= 0.5: deal_pts = 3
    else:                  deal_pts = 1

    total = tier_pts + region_pts + medd_pts + inact_pts + deal_pts

    # Begründung
    reasons = []
    if tier == 1:    reasons.append("C-Suite Kontakt")
    if region in ("DE","CH"): reasons.append(f"Kernmarkt {region}")
    if medd >= 40:   reasons.append(f"MEDDPICC {medd}/64")
    if days >= 14:   reasons.append(f"{days} Tage kein Kontakt")
    if deal_size >= 0.5: reasons.append(f"€{deal_size}M Deal")

    return total, " | ".join(reasons) if reasons else "Standard Prospecting"

def suggest_action(lead, days):
    stage = lead.get("stage", "prospecting")
    tier  = lead.get("tier") or 3
    if stage == "discovery":     return "Follow-up: Konkrete Pain Points vertiefen"
    if stage == "solutioning":   return "Demo anbieten oder Proposal vorbereiten"
    if stage == "negotiation":   return "DRINGEND: Deal pushen, Blocker klären"
    if tier == 1 and days > 30:  return "Re-Engagement: Neues Bitwise Insight teilen"
    if tier == 1:                return "Erstansprache: Persönliche Email an C-Suite"
    if days > 60:                return "Re-Engagement Email + LinkedIn Connect"
    return "Kaltansprache: Personalisierte Intro-Email"

def main():
    # Args
    region_filter = None
    n = 10
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--region" and i+1 < len(args): region_filter = args[i+1]
        if a == "--n" and i+1 < len(args): n = int(args[i+1])

    # Fetch leads (aktive, nicht closed)
    filter_str = "stage=neq.closed_won&stage=neq.closed_lost"
    if region_filter:
        filter_str += f"&region=eq.{region_filter}"

    leads = []
    page_size = 1000
    offset = 0
    while True:
        chunk = fetch(
            f"leads?{filter_str}"
            f"&select=id,company,region,tier,contact_person,title,email,linkedin,"
            f"stage,industry,sub_region,expected_deal_size_millions,updated_at"
            f"&range={offset},{offset+page_size-1}"
        )
        if not chunk: break
        leads.extend(chunk)
        if len(chunk) < page_size: break
        offset += page_size

    # Fetch MEDDPICC scores
    scores_raw = fetch("meddpicc_scores?select=lead_id,total_score,qualification_status")
    meddpicc_map = {s["lead_id"]: s for s in scores_raw}

    # Score all leads
    scored = []
    for lead in leads:
        score, reason = score_lead(lead, meddpicc_map)
        days = days_since(lead.get("updated_at"))
        scored.append({
            "score": score,
            "reason": reason,
            "days_inactive": days,
            "suggested_action": suggest_action(lead, days),
            "meddpicc": meddpicc_map.get(lead["id"], {}).get("total_score", 0) or 0,
            "qualification": meddpicc_map.get(lead["id"], {}).get("qualification_status", "UNQUALIFIED") or "UNQUALIFIED",
            **lead,
        })

    # Sort and take top N
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:n]

    # Output
    result = {
        "generated_at": datetime.now().isoformat(),
        "total_active_leads": len(leads),
        "region_filter": region_filter or "ALL",
        "top_leads": top,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
