#!/usr/bin/env python3
"""
pipo_core.py — Shared Core Functions for Pipo System
=====================================================
Used by: pipo_telegram_bot.py, pipo_morning_brief.py, pipo_followup.py
Contains: Supabase helpers, Telegram helpers, news research, email generation,
          inline keyboard buttons, lead loading.
"""

import os, json, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ.get("SUPABASE_URL", "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY", "")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

DASHBOARD_URL = "https://pipo-bitwise-lead-tracker.streamlit.app"

REGION_SCORE = {"DE": 25, "CH": 22, "UAE": 20, "UK": 18, "NORDICS": 15, "EUROPE": 10, "OTHER": 5}

STAGE_ABBREV = {
    "pro": "prospecting", "dis": "discovery", "sol": "solutioning",
    "prp": "proposal",    "neg": "negotiation", "mtg": "meeting",
    "won": "closed_won",  "lst": "closed_lost",
}

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
            "Prefer": "return=representation"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# ── Telegram ──────────────────────────────────────────────────────────────────
def tg_send(chat_id, text, parse_mode="HTML", disable_preview=True, reply_markup=None):
    """Send message to Telegram. chat_id can be string or int."""
    if not TELEGRAM_TOKEN:
        print(f"[TG] {text[:200]}...")
        return True
    payload = {
        "chat_id": str(chat_id),
        "text": text[:4096],
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup if isinstance(reply_markup, str) else json.dumps(reply_markup)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"Telegram Fehler: {e}")
        return False

def tg_answer_callback(callback_id, text="✅", alert=False):
    payload = json.dumps({
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": alert,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
        data=payload, method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except:
        return None

def tg_get_updates(offset=0, timeout=30):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout={timeout}"
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout + 10) as r:
        return json.loads(r.read())

# ── Inline Keyboard Buttons ──────────────────────────────────────────────────
def make_lead_buttons(lead_id):
    """Inline keyboard with all lead actions — used by bot and morning brief."""
    lid = str(lead_id)
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Email gesendet",  "callback_data": f"e:{lid}"},
                {"text": "✏️ Neue Email",      "callback_data": f"r:{lid}"},
            ],
            [
                {"text": "🔵 Discovery",  "callback_data": f"s:{lid}:dis"},
                {"text": "📅 Meeting",    "callback_data": f"s:{lid}:mtg"},
                {"text": "🟡 Proposal",   "callback_data": f"s:{lid}:prp"},
            ],
            [
                {"text": "🟢 Won",        "callback_data": f"s:{lid}:won"},
                {"text": "❌ Lost",        "callback_data": f"s:{lid}:lst"},
                {"text": "🚫 Skip",        "callback_data": f"sk:{lid}"},
            ],
            [
                {"text": "💡 Battle Card", "callback_data": f"c:{lid}"},
            ],
        ]
    }

# ── Google News Research ──────────────────────────────────────────────────────
def research_company_news(company, region="DE"):
    """Aktuelle News via Google News RSS."""
    try:
        lang = "de" if region in ("DE", "AT", "CH") else "en"
        gl = "DE" if region == "DE" else "CH" if region == "CH" else "AE" if region == "UAE" else "GB"
        query = urllib.parse.quote(f'"{company}" crypto ETH staking digital assets')
        url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={gl}&ceid={gl}:{lang}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            root = ET.fromstring(r.read())
        items = root.findall(".//item")[:3]
        news = []
        for item in items:
            title = item.findtext("title") or ""
            title = title.split(" - ")[0].strip()
            if title:
                news.append(f"• {title[:90]}")
        return news if news else []
    except:
        return []

# ── Claude Email Generation ──────────────────────────────────────────────────
def generate_email_draft(lead, news_items):
    """Generiert Research-Analyse und fertigen Email-Draft via Claude Haiku."""
    news_text = "\n".join(news_items) if news_items else "Keine aktuellen News gefunden."
    region = lead.get("region", "DE")
    lang = "Deutsch" if region in ("DE", "AT", "CH") else "Englisch"
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
Stage: {lead.get('stage')} | Inaktiv seit: {lead.get('days_inactive', 0)} Tagen
MEDDPICC: {lead.get('meddpicc', 0)}/80

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
3. EIN spezifischer Bitwise-Fakt der für sie relevant ist — 1 Satz
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

Antworte NUR in diesem JSON-Format:
{{"why_now": "1 präziser Satz: warum JETZT kontaktieren",
  "angle": "Der eine stärkste Sales-Angle",
  "risk": "Das größte Risiko warum dieser Deal nicht klappt",
  "subject": "Betreff: kurz, max. 8 Wörter",
  "email": "Vollständiger Email-Body — direkt sendbar"}}"""

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
    end = text.rfind("}") + 1
    return json.loads(text[start:end])

# ── Lead Loading ──────────────────────────────────────────────────────────────
def load_lead_with_scores(lead_id):
    """Lädt einen Lead aus Supabase inkl. MEDDPICC Scores."""
    rows = sb_get("leads",
        f"id=eq.{lead_id}&select=*,meddpicc_scores(total_score,qualification_status,pain,champion,economic_buyer)")
    if not rows:
        return None
    lead = rows[0]
    sc = lead.pop("meddpicc_scores", None)
    if isinstance(sc, list):
        sc = sc[0] if sc else None
    lead["meddpicc"]     = (sc.get("total_score") or 0) if sc else 0
    lead["ql"]           = (sc.get("qualification_status") or "UNQUALIFIED") if sc else "UNQUALIFIED"
    lead["m_pain"]       = (sc.get("pain") or 0) if sc else 0
    lead["m_champion"]   = (sc.get("champion") or 0) if sc else 0
    lead["m_economic"]   = (sc.get("economic_buyer") or 0) if sc else 0
    lead["days_inactive"] = days_since(lead.get("updated_at"))
    return lead

def days_since(iso_str):
    """Berechnet Tage seit einem ISO-Datum."""
    if not iso_str:
        return 30
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except:
        return 30

def load_top_leads(region=None, top_n=10):
    """Load and score top leads from Supabase."""
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
        if not chunk:
            break
        all_leads.extend(chunk)
        if len(chunk) < 1000:
            break
        offset += 1000

    scored = []
    for l in all_leads:
        score_data = l.pop("meddpicc_scores", None)
        if isinstance(score_data, list):
            score_data = score_data[0] if score_data else None
        meddpicc = (score_data.get("total_score") or 0) if score_data else 0
        ql = (score_data.get("qualification_status") or "UNQUALIFIED") if score_data else "UNQUALIFIED"

        days_inactive = days_since(l.get("updated_at"))

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
            "m_pain": (score_data.get("pain") or 0) if score_data else 0,
            "m_champion": (score_data.get("champion") or 0) if score_data else 0,
            "m_economic": (score_data.get("economic_buyer") or 0) if score_data else 0,
        })

    scored.sort(key=lambda x: x["priority"], reverse=True)
    return scored[:top_n]

# ── Stale/Follow-Up Detection ────────────────────────────────────────────────
def find_stale_leads(days_threshold=5, stage_filter=None):
    """Find leads that need follow-up (in discovery/meeting but no update in X days)."""
    params = ("select=id,company,contact_person,title,email,region,stage,updated_at,"
              "meddpicc_scores(total_score)"
              "&stage=not.in.(closed_won,closed_lost,prospecting)")
    if stage_filter:
        params = params.replace("&stage=not.in.(closed_won,closed_lost,prospecting)",
                                f"&stage=eq.{stage_filter}")

    leads = sb_get("leads", params)
    stale = []
    for l in leads:
        sc = l.pop("meddpicc_scores", None)
        if isinstance(sc, list):
            sc = sc[0] if sc else None
        l["meddpicc"] = (sc.get("total_score") or 0) if sc else 0
        l["days_inactive"] = days_since(l.get("updated_at"))
        if l["days_inactive"] >= days_threshold:
            stale.append(l)

    stale.sort(key=lambda x: x["days_inactive"], reverse=True)
    return stale

def find_very_stale_leads(days_threshold=14):
    """Find leads stale for 14+ days — candidates for re-engagement or archiving."""
    return [l for l in find_stale_leads(days_threshold=days_threshold)
            if l["days_inactive"] >= days_threshold]

# ── Format Telegram Message ──────────────────────────────────────────────────
def format_lead_message(rank, lead, brief, news):
    ql_emoji = {"QUALIFIED": "🟢", "PROBABLE": "🔵", "POSSIBLE": "🟡", "UNQUALIFIED": "⚪"}.get(lead.get('ql', ''), "⚪")
    tier_emoji = {1: "⭐", 2: "🔹", 3: "▫️"}.get(int(lead.get("tier") or 3), "▫️")
    region = lead.get("region") or "?"
    stage = lead.get("stage") or "prospecting"
    inactive = lead.get("days_inactive") or 0
    aum = lead.get("aum_estimate_millions") or 0
    deal = lead.get("expected_deal_size_millions") or 0

    linkedin = lead.get("linkedin") or ""
    li_link = f'\n🔗 <a href="{linkedin}">LinkedIn</a>' if linkedin else ""

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
📊 MEDDPICC <b>{lead.get('meddpicc', 0)}/80</b> · Stage: {stage}
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
