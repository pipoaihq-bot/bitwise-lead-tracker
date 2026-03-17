#!/usr/bin/env python3
"""
pipo_telegram_bot.py — Pipo Interactive Telegram Bot
=====================================================
Lauscht auf Nachrichten im @Pipo_EMEA_Taskforce_bot und antwortet intelligent.

Unterstützte Befehle / natürliche Sprache:
  LinkedIn URL          → DB-Check + Profil-Enrichment + optionaler Add
  /top [n]              → Top N Leads aus StakeStream
  /status [company]     → MEDDPICC + Stage + letzte Aktivität
  /card [company]       → Battle Card generieren (ruft pipo_battlecard.py)
  /add [url] [company]  → Lead in Supabase anlegen
  /help                 → Alle Befehle

Beispiel:
  "haben wir sie? https://www.linkedin.com/in/beritfuss/"
  → Pipo antwortet: DB-Status, LinkedIn-Daten, Vorschlag zum Hinzufügen

Starten:
  . ./.env && python3 pipo_telegram_bot.py

Als macOS Service (automatisch beim Login):
  python3 pipo_telegram_bot.py --install   # installiert launchd plist
  python3 pipo_telegram_bot.py --uninstall
"""

import os, sys, json, time, re, urllib.request, urllib.parse, argparse, subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ.get("SUPABASE_URL",  "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY",  "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
LINKEDIN_LI_AT = os.environ.get("LINKEDIN_LI_AT", "")
LINKEDIN_LI_A  = os.environ.get("LINKEDIN_LI_A",  "")  # Enterprise: Sales Navigator session cookie
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
EXA_KEY        = os.environ.get("EXA_API_KEY", "")
LEADTRACKER    = Path(__file__).parent
DASHBOARD_URL  = "https://pipo-bitwise-lead-tracker.streamlit.app"
OPS_SCRIPT     = str(LEADTRACKER / "stakestream_ops.py")

POLL_INTERVAL  = 2   # Sekunden zwischen getUpdates-Aufrufen
LOG_FILE       = Path("/tmp/pipo_bot.log")

# ── Kontext-Gedächtnis pro Chat ───────────────────────────────────────────────
# Merkt sich den zuletzt diskutierten Lead pro chat_id
# { chat_id: {"li_url": ..., "name": ..., "company": ..., "profile": ..., "db_lead": ...} }
_context: dict = {}

# ── Utils ─────────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def days_since(ts_str):
    if not ts_str: return 999
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc) - ts).days)
    except: return 999

# ── Supabase ──────────────────────────────────────────────────────────────────
def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def sb_post(path, data):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        log(f"sb_post {path} HTTP {e.code}: {err_body[:300]}")
        raise

def sb_patch(path, params, data):
    url = f"{SUPABASE_URL}/rest/v1/{path}?{params}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="PATCH", headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

# ── Telegram ──────────────────────────────────────────────────────────────────
def tg_send(chat_id, text, parse_mode="HTML", reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=body, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"tg_send error: {e}")
        return None

def tg_get_updates(offset=0):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=30&limit=10"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"getUpdates error: {e}")
        return {"ok": False, "result": []}

# ── LinkedIn ──────────────────────────────────────────────────────────────────
_li_api = None

_li_cookie_expired = False  # Flag, damit wir die Warnung nur 1x senden

def _setup_li_session(sess):
    """Setzt alle LinkedIn Cookies und holt JSESSIONID für CSRF. Unterstützt Enterprise + Standard."""
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    sess.headers.update({"User-Agent": ua})
    sess.cookies.set("li_at", LINKEDIN_LI_AT, domain=".linkedin.com")
    if LINKEDIN_LI_A:  # Enterprise: braucht zusätzlich li_a
        sess.cookies.set("li_a", LINKEDIN_LI_A, domain=".linkedin.com")
    # JSESSIONID für CSRF holen
    try:
        resp = sess.get("https://www.linkedin.com/feed/", allow_redirects=False, timeout=10)
        jsid = sess.cookies.get("JSESSIONID", "") or resp.cookies.get("JSESSIONID", "")
    except Exception:
        jsid = sess.cookies.get("JSESSIONID", "")
    if jsid:
        clean_jsid = jsid.strip('"')
        sess.cookies.set("JSESSIONID", clean_jsid, domain=".linkedin.com")
        sess.headers.update({"csrf-token": clean_jsid})
    return jsid

def _check_li_at_valid(sess):
    """Prüft ob Cookies noch gültig sind (200 = ok, sonst abgelaufen)."""
    try:
        resp = sess.get(
            "https://www.linkedin.com/voyager/api/me",
            allow_redirects=False,
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False

def get_linkedin_api():
    global _li_api, _li_cookie_expired
    if _li_api:
        return _li_api
    if not LINKEDIN_LI_AT:
        return None
    try:
        from linkedin_api import Linkedin
        _li_api = Linkedin("", "", authenticate=False)
        sess = _li_api.client.session
        _setup_li_session(sess)

        # Cookie-Validity-Check — warnt wenn abgelaufen
        if not _check_li_at_valid(sess):
            if not _li_cookie_expired:
                _li_cookie_expired = True
                tg_send(TELEGRAM_CHAT,
                    "⚠️ <b>LinkedIn Cookie abgelaufen!</b>\n\n"
                    "Beide Cookies neu holen (2 min):\n"
                    "1. Chrome → linkedin.com (einloggen)\n"
                    "2. F12 → Application → Cookies → linkedin.com\n"
                    "3. <code>li_at</code> UND <code>li_a</code> kopieren\n"
                    "4. In <code>.env</code> beide Werte ersetzen\n"
                    "5. Bot neu starten: <code>python3 pipo_telegram_bot.py --install</code>"
                )
            log("LinkedIn cookies abgelaufen")
            _li_api = None
            return None
        _li_cookie_expired = False
        return _li_api
    except Exception as e:
        log(f"LinkedIn auth error: {e}")
        return None

def linkedin_get_profile_from_url(li_url):
    """Holt LinkedIn-Profildaten für eine gegebene Profil-URL."""
    api = get_linkedin_api()
    if not api:
        return None
    try:
        # Vanity name aus URL extrahieren
        match = re.search(r'linkedin\.com/in/([^/?#]+)', li_url)
        if not match:
            return None
        public_id = match.group(1).rstrip("/")

        raw = api.get_profile(public_id=public_id)
        profile = raw if isinstance(raw, dict) else {}
        if not profile:
            log(f"get_profile returned empty/None for {public_id}: {type(raw)}")
            return None

        exps = profile.get("experience", [])
        current_company = ""
        current_title = ""
        if exps:
            e = exps[0]
            current_company = e.get("companyName", "")
            current_title   = e.get("title", "")

        name = f"{profile.get('firstName','')} {profile.get('lastName','')}".strip()
        return {
            "public_id":      public_id,
            "name":           name,
            "headline":       profile.get("headline", ""),
            "location":       profile.get("locationName", ""),
            "current_company": current_company,
            "current_title":  current_title,
            "summary":        (profile.get("summary") or "")[:200],
            "connections":    profile.get("connections", 0),
            "profile_url":    f"https://linkedin.com/in/{public_id}",
        }
    except Exception as e:
        log(f"LinkedIn profile error: {e}")
        return None

# ── DB Lookup ─────────────────────────────────────────────────────────────────
def db_find_by_linkedin(li_url):
    """Sucht Lead nach LinkedIn URL."""
    try:
        encoded = urllib.parse.quote(li_url, safe="")
        results = sb_get("leads", f"select=id,company,contact_person,title,stage,region,updated_at&linkedin=eq.{encoded}&limit=1")
        if results:
            return results[0]
        # Auch mit vanity name
        match = re.search(r'linkedin\.com/in/([^/?#]+)', li_url)
        if match:
            vanity = match.group(1).rstrip("/")
            results = sb_get("leads", f"select=id,company,contact_person,title,stage,region,updated_at&linkedin=ilike.*{urllib.parse.quote(vanity)}*&limit=1")
            if results:
                return results[0]
    except Exception as e:
        log(f"db_find_by_linkedin error: {e}")
    return None

def db_find_by_name(name, company=""):
    """Sucht Lead nach Name (und optional Firma)."""
    try:
        first = name.split()[0] if name else ""
        last  = name.split()[-1] if len(name.split()) > 1 else ""
        q = f"select=id,company,contact_person,title,stage,region,linkedin,email,updated_at&contact_person=ilike.*{urllib.parse.quote(last)}*&limit=5"
        results = sb_get("leads", q)
        if company and results:
            filtered = [r for r in results if company.lower() in (r.get("company") or "").lower()]
            if filtered:
                return filtered[0]
        return results[0] if results else None
    except Exception as e:
        log(f"db_find_by_name error: {e}")
    return None

def db_find_by_company(company):
    """Sucht Lead nach Firmenname."""
    try:
        results = sb_get("leads", f"select=id,company,contact_person,title,stage,region,linkedin,email,updated_at,expected_deal_size_millions&company=ilike.*{urllib.parse.quote(company)}*&limit=5")
        return results
    except Exception as e:
        log(f"db_find_by_company error: {e}")
    return []

def db_get_meddpicc(lead_id):
    try:
        r = sb_get("meddpicc_scores", f"select=total_score,qualification_status&lead_id=eq.{lead_id}&limit=1")
        return r[0] if r else {}
    except: return {}

def db_get_top_leads(n=5):
    """Holt Top N Leads nach Priority Score."""
    try:
        leads = sb_get("leads",
            f"select=id,company,contact_person,title,stage,region,tier,updated_at,expected_deal_size_millions"
            f"&stage=neq.closed_won&stage=neq.closed_lost&limit=500"
        )
        scores_raw = sb_get("meddpicc_scores", "select=lead_id,total_score,qualification_status&limit=50000")
        meddpicc = {s["lead_id"]: s for s in scores_raw}

        TIER_SCORE   = {1: 35, 2: 20, 3: 8, 4: 2}
        REGION_SCORE = {"DE": 25, "CH": 22, "UAE": 20, "UK": 18, "NORDICS": 15}

        scored = []
        for l in leads:
            m    = meddpicc.get(l["id"], {})
            medd = m.get("total_score", 0) or 0
            days = days_since(l.get("updated_at"))
            tier = l.get("tier") or 3
            reg  = l.get("region") or "EUROPE"
            score = (
                TIER_SCORE.get(tier, 5) +
                REGION_SCORE.get(reg, 5) +
                min(20, int(medd / 80 * 20)) +
                (15 if days <= 7 else 10 if days <= 30 else 5) +
                (5 if float(l.get("expected_deal_size_millions") or 0) >= 1 else 1)
            )
            scored.append({**l, "meddpicc": medd, "ql": m.get("qualification_status","?"), "priority": score, "days": days})
        scored.sort(key=lambda x: x["priority"], reverse=True)
        return scored[:n]
    except Exception as e:
        log(f"db_get_top_leads error: {e}")
    return []

def db_create_lead(data):
    """Legt neuen Lead in Supabase an."""
    try:
        return sb_post("leads", data)
    except Exception as e:
        log(f"db_create_lead error: {e}")
    return None

# ── Claude: Quick Analysis ────────────────────────────────────────────────────
def claude_quick_analysis(name, company, headline, summary, is_in_db, db_lead=None):
    """Kurze AI-Einschätzung ob dieser Lead interessant ist."""
    if not ANTHROPIC_KEY:
        return ""
    try:
        db_info = ""
        if is_in_db and db_lead:
            db_info = f"BEREITS IN DB: Stage={db_lead.get('stage','?')}, Region={db_lead.get('region','?')}"
        prompt = f"""Du bist Pipo, Pre-Sales AI für Philipp Sandor (HEAD EMEA, Bitwise Asset Management).

Lead-Info:
Name: {name}
Firma: {company}
Headline: {headline}
Summary: {summary[:200]}
{db_info}

Bitwise verkauft institutionelles ETH Staking (MiCA-konform, KPMG-geprüft) und Crypto ETPs an EMEA-Institutionen.

Antworte in 2-3 Sätzen:
1. Ist dieser Lead relevant für Bitwise EMEA? (Ja/Nein/Vielleicht)
2. Warum? (konkret, kein Buzzword)
3. Empfehlung: Hinzufügen / Ignorieren / Weiter prüfen"""

        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload, method="POST",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
        return resp["content"][0]["text"].strip()
    except Exception as e:
        log(f"claude_quick_analysis error: {e}")
    return ""


# ── Claude: Intent Router ─────────────────────────────────────────────────────
_INTENT_SYSTEM = """Du bist Intent-Parser für einen Pre-Sales Telegram-Bot (Bitwise EMEA).
Analysiere die Nachricht und gib NUR JSON zurück — kein Text, kein Markdown.

Aktionen und Parameter:
- linkedin_lookup  → {li_url}
- add_lead         → {li_url?, company?, name?, region?, tier?, want_strategy?}
- battle_card      → {company?}
- status           → {company_or_url?}
- find_contacts    → {role, company}
- top_leads        → {n?}
- email_draft      → {company}
- update_lead      → {company, field, value}
- log_activity     → {company, type, note, next_steps?}
- update_stage     → {company, stage}
- create_task      → {title, priority?, company?, contact?}
- complete_task    → {id}
- pipeline         → {}
- help             → {}
- unknown          → {}

Regeln:
- "hinzufügen/anlegen/add/eintragen" → add_lead
- "strategie/battle card" zusammen mit add → add_lead + want_strategy=true
- "strategie/battle card/card" alleine → battle_card
- "status/wie läuft/wie steht/was ist bei" → status
- "wer ist/finde/entscheider/suche" + Firma → find_contacts
- "top leads/top N/zeig leads" → top_leads
- "email/mail/schreib/draft" + Firma → email_draft
- "update/ändere/setze/stage/tier" + Firma + Wert → update_lead (field: stage|tier|region|use_case|notes)
- "notiere/gesprächsnotiz/notiz/call/meeting/email geschickt/follow-up/hab gesprochen/habe... geschrieben/geschickt" → log_activity
  type: call|email|meeting|demo|proposal|linkedin|other
  note: der Inhalt des Gesprächs/der Aktivität
  next_steps: wenn "nächster Schritt/next steps/nächste Schritte" erwähnt
- "ist jetzt in/stage auf/bewegt auf/verschoben zu" + Stage → update_stage
  stages: prospecting|discovery|solutioning|validation|negotiation|closed_won|closed_lost
- "erstelle aufgabe/task/todo/erinnere mich" → create_task
  priority: P1 (dringend/sofort) | P2 (normal) | P3 (nice-to-have), default P2
- "task erledigt/task N fertig/abgehakt" + ID → complete_task
- "pipeline/wie steht die pipeline/übersicht" → pipeline
- bare LinkedIn-URL → linkedin_lookup
- Firma ohne Befehl → status
- Parameter weglassen wenn unbekannt (nicht raten)

JSON-Format: {"action":"...","params":{...}}"""

def claude_route_intent(text: str, ctx: dict) -> dict | None:
    """Nutzt Claude Haiku um Intent + Parameter zu extrahieren. None bei Fehler."""
    if not ANTHROPIC_KEY:
        return None
    ctx_str = ""
    if ctx:
        ctx_str = f"Letzter Lead: {ctx.get('name','')} @ {ctx.get('company','')} URL={ctx.get('li_url','')}"
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 220,
        "system": _INTENT_SYSTEM,
        "messages": [{"role": "user", "content": f"Kontext: {ctx_str}\nNachricht: {text}"}]
    }).encode()
    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload, method="POST",
            headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = json.loads(r.read())["content"][0]["text"].strip()
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw)
        result = json.loads(raw)
        log(f"claude_route: {result}")
        return result
    except Exception as e:
        log(f"claude_route error: {e}")
        return None


# ── Lead Action Buttons (Inline Keyboard) ────────────────────────────────────

STAGE_MAP = {
    "prospecting": "prospecting", "discovery": "discovery",
    "solutioning": "solutioning", "proposal": "proposal",
    "negotiation": "negotiation", "closed_won": "closed_won",
    "closed_lost": "closed_lost", "won": "closed_won", "lost": "closed_lost",
}
FIELD_MAP = {
    "stage": "stage", "tier": "tier", "region": "region",
    "use_case": "use_case", "notiz": "notes", "note": "notes", "notes": "notes",
}
STAGE_ABBREV = {
    "pro": "prospecting", "dis": "discovery", "mtg": "meeting",
    "sol": "solutioning", "prp": "proposal",  "neg": "negotiation",
    "won": "closed_won",  "lst": "closed_lost",
}

def make_lead_buttons(lead_id):
    """Inline keyboard mit den wichtigsten Actions für einen Lead."""
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

def tg_answer_callback(callback_id, text="✅", alert=False):
    """Bestätigt Button-Druck (entfernt Ladeindikator in Telegram)."""
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
    except Exception as e:
        log(f"answerCallback error: {e}")

# ── Research + Email Generation (shared with morning brief) ──────────────────

def research_company_news(company, region="DE"):
    """Aktuelle News via Google News RSS."""
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
            title = title.split(" - ")[0].strip()
            if title:
                news.append(f"• {title[:90]}")
        return news if news else []
    except:
        return []

def generate_email_draft(lead, news_items):
    """Generiert Email-Draft via Claude Haiku — gleiche Logik wie Morning Brief."""
    news_text = "\n".join(news_items) if news_items else "Keine aktuellen News gefunden."
    region = lead.get("region", "DE")
    lang   = "Deutsch" if region in ("DE", "AT", "CH") else "Englisch"
    use_du = region in ("DE", "AT", "CH") or (lead.get("industry") or "").lower() in (
        "crypto/blockchain", "crypto", "blockchain", "defi", "fintech"
    )
    anrede = lead.get("contact_person", "").split()[0] if lead.get("contact_person") else "zusammen"

    prompt = f"""Du bist Pipo, Pre-Sales Analyst für Philipp Sandor (HEAD EMEA, Bitwise Asset Management, Lissabon).

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

═══ PHILIPPS ECHTER SCHREIBSTIL (STRIKT EINHALTEN) ═══
STIMME: Warm, direkt, menschlich. Nie corporate.
STRUKTUR (max. 4 Sätze im Body):
1. Persönliche Eröffnung — warmth first
2. Konkreter Bezug zu IHNEN (aus News) — 1 Satz
3. EIN spezifischer Bitwise-Fakt — 1 Satz
4. CTA: "Wäre ein 15-minütiger Austausch nächste Woche möglich?" ODER "https://calendly.com/psandor/30min"
ANREDE: {'Verwende "du": "Hallo ' + anrede + ',"' if use_du else 'Verwende "Sie": "Hallo ' + anrede + ',"'}
SIGNATUR: {'Viele Grüße aus Lissabon,\\nPhilipp' if lang == 'Deutsch' else 'Best,\\nPhilipp'}

VERBOTEN: ❌ Mehrere Facts ❌ "revolutionär" ❌ "Ich hoffe..." ❌ Mehr als 1 CTA

Antworte NUR in diesem JSON:
{{"why_now":"1 Satz warum JETZT","angle":"stärkster Sales-Angle","risk":"größtes Risiko","subject":"Betreff max 8 Wörter","email":"vollständiger Email-Body"}}"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, method="POST",
        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        resp = json.loads(r.read())
    text = resp["content"][0]["text"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    start = text.find("{"); end = text.rfind("}") + 1
    return json.loads(text[start:end])

def _load_lead_with_scores(lead_id):
    """Lädt einen Lead aus Supabase inkl. MEDDPICC Scores."""
    rows = sb_get("leads",
        f"id=eq.{lead_id}&select=*,meddpicc_scores(total_score,qualification_status,pain,champion,economic_buyer)")
    if not rows:
        return None
    lead = rows[0]
    sc = lead.pop("meddpicc_scores", None)
    if isinstance(sc, list):
        sc = sc[0] if sc else None
    lead["meddpicc"]   = (sc.get("total_score") or 0) if sc else 0
    lead["ql"]         = (sc.get("qualification_status") or "UNQUALIFIED") if sc else "UNQUALIFIED"
    lead["m_pain"]     = (sc.get("pain") or 0) if sc else 0
    lead["m_champion"] = (sc.get("champion") or 0) if sc else 0
    lead["m_economic"] = (sc.get("economic_buyer") or 0) if sc else 0
    lead["days_inactive"] = days_since(lead.get("updated_at"))
    return lead

# ── Command Handlers ──────────────────────────────────────────────────────────

def set_context(chat_id, li_url="", name="", company="", profile=None, db_lead=None):
    """Speichert letzten Lead-Kontext für diesen Chat."""
    _context[str(chat_id)] = {
        "li_url": li_url, "name": name, "company": company,
        "profile": profile, "db_lead": db_lead, "ts": time.time()
    }

def get_context(chat_id):
    """Gibt Kontext zurück falls < 30 Minuten alt."""
    ctx = _context.get(str(chat_id))
    if ctx and (time.time() - ctx.get("ts", 0)) < 1800:
        return ctx
    return None


def handle_linkedin_lookup(chat_id, text, li_url):
    """Hauptfeature: LinkedIn URL → DB-Check + Profil + AI-Einschätzung."""
    tg_send(chat_id, f"🔍 Prüfe <code>{li_url}</code>...")

    # 1. DB check
    db_lead = db_find_by_linkedin(li_url)
    is_in_db = db_lead is not None

    # 2. LinkedIn Profil holen
    profile = linkedin_get_profile_from_url(li_url)

    name    = profile.get("name", "?") if profile else "?"
    company = profile.get("current_company", "?") if profile else "?"
    title   = profile.get("current_title", "") if profile else ""
    headline = profile.get("headline", "") if profile else ""
    location = profile.get("location", "") if profile else ""
    summary  = profile.get("summary", "") if profile else ""

    # 3. Falls nicht in DB und kein LinkedIn-Profil: Name aus DB versuchen
    if not is_in_db and profile:
        db_lead = db_find_by_name(name, company)
        is_in_db = db_lead is not None

    # 4. MEDDPICC falls in DB
    meddpicc = ""
    if is_in_db and db_lead:
        m = db_get_meddpicc(db_lead["id"])
        score = m.get("total_score", 0) or 0
        ql    = m.get("qualification_status", "")
        days  = days_since(db_lead.get("updated_at"))
        ql_e  = {"QUALIFIED": "🟢", "PROBABLE": "🔵", "POSSIBLE": "🟡"}.get(ql, "⚪")
        meddpicc = f"\n📊 MEDDPICC {ql_e} <b>{score}/80</b> · Stage: {db_lead.get('stage','?')} · {days}d inaktiv"

    # 5. AI-Einschätzung (nur wenn nicht in DB oder interessant)
    ai_note = ""
    if profile and (not is_in_db or True):
        ai_note = claude_quick_analysis(name, company, headline, summary, is_in_db, db_lead)

    # 6. Antwort bauen
    if is_in_db:
        status_line = f"✅ <b>JA — in StakeStream</b> ({db_lead.get('company','?')})"
    else:
        status_line = "❌ <b>NEIN — nicht in StakeStream</b>"

    profile_section = ""
    if profile:
        profile_section = (
            f"\n\n👤 <b>{name}</b>"
            f"\n💼 {title} @ {company}" if title else f"\n💼 {headline}"
            f"\n📍 {location}" if location else ""
        )
        if not title:
            profile_section = f"\n\n👤 <b>{name}</b>\n💼 {headline}\n📍 {location}"

    msg = f"""{status_line}{meddpicc}{profile_section}"""

    if ai_note:
        msg += f"\n\n🤖 <i>{ai_note}</i>"

    if not is_in_db and profile:
        msg += f"\n\n💡 <b>Aktionen:</b>\n<code>hinzufügen</code> — Lead in DB anlegen\n<code>hinzufügen + strategie</code> — anlegen & Battle Card generieren"
    elif is_in_db:
        msg += f"\n\n💡 <code>strategie</code> — Battle Card generieren\n<a href='{DASHBOARD_URL}'>📊 Dashboard</a>"

    # Kontext für Folgebefehle merken (nur wenn echte Daten vorhanden)
    ctx_company = company if (company and company != "?") else ""
    ctx_name    = name    if (name    and name    != "?") else ""
    set_context(chat_id, li_url=li_url, name=ctx_name, company=ctx_company,
                profile=profile, db_lead=db_lead if is_in_db else None)

    tg_send(chat_id, msg)


def handle_top_leads(chat_id, n=5):
    """Zeigt Top N Leads."""
    tg_send(chat_id, f"📊 Lade Top {n} Leads...")
    leads = db_get_top_leads(n)
    if not leads:
        tg_send(chat_id, "❌ Keine Leads gefunden.")
        return

    ql_map = {"QUALIFIED": "🟢", "PROBABLE": "🔵", "POSSIBLE": "🟡", "UNQUALIFIED": "⚪"}
    lines = [f"📊 <b>TOP {len(leads)} LEADS — StakeStream</b>\n"]
    for i, l in enumerate(leads, 1):
        ql = ql_map.get(l.get("ql", ""), "⚪")
        tier = "⭐" if l.get("tier") == 1 else "🔹" if l.get("tier") == 2 else "▫️"
        lines.append(
            f"{i}. {tier} <b>{l['company']}</b> {ql}\n"
            f"   {l.get('contact_person','?')} · {l.get('region','?')} · {l['days']}d · MEDDPICC {l['meddpicc']}/80"
        )
    lines.append(f"\n<a href='{DASHBOARD_URL}'>📊 Dashboard</a>")
    tg_send(chat_id, "\n".join(lines))


def handle_status(chat_id, company_query):
    """Zeigt Status eines Leads. Akzeptiert Firmenname oder LinkedIn-URL."""
    # LinkedIn URL → nach linkedin-Feld suchen
    li_m = LINKEDIN_REGEX.search(company_query)
    if li_m:
        li_url = li_m.group(0).rstrip("/.,!?")
        lead = db_find_by_linkedin(li_url)
        results = [lead] if lead else []
        if not results:
            tg_send(chat_id, f"❌ Diese LinkedIn-URL ist nicht in StakeStream.")
            return
    else:
        results = db_find_by_company(company_query)
    if not results:
        tg_send(chat_id, f"❌ '{company_query}' nicht in StakeStream gefunden.")
        return

    l = results[0]
    m = db_get_meddpicc(l["id"])
    score = m.get("total_score", 0) or 0
    ql = m.get("qualification_status", "?")
    ql_e = {"QUALIFIED": "🟢", "PROBABLE": "🔵", "POSSIBLE": "🟡"}.get(ql, "⚪")
    days = days_since(l.get("updated_at"))

    li_link = f'\n🔗 <a href="{l["linkedin"]}">LinkedIn</a>' if l.get("linkedin") else ""
    msg = f"""📋 <b>{l['company']}</b>

👤 {l.get('contact_person','?')} ({l.get('title','?')})
📍 {l.get('region','?')}
🎯 Stage: <b>{l.get('stage','?')}</b>
📊 MEDDPICC {ql_e} <b>{score}/80</b>
⏱ Zuletzt aktiv: <b>{days}d ago</b>{li_link}

<a href='{DASHBOARD_URL}'>📊 Dashboard</a>"""
    tg_send(chat_id, msg)


def handle_add_lead(chat_id, args_text="", auto_strategy=False, parsed=None):
    """Fügt neuen Lead hinzu. Nutzt Kontext wenn kein Argument angegeben.
    parsed: optionales dict mit vorbereiteten Feldern vom Claude-Router (unterstützt Firmennamen mit Leerzeichen).
    """
    li_url  = ""
    company = ""
    region  = "DE"
    tier    = 2

    if parsed:
        # Direkt vom Claude-Router — Firmennamen mit Leerzeichen funktionieren hier
        li_url  = parsed.get("li_url", "")
        company = parsed.get("company", "")
        region  = (parsed.get("region") or "DE").upper()
        tier    = parsed.get("tier") or 2
    else:
        args_text = args_text.strip()
        parts = args_text.split()
        for p in parts:
            if "linkedin.com/in/" in p:
                li_url = p
            elif p.upper() in ("DE", "CH", "UAE", "UK", "NORDICS", "EUROPE", "MIDEAST", "USA"):
                region = p.upper()
            elif p.lower().startswith("tier"):
                try: tier = int(p[-1])
                except: pass
            elif not company and not p.startswith("/"):
                company = p

    # Kein Argument? → Kontext nutzen
    if not li_url and not company:
        ctx = get_context(chat_id)
        if ctx:
            li_url  = ctx.get("li_url", "")
            company = ctx.get("company", "")
            name    = ctx.get("name", "")
            if not li_url and not company:
                tg_send(chat_id, "❌ Kein Lead im Kontext. Schick zuerst eine LinkedIn URL.")
                return
        else:
            tg_send(chat_id, "❌ Kein Lead im Kontext.\nUsage: <code>/add [linkedin_url] [Firma] [Region] [Tier1/2/3]</code>")
            return

    # LinkedIn-Profil holen falls URL vorhanden
    profile = linkedin_get_profile_from_url(li_url) if li_url else None
    contact_name  = profile.get("name", "") if profile else ""
    contact_title = profile.get("current_title", "") if profile else ""
    if profile and not company:
        company = profile.get("current_company", "")

    if not company:
        # LinkedIn-Profil-Lookup fehlgeschlagen — Firmenname manuell angeben
        li_hint = f" {li_url}" if li_url else ""
        tg_send(chat_id,
            f"⚠️ LinkedIn Profil nicht erreichbar — Firmenname fehlt.\n\n"
            f"Bitte so angeben:\n"
            f"<code>/add{li_hint} FirmaXY</code>\n\n"
            f"Beispiel:\n<code>/add{li_hint} Tangany DE Tier2</code>"
        )
        return

    # Prüfen ob Lead schon existiert (bevor wir versuchen zu inserieren)
    existing = None
    if li_url:
        existing = db_find_by_linkedin(li_url)
    if not existing and company:
        hits = db_find_by_company(company)
        if hits:
            existing = hits[0]

    if existing:
        m = db_get_meddpicc(existing["id"])
        score = m.get("total_score", 0) or 0
        days = days_since(existing.get("updated_at"))
        tg_send(chat_id,
            f"ℹ️ <b>{existing['company']}</b> ist bereits in StakeStream.\n\n"
            f"👤 {existing.get('contact_person','—')} · Stage: {existing.get('stage','?')} · "
            f"MEDDPICC {score}/80 · {days}d inaktiv\n\n"
            f"<code>strategie</code> — Battle Card generieren\n"
            f"<a href='{DASHBOARD_URL}'>📊 Dashboard</a>"
        )
        set_context(chat_id, li_url=li_url, name=existing.get("contact_person",""),
                    company=existing["company"], db_lead=existing)
        if auto_strategy:
            handle_battle_card(chat_id, existing["company"])
        return

    # In Supabase anlegen
    # Region validieren (Supabase-Enum: nur bekannte Werte)
    valid_regions = {"DE", "CH", "UAE", "UK", "NORDICS", "EUROPE", "MIDEAST", "USA"}
    if region not in valid_regions:
        region = "DE"  # Fallback
    data = {
        "company":        company,
        "contact_person": contact_name or "",
        "title":          contact_title or "",
        "linkedin":       li_url or "",
        "region":         region,
        "tier":           tier,
        "stage":          "prospecting",
    }
    try:
        result = db_create_lead(data)
    except Exception as e:
        err_str = str(e)
        log(f"handle_add_lead insert failed: {err_str}")
        tg_send(chat_id, f"❌ Supabase-Fehler beim Anlegen von <b>{company}</b>:\n<code>{err_str[:200]}</code>")
        return
    if result:
        msg = f"""✅ <b>{company}</b> hinzugefügt!

👤 {contact_name or '—'} · {contact_title or '—'}
📍 {region} · Tier {tier}
🎯 Stage: prospecting
{"🔗 " + li_url if li_url else ""}

<a href='{DASHBOARD_URL}'>📊 Dashboard</a>"""
        tg_send(chat_id, msg)
        set_context(chat_id, li_url=li_url, name=contact_name, company=company)
        if auto_strategy:
            handle_battle_card(chat_id, company)
    else:
        tg_send(chat_id, f"❌ Unbekannter Fehler beim Anlegen von <b>{company}</b>.")


def handle_find_contacts(chat_id, role, company):
    """Sales Navigator-ähnlich: Findet Entscheider nach Rolle bei einer Firma."""
    tg_send(chat_id, f"🔍 Suche <b>{role}</b> bei <b>{company}</b> auf LinkedIn...")
    api = get_linkedin_api()
    if not api:
        tg_send(chat_id, "⚠️ LinkedIn nicht verfügbar.")
        return
    try:
        results = api.search_people(
            keyword_title=role,
            keyword_company=company,
            limit=5,
        ) or []
        if not results:
            tg_send(chat_id, f"❌ Keine LinkedIn-Profile für <b>{role}</b> bei <b>{company}</b> gefunden.")
            return

        prio = {"DISTANCE_1": 0, "DISTANCE_2": 1, "DISTANCE_3": 2}
        results.sort(key=lambda x: prio.get(x.get("distance", "DISTANCE_3"), 3))

        lines = [f"👥 <b>{role} bei {company}</b>\n"]
        for r in results[:5]:
            name     = r.get("name", "?")
            jobtitle = r.get("jobtitle", "—")
            distance = r.get("distance", "DISTANCE_3")
            pub_id   = r.get("publicIdentifier") or r.get("public_id", "")
            degree   = "1st ✅" if distance == "DISTANCE_1" else "2nd 🔵" if distance == "DISTANCE_2" else "3rd ❄️"
            li_link  = f' · <a href="https://linkedin.com/in/{pub_id}">Profil</a>' if pub_id else ""
            lines.append(f"• <b>{name}</b> ({degree})\n  {jobtitle}{li_link}")

        lines.append(f"\n💡 <code>hinzufügen</code> oder /card {company}")
        tg_send(chat_id, "\n".join(lines))
        # Kontext auf Firma setzen
        set_context(chat_id, company=company)
    except Exception as e:
        log(f"handle_find_contacts error: {e}")
        tg_send(chat_id, f"❌ LinkedIn Fehler: {str(e)[:200]}")


def handle_battle_card(chat_id, company_query):
    """Startet Battle Card Generierung für eine Firma."""
    tg_send(chat_id, f"⚔️ Starte Battle Card für <b>{company_query}</b>...\n(~2 Minuten)")
    env = LEADTRACKER / ".env"
    script = LEADTRACKER / "pipo_battlecard.py"
    cmd = f'. "{env}" && python3 "{script}" --lead "{company_query}"'
    try:
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=300,
            cwd=str(LEADTRACKER)
        )
        if result.returncode == 0:
            tg_send(chat_id, f"✅ Battle Card für <b>{company_query}</b> gesendet!")
        else:
            tg_send(chat_id, f"⚠️ Battle Card Fehler:\n<code>{result.stderr[-500:]}</code>")
    except subprocess.TimeoutExpired:
        tg_send(chat_id, "⏱ Timeout — Battle Card dauert zu lange. Manuell starten.")
    except Exception as e:
        tg_send(chat_id, f"❌ Fehler: {e}")


def handle_email(chat_id, company_query):
    """Generiert Email-Draft on-demand für eine Firma."""
    tg_send(chat_id, f"✉️ Generiere Email für <b>{company_query}</b>…")
    leads = db_find_by_company(company_query)
    if not leads:
        tg_send(chat_id, f"❌ Kein Lead für '<b>{company_query}</b>' in StakeStream.\nMit <code>/add</code> anlegen.")
        return
    lead = leads[0]
    lead_id = lead.get("id")
    # Scores nachladen
    scores = db_get_meddpicc(lead_id) if lead_id else None
    lead["meddpicc"]      = (scores.get("total_score") or 0) if scores else 0
    lead["ql"]            = (scores.get("qualification_status") or "UNQUALIFIED") if scores else "UNQUALIFIED"
    lead["m_pain"]        = (scores.get("pain") or 0) if scores else 0
    lead["m_champion"]    = (scores.get("champion") or 0) if scores else 0
    lead["m_economic"]    = (scores.get("economic_buyer") or 0) if scores else 0
    lead["days_inactive"] = days_since(lead.get("updated_at"))

    news = research_company_news(lead.get("company", ""), lead.get("region", "DE"))
    try:
        brief = generate_email_draft(lead, news)
    except Exception as e:
        tg_send(chat_id, f"❌ Fehler beim Generieren: {e}")
        return

    company = lead.get("company", company_query)
    contact = lead.get("contact_person") or "—"
    title   = lead.get("title") or ""
    msg = (
        f"✉️ <b>Email Draft — {company}</b>\n"
        f"👤 {contact} · <i>{title}</i>\n\n"
        f"<b>🎯 Angle:</b> {brief.get('angle', '—')}\n"
        f"<b>⚠️ Risiko:</b> <i>{brief.get('risk', '—')}</i>\n\n"
        f"<b>Betreff:</b> <code>{brief.get('subject', '')}</code>\n\n"
        f"<code>{brief.get('email', '')}</code>"
    )
    set_context(chat_id, company=company)
    tg_send(chat_id, msg, reply_markup=make_lead_buttons(lead_id) if lead_id else None)


def handle_update_lead(chat_id, args_text):
    """Updatet ein Lead-Feld direkt aus Telegram.
    Format: /update Firma | field | value
         oder: /update Firma stage discovery
    """
    # Pipe-separiert?
    parts = [p.strip() for p in re.split(r"\|", args_text)]
    if len(parts) == 3:
        company, field, value = parts
    else:
        # Space-basiert: letzte 2 Tokens = field + value, Rest = Firma
        tokens = args_text.strip().split()
        if len(tokens) < 3:
            tg_send(chat_id,
                "❓ Format:\n"
                "<code>/update Firma stage discovery</code>\n"
                "<code>/update Firma | stage | proposal</code>\n\n"
                "Felder: stage · tier · region · use_case · notes\n"
                "Stages: prospecting · discovery · solutioning · proposal · negotiation · closed_won · closed_lost"
            )
            return
        field = tokens[-2]
        value = tokens[-1]
        company = " ".join(tokens[:-2])

    db_field = FIELD_MAP.get(field.lower(), field.lower())
    if db_field == "stage":
        value_norm = STAGE_MAP.get(value.lower(), value.lower())
    elif db_field == "tier":
        try:
            value_norm = int(value)
        except ValueError:
            value_norm = value
    else:
        value_norm = value

    leads = db_find_by_company(company)
    if not leads:
        tg_send(chat_id, f"❌ Kein Lead für '<b>{company}</b>' gefunden.")
        return
    lead   = leads[0]
    lead_id = lead.get("id")
    try:
        sb_patch("leads", f"id=eq.{lead_id}", {db_field: value_norm})
        tg_send(chat_id,
            f"✅ <b>{lead['company']}</b>\n"
            f"<code>{db_field}</code> → <code>{value_norm}</code>",
            reply_markup=make_lead_buttons(lead_id)
        )
        set_context(chat_id, company=lead["company"])
    except Exception as e:
        tg_send(chat_id, f"❌ Update fehlgeschlagen: {e}")


def handle_callback_query(callback_query):
    """Verarbeitet Button-Presses aus Inline-Keyboards."""
    callback_id = callback_query["id"]
    chat_id     = str(callback_query["from"]["id"])
    data        = callback_query.get("data", "")

    parts  = data.split(":", 2)
    action = parts[0] if parts else ""
    lead_id = parts[1] if len(parts) > 1 else ""
    extra   = parts[2] if len(parts) > 2 else ""

    log(f"callback: action={action} lead={lead_id} extra={extra}")

    if action == "e":  # ✅ Email gesendet → stage → discovery, updated_at setzen
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            sb_patch("leads", f"id=eq.{lead_id}", {
                "stage": "discovery",
                "updated_at": now_iso,
            })
            # Verify write
            rows = sb_get("leads", f"id=eq.{lead_id}&select=company,stage,updated_at")
            company = rows[0]["company"] if rows else "Lead"
            verified_stage = rows[0].get("stage", "?") if rows else "?"
            if verified_stage != "discovery":
                log(f"WARNING: stage verify failed for {lead_id}: expected discovery, got {verified_stage}")
                # Retry once
                sb_patch("leads", f"id=eq.{lead_id}", {"stage": "discovery", "updated_at": now_iso})
            tg_answer_callback(callback_id, "✅ Markiert!")
            tg_send(chat_id,
                f"✅ <b>{company}</b> — Email als gesendet markiert.\n"
                f"Stage: <code>discovery</code> · updated_at: heute"
            )
        except Exception as e:
            log(f"callback e:{lead_id} error: {e}")
            tg_answer_callback(callback_id, f"Fehler: {str(e)[:40]}", alert=True)
            tg_send(chat_id, f"❌ Fehler beim Schreiben: {str(e)[:100]}\nBitte nochmal versuchen.")

    elif action == "r":  # ✏️ Neue Email generieren
        tg_answer_callback(callback_id, "✏️ Generiere…")
        lead = _load_lead_with_scores(lead_id)
        if not lead:
            tg_send(chat_id, "❌ Lead nicht gefunden.")
            return
        news = research_company_news(lead.get("company", ""), lead.get("region", "DE"))
        try:
            brief = generate_email_draft(lead, news)
            msg = (
                f"✏️ <b>Neue Email — {lead['company']}</b>\n\n"
                f"<b>🎯 Angle:</b> {brief.get('angle', '—')}\n\n"
                f"<b>Betreff:</b> <code>{brief.get('subject', '')}</code>\n\n"
                f"<code>{brief.get('email', '')}</code>"
            )
            tg_send(chat_id, msg, reply_markup=make_lead_buttons(lead_id))
        except Exception as e:
            tg_send(chat_id, f"❌ Fehler: {e}")

    elif action == "s":  # 📊 Stage ändern
        stage_full = STAGE_ABBREV.get(extra, extra)
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            sb_patch("leads", f"id=eq.{lead_id}", {
                "stage": stage_full,
                "updated_at": now_iso,
            })
            # Verify write
            rows = sb_get("leads", f"id=eq.{lead_id}&select=company,stage")
            company = rows[0]["company"] if rows else "Lead"
            verified = rows[0].get("stage", "?") if rows else "?"
            if verified != stage_full:
                log(f"WARNING: stage verify failed for {lead_id}: expected {stage_full}, got {verified}")
                sb_patch("leads", f"id=eq.{lead_id}", {"stage": stage_full, "updated_at": now_iso})
            tg_answer_callback(callback_id, f"Stage: {stage_full}")
            tg_send(chat_id, f"✅ <b>{company}</b> → Stage: <code>{stage_full}</code>")
        except Exception as e:
            log(f"callback s:{lead_id}:{extra} error: {e}")
            tg_answer_callback(callback_id, f"Fehler: {str(e)[:40]}", alert=True)
            tg_send(chat_id, f"❌ Fehler beim Stage-Update: {str(e)[:100]}\nBitte nochmal versuchen.")

    elif action == "c":  # 💡 Battle Card
        tg_answer_callback(callback_id, "💡 Battle Card…")
        rows = sb_get("leads", f"id=eq.{lead_id}&select=company")
        if rows:
            handle_battle_card(chat_id, rows[0]["company"])

    elif action == "sk":  # 🚫 Skip — update timestamp so lead rotates out
        try:
            sb_patch("leads", f"id=eq.{lead_id}", {
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass  # non-critical
        tg_answer_callback(callback_id, "⏭️ Übersprungen")
        rows    = sb_get("leads", f"id=eq.{lead_id}&select=company")
        company = rows[0]["company"] if rows else "Lead"
        tg_send(chat_id, f"⏭️ <b>{company}</b> übersprungen — erscheint frühestens in 3 Tagen wieder.")

    else:
        tg_answer_callback(callback_id, "❓ Unbekannte Aktion")


def _run_ops(args: list) -> str:
    """Ruft stakestream_ops.py auf und gibt Output zurück."""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            [sys.executable, OPS_SCRIPT] + args,
            capture_output=True, text=True, timeout=30, env=env
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode != 0 and err:
            return f"❌ {err[:300]}"
        return out or "✅ Erledigt."
    except subprocess.TimeoutExpired:
        return "⏱ Timeout — StakeStream nicht erreichbar."
    except Exception as e:
        return f"❌ Fehler: {e}"


def handle_log_activity(chat_id, company, act_type, note, next_steps=""):
    """Loggt eine Aktivität für einen Lead via stakestream_ops."""
    VALID = ["email", "call", "meeting", "demo", "proposal", "linkedin", "other"]
    t = act_type.lower()
    if t not in VALID:
        # Mapping von Alltagssprache
        if any(w in t for w in ["tel", "ruf", "phone", "gespräch"]): t = "call"
        elif any(w in t for w in ["mail", "brief", "geschickt", "geschrieben"]): t = "email"
        elif any(w in t for w in ["meet", "treffen", "london", "person", "vor ort"]): t = "meeting"
        elif any(w in t for w in ["demo", "präsen"]): t = "demo"
        elif any(w in t for w in ["linked"]): t = "linkedin"
        else: t = "other"

    args = ["add-note", company, t, note]
    if next_steps:
        args += ["--next-steps", next_steps]

    out = _run_ops(args)
    # HTML-safe output
    tg_send(chat_id, out.replace("*", "<b>").replace("_", ""), parse_mode="HTML")


def handle_update_stage(chat_id, company, stage):
    """Setzt die Deal-Stage eines Leads."""
    STAGE_NORM = {
        "pro": "prospecting", "prospecting": "prospecting",
        "dis": "discovery",   "discovery": "discovery",
        "sol": "solutioning", "solutioning": "solutioning",
        "val": "validation",  "validation": "validation",
        "neg": "negotiation", "negotiation": "negotiation",
        "won": "closed_won",  "closed_won": "closed_won",  "gewonnen": "closed_won",
        "lost": "closed_lost","closed_lost": "closed_lost","verloren": "closed_lost",
    }
    stage_norm = STAGE_NORM.get(stage.lower(), stage.lower())
    out = _run_ops(["update-stage", company, stage_norm])
    tg_send(chat_id, out.replace("*", "<b>"), parse_mode="HTML")


def handle_create_task(chat_id, title, priority="P2", company=None, contact=None, due=None):
    """Erstellt eine Aufgabe im StakeStream Dashboard."""
    args = ["create-task", title, priority.upper()]
    if company:  args += ["--company", company]
    if contact:  args += ["--contact", contact]
    if due:      args += ["--due", due]
    out = _run_ops(args)
    tg_send(chat_id, out.replace("*", "<b>"), parse_mode="HTML")


def handle_complete_task(chat_id, task_id):
    """Markiert eine Aufgabe als erledigt."""
    try:
        tid = int(str(task_id).strip())
    except ValueError:
        tg_send(chat_id, "❓ Task-ID muss eine Zahl sein. Beispiel: <code>Task 42 erledigt</code>")
        return
    out = _run_ops(["complete-task", str(tid)])
    tg_send(chat_id, out.replace("*", "<b>"), parse_mode="HTML")


def handle_pipeline(chat_id):
    """Zeigt Pipeline-Übersicht."""
    out = _run_ops(["pipeline"])
    tg_send(chat_id, out.replace("*", "<b>"), parse_mode="HTML")


def handle_tasks(chat_id, status_filter=None):
    """Zeigt Aufgaben."""
    args = ["tasks"]
    if status_filter:
        args += ["--status", status_filter]
    out = _run_ops(args)
    tg_send(chat_id, out.replace("*", "<b>"), parse_mode="HTML")


def handle_export(chat_id):
    """Führt Salesforce Export aus und sendet an @Taskforce."""
    tg_send(chat_id, "📤 <b>Salesforce Export wird generiert...</b>", parse_mode="HTML")
    export_script = str(LEADTRACKER / "salesforce_export.py")
    env_file      = str(LEADTRACKER / ".env")
    try:
        import subprocess
        env = os.environ.copy()
        # Source .env manually
        env_result = subprocess.run(
            ["bash", "-c", f"set -a && source {env_file} && env"],
            capture_output=True, text=True, timeout=10
        )
        for line in env_result.stdout.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                env[k] = v
        result = subprocess.run(
            [sys.executable, export_script],
            capture_output=True, text=True, timeout=60, env=env
        )
        if result.returncode == 0:
            tg_send(chat_id, "✅ <b>Export gesendet</b> → @Pipo_EMEA_Taskforce_bot", parse_mode="HTML")
        else:
            err = (result.stderr or result.stdout)[:300]
            tg_send(chat_id, f"❌ <b>Export fehlgeschlagen:</b>\n<code>{err}</code>", parse_mode="HTML")
    except Exception as e:
        tg_send(chat_id, f"❌ <b>Fehler:</b> <code>{e}</code>", parse_mode="HTML")


def handle_help(chat_id):
    msg = """🤖 <b>Pipo Bot — Befehle</b>

<b>📥 Lesen:</b>
/top [n]              — Top N Leads (default: 5)
/status [firma]       — Lead-Status + MEDDPICC + Aktivitäten
/pipeline             — Pipeline-Übersicht nach Stage
/tasks                — Offene Aufgaben
/export               — Salesforce Export → @Taskforce
/card [firma]         — Battle Card generieren

<b>✍️ Schreiben (Chief of Staff):</b>
/note Firma | call | Gesprächsnotiz | Nächste Schritte
/stage Firma negotiation        — Deal-Stage setzen
/task Titel | P1 | Firma        — Aufgabe erstellen
/update Firma stage discovery   — Feld aktualisieren
"Task 42 erledigt"              — Aufgabe abhaken

<b>➕ Lead Management:</b>
/add [url] [firma] [Region]     — Lead anlegen
/find [rolle] bei [firma]       — Entscheider suchen
/email [firma]                  — Email-Draft generieren

<b>💬 Natürliche Sprache:</b>
"Hab heute mit Jared von Re7 telefoniert, sehr positiv"
"Re7 ist jetzt in Negotiation"
"Erstelle Task: Follow-up an Sabih, P1"
"Wie steht die Pipeline?"

<b>Stages:</b> prospecting · discovery · solutioning · validation · negotiation · closed_won · closed_lost

<a href='https://pipo-bitwise-lead-tracker.streamlit.app'>📊 Dashboard öffnen</a>"""
    tg_send(chat_id, msg)


# ── Intent Detection ──────────────────────────────────────────────────────────
LINKEDIN_REGEX = re.compile(r'https?://(?:www\.)?linkedin\.com/in/[^\s\]>]+', re.IGNORECASE)

def process_message(chat_id, text):
    """Parst Nachricht und dispatcht an den richtigen Handler.
    Strategie: Claude Haiku als Intent-Router (natürliche Sprache),
    Regex-Fallback für explizite Befehle und wenn Claude nicht verfügbar.
    """
    text = text.strip()
    text_lower = text.lower()

    # ── Explizite Slash-Befehle (immer direkt, kein AI-Overhead) ─────────────
    if text_lower.startswith("/status "):
        handle_status(chat_id, text[8:].strip())
        return
    if text_lower.startswith("/card "):
        handle_battle_card(chat_id, text[6:].strip())
        return
    if text_lower.startswith("/top"):
        parts = text.split()
        handle_top_leads(chat_id, int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5)
        return
    if text_lower.startswith("/email "):
        handle_email(chat_id, text[7:].strip())
        return
    if text_lower.startswith("/update "):
        handle_update_lead(chat_id, text[8:].strip())
        return
    if text_lower in ("/help", "help", "hilfe", "?", "/start"):
        handle_help(chat_id)
        return
    if text_lower in ("/pipeline", "pipeline", "übersicht", "wie steht die pipeline"):
        handle_pipeline(chat_id)
        return
    if text_lower.startswith("/tasks") or text_lower in ("aufgaben", "tasks", "todos"):
        parts = text.split()
        sf = parts[1] if len(parts) > 1 and parts[1] in ("todo","in_progress","done") else None
        handle_tasks(chat_id, sf)
        return
    if text_lower in ("/export", "export", "salesforce export", "sf export"):
        handle_export(chat_id)
        return
    if text_lower.startswith("/note "):
        # /note Firma | Typ | Notiz [| next_steps]
        parts_n = [p.strip() for p in text[6:].split("|")]
        if len(parts_n) >= 3:
            handle_log_activity(chat_id, parts_n[0], parts_n[1], parts_n[2],
                                parts_n[3] if len(parts_n) > 3 else "")
        else:
            tg_send(chat_id, "❓ Format: <code>/note Firma | call | Notiztext | Nächste Schritte</code>")
        return
    if text_lower.startswith("/stage "):
        parts_s = text[7:].strip().rsplit(" ", 1)
        if len(parts_s) == 2:
            handle_update_stage(chat_id, parts_s[0].strip(), parts_s[1].strip())
        else:
            tg_send(chat_id, "❓ Format: <code>/stage Firmenname negotiation</code>")
        return
    if text_lower.startswith("/task "):
        # /task Titel | Priorität | Firma
        parts_t = [p.strip() for p in text[6:].split("|")]
        handle_create_task(chat_id, parts_t[0],
                           parts_t[1] if len(parts_t) > 1 else "P2",
                           parts_t[2] if len(parts_t) > 2 else None)
        return
    if text_lower.startswith("/find "):
        find_rest = text[6:].strip()
        m = re.search(r'^(.+?)\s+(?:bei|at|@|von|from)\s+(.+)$', find_rest, re.IGNORECASE)
        if m:
            handle_find_contacts(chat_id, m.group(1).strip(), m.group(2).strip())
            return

    # ── Claude Intent-Router ─────────────────────────────────────────────────
    ctx = get_context(chat_id)
    intent = claude_route_intent(text, ctx)

    if intent and intent.get("action") not in (None, "unknown"):
        action = intent["action"]
        params = intent.get("params", {})

        if action == "linkedin_lookup":
            li_url = params.get("li_url") or ""
            if not li_url:
                li_m = LINKEDIN_REGEX.search(text)
                li_url = li_m.group(0).rstrip("/.,!?") if li_m else ""
            if li_url:
                handle_linkedin_lookup(chat_id, text, li_url)
                return

        elif action == "add_lead":
            handle_add_lead(chat_id, auto_strategy=params.get("want_strategy", False), parsed=params)
            return

        elif action == "battle_card":
            company = params.get("company", "")
            if not company and ctx:
                company = ctx.get("company", "")
            if company:
                handle_battle_card(chat_id, company)
            else:
                tg_send(chat_id, "❓ Für welche Firma?\n<code>/card Firmenname</code>")
            return

        elif action == "status":
            query = params.get("company_or_url", "")
            if not query and ctx:
                query = ctx.get("company", "")
            if query:
                handle_status(chat_id, query)
            else:
                tg_send(chat_id, "❓ Welche Firma? Beispiel: /status Tangany")
            return

        elif action == "find_contacts":
            role    = params.get("role", "Managing Director CIO CFO")
            company = params.get("company", "")
            if company:
                handle_find_contacts(chat_id, role, company)
                return

        elif action == "top_leads":
            handle_top_leads(chat_id, params.get("n", 5))
            return

        elif action == "email_draft":
            company = params.get("company", "")
            if not company and ctx:
                company = ctx.get("company", "")
            if company:
                handle_email(chat_id, company)
            else:
                tg_send(chat_id, "❓ Für welche Firma? Beispiel: <code>/email Tangany</code>")
            return

        elif action == "update_lead":
            company = params.get("company", "")
            field   = params.get("field", "")
            value   = params.get("value", "")
            if company and field and value:
                handle_update_lead(chat_id, f"{company} | {field} | {value}")
            else:
                tg_send(chat_id, "❓ Format: <code>/update Firma stage discovery</code>")
            return

        elif action == "log_activity":
            company    = params.get("company", "")
            act_type   = params.get("type", "other")
            note       = params.get("note", "")
            next_steps = params.get("next_steps", "")
            if not company and ctx:
                company = ctx.get("company", "")
            if company and note:
                handle_log_activity(chat_id, company, act_type, note, next_steps)
            else:
                tg_send(chat_id, "❓ Konnte Firma oder Notiz nicht erkennen.\nFormat: <code>/note Firma | call | Notiz</code>")
            return

        elif action == "update_stage":
            company = params.get("company", "")
            stage   = params.get("stage", "")
            if not company and ctx:
                company = ctx.get("company", "")
            if company and stage:
                handle_update_stage(chat_id, company, stage)
            else:
                tg_send(chat_id, "❓ Format: <code>/stage Firmenname negotiation</code>")
            return

        elif action == "create_task":
            title    = params.get("title", "")
            priority = params.get("priority", "P2")
            company  = params.get("company", "")
            contact  = params.get("contact", "")
            if title:
                handle_create_task(chat_id, title, priority, company or None, contact or None)
            else:
                tg_send(chat_id, "❓ Format: <code>/task Aufgabentitel | P1 | Firmenname</code>")
            return

        elif action == "complete_task":
            tid = params.get("id")
            if tid is not None:
                handle_complete_task(chat_id, tid)
            else:
                tg_send(chat_id, "❓ Welche Task-ID? Beispiel: <code>Task 42 erledigt</code>")
            return

        elif action == "pipeline":
            handle_pipeline(chat_id)
            return

        elif action == "help":
            handle_help(chat_id)
            return

    # ── Regex Fallback (wenn Claude unavailable oder action == unknown) ───────
    # LinkedIn URL
    li_match = LINKEDIN_REGEX.search(text)
    if li_match:
        # /add [url] darf nicht als Lookup landen
        want_strategy = any(w in text_lower for w in ["strategie", "strategy", "battle card", "battlecard"])
        if (text_lower.startswith("/add") or
                any(w in text_lower for w in ["hinzufügen", "hinzufuegen", "füge hinzu", "fueg hinzu", "eintragen"])):
            args = re.sub(r'\b(?:strategie|strategy|battle\s*card|battlecard)\b', '', text[text_lower.find(" ")+1:], flags=re.IGNORECASE)
            args = re.sub(r'^[\s+,&|]+', '', args).rstrip()
            handle_add_lead(chat_id, args, auto_strategy=want_strategy)
        else:
            handle_linkedin_lookup(chat_id, text, li_match.group(0).rstrip("/.,!?"))
        return

    # /add und hinzufügen (ohne URL)
    want_strategy = any(w in text_lower for w in ["strategie", "strategy", "battle card", "battlecard"])
    if (text_lower.startswith("/add") or
            any(w in text_lower for w in ["hinzufügen", "hinzufuegen", "füge hinzu", "fueg hinzu", "add lead", "eintragen", "in db"])):
        args = ""
        for prefix in ("/add ", "add ", "hinzufügen ", "hinzufuegen ", "füge hinzu ", "fueg hinzu "):
            if text_lower.startswith(prefix):
                args = text[len(prefix):]
                break
        args = re.sub(r'\b(?:strategie|strategy|battle\s*card|battlecard)\b', '', args, flags=re.IGNORECASE)
        args = re.sub(r'^[\s+,&|]+', '', args).rstrip()
        handle_add_lead(chat_id, args, auto_strategy=want_strategy)
        return

    # battle card / strategie
    if text_lower in ("strategie", "strategy", "/card", "battle card", "battlecard"):
        if ctx and ctx.get("company"):
            handle_battle_card(chat_id, ctx["company"])
        else:
            tg_send(chat_id, "❓ Für welche Firma?\n<code>/card Firmenname</code>")
        return
    if "battle card" in text_lower or "battlecard" in text_lower or "strategie" in text_lower:
        query = re.sub(r'(battle\s*card|battlecard|strategie|strategy)\s*(für|for|von|about|zu)?', '', text, flags=re.IGNORECASE).strip()
        company = query or (ctx.get("company") if ctx else "")
        if company:
            handle_battle_card(chat_id, company)
        else:
            tg_send(chat_id, "❓ Für welche Firma?\n<code>/card Firmenname</code>")
        return

    # "haben wir X?"
    m = re.search(r'(?:haben wir|sind wir|in db|in der datenbank)[?:,\s]+(.+)', text_lower)
    if m:
        query = m.group(1).strip().rstrip("?").strip()
        results = db_find_by_company(query)
        if results:
            l = results[0]
            tg_send(chat_id, f"✅ <b>Ja</b> — <b>{l['company']}</b> ist in StakeStream.\n/status {query}")
        else:
            tg_send(chat_id, f"❌ <b>Nein</b> — '{query}' nicht in StakeStream.\n<code>/add [url] {query}</code>")
        return

    # Fallback
    ctx_hint = ""
    if ctx and ctx.get("company"):
        ctx_hint = f"\n\n💡 Letzter Lead: <b>{ctx['company']}</b>\n<code>hinzufügen</code> · <code>strategie</code> · <code>/status {ctx['company']}</code>"
    tg_send(chat_id, f"🤔 Nicht verstanden.{ctx_hint}\n\n/help — alle Befehle")


# ── Proactive Checks ─────────────────────────────────────────────────────────
_last_proactive_check = 0
PROACTIVE_INTERVAL = 6 * 3600  # Check every 6 hours

def run_proactive_checks():
    """Proaktive Alerts: stale leads in discovery 7+ Tage, breaking news."""
    global _last_proactive_check
    now = time.time()
    if now - _last_proactive_check < PROACTIVE_INTERVAL:
        return
    _last_proactive_check = now

    if not TELEGRAM_CHAT:
        return

    log("Running proactive checks...")

    try:
        # Find leads stuck in active stages for 7+ days
        params = ("select=id,company,contact_person,stage,updated_at,"
                  "meddpicc_scores(total_score)"
                  "&stage=in.(discovery,meeting,solutioning,proposal)")
        leads = sb_get("leads", params)

        alerts = []
        for l in leads:
            sc = l.pop("meddpicc_scores", None)
            if isinstance(sc, list):
                sc = sc[0] if sc else None
            meddpicc = (sc.get("total_score") or 0) if sc else 0

            upd = l.get("updated_at") or ""
            try:
                dt = datetime.fromisoformat(str(upd).replace("Z", "+00:00"))
                days = max(0, (datetime.now(timezone.utc) - dt).days)
            except:
                days = 30

            if days >= 7:
                alerts.append({**l, "days_inactive": days, "meddpicc": meddpicc})

        if alerts:
            alerts.sort(key=lambda x: x["days_inactive"], reverse=True)
            stage_emoji = {"discovery": "🔵", "meeting": "📅", "solutioning": "🔧",
                           "proposal": "🟡"}

            msg_lines = [f"🔔 <b>PIPO PROAKTIV-CHECK</b> — {len(alerts)} Leads brauchen Aufmerksamkeit\n"]
            for a in alerts[:5]:
                emoji = stage_emoji.get(a["stage"], "⚪")
                msg_lines.append(
                    f"{emoji} <b>{a['company']}</b> ({a['stage']}) — "
                    f"{a['days_inactive']}d inaktiv · MEDDPICC {a['meddpicc']}/80"
                )

            if len(alerts) > 5:
                msg_lines.append(f"\n... und {len(alerts)-5} weitere")

            msg_lines.append(f"\n💡 <i>Tippe /top oder /status [company] für Details</i>")

            tg_send(TELEGRAM_CHAT, "\n".join(msg_lines))
            log(f"Proactive: sent {len(alerts)} stale alerts")

    except Exception as e:
        log(f"Proactive check error: {e}")


# ── Main Loop ─────────────────────────────────────────────────────────────────
def run_bot():
    log("=== Pipo Bot startet ===")
    if not TELEGRAM_TOKEN:
        log("FEHLER: TELEGRAM_BOT_TOKEN nicht gesetzt!")
        sys.exit(1)

    # Test-Ping
    tg_send(TELEGRAM_CHAT, "🤖 <b>Pipo Bot online</b>\n\nSchick mir eine LinkedIn URL oder /help für alle Befehle.")
    log("Startup-Message gesendet")

    offset = 0
    while True:
        try:
            # Proactive checks (every 6 hours)
            run_proactive_checks()

            updates = tg_get_updates(offset)
            if not updates.get("ok"):
                time.sleep(5)
                continue

            for update in updates.get("result", []):
                offset = update["update_id"] + 1

                # ── Callback Query (Button-Presses) ───────────────────────
                if "callback_query" in update:
                    cq = update["callback_query"]
                    cq_chat = str(cq.get("from", {}).get("id", ""))
                    if TELEGRAM_CHAT and cq_chat != str(TELEGRAM_CHAT):
                        log(f"Unauthorized callback from {cq_chat}")
                        continue
                    log(f"Callback: {cq.get('data', '')[:60]}")
                    try:
                        handle_callback_query(cq)
                    except Exception as e:
                        log(f"callback_query error: {e}")
                    continue

                # ── Normale Text-Nachrichten ──────────────────────────────
                msg = update.get("message", {})
                if not msg:
                    continue

                chat_id  = msg.get("chat", {}).get("id")
                text     = msg.get("text", "").strip()
                from_id  = str(msg.get("from", {}).get("id", ""))

                if not text or not chat_id:
                    continue

                # Nur von autorisiertem Chat akzeptieren
                if TELEGRAM_CHAT and str(chat_id) != str(TELEGRAM_CHAT):
                    log(f"Unauthorized message from chat_id {chat_id}")
                    continue

                log(f"Message: {text[:80]}")
                try:
                    process_message(chat_id, text)
                except Exception as e:
                    log(f"process_message error: {e}")
                    tg_send(chat_id, f"❌ Fehler: {str(e)[:200]}")

        except KeyboardInterrupt:
            log("Bot gestoppt (KeyboardInterrupt)")
            break
        except Exception as e:
            log(f"Main loop error: {e}")
            time.sleep(5)


# ── launchd Install / Uninstall ───────────────────────────────────────────────
PLIST_PATH = Path.home() / "Library/LaunchAgents/com.pipo.telegrambot.plist"

def install_service():
    env_file = LEADTRACKER / ".env"
    script   = Path(__file__).resolve()
    python   = sys.executable

    # Lese env file für launchd EnvironmentVariables
    env_vars = {}
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("export ") and "=" in line:
                    kv = line[7:]
                    k, v = kv.split("=", 1)
                    v = v.strip('"').strip("'")
                    if v:
                        env_vars[k.strip()] = v
    except Exception as e:
        print(f"Konnte .env nicht lesen: {e}")

    env_xml = "\n".join(
        f"        <key>{k}</key>\n        <string>{v}</string>"
        for k, v in env_vars.items()
    )

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pipo.telegrambot</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{script}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
{env_xml}
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/pipo_bot.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/pipo_bot_err.log</string>
    <key>WorkingDirectory</key>
    <string>{LEADTRACKER}</string>
</dict>
</plist>"""

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist)
    print(f"✅ Service installiert: {PLIST_PATH}")

    # Laden
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    result = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Service gestartet (läuft ab jetzt automatisch beim Login)")
    else:
        print(f"⚠️ launchctl load: {result.stderr}")


def uninstall_service():
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink()
        print(f"✅ Service entfernt: {PLIST_PATH}")
    else:
        print("Service nicht installiert.")


# ── Entry Point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pipo Interactive Telegram Bot")
    parser.add_argument("--install",   action="store_true", help="Als macOS Service installieren")
    parser.add_argument("--uninstall", action="store_true", help="Service deinstallieren")
    args = parser.parse_args()

    if args.install:
        install_service()
        return
    if args.uninstall:
        uninstall_service()
        return

    run_bot()


if __name__ == "__main__":
    main()
