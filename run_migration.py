#!/usr/bin/env python3
"""
StakeStream -> Supabase Migration
Kein pip install noetig -- nur Python Standard Library
Ausfuehren auf dem Mac mini: python3 run_migration.py
"""

import sqlite3, json, urllib.request, urllib.error, os, sys
from datetime import datetime

# -- Config ------------------------------------------------------------------
SQLITE_PATH = "/Users/philippsandor/.openclaw/workspace/bitwise/leadtracker/bitwise_leads.db"
SUPABASE_URL = "https://cxrhqzggukuqxpsausrd.supabase.co"
SERVICE_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4cmhxemdndWt1cXhwc2F1c3JkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjE4NTk4NiwiZXhwIjoyMDg3NzYxOTg2fQ.Xtq5UJtPWDgKvBVOBfU-nvBqFV_rf3UbHUBJCBsvalE"
BATCH_SIZE   = 50

HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=minimal",
}

def api(method, path, data=None):
    url  = f"{SUPABASE_URL}/rest/v1/{path}"
    body = json.dumps(data).encode() if data is not None else None
    req  = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} {path}: {err[:300]}")

def upsert_batch(table, rows):
    url  = f"{SUPABASE_URL}/rest/v1/{table}"
    body = json.dumps(rows).encode()
    req  = urllib.request.Request(url, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  FEHLER ({table}): HTTP {e.code} -- {err[:200]}")
        return False

def to_int(v):
    try: return int(v) if v is not None else None
    except: return None

def to_float(v):
    try: return float(v) if v is not None else None
    except: return 0.0

def to_str(v):
    return str(v) if v is not None else None

# -- Main --------------------------------------------------------------------
print("=" * 50)
print("  StakeStream -> Supabase Migration")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 50)
print()

# 1. Verbindung testen
print("Teste Supabase-Verbindung...")
try:
    result = api("GET", "leads?select=id&limit=1")
    print("OK - Verbindung erfolgreich\n")
except RuntimeError as e:
    if "42P01" in str(e):
        print("FEHLER: Tabellen nicht gefunden!")
        print("  -> Oeffne: https://supabase.com/dashboard/project/cxrhqzggukuqxpsausrd/sql/new")
        print("  -> Fuege supabase_schema.sql ein und klicke Run")
        sys.exit(1)
    else:
        print(f"FEHLER: {e}")
        sys.exit(1)

# 2. SQLite oeffnen
print(f"SQLite: {SQLITE_PATH}")
if not os.path.exists(SQLITE_PATH):
    print("FEHLER: SQLite-Datei nicht gefunden!")
    sys.exit(1)

conn = sqlite3.connect(SQLITE_PATH)
conn.row_factory = sqlite3.Row

# 3. Leads migrieren
print("\nMigriere Leads...")
leads = conn.execute("SELECT * FROM leads ORDER BY id").fetchall()
print(f"  {len(leads)} Leads gefunden")

migrated = 0
errors   = 0
batch    = []

for row in leads:
    d = dict(row)
    # WICHTIG: alle Felder explizit setzen, None bleibt None (= null in JSON)
    # So haben ALLE Rows exakt dieselben Keys -> kein PGRST102 Fehler
    lead = {
        "id":                          to_int(d.get("id")),
        "company":                     d.get("company") or "Unknown",
        "region":                      d.get("region") or "DE",
        "tier":                        to_int(d.get("tier")) or 2,
        "aum_estimate_millions":       to_float(d.get("aum_estimate_millions")) or 0.0,
        "contact_person":              to_str(d.get("contact_person")),
        "title":                       to_str(d.get("title")),
        "email":                       to_str(d.get("email")),
        "linkedin":                    to_str(d.get("linkedin")),
        "stage":                       d.get("stage") or "prospecting",
        "pain_points":                 to_str(d.get("pain_points")),
        "use_case":                    to_str(d.get("use_case")),
        "expected_deal_size_millions": to_float(d.get("expected_deal_size_millions")) or 0.0,
        "expected_yield":              to_float(d.get("expected_yield")) or 0.0,
        "employee_count":              to_str(d.get("employee_count")),
        "industry":                    to_str(d.get("industry")),
        "sub_region":                  to_str(d.get("sub_region")),
        "company_type":                to_str(d.get("company_type")),
        "funding_stage":               to_str(d.get("funding_stage")),
        "year_founded":                to_int(d.get("year_founded")),
        "tech_stack":                  to_str(d.get("tech_stack")),
        "staking_readiness":           to_str(d.get("staking_readiness")),
        "data_enriched":               bool(d.get("data_enriched", False)),
        "enriched_at":                 to_str(d.get("enriched_at")),
        "created_at":                  to_str(d.get("created_at")),
        "updated_at":                  to_str(d.get("updated_at")),
    }
    batch.append(lead)

    if len(batch) >= BATCH_SIZE:
        if upsert_batch("leads", batch):
            migrated += len(batch)
            print(f"  OK {migrated}/{len(leads)} Leads...")
        else:
            errors += len(batch)
        batch = []

if batch:
    if upsert_batch("leads", batch):
        migrated += len(batch)
        print(f"  OK {migrated}/{len(leads)} Leads...")
    else:
        errors += len(batch)

print(f"\n  ERGEBNIS: {migrated} Leads migriert, {errors} Fehler")

# 4. MEDDPICC migrieren
print("\nMigriere MEDDPICC Scores...")
scores = conn.execute("SELECT * FROM meddpicc_scores").fetchall()
print(f"  {len(scores)} Scores")

s_batch = []
s_ok    = 0
for row in scores:
    d = dict(row)
    s = {
        "id":                   to_int(d.get("id")),
        "lead_id":              to_int(d.get("lead_id")),
        "metrics":              to_int(d.get("metrics")) or 0,
        "economic_buyer":       to_int(d.get("economic_buyer")) or 0,
        "decision_process":     to_int(d.get("decision_process")) or 0,
        "decision_criteria":    to_int(d.get("decision_criteria")) or 0,
        "paper_process":        to_int(d.get("paper_process")) or 0,
        "pain":                 to_int(d.get("pain")) or 0,
        "champion":             to_int(d.get("champion")) or 0,
        "competition":          to_int(d.get("competition")) or 0,
        "total_score":          to_int(d.get("total_score")) or 0,
        "qualification_status": d.get("qualification_status") or "UNQUALIFIED",
        "updated_at":           to_str(d.get("updated_at")),
    }
    s_batch.append(s)
    if len(s_batch) >= BATCH_SIZE:
        if upsert_batch("meddpicc_scores", s_batch):
            s_ok += len(s_batch)
        s_batch = []

if s_batch:
    if upsert_batch("meddpicc_scores", s_batch):
        s_ok += len(s_batch)

print(f"  ERGEBNIS: {s_ok} Scores migriert")

# 5. Activities
print("\nMigriere Activities...")
try:
    acts = conn.execute("SELECT * FROM activities").fetchall()
    if acts:
        a_batch = []
        for row in acts:
            d = dict(row)
            a = {
                "id":            to_int(d.get("id")),
                "lead_id":       to_int(d.get("lead_id")),
                "activity_type": to_str(d.get("activity_type")),
                "notes":         to_str(d.get("notes")),
                "outcome":       to_str(d.get("outcome")),
                "next_steps":    to_str(d.get("next_steps")),
                "created_at":    to_str(d.get("created_at")),
            }
            a_batch.append(a)
        ok = upsert_batch("activities", a_batch)
        print(f"  ERGEBNIS: {len(acts)} Activities migriert" if ok else "  FEHLER: Activities fehlgeschlagen")
    else:
        print("  (keine Activities vorhanden)")
except sqlite3.OperationalError:
    print("  (activities Tabelle nicht vorhanden - wird uebersprungen)")

# 6. Tasks
print("\nMigriere Tasks...")
try:
    tasks = conn.execute("SELECT * FROM tasks").fetchall()
    if tasks:
        t_batch = []
        for row in tasks:
            d = dict(row)
            t = {
                "id":             to_int(d.get("id")),
                "title":          d.get("title") or "Task",
                "description":    to_str(d.get("description")),
                "status":         d.get("status") or "todo",
                "priority":       d.get("priority") or "P2",
                "category":       d.get("category") or "OUTREACH",
                "target_company": to_str(d.get("target_company")),
                "target_contact": to_str(d.get("target_contact")),
                "due_date":       to_str(d.get("due_date")),
                "linkedin_url":   to_str(d.get("linkedin_url")),
                "created_at":     to_str(d.get("created_at")),
            }
            t_batch.append(t)
        ok = upsert_batch("tasks", t_batch)
        print(f"  ERGEBNIS: {len(tasks)} Tasks migriert" if ok else "  FEHLER: Tasks fehlgeschlagen")
    else:
        print("  (keine Tasks vorhanden)")
except sqlite3.OperationalError:
    print("  (tasks Tabelle nicht vorhanden - wird uebersprungen)")

conn.close()

# 7. Verifikation
print("\nVerifikation...")
try:
    check = api("GET", "leads?select=id,company,region&limit=5&order=id.asc")
    all_leads = api("GET", "leads?select=id")
    print(f"  Leads in Supabase: {len(all_leads)}")
    for lead in check:
        print(f"    - {lead.get('company','?')} ({lead.get('region','?')})")
except Exception as e:
    print(f"  Verifikation Fehler: {e}")

print()
print("=" * 50)
print("MIGRATION ABGESCHLOSSEN!")
print()
print("NAECHSTE SCHRITTE:")
print("  1. Anon Key holen:")
print("     https://supabase.com/dashboard/project/cxrhqzggukuqxpsausrd/settings/api")
print("     -> 'anon public' Key kopieren (NICHT service_role!)")
print()
print("  2. Streamlit Cloud Secrets setzen:")
print("     https://share.streamlit.io -> App -> Settings -> Secrets")
print('     SUPABASE_URL = "https://cxrhqzggukuqxpsausrd.supabase.co"')
print('     SUPABASE_KEY = "anon-key-hier-einfuegen"')
print()
print("  3. App file aendern: streamlit_app_v7.py -> Reboot App")
print("=" * 50)
