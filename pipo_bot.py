#!/usr/bin/env python3
"""
pipo_bot.py — Pipo Interactive Telegram Bot
============================================
Sendet Morning Brief mit Inline-Buttons und hört auf Philipp's Antworten.
Philipp tippt einmal → Pipo loggt, aktualisiert Stage, bestätigt.

Usage:
  python3 pipo_bot.py --brief            # Brief senden + Listener starten
  python3 pipo_bot.py --brief --top 5    # Nur Top 5
  python3 pipo_bot.py --brief --region DE
  python3 pipo_bot.py --listen           # Nur Listener (Daemon-Modus)
  python3 pipo_bot.py --brief --dry-run  # Terminal-Vorschau (kein Telegram)

Voraussetzungen:
  export SUPABASE_URL=...
  export SUPABASE_KEY=...
  export ANTHROPIC_API_KEY=...
  export TELEGRAM_BOT_TOKEN=...
  export TELEGRAM_CHAT_ID=...

Supabase SQL (einmalig ausführen):
  CREATE TABLE IF NOT EXISTS activities (
    id BIGSERIAL PRIMARY KEY,
    lead_id BIGINT REFERENCES leads(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );
"""

import os, sys, json, time, argparse, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ.get("SUPABASE_URL",  "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY",  "")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

DASHBOARD_URL = "https://pipo-bitwise-lead-tracker.streamlit.app"
TOP_N_DEFAULT = 10
REGION_SCORE  = {"DE": 25, "CH": 22, "UAE": 20, "UK": 18, "NORDICS": 15, "EUROPE": 10, "OTHER": 5}

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

def sb_insert(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=body, method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status

def log_activity(lead_id, action, notes=""):
    """Logt eine Aktion in die activities Tabelle."""
    try:
        sb_insert("activities", [{
            "lead_id": lead_id,
            "action":  action,
            "notes":   notes,
        }])
    except Exception as e:
        # Falls Tabelle noch nicht existiert → graceful
        print(f"{Y}  ⚠️ Activity-Log fehlgeschlagen (Tabelle vorhanden?): {e}{X}")
        print(f"     SQL zum Erstellen: CREATE TABLE IF NOT EXISTS activities (id BIGSERIAL PRIMARY KEY, lead_id BIGINT REFERENCES leads(id) ON DELETE SET NULL, action TEXT NOT NULL, notes TEXT, created_at TIMESTAMPTZ DEFAULT NOW());")

def update_lead_stage(lead_id, stage):
    """Setzt Stage des Leads in Supabase."""
    try:
        sb_patch("leads", f"id=eq.{lead_id}", {
            "stage": stage,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        })
    except Exception as e:
        print(f"{R}  Stage-Update fehlgeschlagen: {e}{X}")

# ── Telegram ──────────────────────────────────────────────────────────────────
def tg_request(method, payload):
    """Sendet beliebige Telegram Bot API Request."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}",
        data=data, method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"{R}TG {method} HTTP {e.code}: {body}{X}")
        return {"ok": False}
    except Exception as e:
        print(f"{R}TG {method} Fehler: {e}{X}")
        return {"ok": False}

def tg_send(text, parse_mode="HTML", disable_preview=True):
    result = tg_request("sendMessage", {
        "chat_id": TELEGRAM_CHAT,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview
    })
    return result.get("result", {}).get("message_id")

def tg_send_with_buttons(text, lead_id, company, parse_mode="HTML"):
    """Sendet eine Nachricht mit Inline-Keyboard Buttons."""
    # callback_data max 64 Bytes: "action:lead_id"
    result = tg_request("sendMessage", {
        "chat_id": TELEGRAM_CHAT,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Email gesendet",    "callback_data": f"s:{lead_id}"},
                {"text": "⏭ Skip",               "callback_data": f"x:{lead_id}"},
                {"text": "🔔 Follow-Up in 5T",  "callback_data": f"f:{lead_id}"}
            ]]
        }
    })
    return result.get("result", {}).get("message_id")

def tg_remove_buttons(chat_id, message_id):
    """Entfernt nur die Inline-Buttons — berührt den Text nicht (sicherer als editMessageText)."""
    tg_request("editMessageReplyMarkup", {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": []}
    })

def tg_answer_callback(callback_query_id, text=""):
    """Bestätigt einen Callback (verhindert 'Loading...' in Telegram)."""
    tg_request("answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": False
    })

def tg_get_updates(offset=0, timeout=30):
    """Long Polling: holt neue Updates ab offset."""
    result = tg_request("getUpdates", {
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": ["callback_query", "message"]
    })
    return result.get("result", [])

# ── Load Top Leads ────────────────────────────────────────────────────────────
def load_top_leads(region=None, top_n=TOP_N_DEFAULT):
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

        upd = l.get("updated_at") or ""
        try:
            dt = datetime.fromisoformat(upd.replace("Z", "+00:00"))
            days_inactive = max(0, (now - dt.replace(tzinfo=None)).days)
        except:
            days_inactive = 30

        tier = l.get("tier") or 3
        tier_score   = {1: 40, 2: 25, 3: 10, 4: 0}.get(int(tier), 0)
        region_score = REGION_SCORE.get(l.get("region") or "DE", 5)
        meddp_score  = min(meddpicc / 80 * 20, 20)
        inact_score  = min(days_inactive / 30 * 10, 10)
        deal_score   = min((l.get("expected_deal_size_millions") or 0) / 50 * 5, 5)
        priority     = tier_score + region_score + meddp_score + inact_score + deal_score

        scored.append({
            **l,
            "meddpicc": meddpicc,
            "ql": ql,
            "days_inactive": days_inactive,
            "priority": priority,
            "m_pain":     (score_data.get("pain") or 0) if score_data else 0,
            "m_champion": (score_data.get("champion") or 0) if score_data else 0,
            "m_economic": (score_data.get("economic_buyer") or 0) if score_data else 0,
        })

    scored.sort(key=lambda x: x["priority"], reverse=True)
    return scored[:top_n]

# ── Google News Research ──────────────────────────────────────────────────────
def research_company(company, region="DE"):
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
            title = (item.findtext("title") or "").split(" - ")[0].strip()
            if title:
                news.append(f"• {title[:90]}")
        return news if news else []
    except:
        return []

# ── Claude: Brief + Email Draft ───────────────────────────────────────────────
def generate_brief_and_email(lead, news_items):
    news_text = "\n".join(news_items) if news_items else "Keine aktuellen News gefunden."
    lang = "Deutsch" if lead.get("region") in ("DE", "AT", "CH") else "Englisch"
    region = lead.get("region", "DE")
    use_du = region in ("DE", "AT", "CH") or (lead.get("industry") or "").lower() in (
        "crypto/blockchain", "crypto", "blockchain", "defi", "fintech"
    )
    anrede = lead.get("contact_person", "").split()[0] if lead.get("contact_person") else "zusammen"

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

ECHTE PHILIPP-BEISPIELE:
→ "Hallo Pascal, vielen Dank für deine herzliche Nachricht. Bei uns stehen große Neuigkeiten an — ich würde mich gerne kurz austauschen. Wäre dir ein 15-minütiges Gespräch nächste Woche möglich? Viele Grüße aus Dubai, Philipp"
→ "Hi Guy, Really enjoyed the chat earlier. From what you shared, I feel like there's a solid overlap. Once you've had a chance to look through the deck, just send me a few time slots. Best, Philipp"

Antworte NUR in diesem JSON-Format:
{{
  "why_now": "1 präziser Satz: warum JETZT kontaktieren",
  "angle": "Der eine stärkste Sales-Angle speziell für diesen Lead",
  "risk": "Das größte Risiko warum dieser Deal nicht klappt",
  "subject": "Betreff: kurz, spezifisch, max. 8 Wörter",
  "email": "Vollständiger Email-Body — direkt sendbar"
}}"""

    payload = json.dumps({
        "model": "claude-sonnet-4-5-20250929",
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

# ── Format Lead Message ────────────────────────────────────────────────────────
def format_lead_message(rank, lead, brief, news):
    ql_emoji   = {"QUALIFIED": "🟢", "PROBABLE": "🔵", "POSSIBLE": "🟡", "UNQUALIFIED": "⚪"}.get(lead["ql"], "⚪")
    tier_emoji = {1: "⭐", 2: "🔹", 3: "▫️"}.get(int(lead.get("tier") or 3), "▫️")
    region     = lead.get("region") or "?"
    stage      = lead.get("stage") or "prospecting"
    inactive   = lead.get("days_inactive") or 0
    aum        = lead.get("aum_estimate_millions") or 0
    deal       = lead.get("expected_deal_size_millions") or 0

    linkedin   = lead.get("linkedin") or ""
    li_link    = f'\n🔗 <a href="{linkedin}">LinkedIn</a>' if linkedin else ""

    news_block = ""
    if news:
        news_block = "\n\n<b>📰 Aktuelle News:</b>\n" + "\n".join([f"  {n}" for n in news[:2]])

    return f"""{'━'*30}
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

# ── Handle Callback Query (Button Press) ──────────────────────────────────────
ACTION_CONFIG = {
    "s": {
        "label":     "✅ Email gesendet",
        "stage":     "discovery",
        "activity":  "email_sent",
        "confirm":   "📬 Perfekt! Email als gesendet markiert. Stage → Discovery.",
        "alert":     "✅ Geloggt — gut gemacht!",
        "emoji":     "✅",
    },
    "x": {
        "label":     "⏭ Skip",
        "stage":     None,          # Stage nicht ändern
        "activity":  "skipped",
        "confirm":   "⏭ Lead übersprungen. Kommt morgen nicht mehr ins Briefing.",
        "alert":     "⏭ Geskippt",
        "emoji":     "⏭",
    },
    "f": {
        "label":     "🔔 Follow-Up in 5T",
        "stage":     None,          # Stage bleibt
        "activity":  "followup_scheduled",
        "confirm":   "🔔 Follow-Up in 5 Tagen vorgemerkt. Pipo erinnert dich.",
        "alert":     "🔔 Follow-Up gesetzt!",
        "emoji":     "🔔",
    },
}

def handle_callback(callback):
    """Verarbeitet einen Button-Tap von Philipp."""
    try:
        cb_id   = callback.get("id")
        data    = callback.get("data", "")
        chat_id = callback["message"]["chat"]["id"]
        msg_id  = callback["message"]["message_id"]
        company = ""  # wird unten aus der Nachricht extrahiert

        # Parse callback_data: "action:lead_id"
        if ":" not in data:
            tg_answer_callback(cb_id, "Unbekannte Aktion")
            return

        action_key, lead_id_str = data.split(":", 1)
        try:
            lead_id = int(lead_id_str)
        except ValueError:
            tg_answer_callback(cb_id, "Ungültige Lead-ID")
            return

        cfg = ACTION_CONFIG.get(action_key)
        if not cfg:
            tg_answer_callback(cb_id, "Unbekannte Aktion")
            return

        print(f"  {G}→ Callback: {cfg['label']} für Lead ID {lead_id}{X}")

        # 1. Callback SOFORT bestätigen — verhindert "Loading..." in Telegram
        tg_answer_callback(cb_id, cfg["alert"])

        # 2. Buttons entfernen (nur Markup editieren, kein Text-Truncation-Problem)
        tg_remove_buttons(chat_id, msg_id)

        # 3. Aktion ausführen
        log_activity(lead_id, cfg["activity"], "Via Telegram Bot")

        if cfg["stage"]:
            update_lead_stage(lead_id, cfg["stage"])
            print(f"     Stage → {cfg['stage']}")

        # 4. Kurze Bestätigung als neue Nachricht
        ts = datetime.now().strftime("%H:%M")
        tg_send(
            f"{cfg['emoji']} <b>{cfg['label']}</b> · Lead #{lead_id} · {ts}\n"
            f"{cfg['confirm']}\n\n"
            f"<a href='{DASHBOARD_URL}'>📊 Dashboard öffnen</a>"
        )
        print(f"     {G}✓ Fertig{X}")

    except Exception as e:
        # Listener darf NIE crashen — Fehler loggen und weitermachen
        print(f"  {R}⚠️ Callback-Fehler: {e}{X}")
        try:
            tg_answer_callback(callback.get("id", ""), "Fehler — bitte nochmal tippen")
        except:
            pass

# ── Long Polling Listener ──────────────────────────────────────────────────────
def run_listener(duration_minutes=None):
    """
    Hört auf Button-Taps via Telegram Long Polling.
    duration_minutes=None → läuft unbegrenzt (Daemon-Modus)
    """
    label = f"für {duration_minutes} Min." if duration_minutes else "dauerhaft"
    print(f"\n{BOLD}{'='*50}")
    print(f"  👂 PIPO LISTENER {label.upper()}")
    print(f"{'='*50}{X}")
    print(f"  Warte auf Button-Taps von Philipp...")
    print(f"  STRG+C zum Beenden\n")

    # ── Wichtig: Alle alten/pending Updates überspringen ──────────────────────
    # Ohne das verarbeitet der Listener alte Callbacks aus vorherigen Sessions
    # und der Offset springt vor, sodass neue Taps verpasst werden.
    print(f"  Überspringe alte Updates...", end="", flush=True)
    try:
        pending = tg_get_updates(offset=0, timeout=0)
        if pending:
            offset = pending[-1]["update_id"] + 1
            print(f" {len(pending)} übersprungen (offset={offset})")
        else:
            print(f" keine alten Updates")
    except Exception as e:
        print(f" {Y}Fehler beim Skip: {e}{X}")
    # ──────────────────────────────────────────────────────────────────────────

    start  = time.time()

    while True:
        # Prüfe ob Zeit abgelaufen
        if duration_minutes and (time.time() - start) > duration_minutes * 60:
            print(f"\n{Y}  ⏰ Listening-Zeit abgelaufen ({duration_minutes} Min.){X}")
            break

        try:
            updates = tg_get_updates(offset=offset, timeout=30)
        except KeyboardInterrupt:
            print(f"\n{G}  👋 Listener beendet.{X}")
            break
        except Exception as e:
            print(f"  {R}Polling Fehler: {e}{X} — retry in 5s")
            time.sleep(5)
            continue

        for update in updates:
            update_id = update.get("update_id", 0)
            offset = max(offset, update_id + 1)  # Nicht nochmal verarbeiten

            # Callback Query (Button Tap)
            if "callback_query" in update:
                cb = update["callback_query"]
                # Nur aus unserem Chat
                if str(cb["message"]["chat"]["id"]) == str(TELEGRAM_CHAT):
                    handle_callback(cb)

            # Nachrichten-Commands (optional)
            elif "message" in update:
                msg = update["message"]
                if str(msg["chat"]["id"]) == str(TELEGRAM_CHAT):
                    text = msg.get("text", "").strip().lower()
                    if text in ("/status", "/pipo"):
                        tg_send(f"🤖 <b>Pipo ist aktiv</b>\n{datetime.now().strftime('%H:%M:%S')}\n<a href='{DASHBOARD_URL}'>📊 Dashboard</a>")
                    elif text == "/help":
                        tg_send(
                            "🤖 <b>Pipo Bot Befehle:</b>\n\n"
                            "/status — Pipo aktiv?\n"
                            "/pipo — wie /status\n"
                            "/help — diese Hilfe\n\n"
                            "Button-Aktionen:\n"
                            "✅ <b>Email gesendet</b> — Stage → Discovery, Activity geloggt\n"
                            "⏭ <b>Skip</b> — Lead übersprungen, Activity geloggt\n"
                            "🔔 <b>Follow-Up in 5T</b> — Erinnerung vorgemerkt"
                        )

# ── Morning Brief mit Buttons ──────────────────────────────────────────────────
def run_brief(top_n=TOP_N_DEFAULT, region=None, dry_run=False, listen_after=True):
    now_str = datetime.now().strftime("%A, %d. %b %Y · %H:%M")

    print(f"\n{BOLD}{'='*60}")
    print(f"  🤖 PIPO MORNING BRIEF (Interaktiv)")
    print(f"  {now_str}")
    print(f"{'='*60}{X}\n")

    print(f"{B}Loading top {top_n} leads...{X}")
    leads = load_top_leads(region=region, top_n=top_n)
    if not leads:
        print(f"{R}Keine Leads gefunden!{X}")
        return

    print(f"  → {G}{len(leads)} Leads geladen{X}\n")

    header = f"""🤖 <b>PIPO MORNING BRIEF</b>
{now_str}
<a href="{DASHBOARD_URL}">📊 Dashboard öffnen</a>

Heute: <b>{len(leads)} priorisierte Leads</b> mit Research &amp; Email-Drafts.
Tap die Buttons nach jedem Lead — Pipo loggt alles automatisch.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    if not dry_run:
        tg_send(header)
        time.sleep(0.5)
    else:
        print(f"\n{BOLD}HEADER:{X}\n{header}\n")

    for i, lead in enumerate(leads, 1):
        company  = lead["company"]
        lead_id  = lead["id"]
        print(f"  [{i}/{len(leads)}] {company} — Research...", end="", flush=True)

        news = research_company(company, lead.get("region", "DE"))
        print(f" {len(news)} News → Brief...", end="", flush=True)

        try:
            brief = generate_brief_and_email(lead, news)
        except Exception as e:
            print(f" {R}Fehler: {e}{X}")
            brief = {
                "why_now": "KI-Analyse nicht verfügbar.",
                "angle":   lead.get("use_case") or "ETH-Staking-Potenzial",
                "risk":    "Manuelle Bewertung empfohlen.",
                "subject": f"ETH-Staking für {company}",
                "email":   f"Hallo,\n\nichts Besonderes vorbereitet — bitte manuell prüfen.\n\nViele Grüße,\nPhilipp"
            }

        print(f" {G}✓{X}")

        msg = format_lead_message(i, lead, brief, news)

        if not dry_run:
            tg_send_with_buttons(msg, lead_id, company)
            time.sleep(1.5)  # Telegram Rate Limit
        else:
            print(f"\n{BOLD}LEAD {i}:{X}\n{msg}")
            print(f"\n  Buttons: [✅ Email gesendet | ⏭ Skip | 🔔 Follow-Up in 5T]")
            print(f"  callback_data: s:{lead_id} | x:{lead_id} | f:{lead_id}")
            print(f"\n{'─'*60}\n")

    footer = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>Brief gesendet</b> — {len(leads)} Leads · Tippe die Buttons direkt!

<i>Pipo hört jetzt auf deine Antworten...</i>
<a href="{DASHBOARD_URL}">📊 Dashboard</a> · Powered by Pipo 🤖"""

    if not dry_run:
        tg_send(footer)
        print(f"\n{G}{BOLD}✅ Brief gesendet — {len(leads)} Leads{X}")

        if listen_after:
            # Nach Brief: Listener für 8 Stunden (ganzer Arbeitstag)
            run_listener(duration_minutes=480)
    else:
        print(f"\n{BOLD}FOOTER:{X}\n{footer}\n")
        print(f"\n{G}{BOLD}✅ Dry Run fertig{X}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pipo Interactive Telegram Bot")
    parser.add_argument("--brief",      action="store_true", help="Morning Brief senden")
    parser.add_argument("--listen",     action="store_true", help="Nur Listener (Daemon)")
    parser.add_argument("--top",        type=int, default=TOP_N_DEFAULT, help="Anzahl Leads")
    parser.add_argument("--region",     help="Nur eine Region (z.B. DE, CH, UAE)")
    parser.add_argument("--dry-run",    action="store_true", help="Terminal-Vorschau, kein Telegram")
    parser.add_argument("--no-listen",  action="store_true", help="Kein Listener nach Brief")
    args = parser.parse_args()

    # Validation
    if not args.dry_run:
        if not SUPABASE_KEY:
            print(f"{R}❌ SUPABASE_KEY nicht gesetzt{X}"); sys.exit(1)
        if not ANTHROPIC_KEY and args.brief:
            print(f"{R}❌ ANTHROPIC_API_KEY nicht gesetzt{X}"); sys.exit(1)
        if not TELEGRAM_TOKEN:
            print(f"{R}❌ TELEGRAM_BOT_TOKEN nicht gesetzt{X}"); sys.exit(1)
        if not TELEGRAM_CHAT:
            print(f"{R}❌ TELEGRAM_CHAT_ID nicht gesetzt{X}"); sys.exit(1)

    if args.brief:
        run_brief(
            top_n=args.top,
            region=args.region,
            dry_run=args.dry_run,
            listen_after=not args.no_listen
        )
    elif args.listen:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
            print(f"{R}❌ Telegram Credentials fehlen{X}"); sys.exit(1)
        run_listener(duration_minutes=None)  # Läuft bis STRG+C
    else:
        parser.print_help()
        print(f"\n{Y}Beispiele:{X}")
        print(f"  python3 pipo_bot.py --brief           # Brief senden + Listener")
        print(f"  python3 pipo_bot.py --brief --top 5   # Nur Top 5")
        print(f"  python3 pipo_bot.py --listen          # Nur Listener (Daemon)")
        print(f"  python3 pipo_bot.py --brief --dry-run # Terminal-Vorschau")

if __name__ == "__main__":
    main()
