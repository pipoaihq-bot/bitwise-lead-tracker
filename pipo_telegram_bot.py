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
- help             → {}
- unknown          → {}

Regeln:
- "hinzufügen/anlegen/add/eintragen" → add_lead
- "strategie/battle card" zusammen mit add → add_lead + want_strategy=true
- "strategie/battle card/card" alleine → battle_card
- "status/wie läuft/wie steht/was ist bei" → status
- "wer ist/finde/entscheider/suche" + Firma → find_contacts
- "top leads/top N/zeig leads" → top_leads
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
        "max_tokens": 120,
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


def handle_help(chat_id):
    msg = """🤖 <b>Pipo Bot — Befehle</b>

<b>LinkedIn URL einfach senden:</b>
<code>https://linkedin.com/in/beritfuss</code>
→ DB-Check + Profil + AI-Einschätzung

<b>Explizite Befehle:</b>
/top [n]                        — Top N Leads (default: 5)
/status [firma]                 — Lead-Status + MEDDPICC
/card [firma]                   — Battle Card generieren
/add [url] [firma] [Region]     — Lead anlegen
/find [rolle] bei [firma]       — Entscheider auf LinkedIn suchen

<b>Sales Navigator (natürliche Sprache):</b>
"wer ist CTO bei Euler Hermes?"   → LinkedIn Suche
"finde Entscheider bei DDA"       → C-Level Suche
"entscheider bei [firma]"         → Gleich

<b>Weitere Befehle:</b>
"haben wir [name/firma]?"  → DB-Suche
"zeig mir die top leads"   → /top
"battle card für [firma]"  → /card
"hinzufügen + strategie"   → Add + Battle Card

<a href='https://pipo-bitwise-lead-tracker.streamlit.app'>📊 Dashboard</a>"""
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
    if text_lower in ("/help", "help", "hilfe", "?", "/start"):
        handle_help(chat_id)
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
            updates = tg_get_updates(offset)
            if not updates.get("ok"):
                time.sleep(5)
                continue

            for update in updates.get("result", []):
                offset = update["update_id"] + 1
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
