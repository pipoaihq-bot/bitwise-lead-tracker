#!/usr/bin/env python3
"""
pipo_morning_brief.py — Pipo's Autonomes Tages-Briefing
========================================================
Sendet täglich 10 Top-Leads mit Research + fertigen Email-Drafts via Telegram.
Keine halben Sachen: Jeder Lead kommt mit Kontext, Begründung und einer Email
die du nur noch kopieren und senden musst.

Setup (einmalig):
  python3 pipo_morning_brief.py --setup

Usage:
  python3 pipo_morning_brief.py              # Top 10, alle Regionen
  python3 pipo_morning_brief.py --top 5      # Nur Top 5
  python3 pipo_morning_brief.py --region DE  # Nur DE-Leads
  python3 pipo_morning_brief.py --dry-run    # Terminal-Vorschau, kein Telegram
"""

import os, sys, json, time, argparse, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL  = os.environ.get("SUPABASE_URL",  "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY",  "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

DASHBOARD_URL = "https://pipo-bitwise-lead-tracker.streamlit.app"
TOP_N_DEFAULT = 10

# Region-Priorität für Scoring
REGION_SCORE = {"DE": 25, "CH": 22, "UAE": 20, "UK": 18, "NORDICS": 15, "EUROPE": 10, "OTHER": 5}

# ── Colors (Terminal) ────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; X = "\033[0m"; BOLD = "\033[1m"

# ── Supabase ─────────────────────────────────────────────────────────────────
def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def sb_patch(path, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}?{params}",
        data=body, method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status

# ── Telegram ─────────────────────────────────────────────────────────────────
def tg_send(text, parse_mode="HTML", disable_preview=True, reply_markup=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print(f"\n{Y}[TELEGRAM]{X} {text[:200]}...\n")
        return True
    payload = {
        "chat_id": TELEGRAM_CHAT,
        "text": text[:4096],
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"{R}Telegram Fehler: {e}{X}")
        return False

def make_lead_buttons(lead_id):
    """Inline-Keyboard für jeden Lead im Briefing — direkte Actions ohne tippen."""
    lid = str(lead_id)
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Email gesendet",  "callback_data": f"e:{lid}"},
                {"text": "✏️ Neue Email",      "callback_data": f"r:{lid}"},
            ],
            [
                {"text": "🔵 Discovery",  "callback_data": f"s:{lid}:dis"},
                {"text": "🟡 Proposal",   "callback_data": f"s:{lid}:prp"},
                {"text": "🟢 Won",        "callback_data": f"s:{lid}:won"},
            ],
            [
                {"text": "💡 Battle Card", "callback_data": f"c:{lid}"},
                {"text": "🚫 Skip",        "callback_data": f"sk:{lid}"},
            ],
        ]
    }

def tg_get_updates():
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# ── Load Top Leads ────────────────────────────────────────────────────────────
def load_top_leads(region=None, top_n=TOP_N_DEFAULT):
    # Load leads with scores
    params = ("select=id,company,contact_person,title,email,linkedin,industry,"
              "region,tier,aum_estimate_millions,expected_deal_size_millions,"
              "stage,use_case,updated_at,"
              "meddpicc_scores(total_score,qualification_status,"
              "metrics,economic_buyer,pain,champion)"
              "&stage=not.in.(closed_won,closed_lost)&order=tier.asc")
    if region:
        params += f"&region=eq.{region}"

    all_leads = []
    offset = 0
    while True:
        chunk = sb_get("leads", params + f"&offset={offset}&limit=1000")
        if not chunk: break
        all_leads.extend(chunk)
        if len(chunk) < 1000: break
        offset += 1000

    now = datetime.now()
    scored = []
    for l in all_leads:
        score_data = l.pop("meddpicc_scores", None)
        if isinstance(score_data, list):
            score_data = score_data[0] if score_data else None
        meddpicc = (score_data.get("total_score") or 0) if score_data else 0
        ql = (score_data.get("qualification_status") or "UNQUALIFIED") if score_data else "UNQUALIFIED"

        # Days inactive
        upd = l.get("updated_at") or ""
        try:
            dt = datetime.fromisoformat(upd.replace("Z", "+00:00"))
            days_inactive = max(0, (now - dt.replace(tzinfo=None)).days)
        except:
            days_inactive = 30

        # Priority Score (Pipo's eigene Gewichtung)
        tier = l.get("tier") or 3
        tier_score    = {1: 40, 2: 25, 3: 10, 4: 0}.get(int(tier), 0)
        region_score  = REGION_SCORE.get(l.get("region") or "DE", 5)
        meddp_score   = min(meddpicc / 80 * 20, 20)  # max 20 Punkte
        inact_score   = min(days_inactive / 30 * 10, 10)  # max 10 Punkte (länger inaktiv = mehr Potenzial)
        deal_score    = min((l.get("expected_deal_size_millions") or 0) / 50 * 5, 5)
        priority      = tier_score + region_score + meddp_score + inact_score + deal_score

        scored.append({
            **l,
            "meddpicc": meddpicc,
            "ql": ql,
            "days_inactive": days_inactive,
            "priority": priority,
            "m_pain": (score_data.get("pain") or 0) if score_data else 0,
            "m_champion": (score_data.get("champion") or 0) if score_data else 0,
            "m_economic": (score_data.get("economic_buyer") or 0) if score_data else 0,
        })

    # Sort by priority
    scored.sort(key=lambda x: x["priority"], reverse=True)
    return scored[:top_n]

# ── Google News Research ──────────────────────────────────────────────────────
def research_company(company, region="DE"):
    """Sucht aktuelle News über das Unternehmen via Google News RSS."""
    try:
        lang = "de" if region in ("DE", "AT", "CH") else "en"
        gl   = "DE" if region == "DE" else "CH" if region == "CH" else "AE" if region == "UAE" else "GB"
        query = urllib.parse.quote(f'"{company}" crypto ETH staking digital assets')
        url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={gl}&ceid={gl}:{lang}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            root = ET.fromstring(r.read())
        items = root.findall(".//item")[:3]
        news = []
        for item in items:
            title = item.findtext("title") or ""
            pub   = item.findtext("pubDate") or ""
            # Trim feed source from title (e.g. " - Bloomberg")
            title = title.split(" - ")[0].strip()
            if title:
                news.append(f"• {title[:90]}")
        return news if news else []
    except:
        return []

# ── Claude: Research Brief + Email Draft ─────────────────────────────────────
def generate_brief_and_email(lead, news_items):
    """Generiert Research-Analyse und fertigen Email-Draft via Claude Sonnet."""
    news_text = "\n".join(news_items) if news_items else "Keine aktuellen News gefunden."
    lang = "Deutsch" if lead.get("region") in ("DE", "AT", "CH") else "Englisch"

    # Language + formality rule
    region = lead.get('region', 'DE')
    use_du = region in ('DE', 'AT', 'CH') or (lead.get('industry') or '').lower() in ('crypto/blockchain', 'crypto', 'blockchain', 'defi', 'fintech')
    anrede = lead.get('contact_person', '').split()[0] if lead.get('contact_person') else 'zusammen'

    prompt = f"""Du bist Pipo, Pre-Sales Analyst für Philipp Sandor (HEAD EMEA, Bitwise Asset Management, Dubai).

DEINE AUFGABE: Analysiere diesen Lead und schreibe eine Email GENAU in Philipps Stimme.

═══ LEAD ═══
Unternehmen: {lead['company']}
Kontakt: {lead.get('contact_person') or 'unbekannt'} ({lead.get('title') or 'Titel unbekannt'})
Region: {region} | Industry: {lead.get('industry') or 'Institutional'}
AUM: ~€{lead.get('aum_estimate_millions') or 0:.0f}M | Deal: €{lead.get('expected_deal_size_millions') or 0:.0f}M
Stage: {lead.get('stage')} | Inaktiv seit: {lead['days_inactive']} Tagen
MEDDPICC: {lead['meddpicc']}/80 ({lead['ql']})
Pain: {lead['m_pain']}/10 | Champion: {lead['m_champion']}/10

═══ AKTUELLE NEWS/KONTEXT ═══
{news_text}

═══ BITWISE BOS (NUR 1 FAKT PRO EMAIL VERWENDEN) ═══
- ~$5B ETH gestaked, non-custodial
- Zero Slashings seit Genesis September 2022
- 99.984% Uptime 2025
- APR 3.170% vs Benchmark 3.015% (+0.155% Outperformance)
- MiCA-konform, KPMG-geprüft
- Custody-Integration (Fireblocks, Ledger Enterprise, etc.)
- 40+ institutionelle Kunden in EMEA

═══ PHILIPPS ECHTER SCHREIBSTIL (STRIKT EINHALTEN) ═══

STIMME: Warm, direkt, menschlich. Nie corporate. Nie wie Marketing.

STRUKTUR (max. 4 Sätze im Body):
1. Persönliche Eröffnung — warmth first, niemals direkt mit Pitch starten
2. Konkreter Bezug zu IHNEN (aus News oder Kontext) — 1 Satz
3. EIN spezifischer Bitwise-Fakt der für sie relevant ist — 1 Satz, nicht mehr
4. CTA: entweder "Wäre ein 15-minütiger Austausch nächste Woche möglich?" ODER "https://calendly.com/psandor/30min"

ANREDE:
- Sprache: {lang}
- {'Verwende "du" und ersten Vornamen: "Hallo ' + anrede + ',"' if use_du else 'Verwende "Sie" und ersten Vornamen: "Hallo ' + anrede + ',"'}
- Crypto/Startup/Fintech → immer "du"
- Traditionelle Bank/Versicherung → "Sie"

SIGNATUR:
- Deutsch: "Viele Grüße aus Dubai,\\nPhilipp"
- Englisch: "Best,\\nPhilipp"

VERBOTEN:
❌ Mehrere Produkt-Facts auf einmal ("Zero Slashings, 99.984%, 3.17%, KPMG..." — NIEMALS so)
❌ "revolutionär", "cutting-edge", "synergies", "game-changing", "unique"
❌ Lange Einleitung über Bitwise als Firma
❌ "Ich hoffe diese Email findet Sie wohl"
❌ Mehr als einen CTA
❌ "Lassen Sie mich wissen ob Sie Interesse haben"
❌ Subject mit Fragezeichen UND Ausrufezeichen

ECHTE PHILIPP-BEISPIELE:
→ "Hallo Pascal, vielen Dank für deine herzliche Nachricht. Bei uns stehen große Neuigkeiten an — ich würde mich gerne kurz austauschen. Wäre dir ein 15-minütiges Gespräch nächste Woche möglich? Viele Grüße aus Dubai, Philipp"
→ "Hi Guy, Really enjoyed the chat earlier. From what you shared, I feel like there's a solid overlap — particularly around integration and reporting. Once you've had a chance to look through the deck, just send me a few time slots. Best, Philipp"
→ "Servus Flo, danke für unseren Austausch gestern. Ich denke der erste Use Case könnte ein cooles Projekt mit großem Potential werden. Lass uns ein tieferes Meeting arrangieren — ich richte mich nach deinem Kalender. Liebe Grüße, Philipp"

Antworte NUR in diesem JSON-Format:
{{
  "why_now": "1 präziser Satz: warum JETZT kontaktieren (basierend auf News/Stage/Inaktivität)",
  "angle": "Der eine stärkste Sales-Angle speziell für diesen Lead und diese Person",
  "risk": "Das größte Risiko warum dieser Deal nicht klappt",
  "subject": "Betreff: kurz, spezifisch, kein Spam-Trigger, max. 8 Wörter",
  "email": "Vollständiger Email-Body — direkt sendbar, kein Platzhalter, kein [Name]"
}}"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1200,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, method="POST",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        resp = json.loads(r.read())

    text = resp["content"][0]["text"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    return json.loads(text[start:end])

# ── Format Telegram Message ───────────────────────────────────────────────────
def format_lead_message(rank, lead, brief, news):
    ql_emoji = {"QUALIFIED": "🟢", "PROBABLE": "🔵", "POSSIBLE": "🟡", "UNQUALIFIED": "⚪"}.get(lead['ql'], "⚪")
    tier_emoji = {1: "⭐", 2: "🔹", 3: "▫️"}.get(int(lead.get("tier") or 3), "▫️")
    region = lead.get("region") or "?"
    stage  = lead.get("stage") or "prospecting"
    inactive = lead.get("days_inactive") or 0
    aum  = lead.get("aum_estimate_millions") or 0
    deal = lead.get("expected_deal_size_millions") or 0

    linkedin = lead.get("linkedin") or ""
    li_link  = f'\n🔗 <a href="{linkedin}">LinkedIn</a>' if linkedin else ""

    news_block = ""
    if news:
        news_block = "\n\n<b>📰 Aktuelle News:</b>\n" + "\n".join(
            [f"  {n}" for n in news[:2]]
        )

    msg = f"""{'━'*30}
<b>{rank}. {lead['company']}</b> {tier_emoji} {ql_emoji}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>{lead.get('contact_person') or '—'}</b>  <i>{lead.get('title') or ''}</i>
📍 {region} · {lead.get('industry') or 'Institutional'}{li_link}
📊 MEDDPICC <b>{lead['meddpicc']}/80</b> · Stage: {stage}
💰 AUM ~€{aum:.0f}M · Deal ~€{deal:.0f}M
⏰ Inaktiv: <b>{inactive} Tage</b>{news_block}

<b>🎯 Warum jetzt:</b>
{brief.get('why_now', '—')}

<b>💡 Angle:</b>
{brief.get('angle', '—')}

<b>⚠️ Risiko:</b>
<i>{brief.get('risk', '—')}</i>

<b>✉️ Email-Draft:</b>
<b>Betreff:</b> <code>{brief.get('subject', '')}</code>

<code>{brief.get('email', '')}</code>"""

    return msg

# ── Main Briefing ─────────────────────────────────────────────────────────────
def run_briefing(top_n=TOP_N_DEFAULT, region=None, dry_run=False):
    now_str = datetime.now().strftime("%A, %d. %b %Y · %H:%M")

    print(f"\n{BOLD}{'='*60}")
    print(f"  🤖 PIPO MORNING BRIEF")
    print(f"  {now_str}")
    print(f"{'='*60}{X}\n")

    # Load leads
    print(f"{B}Loading top {top_n} leads...{X}")
    leads = load_top_leads(region=region, top_n=top_n)
    if not leads:
        print(f"{R}Keine Leads gefunden!{X}")
        return

    print(f"  → {G}{len(leads)} Leads geladen{X}\n")

    # Header message
    header = f"""🤖 <b>PIPO MORNING BRIEF</b>
{now_str}
<a href="{DASHBOARD_URL}">📊 Dashboard öffnen</a>

Heute: <b>{len(leads)} priorisierte Leads</b> mit Research &amp; Email-Drafts.
Jede Email ist fertig zum Senden — kein Copy-Paste nötig.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    if not dry_run:
        tg_send(header)
        time.sleep(0.5)
    else:
        print(f"\n{BOLD}HEADER:{X}\n{header}\n")

    # Process each lead
    for i, lead in enumerate(leads, 1):
        company = lead['company']
        print(f"  [{i}/{len(leads)}] {company} — Research...", end="", flush=True)

        # Research
        news = research_company(company, lead.get("region", "DE"))
        print(f" {len(news)} News → Brief...", end="", flush=True)

        # Brief + Email
        try:
            brief = generate_brief_and_email(lead, news)
        except Exception as e:
            print(f" {R}Fehler: {e}{X}")
            brief = {
                "why_now": "KI-Analyse nicht verfügbar.",
                "angle": lead.get("use_case") or "ETH-Staking-Potenzial",
                "risk": "Manuelle Bewertung empfohlen.",
                "subject": f"ETH-Staking für {company}",
                "email": f"Sehr geehrte Damen und Herren,\n\nbei Bitwise Asset Management helfen wir institutionellen Investoren dabei, ihre ETH-Position zu optimieren. Ich würde mich über einen kurzen Austausch freuen.\n\nMit freundlichen Grüßen\nPhilipp Sandor\nHEAD EMEA | Bitwise Asset Management"
            }

        print(f" {G}✓{X}")

        # Format & send
        msg = format_lead_message(i, lead, brief, news)
        lead_id = lead.get("id")

        if not dry_run:
            buttons = make_lead_buttons(lead_id) if lead_id else None
            tg_send(msg, reply_markup=buttons)
            # We DON'T update updated_at so "days_inactive" stays accurate
            time.sleep(1.5)  # Telegram rate limit
        else:
            print(f"\n{BOLD}LEAD {i}:{X}\n{msg}\n")
            print(f"\n{'─'*60}\n")

    # Footer
    footer = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>Briefing abgeschlossen</b> — {len(leads)} Leads analysiert

Nächste Schritte:
1. Email senden → Lead in Dashboard auf "Discovery" setzen
2. Kein Reply in 5 Tagen → Pipo schickt Follow-Up Draft
3. Meeting gebucht → Stage auf "Solutioning"

<a href="{DASHBOARD_URL}">📊 Dashboard öffnen</a> · Powered by Pipo 🤖"""

    if not dry_run:
        tg_send(footer)
    else:
        print(f"\n{BOLD}FOOTER:{X}\n{footer}\n")

    print(f"\n{G}{BOLD}✅ Briefing fertig — {len(leads)} Leads mit Email-Drafts{X}")
    if not dry_run:
        print(f"  → Telegram: {len(leads)+2} Nachrichten gesendet")

# ── Setup Mode ────────────────────────────────────────────────────────────────
def run_setup():
    print(f"\n{BOLD}{'='*60}")
    print(f"  🤖 PIPO TELEGRAM SETUP")
    print(f"{'='*60}{X}\n")

    print(f"""
{BOLD}SCHRITT 1: Telegram Bot erstellen{X}
  1. Öffne Telegram → suche @BotFather
  2. Sende: /newbot
  3. Wähle einen Namen (z.B. "Pipo Bitwise")
  4. Wähle einen Username (z.B. "PipoBitwiseBot")
  5. Kopiere den Bot Token (sieht aus wie: 1234567890:AAF...)

{BOLD}SCHRITT 2: Chat ID herausfinden{X}
  1. Sende deinem neuen Bot eine beliebige Nachricht (z.B. "Hallo")
  2. Öffne in deinem Browser:
     https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates
  3. Suche nach "chat":{"id": XXXXXX} — das ist deine Chat ID

{BOLD}SCHRITT 3: Environment Variablen setzen{X}
  Füge diese Zeilen zu deiner ~/.zshrc hinzu:

  export TELEGRAM_BOT_TOKEN="1234567890:AAF..."
  export TELEGRAM_CHAT_ID="987654321"

  Dann: source ~/.zshrc

{BOLD}SCHRITT 4: Testen{X}
  python3 pipo_morning_brief.py --dry-run   # Terminal-Vorschau
  python3 pipo_morning_brief.py --top 1     # Ersten Lead via Telegram senden
""")

    # Test if token is already set
    if TELEGRAM_TOKEN:
        print(f"{G}✅ TELEGRAM_BOT_TOKEN ist gesetzt{X}")
        try:
            data = tg_get_updates()
            if data.get("ok"):
                updates = data.get("result", [])
                if updates:
                    chat_id = updates[-1]["message"]["chat"]["id"]
                    username = updates[-1]["message"]["chat"].get("first_name", "?")
                    print(f"{G}✅ Chat ID gefunden: {chat_id} (von: {username}){X}")
                    print(f"\n{Y}Füge dies zu ~/.zshrc hinzu:{X}")
                    print(f'  export TELEGRAM_CHAT_ID="{chat_id}"')
                else:
                    print(f"{Y}⚠️ Noch keine Nachrichten. Sende deinem Bot eine Nachricht und versuche nochmal.{X}")
        except Exception as e:
            print(f"{R}Bot Token ungültig: {e}{X}")
    else:
        print(f"{Y}⚠️ TELEGRAM_BOT_TOKEN nicht gesetzt{X}")

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pipo Morning Brief")
    parser.add_argument("--top",     type=int, default=TOP_N_DEFAULT, help="Anzahl Leads (default: 10)")
    parser.add_argument("--region",  help="Nur eine Region (z.B. DE, CH, UAE)")
    parser.add_argument("--dry-run", action="store_true", help="Nur im Terminal ausgeben, kein Telegram")
    parser.add_argument("--setup",   action="store_true", help="Telegram Bot Setup Anleitung")
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    if not SUPABASE_KEY:
        print(f"{R}❌ SUPABASE_KEY nicht gesetzt{X}"); sys.exit(1)
    if not ANTHROPIC_KEY:
        print(f"{R}❌ ANTHROPIC_API_KEY nicht gesetzt{X}"); sys.exit(1)
    if not args.dry_run and (not TELEGRAM_TOKEN or not TELEGRAM_CHAT):
        print(f"{R}❌ TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt{X}")
        print(f"  → Starte mit: python3 pipo_morning_brief.py --setup")
        print(f"  → Oder testen mit: python3 pipo_morning_brief.py --dry-run")
        sys.exit(1)

    run_briefing(top_n=args.top, region=args.region, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
