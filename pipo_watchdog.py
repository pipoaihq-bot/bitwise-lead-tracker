#!/usr/bin/env python3
"""
pipo_watchdog.py — Deal & Follow-Up Watchdog
=============================================
Läuft 2x täglich (10:00 + 18:00 Dubai) via LaunchAgent.
Prüft aktive Deals auf Handlungsbedarf und sendet nur dann
eine Telegram-Nachricht wenn wirklich etwas ansteht.

Usage:
  python3 pipo_watchdog.py           # Normal run
  python3 pipo_watchdog.py --dry-run # Terminal-Vorschau
  python3 pipo_watchdog.py --force   # Immer senden, auch wenn nichts dringend
"""

import os, sys, json, argparse, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ.get("SUPABASE_URL",  "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY",  "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
DASHBOARD_URL  = "https://pipo-bitwise-lead-tracker.streamlit.app"

# Wann ist ein Lead "überfällig" (je nach Stage in Tagen)
STAGE_THRESHOLDS = {
    "negotiation": 2,    # 2 Tage ohne Update → sehr dringend
    "proposal":    3,    # 3 Tage → dringend
    "solutioning": 5,    # 5 Tage → follow up nötig
    "discovery":   7,    # 7 Tage → check in
}

ACTIVE_STAGES = list(STAGE_THRESHOLDS.keys())

# ── Colors (Terminal) ────────────────────────────────────────────────────────
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
        print(f"\n{Y}[TELEGRAM]{X}\n{text}\n")
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

# ── Load Active Leads ─────────────────────────────────────────────────────────
def load_active_leads():
    """Lädt alle Leads in aktiven Stages mit MEDDPICC Score."""
    stages_filter = ",".join(ACTIVE_STAGES)
    params = (
        "select=id,company,contact_person,title,region,tier,"
        "stage,updated_at,expected_deal_size_millions,"
        "meddpicc_scores(total_score,qualification_status)"
        f"&stage=in.({stages_filter})"
        "&order=updated_at.asc"  # älteste zuerst
        "&limit=200"
    )
    try:
        leads = sb_get("leads", params)
    except Exception as e:
        print(f"{R}Supabase Fehler: {e}{X}")
        return []

    now = datetime.now()
    result = []
    for l in leads:
        score_data = l.pop("meddpicc_scores", None)
        if isinstance(score_data, list):
            score_data = score_data[0] if score_data else None
        meddpicc = (score_data.get("total_score") or 0) if score_data else 0
        ql = (score_data.get("qualification_status") or "UNQUALIFIED") if score_data else "UNQUALIFIED"

        upd = l.get("updated_at") or ""
        try:
            dt = datetime.fromisoformat(upd.replace("Z", "+00:00"))
            days_inactive = max(0, (now - dt.replace(tzinfo=None)).days)
        except:
            days_inactive = 30

        result.append({
            **l,
            "meddpicc": meddpicc,
            "ql": ql,
            "days_inactive": days_inactive,
        })
    return result

# ── Load Pending Follow-Ups ───────────────────────────────────────────────────
def load_pending_followups():
    """Lädt Leads mit followup_scheduled Activity die >5 Tage alt ist."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = (
        f"select=lead_id,created_at"
        f"&action=eq.followup_scheduled"
        f"&created_at=lte.{cutoff}"
        f"&order=created_at.asc"
        f"&limit=50"
    )
    try:
        activities = sb_get("activities", params)
        return {a["lead_id"] for a in activities if a.get("lead_id")}
    except:
        return set()

# ── Analyse & Priorisieren ────────────────────────────────────────────────────
def analyse_leads(leads, followup_ids):
    """Sortiert Leads nach Dringlichkeit."""
    urgent   = []  # Negotiation/Proposal überfällig
    due      = []  # Solutioning/Discovery überfällig
    followup = []  # Follow-Up fällig

    for l in leads:
        stage    = l.get("stage", "")
        inactive = l.get("days_inactive", 0)
        threshold = STAGE_THRESHOLDS.get(stage, 99)
        lead_id  = l.get("id")

        # Follow-Up fällig?
        if lead_id in followup_ids:
            followup.append(l)
            continue

        # Überfällig?
        if inactive >= threshold:
            if stage in ("negotiation", "proposal"):
                urgent.append(l)
            else:
                due.append(l)

    # Sortieren: Tier 1 zuerst, dann nach Inaktivität
    def sort_key(l):
        return (int(l.get("tier") or 3), -l.get("days_inactive", 0))

    urgent.sort(key=sort_key)
    due.sort(key=sort_key)
    followup.sort(key=sort_key)

    return urgent[:3], due[:5], followup[:3]

# ── Format Watchdog Message ───────────────────────────────────────────────────
def format_watchdog_message(urgent, due, followup):
    now_str = datetime.now().strftime("%d. %b · %H:%M")
    lines   = [f"🐺 <b>PIPO WATCHDOG</b> · {now_str}\n"]

    def lead_line(l, emoji):
        company  = l.get("company", "?")
        contact  = l.get("contact_person", "").split()[0] if l.get("contact_person") else "—"
        stage    = l.get("stage", "?")
        inactive = l.get("days_inactive", 0)
        tier     = l.get("tier", 3)
        deal     = l.get("expected_deal_size_millions") or 0
        t_emoji  = {1: "⭐", 2: "🔹", 3: "▫️"}.get(int(tier), "▫️")
        return (f"{emoji} <b>{company}</b> {t_emoji} · {contact}\n"
                f"   {stage} · {inactive}d inaktiv"
                + (f" · €{deal:.0f}M" if deal else ""))

    if urgent:
        lines.append("🚨 <b>DRINGEND — Jetzt handeln:</b>")
        for l in urgent:
            lines.append(lead_line(l, "🔴"))
        lines.append("")

    if followup:
        lines.append("🔔 <b>Follow-Up fällig (&gt;5 Tage):</b>")
        for l in followup:
            lines.append(lead_line(l, "🟠"))
        lines.append("")

    if due:
        lines.append("⏰ <b>Check-In empfohlen:</b>")
        for l in due:
            lines.append(lead_line(l, "🟡"))
        lines.append("")

    total = len(urgent) + len(due) + len(followup)
    lines.append(f"<a href='{DASHBOARD_URL}'>📊 Dashboard</a> · {total} Leads brauchen Attention")

    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pipo Deal Watchdog")
    parser.add_argument("--dry-run", action="store_true", help="Terminal-Vorschau, kein Telegram")
    parser.add_argument("--force",   action="store_true", help="Immer senden, auch wenn nichts dringend")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*50}")
    print(f"  🐺 PIPO WATCHDOG — {datetime.now().strftime('%H:%M')}")
    print(f"{'='*50}{X}\n")

    if not SUPABASE_KEY:
        print(f"{R}❌ SUPABASE_KEY fehlt{X}"); sys.exit(1)

    # Daten laden
    print(f"{B}Lade aktive Deals...{X}", end="", flush=True)
    leads = load_active_leads()
    print(f" {len(leads)} Leads")

    print(f"{B}Prüfe pending Follow-Ups...{X}", end="", flush=True)
    followup_ids = load_pending_followups()
    print(f" {len(followup_ids)} fällig")

    # Analysieren
    urgent, due, followup = analyse_leads(leads, followup_ids)
    total = len(urgent) + len(due) + len(followup)

    print(f"\n  🔴 Dringend:   {len(urgent)}")
    print(f"  🟠 Follow-Up:  {len(followup)}")
    print(f"  🟡 Check-In:   {len(due)}")

    # Nichts zu tun?
    if total == 0 and not args.force:
        print(f"\n{G}✅ WATCHDOG_OK — alles im Griff, kein Telegram{X}\n")
        return

    # Nachricht formatieren & senden
    msg = format_watchdog_message(urgent, due, followup)

    if args.dry_run:
        print(f"\n{BOLD}WATCHDOG MESSAGE:{X}\n{msg}\n")
    else:
        tg_send(msg)
        print(f"\n{G}✅ Telegram gesendet — {total} Alerts{X}\n")

if __name__ == "__main__":
    main()
