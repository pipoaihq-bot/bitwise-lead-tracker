#!/usr/bin/env python3
"""
pipo_morning_brief.py — Pipo's Unified Daily Briefing
======================================================
Sendet täglich:
  1. Top Leads mit Research + fertigen Email-Drafts
  2. Follow-Up Reminders (5+ Tage ohne Update)
  3. Stale Lead Alerts (14+ Tage — Re-Engagement oder Archivierung)
  4. Pipeline Summary

Usage:
  python3 pipo_morning_brief.py              # Top 10, alle Regionen
  python3 pipo_morning_brief.py --top 5      # Nur Top 5
  python3 pipo_morning_brief.py --region DE  # Nur DE-Leads
  python3 pipo_morning_brief.py --dry-run    # Terminal-Vorschau, kein Telegram
  python3 pipo_morning_brief.py --evening    # Evening Digest (nur Summary)
"""

import sys, time, argparse
from datetime import datetime

from pipo_core import (
    SUPABASE_KEY, ANTHROPIC_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT,
    DASHBOARD_URL,
    tg_send, make_lead_buttons, load_top_leads,
    research_company_news, generate_email_draft, format_lead_message,
    find_stale_leads, find_very_stale_leads, sb_get,
)

TOP_N_DEFAULT = 10

# ── Colors (Terminal) ────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; X = "\033[0m"; BOLD = "\033[1m"


# ── Follow-Up Section ────────────────────────────────────────────────────────
def send_followup_reminders(dry_run=False):
    """Send follow-up reminders for leads 5-13 days without update."""
    stale = find_stale_leads(days_threshold=5)
    # Exclude very stale (14+) — those get their own section
    followups = [l for l in stale if l["days_inactive"] < 14]

    if not followups:
        return 0

    header = f"""📬 <b>FOLLOW-UP REMINDERS</b> — {len(followups)} Leads warten

Leads in aktiver Stage ohne Update seit 5+ Tagen:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    if not dry_run:
        tg_send(TELEGRAM_CHAT, header)
        time.sleep(0.5)
    else:
        print(f"\n{BOLD}FOLLOW-UPS:{X}\n{header}\n")

    for l in followups[:10]:  # Max 10 follow-ups
        stage_emoji = {"discovery": "🔵", "meeting": "📅", "solutioning": "🔧",
                       "proposal": "🟡", "negotiation": "🟠"}.get(l["stage"], "⚪")
        msg = (
            f"{stage_emoji} <b>{l['company']}</b> — {l['stage']}\n"
            f"👤 {l.get('contact_person') or '—'}\n"
            f"⏰ <b>{l['days_inactive']} Tage</b> ohne Update\n"
            f"📊 MEDDPICC: {l['meddpicc']}/80"
        )
        if not dry_run:
            tg_send(TELEGRAM_CHAT, msg, reply_markup=make_lead_buttons(l["id"]))
            time.sleep(0.8)
        else:
            print(f"  {msg}\n")

    return len(followups)


def send_stale_alerts(dry_run=False):
    """Send alerts for leads 14+ days without update — re-engage or archive."""
    very_stale = find_very_stale_leads(days_threshold=14)

    if not very_stale:
        return 0

    header = f"""🚨 <b>STALE LEADS</b> — {len(very_stale)} Leads seit 14+ Tagen inaktiv

Diese Leads brauchen eine Entscheidung: Re-Engagement oder Archivierung.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    if not dry_run:
        tg_send(TELEGRAM_CHAT, header)
        time.sleep(0.5)
    else:
        print(f"\n{BOLD}STALE:{X}\n{header}\n")

    for l in very_stale[:8]:  # Max 8 stale alerts
        msg = (
            f"💤 <b>{l['company']}</b> — {l['stage']}\n"
            f"👤 {l.get('contact_person') or '—'}\n"
            f"⏰ <b>{l['days_inactive']} Tage</b> ohne Update\n"
            f"💡 Vorschlag: Neue Email mit frischem Angle oder ❌ Lost markieren"
        )
        if not dry_run:
            tg_send(TELEGRAM_CHAT, msg, reply_markup=make_lead_buttons(l["id"]))
            time.sleep(0.8)
        else:
            print(f"  {msg}\n")

    return len(very_stale)


# ── Pipeline Summary ─────────────────────────────────────────────────────────
def send_pipeline_summary(dry_run=False):
    """Send pipeline summary with stage counts."""
    leads = sb_get("leads", "select=stage&stage=not.in.(closed_won,closed_lost)")
    stages = {}
    for l in leads:
        s = l.get("stage") or "prospecting"
        stages[s] = stages.get(s, 0) + 1

    stage_order = ["prospecting", "discovery", "meeting", "solutioning", "proposal", "negotiation"]
    stage_emoji = {"prospecting": "⚪", "discovery": "🔵", "meeting": "📅",
                   "solutioning": "🔧", "proposal": "🟡", "negotiation": "🟠"}

    lines = []
    for s in stage_order:
        if s in stages:
            lines.append(f"  {stage_emoji.get(s, '⚪')} {s}: <b>{stages[s]}</b>")

    total = sum(stages.values())
    summary = f"""📊 <b>PIPELINE SUMMARY</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(lines)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total aktiv: <b>{total}</b>

<a href="{DASHBOARD_URL}">📊 Dashboard öffnen</a>"""

    if not dry_run:
        tg_send(TELEGRAM_CHAT, summary)
    else:
        print(f"\n{BOLD}SUMMARY:{X}\n{summary}\n")


# ── Main Briefing ─────────────────────────────────────────────────────────────
def run_briefing(top_n=TOP_N_DEFAULT, region=None, dry_run=False):
    now_str = datetime.now().strftime("%A, %d. %b %Y · %H:%M")

    print(f"\n{BOLD}{'='*60}")
    print(f"  PIPO MORNING BRIEF")
    print(f"  {now_str}")
    print(f"{'='*60}{X}\n")

    # Load leads
    print(f"{B}Loading top {top_n} leads...{X}")
    leads = load_top_leads(region=region, top_n=top_n)
    if not leads:
        print(f"{R}Keine Leads gefunden!{X}")
        return

    print(f"  -> {G}{len(leads)} Leads geladen{X}\n")

    # Header message
    header = f"""🤖 <b>PIPO MORNING BRIEF</b>
{now_str}
<a href="{DASHBOARD_URL}">📊 Dashboard öffnen</a>

Heute: <b>{len(leads)} priorisierte Leads</b> mit Research &amp; Email-Drafts.
Jede Email ist fertig zum Senden — kein Copy-Paste nötig.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    if not dry_run:
        tg_send(TELEGRAM_CHAT, header)
        time.sleep(0.5)
    else:
        print(f"\n{BOLD}HEADER:{X}\n{header}\n")

    # Process each lead
    for i, lead in enumerate(leads, 1):
        company = lead['company']
        print(f"  [{i}/{len(leads)}] {company} — Research...", end="", flush=True)

        # Research
        news = research_company_news(company, lead.get("region", "DE"))
        print(f" {len(news)} News -> Brief...", end="", flush=True)

        # Brief + Email
        try:
            brief = generate_email_draft(lead, news)
        except Exception as e:
            print(f" {R}Fehler: {e}{X}")
            brief = {
                "why_now": "KI-Analyse nicht verfügbar.",
                "angle": lead.get("use_case") or "ETH-Staking-Potenzial",
                "risk": "Manuelle Bewertung empfohlen.",
                "subject": f"ETH-Staking für {company}",
                "email": f"Sehr geehrte Damen und Herren,\n\nbei Bitwise Asset Management helfen wir institutionellen Investoren dabei, ihre ETH-Position zu optimieren. Ich würde mich über einen kurzen Austausch freuen.\n\nMit freundlichen Grüßen\nPhilipp Sandor\nHEAD EMEA | Bitwise Asset Management"
            }

        print(f" {G}ok{X}")

        # Format & send
        msg = format_lead_message(i, lead, brief, news)
        lead_id = lead.get("id")

        if not dry_run:
            buttons = make_lead_buttons(lead_id) if lead_id else None
            tg_send(TELEGRAM_CHAT, msg, reply_markup=buttons)
            time.sleep(1.5)  # Telegram rate limit
        else:
            print(f"\n{BOLD}LEAD {i}:{X}\n{msg}\n")
            print(f"\n{'_'*60}\n")

    # Follow-Up Reminders
    print(f"\n{B}Checking follow-ups...{X}")
    n_followups = send_followup_reminders(dry_run=dry_run)
    print(f"  -> {G}{n_followups} Follow-Up Reminders{X}")

    # Stale Alerts
    print(f"\n{B}Checking stale leads...{X}")
    n_stale = send_stale_alerts(dry_run=dry_run)
    print(f"  -> {Y}{n_stale} Stale Alerts{X}")

    # Pipeline Summary
    print(f"\n{B}Pipeline Summary...{X}")
    send_pipeline_summary(dry_run=dry_run)

    # Footer
    footer = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>Briefing abgeschlossen</b>
• {len(leads)} neue Lead-Vorschläge mit Email-Drafts
• {n_followups} Follow-Up Reminders (5+ Tage)
• {n_stale} Stale Alerts (14+ Tage)

<a href="{DASHBOARD_URL}">📊 Dashboard öffnen</a> · Powered by Pipo 🤖"""

    if not dry_run:
        tg_send(TELEGRAM_CHAT, footer)
    else:
        print(f"\n{BOLD}FOOTER:{X}\n{footer}\n")

    print(f"\n{G}{BOLD}Briefing fertig — {len(leads)} Leads + {n_followups} Follow-Ups + {n_stale} Stale{X}")
    if not dry_run:
        print(f"  -> Telegram: {len(leads) + n_followups + n_stale + 4} Nachrichten gesendet")


# ── Evening Digest ───────────────────────────────────────────────────────────
def run_evening_digest(dry_run=False):
    """Evening Digest — nur Pipeline Summary + Follow-Ups, keine neuen Leads."""
    now_str = datetime.now().strftime("%A, %d. %b %Y · %H:%M")

    print(f"\n{BOLD}{'='*60}")
    print(f"  PIPO EVENING DIGEST")
    print(f"  {now_str}")
    print(f"{'='*60}{X}\n")

    header = f"""🌙 <b>PIPO EVENING DIGEST</b>
{now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    if not dry_run:
        tg_send(TELEGRAM_CHAT, header)
        time.sleep(0.5)
    else:
        print(f"\n{BOLD}HEADER:{X}\n{header}\n")

    # Follow-Ups
    n_followups = send_followup_reminders(dry_run=dry_run)

    # Pipeline Summary
    send_pipeline_summary(dry_run=dry_run)

    footer = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Morgen gibt's neue Lead-Vorschläge im Morning Brief.
Gute Nacht! 🌙 · Powered by Pipo 🤖"""

    if not dry_run:
        tg_send(TELEGRAM_CHAT, footer)
    else:
        print(f"\n{BOLD}FOOTER:{X}\n{footer}\n")

    print(f"\n{G}{BOLD}Evening Digest fertig — {n_followups} Follow-Ups{X}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pipo Morning Brief")
    parser.add_argument("--top",     type=int, default=TOP_N_DEFAULT, help="Anzahl Leads (default: 10)")
    parser.add_argument("--region",  help="Nur eine Region (z.B. DE, CH, UAE)")
    parser.add_argument("--dry-run", action="store_true", help="Nur im Terminal ausgeben, kein Telegram")
    parser.add_argument("--evening", action="store_true", help="Evening Digest (nur Summary + Follow-Ups)")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print(f"{R}SUPABASE_KEY nicht gesetzt{X}"); sys.exit(1)
    if not ANTHROPIC_KEY and not args.evening:
        print(f"{R}ANTHROPIC_API_KEY nicht gesetzt{X}"); sys.exit(1)
    if not args.dry_run and (not TELEGRAM_TOKEN or not TELEGRAM_CHAT):
        print(f"{R}TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt{X}")
        sys.exit(1)

    if args.evening:
        run_evening_digest(dry_run=args.dry_run)
    else:
        run_briefing(top_n=args.top, region=args.region, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
