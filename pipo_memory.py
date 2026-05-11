#!/usr/bin/env python3
"""
pipo_memory.py — Nightly Memory Distill
========================================
Läuft täglich um 22:00 via LaunchAgent.
Fasst den heutigen Tag zusammen (Supabase-Aktivität)
und aktualisiert MEMORY.md mit einem täglichen Log-Eintrag.

Usage:
  python3 pipo_memory.py           # Normal run
  python3 pipo_memory.py --dry-run # Terminal-Vorschau, kein Schreiben
"""

import os, sys, json, argparse, urllib.request, re
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ.get("SUPABASE_URL",  "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY",  "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

MEMORY_FILE    = os.path.join(os.path.dirname(__file__), "..", "..", "MEMORY.md")
MEMORY_FILE    = os.path.normpath(MEMORY_FILE)

# ── Colors ────────────────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; X = "\033[0m"; BOLD = "\033[1m"

# ── Supabase ──────────────────────────────────────────────────────────────────
def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# ── Telegram ──────────────────────────────────────────────────────────────────
def tg_send(text, parse_mode="HTML"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return True
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=payload, method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"{R}Telegram Fehler: {e}{X}")
        return False

# ── Todays Stats ──────────────────────────────────────────────────────────────
def get_todays_stats():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    stats = {}

    # Aktivitäten heute
    try:
        activities = sb_get("activities",
            f"select=id,action,lead_id"
            f"&created_at=gte.{today}T00:00:00Z"
            f"&created_at=lt.{tomorrow}T00:00:00Z"
            f"&limit=500"
        )
        stats["activities_total"] = len(activities)
        # Breakdown nach Action
        by_action = {}
        for a in activities:
            key = a.get("action", "unknown")
            by_action[key] = by_action.get(key, 0) + 1
        stats["activities_by_action"] = by_action
        stats["leads_touched"] = len({a["lead_id"] for a in activities if a.get("lead_id")})
    except Exception as e:
        print(f"{Y}Aktivitäten-Fehler: {e}{X}")
        stats["activities_total"] = 0
        stats["leads_touched"] = 0
        stats["activities_by_action"] = {}

    # Leads nach Stage (aktuell)
    try:
        stage_counts = {}
        for stage in ["negotiation", "proposal", "solutioning", "discovery", "closed_won", "closed_lost"]:
            rows = sb_get("leads",
                f"select=id&stage=eq.{stage}&limit=1000"
            )
            stage_counts[stage] = len(rows)
        stats["stage_counts"] = stage_counts
    except Exception as e:
        print(f"{Y}Stage-Counts Fehler: {e}{X}")
        stats["stage_counts"] = {}

    # Deals heute bewegt (stage geändert)
    try:
        moved = sb_get("activities",
            f"select=lead_id,action,old_value,new_value"
            f"&action=eq.stage_changed"
            f"&created_at=gte.{today}T00:00:00Z"
            f"&created_at=lt.{tomorrow}T00:00:00Z"
            f"&limit=100"
        )
        stats["deals_moved"] = len(moved)
        stats["stage_moves"] = [
            f"{m.get('old_value','?')} → {m.get('new_value','?')}"
            for m in moved[:5]
        ]
    except:
        stats["deals_moved"] = 0
        stats["stage_moves"] = []

    return stats

# ── Build Daily Log Entry ─────────────────────────────────────────────────────
def build_log_entry(stats):
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"\n### {today}"]

    act = stats.get("activities_total", 0)
    touched = stats.get("leads_touched", 0)
    moved = stats.get("deals_moved", 0)

    if act == 0 and moved == 0:
        lines.append("- Ruhiger Tag. Keine Aktivitäten in Supabase.")
        return "\n".join(lines)

    lines.append(f"- **{act} Aktivitäten** auf **{touched} Leads**")

    # Activity Breakdown
    by_action = stats.get("activities_by_action", {})
    if by_action:
        breakdown = ", ".join(f"{v}x {k}" for k, v in sorted(by_action.items(), key=lambda x: -x[1])[:5])
        lines.append(f"  - {breakdown}")

    # Stage Moves
    if moved > 0:
        lines.append(f"- **{moved} Deals** Stage-Wechsel:")
        for mv in stats.get("stage_moves", [])[:3]:
            lines.append(f"  - {mv}")

    # Pipeline Snapshot
    sc = stats.get("stage_counts", {})
    if sc:
        active = sc.get("negotiation", 0) + sc.get("proposal", 0) + sc.get("solutioning", 0) + sc.get("discovery", 0)
        won  = sc.get("closed_won", 0)
        lost = sc.get("closed_lost", 0)
        lines.append(f"- Pipeline: {active} aktiv · {won} won · {lost} lost")

    return "\n".join(lines)

# ── Update MEMORY.md ──────────────────────────────────────────────────────────
def update_memory(log_entry, dry_run=False):
    if not os.path.exists(MEMORY_FILE):
        print(f"{R}MEMORY.md nicht gefunden: {MEMORY_FILE}{X}")
        return False

    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    today = datetime.now().strftime("%Y-%m-%d")

    # Timestamp am Ende aktualisieren
    content = re.sub(
        r"_Zuletzt aktualisiert:.*_",
        f"_Zuletzt aktualisiert: {today} (auto distill 22:00)_",
        content
    )

    # Tageseintrag hinzufügen — nach "## Daily Log" Section oder am Ende
    if "## Daily Log" in content:
        # Eintrag nach dem Header einfügen
        content = content.replace(
            "## Daily Log",
            f"## Daily Log{log_entry}"
        )
    else:
        # Section neu anlegen
        content = content.rstrip() + f"\n\n---\n\n## Daily Log{log_entry}\n"

    if dry_run:
        print(f"\n{BOLD}MEMORY UPDATE PREVIEW:{X}")
        print(log_entry)
        return True

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"{G}✅ MEMORY.md aktualisiert{X}")
    return True

# ── Format Telegram Summary ───────────────────────────────────────────────────
def format_tg_summary(stats, log_entry):
    today = datetime.now().strftime("%d. %b")
    act  = stats.get("activities_total", 0)
    touched = stats.get("leads_touched", 0)
    moved = stats.get("deals_moved", 0)
    sc   = stats.get("stage_counts", {})
    active = sum(sc.get(s, 0) for s in ["negotiation", "proposal", "solutioning", "discovery"])

    lines = [f"🧠 <b>MEMORY DISTILL</b> · {today}\n"]

    if act == 0:
        lines.append("Ruhiger Tag — keine Supabase-Aktivitäten.")
    else:
        lines.append(f"📋 <b>{act}</b> Aktivitäten · <b>{touched}</b> Leads berührt")
        if moved:
            lines.append(f"↗️ <b>{moved}</b> Stage-Wechsel")
        lines.append(f"🎯 Pipeline aktiv: <b>{active}</b> Deals")

    lines.append("\n✅ MEMORY.md aktualisiert")
    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pipo Memory Distill")
    parser.add_argument("--dry-run", action="store_true", help="Vorschau, kein Schreiben")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*50}")
    print(f"  🧠 PIPO MEMORY DISTILL — {datetime.now().strftime('%H:%M')}")
    print(f"{'='*50}{X}\n")

    if not SUPABASE_KEY:
        print(f"{R}❌ SUPABASE_KEY fehlt{X}"); sys.exit(1)

    # Stats sammeln
    print(f"{B}Lade heutige Aktivitäten...{X}", end="", flush=True)
    stats = get_todays_stats()
    print(f" {stats.get('activities_total', 0)} Aktivitäten, {stats.get('leads_touched', 0)} Leads")

    # Log Entry bauen
    log_entry = build_log_entry(stats)
    print(f"\n{B}Tages-Eintrag:{X}{log_entry}\n")

    # MEMORY.md aktualisieren
    update_memory(log_entry, dry_run=args.dry_run)

    # Telegram Summary (nur wenn nicht dry-run)
    if not args.dry_run:
        msg = format_tg_summary(stats, log_entry)
        if TELEGRAM_TOKEN and TELEGRAM_CHAT:
            tg_send(msg)
            print(f"{G}✅ Telegram Summary gesendet{X}")
        else:
            print(f"\n{Y}[TELEGRAM PREVIEW]{X}\n{msg}")

    print()

if __name__ == "__main__":
    main()
