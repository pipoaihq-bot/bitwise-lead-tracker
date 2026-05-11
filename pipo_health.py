#!/usr/bin/env python3
"""
pipo_health.py — System Health Check
=====================================
Läuft täglich um 09:00 via LaunchAgent.
Prüft alle kritischen Systeme und sendet einen Telegram-Report.

Checks:
  1. Supabase erreichbar & Leads-Count plausibel
  2. LaunchAgent Log-Dateien auf Fehler prüfen (letzte 24h)
  3. .env vollständig (alle Keys vorhanden)
  4. Python Scripts syntaktisch valide

Usage:
  python3 pipo_health.py           # Normal run
  python3 pipo_health.py --dry-run # Terminal-Vorschau, kein Telegram
"""

import os, sys, json, argparse, urllib.request, ast
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ.get("SUPABASE_URL",  "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY",  "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")

SCRIPTS_DIR    = os.path.dirname(__file__)
LOGS_DIR       = "/Users/philippsandor/.openclaw/logs"
DASHBOARD_URL  = "https://pipo-bitwise-lead-tracker.streamlit.app"

# Alle Scripts die täglich laufen sollten
CRITICAL_SCRIPTS = [
    "pipo_bot.py",
    "pipo_watchdog.py",
    "pipo_memory.py",
    "pipo_health.py",
]

# Log-Dateien und welche LaunchAgents sie erzeugen
LOG_FILES = {
    "morning-brief":  "morning-brief.log",
    "deal-watchdog":  "deal-watchdog.log",
    "memory-distill": "memory-distill.log",
    "health-check":   "health-check.log",
}

# ── Colors ────────────────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; X = "\033[0m"; BOLD = "\033[1m"

# ── Supabase ──────────────────────────────────────────────────────────────────
def check_supabase():
    """Prüft ob Supabase erreichbar ist und gibt Lead-Count zurück."""
    if not SUPABASE_KEY:
        return False, "SUPABASE_KEY fehlt in .env"
    try:
        url = f"{SUPABASE_URL}/rest/v1/leads?select=id&limit=1"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "count=exact"
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            count_header = r.headers.get("Content-Range", "")
            # Content-Range: 0-0/21890
            total = count_header.split("/")[-1] if "/" in count_header else "?"
            return True, f"{total} Leads"
    except Exception as e:
        return False, str(e)[:80]

# ── Env Check ─────────────────────────────────────────────────────────────────
def check_env():
    """Prüft ob alle wichtigen Keys in .env gesetzt sind."""
    results = {}
    results["SUPABASE_URL"]      = bool(SUPABASE_URL)
    results["SUPABASE_KEY"]      = bool(SUPABASE_KEY)
    results["TELEGRAM_BOT_TOKEN"] = bool(TELEGRAM_TOKEN)
    results["TELEGRAM_CHAT_ID"]  = bool(TELEGRAM_CHAT)
    results["ANTHROPIC_API_KEY"] = bool(ANTHROPIC_KEY)
    missing = [k for k, v in results.items() if not v]
    return len(missing) == 0, missing

# ── Script Syntax Check ───────────────────────────────────────────────────────
def check_scripts():
    """Prüft ob alle kritischen Scripts syntaktisch valide sind."""
    results = {}
    for script in CRITICAL_SCRIPTS:
        path = os.path.join(SCRIPTS_DIR, script)
        if not os.path.exists(path):
            results[script] = "FEHLT"
            continue
        try:
            with open(path, "r") as f:
                ast.parse(f.read())
            results[script] = "OK"
        except SyntaxError as e:
            results[script] = f"SYNTAX ERROR L{e.lineno}"
    return results

# ── Log Check ─────────────────────────────────────────────────────────────────
def check_logs():
    """Prüft ob LaunchAgent Logs Fehler enthalten (letzte 24h)."""
    cutoff = datetime.now() - timedelta(hours=25)
    issues = {}

    for name, logfile in LOG_FILES.items():
        path = os.path.join(LOGS_DIR, logfile)
        if not os.path.exists(path):
            issues[name] = "kein Log"
            continue

        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if mtime < cutoff:
            issues[name] = f"nicht gelaufen seit {mtime.strftime('%d.%b %H:%M')}"
            continue

        # Fehler in letzten 100 Zeilen suchen
        try:
            with open(path, "r", errors="replace") as f:
                lines = f.readlines()[-100:]
            error_lines = [l.strip() for l in lines if any(
                kw in l.lower() for kw in ["error", "fehler", "traceback", "exception", "❌"]
            )]
            if error_lines:
                issues[name] = f"{len(error_lines)} Fehler · zuletzt: {error_lines[-1][:60]}"
        except Exception as e:
            issues[name] = f"lesefehler: {e}"

    return issues

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

# ── Format Report ─────────────────────────────────────────────────────────────
def format_report(sb_ok, sb_msg, env_ok, missing_keys, script_results, log_issues):
    now = datetime.now().strftime("%d. %b · %H:%M")
    all_ok = sb_ok and env_ok and all(v == "OK" for v in script_results.values()) and not log_issues

    status_icon = "✅" if all_ok else "⚠️"
    lines = [f"{status_icon} <b>HEALTH CHECK</b> · {now}\n"]

    # Supabase
    sb_icon = "✅" if sb_ok else "❌"
    lines.append(f"{sb_icon} <b>Supabase</b> — {sb_msg}")

    # Env
    if env_ok:
        lines.append("✅ <b>.env</b> — alle Keys vorhanden")
    else:
        lines.append(f"❌ <b>.env</b> — fehlt: {', '.join(missing_keys)}")

    # Scripts
    script_errors = {k: v for k, v in script_results.items() if v != "OK"}
    if not script_errors:
        lines.append(f"✅ <b>Scripts</b> — {len(script_results)} OK")
    else:
        lines.append(f"⚠️ <b>Scripts</b>:")
        for k, v in script_errors.items():
            lines.append(f"   • {k}: {v}")

    # Logs
    if not log_issues:
        lines.append("✅ <b>LaunchAgent Logs</b> — keine Fehler")
    else:
        lines.append("⚠️ <b>LaunchAgent Logs</b>:")
        for name, issue in log_issues.items():
            lines.append(f"   • {name}: {issue}")

    if all_ok:
        lines.append("\n<b>Alles grün.</b> Guten Morgen! ☕")
    else:
        lines.append(f"\n<a href='{DASHBOARD_URL}'>📊 Dashboard</a>")

    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pipo System Health Check")
    parser.add_argument("--dry-run", action="store_true", help="Terminal-Vorschau, kein Telegram")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*50}")
    print(f"  ❤️  PIPO HEALTH CHECK — {datetime.now().strftime('%H:%M')}")
    print(f"{'='*50}{X}\n")

    # 1. Supabase
    print(f"{B}Prüfe Supabase...{X}", end="", flush=True)
    sb_ok, sb_msg = check_supabase()
    icon = f"{G}✅{X}" if sb_ok else f"{R}❌{X}"
    print(f" {icon} {sb_msg}")

    # 2. Env
    print(f"{B}Prüfe .env...{X}", end="", flush=True)
    env_ok, missing = check_env()
    if env_ok:
        print(f" {G}✅ alle Keys{X}")
    else:
        print(f" {R}❌ fehlt: {', '.join(missing)}{X}")

    # 3. Scripts
    print(f"{B}Prüfe Scripts...{X}", end="", flush=True)
    scripts = check_scripts()
    errors = {k: v for k, v in scripts.items() if v != "OK"}
    if not errors:
        print(f" {G}✅ {len(scripts)} OK{X}")
    else:
        print(f" {Y}⚠️  {len(errors)} Probleme{X}")
        for k, v in errors.items():
            print(f"   {R}• {k}: {v}{X}")

    # 4. Logs
    print(f"{B}Prüfe LaunchAgent Logs...{X}", end="", flush=True)
    log_issues = check_logs()
    if not log_issues:
        print(f" {G}✅ alles OK{X}")
    else:
        print(f" {Y}⚠️  {len(log_issues)} Issues{X}")
        for name, issue in log_issues.items():
            print(f"   {Y}• {name}: {issue}{X}")

    # Report
    report = format_report(sb_ok, sb_msg, env_ok, missing, scripts, log_issues)

    all_ok = sb_ok and env_ok and not errors and not log_issues
    if all_ok:
        print(f"\n{G}{'='*50}")
        print(f"  ✅ HEALTH_OK — Alles grün")
        print(f"{'='*50}{X}")

    if args.dry_run:
        print(f"\n{BOLD}HEALTH REPORT:{X}\n{report}\n")
    else:
        tg_send(report)
        if not args.dry_run:
            print(f"\n{G}✅ Telegram Report gesendet{X}\n")

if __name__ == "__main__":
    main()
