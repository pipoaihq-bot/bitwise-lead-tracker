#!/usr/bin/env python3
"""
pipo_battlecard.py — Pipo's Autonomes Deep Research & Battle Card System
=========================================================================
Für jeden der Top N Leads:
  1. Deep Research via Exa (News, LinkedIn, Trigger, Hiring, Konkurrenz)
  2. Battle Card via Claude Sonnet (Strategie, Einwände, Multi-Channel)
  3. Telegram Digest (kompakt, actionable)
  4. Battlecard als Markdown gespeichert (lokale Referenz)

Usage:
  python3 pipo_battlecard.py              # Top 5, alle Regionen
  python3 pipo_battlecard.py --top 10     # Top 10
  python3 pipo_battlecard.py --region DE  # Nur DACH
  python3 pipo_battlecard.py --dry-run    # Nur Terminal, kein Telegram
  python3 pipo_battlecard.py --lead "Deutsche Bank"  # Nur ein spezifischer Lead
"""

import os, sys, json, time, argparse, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ.get("SUPABASE_URL",  "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY",  "")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
EXA_KEY        = os.environ.get("EXA_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
DASHBOARD_URL  = "https://pipo-bitwise-lead-tracker.streamlit.app"
BATTLECARD_DIR = Path.home() / ".openclaw/workspace/leads/battlecards"

# LinkedIn Navigator (optional — pip install linkedin-api + .env konfigurieren)
# li_at holen: Chrome → linkedin.com → F12 → Application → Cookies → li_at → Wert kopieren
LINKEDIN_EMAIL    = os.environ.get("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "")
LINKEDIN_LI_AT    = os.environ.get("LINKEDIN_LI_AT", "")
_LI_API_CLIENT    = None

# ── Colors ──────────────────────────────────────────────────────────────────
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

# ── Exa Search ───────────────────────────────────────────────────────────────
def exa_search(query, num_results=5, start_date=None, include_domains=None, exclude_domains=None, text_max_chars=800):
    """Exa Neural Search — bessere Ergebnisse als Google News RSS."""
    if not EXA_KEY:
        return []
    try:
        payload = {
            "query": query,
            "numResults": num_results,
            "contents": {"text": {"maxCharacters": text_max_chars}},
            "useAutoprompt": True,
        }
        if start_date:
            payload["startPublishedDate"] = start_date
        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains

        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://api.exa.ai/search",
            data=body, method="POST",
            headers={
                "x-api-key": EXA_KEY,
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "text": r.get("text", "")[:text_max_chars],
                "published": r.get("publishedDate", "")[:10] if r.get("publishedDate") else "",
                "author": r.get("author", ""),
            }
            for r in results
            if r.get("title") or r.get("text")
        ]
    except Exception as e:
        return []

# ── LinkedIn Navigator Integration ────────────────────────────────────────────
# Einmalig installieren:  pip install linkedin-api
# li_at Cookie holen:     Chrome → linkedin.com → F12 → Application → Cookies → li_at
#
# Option A (empfohlen):   Nur li_at Cookie setzen → LINKEDIN_LI_AT in .env
# Option B:               Email + Passwort → LINKEDIN_EMAIL + LINKEDIN_PASSWORD in .env

def _linkedin_api():
    """Gibt gecachten LinkedIn API Client zurück oder None wenn nicht verfügbar."""
    global _LI_API_CLIENT
    if _LI_API_CLIENT:
        return _LI_API_CLIENT
    if not LINKEDIN_EMAIL and not LINKEDIN_LI_AT:
        return None
    try:
        from linkedin_api import Linkedin  # pip install linkedin-api
        if LINKEDIN_EMAIL and LINKEDIN_PASSWORD:
            _LI_API_CLIENT = Linkedin(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        elif LINKEDIN_LI_AT:
            # Cookie-only Auth: li_at setzen, dann JSESSIONID holen für CSRF-Token
            _LI_API_CLIENT = Linkedin("", "", authenticate=False)
            sess = _LI_API_CLIENT.client.session
            sess.cookies.set("li_at", LINKEDIN_LI_AT, domain=".linkedin.com")
            # Init-Request um JSESSIONID zu bekommen
            sess.get(
                "https://www.linkedin.com/",
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
            # CSRF-Token aus JSESSIONID ableiten
            jsid = sess.cookies.get("JSESSIONID", "")
            if jsid:
                sess.headers.update({"csrf-token": jsid})
        return _LI_API_CLIENT
    except ImportError:
        print(f"{Y}  [LinkedIn] linkedin-api nicht installiert → pip install linkedin-api{X}")
        return None
    except Exception as e:
        print(f"{Y}  [LinkedIn] Auth Fehler: {e}{X}")
        return None


def linkedin_enrich_contact(contact_name, company):
    """
    Sucht eine Person auf LinkedIn und gibt angereichertes Profil zurück.
    Felder aus linkedin-api v2: urn_id, name, jobtitle, location, distance
    distance='DISTANCE_1' → 1st degree connection (warmer Kontakt!)
    distance='DISTANCE_2' → 2nd degree (mutual connections möglich)
    """
    api = _linkedin_api()
    if not api or not contact_name:
        return None
    try:
        results = api.search_people(keywords=f"{contact_name} {company}", limit=5)
        if not results:
            return None

        # Bestes Match: Firmenname in jobtitle oder name
        best = results[0]
        co_words = [w for w in company.lower().split() if len(w) > 3]
        for r in results:
            jt = (r.get("jobtitle") or "").lower()
            nm = (r.get("name") or "").lower()
            if any(w in jt or w in nm for w in co_words):
                best = r
                break

        urn_id   = best.get("urn_id", "")
        distance = best.get("distance", "DISTANCE_3")
        name     = best.get("name", "")
        jobtitle = best.get("jobtitle", "")
        location = best.get("location", "")

        # Vollprofil laden (enthält experience, summary, connections)
        profile = {}
        try:
            if urn_id:
                profile = api.get_profile(urn_id=urn_id) or {}
        except Exception:
            pass

        public_id = profile.get("public_id", "")

        # Aktuelle Rolle aus Experience
        exps = profile.get("experience", [])
        current_role = jobtitle  # Fallback auf search result
        if exps:
            e = exps[0]
            title   = e.get("title", "")
            co_name = e.get("companyName", "")
            if title or co_name:
                current_role = f"{title} bei {co_name}".strip(" bei")

        # Letzte LinkedIn Posts
        recent_posts = []
        try:
            if urn_id:
                posts = api.get_profile_posts(urn_id=urn_id, post_count=5) or []
                for p in posts[:3]:
                    text = ""
                    try:
                        commentary = p.get("commentary") or {}
                        if isinstance(commentary, dict):
                            inner = commentary.get("text", {})
                            text = inner.get("text", "") if isinstance(inner, dict) else str(inner)
                        elif isinstance(commentary, str):
                            text = commentary
                    except Exception:
                        pass
                    if text and len(str(text)) > 20:
                        recent_posts.append(str(text)[:200])
        except Exception:
            pass

        # Gemeinsame Verbindungen (Mutual Connections via get_profile_connections)
        mutual = []
        try:
            if urn_id:
                conns = api.get_profile_connections(urn_id) or []
                for c in conns[:8]:
                    cname  = c.get("name", "")
                    ctitle = str(c.get("jobtitle") or c.get("headline", ""))[:60]
                    if cname:
                        mutual.append({"name": cname, "title": ctitle})
        except Exception:
            pass

        # Degree-of-connection als Intro-Hinweis
        intro_hint = ""
        if distance == "DISTANCE_1":
            intro_hint = "✅ 1st-degree — Philipp kennt diese Person direkt!"
        elif distance == "DISTANCE_2":
            intro_hint = "🔵 2nd-degree — Intro über gemeinsamen Kontakt möglich"
        else:
            intro_hint = "❄️ 3rd+ degree — kein warmer Pfad via LinkedIn"

        return {
            "urn_id":             urn_id,
            "public_id":          public_id,
            "profile_url":        f"https://linkedin.com/in/{public_id}" if public_id else "",
            "name":               name,
            "headline":           jobtitle,
            "location":           location,
            "connections_count":  profile.get("connections", 0),
            "summary":            (profile.get("summary") or "")[:300],
            "current_role":       current_role,
            "distance":           distance,
            "intro_hint":         intro_hint,
            "mutual_connections": mutual,
            "recent_posts":       recent_posts,
        }
    except Exception as e:
        print(f"{Y}  [LinkedIn] Kontaktsuche Fehler: {e}{X}")
        return None


def linkedin_find_decision_makers(company_urn, company_name, top_roles=None):
    """
    Sales Navigator-ähnliche Suche: C-Level / VP / Head-of bei einer Firma.
    Nutzt search_people(keyword_title=..., keyword_company=...) — kein Sales Navigator Abo nötig.
    Gibt Liste zurück sortiert nach Degree (1st → 2nd → 3rd+).
    """
    api = _linkedin_api()
    if not api:
        return []
    if top_roles is None:
        top_roles = [
            "Managing Director", "CIO", "CFO", "CTO",
            "Head of Digital Assets", "Head of Treasury",
            "Director", "Portfolio Manager",
        ]
    found = []
    seen_names = set()
    for role in top_roles[:4]:  # max 4 Suchen → Rate Limit schonen
        try:
            results = api.search_people(
                keyword_title=role,
                keyword_company=company_name,
                limit=3,
            ) or []
            for r in results:
                name     = (r.get("name") or "").strip()
                jobtitle = r.get("jobtitle", "")
                distance = r.get("distance", "DISTANCE_3")
                urn_id   = r.get("urn_id", "")
                pub_id   = r.get("publicIdentifier") or r.get("public_id", "")
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                degree = "1st" if distance == "DISTANCE_1" else "2nd" if distance == "DISTANCE_2" else "3rd+"
                found.append({
                    "name":       name,
                    "title":      jobtitle,
                    "distance":   distance,
                    "degree":     degree,
                    "urn_id":     urn_id,
                    "public_id":  pub_id,
                    "profile_url": f"https://linkedin.com/in/{pub_id}" if pub_id else "",
                })
        except Exception:
            pass
        time.sleep(0.5)
    prio = {"DISTANCE_1": 0, "DISTANCE_2": 1, "DISTANCE_3": 2}
    found.sort(key=lambda x: prio.get(x["distance"], 3))
    return found[:8]


def linkedin_get_company_news(company_public_id):
    """
    Holt aktuelle LinkedIn Company Updates als Conversation Starter.
    company_public_id: z.B. "deutsche-digital-assets" (aus get_company URL).
    """
    api = _linkedin_api()
    if not api or not company_public_id:
        return []
    try:
        updates = api.get_company_updates(public_id=str(company_public_id), max_results=5) or []
        news = []
        for u in updates[:5]:
            text = ""
            try:
                commentary = u.get("commentary") or {}
                if isinstance(commentary, dict):
                    inner = commentary.get("text", {})
                    text = inner.get("text", "") if isinstance(inner, dict) else str(inner)
                elif isinstance(commentary, str):
                    text = commentary
            except Exception:
                pass
            if text and len(str(text)) > 20:
                news.append({
                    "title":     "LinkedIn Company Post",
                    "text":      str(text)[:300],
                    "url":       f"https://linkedin.com/company/{company_public_id}/posts",
                    "published": "",
                    "author":    "",
                })
        return news
    except Exception as e:
        print(f"{Y}  [LinkedIn] Company News Fehler: {e}{X}")
        return []


def linkedin_get_company(company_name):
    """Holt LinkedIn-Firmendaten. Felder: urn_id, name, headline (Branche+HQ), subline (Follower)."""
    api = _linkedin_api()
    if not api:
        return None
    try:
        results = api.search_companies(keywords=company_name, limit=5)
        if not results:
            return None

        best = results[0]
        for r in results:
            if company_name.lower() in (r.get("name") or "").lower():
                best = r
                break

        co_urn = str(best.get("urn_id", ""))
        co_name = best.get("name", company_name)
        headline = best.get("headline", "")   # "Financial Services • Frankfurt"
        subline  = best.get("subline", "")    # "5K followers"

        # Versuche Vollprofil via urn_id (numeric company ID)
        co = {}
        if co_urn:
            try:
                co = api.get_company(co_urn) or {}
            except Exception:
                pass

        industries = co.get("companyIndustries") or []
        industry = industries[0].get("localizedName", "") if industries else ""
        if not industry and headline:
            industry = headline.split("•")[0].strip()

        hq = co.get("headquarter") or {}
        hq_str = f"{hq.get('city','')} {hq.get('country','')}".strip()
        if not hq_str and "•" in headline:
            hq_str = headline.split("•")[-1].strip()

        return {
            "name":           co.get("name", co_name),
            "tagline":        co.get("tagline", ""),
            "description":    (co.get("description") or "")[:250],
            "employee_count": co.get("staffCount", 0),
            "follower_count": subline,
            "industry":       industry,
            "hq":             hq_str,
            "founded":        co.get("foundedOn", {}).get("year", ""),
            "url":            f"https://linkedin.com/company/{co_urn}" if co_urn else "",
            "specialties":    (co.get("specialities") or [])[:5],
        }
    except Exception as e:
        print(f"{Y}  [LinkedIn] Firmensuche Fehler: {e}{X}")
        return None


# ── Deep Research per Lead ────────────────────────────────────────────────────
def deep_research(lead):
    """
    6 Exa-Suchen pro Lead:
    1. Company news (letzte 90 Tage)
    2. Crypto/Staking Relevanz
    3. Hiring signals (Digital Assets Team aufbauen?)
    4. Contact person's public activity
    5. LinkedIn profile data
    6. MiCA / regulatory triggers
    """
    company = lead["company"]
    contact = lead.get("contact_person") or ""
    region  = lead.get("region") or "DE"
    industry = lead.get("industry") or "Institutional"

    since_90d = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00.000Z")
    since_30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z")

    research = {
        "company_news": [],
        "crypto_relevance": [],
        "hiring_signals": [],
        "contact_activity": [],
        "linkedin_profile": [],
        "regulatory_triggers": [],
        "mutual_connections": [],
        "linkedin_company": {},
        "decision_makers": [],
        "company_updates": [],
    }

    # 1. Company news — general (funding, partnerships, expansions, leadership)
    r1 = exa_search(
        f'"{company}" news announcement 2025 2026',
        num_results=4,
        start_date=since_90d
    )
    research["company_news"] = r1

    # 2. Crypto / ETH Staking relevance
    r2 = exa_search(
        f'"{company}" crypto digital assets ETH staking blockchain institutional',
        num_results=3,
        start_date=since_90d
    )
    research["crypto_relevance"] = r2

    # 3. Hiring signals — are they building a digital assets team?
    r3 = exa_search(
        f'"{company}" hiring digital assets crypto blockchain DeFi "head of" "director" 2025 2026',
        num_results=3,
        include_domains=["linkedin.com", "indeed.com", "glassdoor.com", "jobs.ashbyhq.com", "lever.co", "greenhouse.io"]
    )
    research["hiring_signals"] = r3

    # 4. Contact person public activity (interviews, posts, speeches)
    if contact:
        first_name = contact.split()[0] if contact else ""
        r4 = exa_search(
            f'"{contact}" {company} digital assets crypto staking interview article post 2025 2026',
            num_results=3,
            start_date=since_90d
        )
        research["contact_activity"] = r4

    # 5. LinkedIn profile data (via Exa neural search)
    if contact:
        r5 = exa_search(
            f'site:linkedin.com "{contact}" {company}',
            num_results=2,
            include_domains=["linkedin.com"]
        )
        research["linkedin_profile"] = r5

    # 6. MiCA / regulatory triggers relevant to their region & industry
    r6 = exa_search(
        f'"{company}" MiCA regulation crypto compliance EMEA institutional 2025 2026',
        num_results=3,
        start_date=since_90d
    )
    research["regulatory_triggers"] = r6

    # ── LinkedIn Navigator Enrichment (falls Zugangsdaten gesetzt) ──────────────
    if LINKEDIN_EMAIL or LINKEDIN_LI_AT:
        print(f"    → LinkedIn enrichment...", end="", flush=True)
        li_count = 0

        if contact:
            li_data = linkedin_enrich_contact(contact, company)
            if li_data:
                li_count += 1
                research["linkedin_profile"] = [{
                    "title":     li_data.get("headline", ""),
                    "url":       li_data.get("profile_url", ""),
                    "text": (
                        f"Name: {li_data.get('name','')}\n"
                        f"Headline: {li_data.get('headline','')}\n"
                        f"Location: {li_data.get('location','')}\n"
                        f"Current: {li_data.get('current_role','')}\n"
                        f"Connections: {li_data.get('connections_count',0)}\n"
                        f"Connection-Degree: {li_data.get('intro_hint','')}\n"
                        f"Summary: {li_data.get('summary','')}"
                    ),
                    "published": "",
                    "author":    "",
                    "_li":       li_data,
                }]
                research["mutual_connections"] = li_data.get("mutual_connections", [])
                # Intro-Hint direkt in research speichern
                research["intro_hint"] = li_data.get("intro_hint", "")
                if li_data.get("recent_posts"):
                    research["contact_activity"] = [
                        {
                            "title":     "LinkedIn Post",
                            "url":       li_data.get("profile_url", ""),
                            "text":      post,
                            "published": "",
                        }
                        for post in li_data["recent_posts"]
                    ]

        li_co = linkedin_get_company(company)
        if li_co:
            li_count += 1
            research["linkedin_company"] = li_co

            # Decision Makers — C-Level / VP / Director bei dieser Firma suchen
            co_urn = li_co.get("url", "").split("/company/")[-1].rstrip("/") if li_co.get("url") else ""
            dm = linkedin_find_decision_makers(co_urn, company)
            if dm:
                research["decision_makers"] = dm
                li_count += 1

            # Company News/Updates — conversation starters
            # public_id aus URL ableiten (linkedin.com/company/SLUG)
            co_public_id = li_co.get("url", "").split("/company/")[-1].rstrip("/") if li_co.get("url") else ""
            if co_public_id:
                cn = linkedin_get_company_news(co_public_id)
                if cn:
                    research["company_updates"] = cn
                    li_count += 1

        print(f" {G}✓{X} ({li_count} LinkedIn Quellen)")

    return research

# ── Claude: Full Battle Card ──────────────────────────────────────────────────
def generate_battlecard(lead, research):
    """
    Claude Sonnet generates a comprehensive battle card with:
    - Trigger (THE reason to reach out NOW)
    - Company intel (what they actually do, size, context)
    - Contact intel (who they are, their background, their angle)
    - Pain points (3 specific, for this company type)
    - Our edge (why Bitwise BOS for them specifically)
    - Objection handlers (3 most likely, with rebuttals)
    - Competitor landscape (who else they might use)
    - Strategy (3-step sequence)
    - Email draft (ready to send)
    - LinkedIn connect text
    - LinkedIn InMail text
    - First call agenda (15 min)
    """
    if not ANTHROPIC_KEY:
        return _empty_battlecard()

    region  = lead.get("region", "DE")
    contact = lead.get("contact_person") or "unbekannt"
    lang = "Deutsch" if region in ("DE", "AT", "CH") else "Englisch"
    use_du = region in ("DE", "AT", "CH") or (lead.get("industry") or "").lower() in ("crypto/blockchain", "crypto", "blockchain", "defi", "fintech")
    first_name = contact.split()[0] if contact != "unbekannt" else "zusammen"

    # Compile research into structured text
    def format_results(results, label):
        if not results:
            return f"{label}: keine Ergebnisse"
        lines = []
        for r in results[:3]:
            title = r.get("title", "")
            text  = r.get("text", "")[:200]
            pub   = r.get("published", "")
            url   = r.get("url", "")
            lines.append(f"  [{pub}] {title}\n    {text[:150]}...\n    URL: {url}")
        return f"{label}:\n" + "\n".join(lines)

    # Mutual Connections formatieren
    mutual = research.get("mutual_connections", [])
    if mutual:
        mutual_text = "GEMEINSAME VERBINDUNGEN (LinkedIn):\n" + "\n".join(
            f"  • {m['name']} — {m.get('title','')}" for m in mutual
        )
    else:
        mutual_text = "GEMEINSAME VERBINDUNGEN: Keine gefunden — kalt angehen"

    # LinkedIn Firmendaten
    li_co = research.get("linkedin_company", {})
    if li_co:
        li_co_text = (
            f"LINKEDIN FIRMENDATEN:\n"
            f"  Mitarbeiter: {li_co.get('employee_count','?')}\n"
            f"  Branche: {li_co.get('industry','?')}\n"
            f"  HQ: {li_co.get('hq','?')}\n"
            f"  Gegründet: {li_co.get('founded','?')}\n"
            f"  Tagline: {li_co.get('tagline','')}\n"
            f"  Beschreibung: {li_co.get('description','')[:150]}"
        )
    else:
        li_co_text = "LINKEDIN FIRMENDATEN: Nicht verfügbar"

    # Decision Makers
    dm_list = research.get("decision_makers", [])
    if dm_list:
        dm_text = "ENTSCHEIDER BEI DIESER FIRMA (LinkedIn Navigator):\n" + "\n".join(
            f"  • {d['name']} — {d.get('title','')} ({d['degree']}-degree)"
            + (f"  → WARM: {d['name']} ist 1st-degree, Philipp kennt diese Person!" if d['degree'] == "1st" else "")
            for d in dm_list
        )
    else:
        dm_text = "ENTSCHEIDER: Keine gefunden via LinkedIn Navigator"

    # Company Updates / Conversation Starters
    cu_list = research.get("company_updates", [])
    if cu_list:
        cu_text = "AKTUELLE LINKEDIN COMPANY POSTS (Conversation Starters):\n" + "\n".join(
            f"  • {p.get('text','')[:150]}" for p in cu_list[:3]
        )
    else:
        cu_text = "COMPANY UPDATES: Keine LinkedIn Posts gefunden"

    research_text = "\n\n".join([
        format_results(research["company_news"],        "COMPANY NEWS"),
        format_results(research["crypto_relevance"],    "CRYPTO/STAKING RELEVANZ"),
        format_results(research["hiring_signals"],      "HIRING SIGNALE"),
        format_results(research["contact_activity"],    "KONTAKTPERSON AKTIVITÄT / POSTS"),
        format_results(research["linkedin_profile"],    "LINKEDIN PROFIL"),
        format_results(research["regulatory_triggers"], "REGULATORIK/MICA"),
        mutual_text,
        li_co_text,
        dm_text,
        cu_text,
    ])

    prompt = f"""Du bist Pipo, Senior Pre-Sales Analyst für Philipp Sandor (HEAD EMEA, Bitwise Asset Management, Dubai).

DEINE AUFGABE: Erstelle eine vollständige Battle Card für diesen Lead. Nutze NUR die bereitgestellten Research-Daten. Erfinde NICHTS.

════════════════════════════════════
LEAD PROFIL
════════════════════════════════════
Unternehmen: {lead['company']}
Kontakt: {contact} ({lead.get('title') or 'Titel unbekannt'})
Region: {region} | Industry: {lead.get('industry') or 'Institutional'}
AUM: ~€{lead.get('aum_estimate_millions') or 0:.0f}M
Deal Potential: €{lead.get('expected_deal_size_millions') or 0:.0f}M
Stage: {lead.get('stage', 'prospecting')} | Inaktiv: {lead['days_inactive']} Tage
MEDDPICC: {lead['meddpicc']}/80
Metrics: {lead.get('m_metrics',0)}/10 | Eco.Buyer: {lead.get('m_economic',0)}/10 | Pain: {lead.get('m_pain',0)}/10 | Champion: {lead.get('m_champion',0)}/10
LinkedIn: {lead.get('linkedin') or 'unbekannt'}
Email: {lead.get('email') or 'unbekannt'}

════════════════════════════════════
RESEARCH ERGEBNISSE
════════════════════════════════════
{research_text}

════════════════════════════════════
BITWISE BOS — FAKTEN (nur verwenden was relevant ist)
════════════════════════════════════
- ~$5B ETH gestaked, non-custodial
- Zero Slashings seit Genesis September 2022
- 99.984% Uptime 2025
- APR 3.170% vs Benchmark 3.015% (+0.155% Outperformance)
- MiCA-konform, KPMG-geprüft
- Custody-Integration: Fireblocks, Ledger Enterprise, etc.
- 40+ institutionelle Kunden in EMEA
- Institutional-grade Reporting & Attribution
- Philipps Ansprechpartner: Philipp Sandor, HEAD EMEA

════════════════════════════════════
PHILIPPS SCHREIBSTIL (ZWINGEND EINHALTEN)
════════════════════════════════════
- Warm, direkt, menschlich. Nie corporate.
- Max. 4 Sätze im Body
- Anrede: {"'du' / '" + first_name + "'" if use_du else "'Sie' / '" + first_name + "'"}
- Crypto/Startup/Fintech → immer "du"
- Traditionelle Bank/Versicherung → "Sie"
- Signatur DE: "Viele Grüße aus Dubai,\\nPhilipp"
- Signatur EN: "Best,\\nPhilipp"
- VERBOTEN: Buzzwords, mehrere Produkt-Facts, "Ich hoffe...", mehrere CTAs

ECHTE PHILIPPS BEISPIELE:
→ "Hallo Pascal, bei uns stehen große Neuigkeiten an — wäre dir ein 15-minütiges Gespräch nächste Woche möglich?"
→ "Hi Guy, Really enjoyed the chat. From what you shared, there's solid overlap around integration. Send me a few time slots. Best, Philipp"

════════════════════════════════════
AUSGABE — NUR DIESES JSON-FORMAT, KEIN KOMMENTAR:
════════════════════════════════════
{{
  "trigger": "DER EINE Grund warum JETZT kontaktieren — konkret, aus Research (falls kein Research: aus Stage/Inaktivität/MEDDPICC)",
  "company_intel": "2 Sätze: was macht das Unternehmen, relevante Größe/Kontext",
  "contact_intel": "Was wir über die Kontaktperson wissen — Hintergrund, Rolle, Stance zu Crypto/Digital Assets",
  "pain_points": ["Pain Point 1 spezifisch für diese Firma", "Pain Point 2", "Pain Point 3"],
  "our_edge": "Warum Bitwise BOS speziell für DIESE Firma — 1-2 Sätze, spezifisch",
  "objections": [
    {{"objection": "Wahrscheinlichster Einwand 1", "rebuttal": "Kurze, direkte Antwort"}},
    {{"objection": "Wahrscheinlichster Einwand 2", "rebuttal": "Kurze, direkte Antwort"}},
    {{"objection": "Wahrscheinlichster Einwand 3", "rebuttal": "Kurze, direkte Antwort"}}
  ],
  "competitors": "Wer würde sonst für ETH Staking in Frage kommen (Coinbase Prime, Lido, Figment, Kiln, Eigenentwicklung — was ist am wahrscheinlichsten für diese Firma?)",
  "strategy": {{
    "step1": "Erste Aktion (z.B. LinkedIn Connect + kurze Note)",
    "step2": "Falls kein Reply in 5 Tagen: Cold Email mit Aufhänger",
    "step3": "Falls kein Reply in 10 Tagen: Follow-up mit konkretem Value"
  }},
  "email": {{
    "subject": "Betreff — kurz, spezifisch, kein Spam-Trigger, max. 8 Wörter",
    "body": "Vollständiger Email-Body — direkt sendbar, kein Platzhalter"
  }},
  "mutual_connections": "Gemeinsame Verbindungen / Intro-Möglichkeit — aus den LinkedIn-Daten; falls keiner: 'Kein gemeinsamer Kontakt — kalt angehen'",
  "key_contacts": "Top 2-3 Entscheider bei dieser Firma die Philipp ansprechen sollte — aus ENTSCHEIDER-Liste; mit Rolle und warum relevant",
  "linkedin_connect": "Kurzer LinkedIn Connection Request Text (max. 300 Zeichen) — persönlich, nicht generisch; falls gemeinsamer Kontakt vorhanden → namentlich erwähnen",
  "linkedin_inmail": "LinkedIn InMail Text — etwas länger als Email, gleiche Regeln",
  "call_agenda": "15-Minuten First Call Agenda — 3 Punkte die Philipp besprechen soll"
}}"""

    try:
        payload = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 2500,
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
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())

        text = resp["content"][0]["text"].strip()
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON in response")
        return json.loads(text[start:end])
    except Exception as e:
        print(f" {R}Claude Error: {e}{X}")
        return _empty_battlecard()

def _empty_battlecard():
    return {
        "trigger": "Kein Research verfügbar — manuelle Bewertung empfohlen",
        "company_intel": "—",
        "contact_intel": "—",
        "pain_points": ["—", "—", "—"],
        "our_edge": "—",
        "objections": [],
        "competitors": "—",
        "strategy": {"step1": "LinkedIn Connect", "step2": "Cold Email", "step3": "Follow-up"},
        "email": {"subject": "ETH Staking — Bitwise EMEA", "body": "—"},
        "mutual_connections": "Kein gemeinsamer Kontakt — kalt angehen",
        "linkedin_connect": "—",
        "linkedin_inmail": "—",
        "call_agenda": "—"
    }

# ── Load Top Leads from Supabase ──────────────────────────────────────────────
REGION_SCORE = {"DE": 25, "CH": 22, "UAE": 20, "UK": 18, "NORDICS": 15, "EUROPE": 10, "MIDEAST": 12, "USA": 5}
TIER_SCORE   = {1: 35, 2: 20, 3: 8, 4: 2}

def days_since(ts_str):
    if not ts_str: return 999
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc) - ts).days)
    except: return 999

def load_top_leads(region=None, top_n=5, company_filter=None):
    print(f"{B}Loading leads from Supabase...{X}")
    all_leads, offset, page = [], 0, 1000
    while True:
        params = (
            "select=id,company,region,tier,contact_person,title,email,linkedin,"
            "stage,industry,sub_region,expected_deal_size_millions,aum_estimate_millions,updated_at,created_at"
            "&stage=neq.closed_won&stage=neq.closed_lost"
            f"&limit={page}&offset={offset}"
        )
        if region: params += f"&region=eq.{region}"
        if company_filter: params += f"&company=ilike.*{urllib.parse.quote(company_filter)}*"
        chunk = sb_get("leads", params)
        if not chunk: break
        all_leads.extend(chunk)
        if len(chunk) < page: break
        offset += page

    scores_raw = sb_get("meddpicc_scores", "select=lead_id,total_score,qualification_status,metrics,economic_buyer,pain,champion&limit=50000")
    meddpicc = {s["lead_id"]: s for s in scores_raw}

    scored = []
    for l in all_leads:
        m    = meddpicc.get(l["id"], {})
        medd = m.get("total_score", 0) or 0
        days = days_since(l.get("updated_at"))
        tier = l.get("tier") or 3
        reg  = l.get("region") or "EUROPE"

        tier_pts   = TIER_SCORE.get(tier, 5)
        region_pts = REGION_SCORE.get(reg, 5)
        medd_pts   = min(20, int(medd / 80 * 20))
        inact_pts  = 15 if days <= 7 else 10 if days <= 30 else 5 if days <= 90 else 2
        deal       = float(l.get("expected_deal_size_millions") or 0)
        deal_pts   = 5 if deal >= 1 else 3 if deal >= 0.5 else 1

        scored.append({
            **l,
            "meddpicc":    medd,
            "ql":          m.get("qualification_status", "UNQUALIFIED"),
            "m_metrics":   m.get("metrics", 0) or 0,
            "m_economic":  m.get("economic_buyer", 0) or 0,
            "m_pain":      m.get("pain", 0) or 0,
            "m_champion":  m.get("champion", 0) or 0,
            "days_inactive": days,
            "priority_score": tier_pts + region_pts + medd_pts + inact_pts + deal_pts,
        })

    scored.sort(key=lambda x: x["priority_score"], reverse=True)
    result = scored[:top_n]
    print(f"  → {G}{len(result)} Leads geladen{X} (aus {len(all_leads)} aktiven)\n")
    return result

# ── Save Battle Card as Markdown ──────────────────────────────────────────────
def save_battlecard(lead, bc, research):
    today = datetime.now().strftime("%Y-%m-%d")
    company_slug = lead["company"].lower().replace(" ", "_").replace("/", "_")[:30]
    card_dir = BATTLECARD_DIR / today
    card_dir.mkdir(parents=True, exist_ok=True)
    card_path = card_dir / f"{company_slug}.md"

    ql_emoji = {"QUALIFIED": "🟢", "PROBABLE": "🔵", "POSSIBLE": "🟡", "UNQUALIFIED": "⚪"}.get(lead["ql"], "⚪")

    md = f"""# Battle Card: {lead['company']}
*Erstellt von Pipo · {datetime.now().strftime("%d.%m.%Y %H:%M")} · {today}*

---

## 📍 Lead-Profil

| Feld | Wert |
|------|------|
| **Unternehmen** | {lead['company']} |
| **Kontakt** | {lead.get('contact_person') or '—'} ({lead.get('title') or '—'}) |
| **Region** | {lead.get('region','?')} · {lead.get('industry','?')} |
| **AUM** | ~€{lead.get('aum_estimate_millions') or 0:.0f}M |
| **Deal Potential** | €{lead.get('expected_deal_size_millions') or 0:.0f}M |
| **Stage** | {lead.get('stage','prospecting')} |
| **MEDDPICC** | {ql_emoji} {lead['meddpicc']}/80 |
| **LinkedIn** | {lead.get('linkedin') or '—'} |
| **Email** | {lead.get('email') or '—'} |

---

## ⚡ TRIGGER — Warum JETZT

> {bc.get('trigger','—')}

---

## 🏢 Company Intel

{bc.get('company_intel','—')}

## 👤 Contact Intel

{bc.get('contact_intel','—')}

---

## 🤝 Gemeinsame Verbindungen / Intro-Möglichkeit

{bc.get('mutual_connections','Kein gemeinsamer Kontakt — kalt angehen')}

---

## 🩹 Pain Points

"""
    for i, p in enumerate(bc.get("pain_points", []), 1):
        md += f"{i}. {p}\n"

    md += f"""
---

## 🎯 Unser Edge

{bc.get('our_edge','—')}

---

## ⚔️ Objection Handlers

"""
    for obj in bc.get("objections", []):
        md += f"**❓ {obj.get('objection','?')}**\n→ {obj.get('rebuttal','—')}\n\n"

    md += f"""---

## 🏁 Wettbewerb

{bc.get('competitors','—')}

---

## 📋 Strategie (3 Schritte)

**Schritt 1:** {bc.get('strategy',{}).get('step1','—')}
**Schritt 2:** {bc.get('strategy',{}).get('step2','—')}
**Schritt 3:** {bc.get('strategy',{}).get('step3','—')}

---

## ✉️ Email Draft

**Subject:** `{bc.get('email',{}).get('subject','—')}`

```
{bc.get('email',{}).get('body','—')}
```

---

## 🔗 LinkedIn Connect Request

```
{bc.get('linkedin_connect','—')}
```

---

## 💬 LinkedIn InMail

```
{bc.get('linkedin_inmail','—')}
```

---

## 📞 First Call Agenda (15 min)

{bc.get('call_agenda','—')}

---

## 🔍 Research Details

"""
    for category, results in research.items():
        if not results or not isinstance(results, list):
            continue
        md += f"### {category.replace('_',' ').title()}\n"
        for r in results[:2]:
            if not isinstance(r, dict):
                continue
            md += f"- [{r.get('published','')}] [{r.get('title','')}]({r.get('url','')})\n"
            if r.get("text"):
                text_preview = str(r['text'])[:200]
                md += f"  > {text_preview}...\n"
        md += "\n"

    md += f"\n---\n*Pipo Battle Card System · Bitwise EMEA · {DASHBOARD_URL}*\n"

    card_path.write_text(md, encoding="utf-8")
    return card_path

# ── Telegram ──────────────────────────────────────────────────────────────────
def tg_send(text, parse_mode="HTML", disable_preview=True):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print(f"\n{Y}[TELEGRAM DRY]{X}\n{text[:500]}\n")
        return True
    try:
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT,
            "text": text[:4096],
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=payload, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        return resp.get("ok", False)
    except Exception as e:
        print(f"{R}Telegram Error: {e}{X}")
        return False

def format_telegram_card(rank, lead, bc):
    """Kompaktes Telegram-Format pro Lead."""
    ql_emoji = {"QUALIFIED": "🟢", "PROBABLE": "🔵", "POSSIBLE": "🟡", "UNQUALIFIED": "⚪"}.get(lead["ql"], "⚪")
    tier_star = "⭐" if lead.get("tier") == 1 else "🔹" if lead.get("tier") == 2 else "▫️"
    region = lead.get("region") or "?"
    contact = lead.get("contact_person") or "—"
    title_str = lead.get("title") or ""
    li_link = f'\n🔗 <a href="{lead["linkedin"]}">LinkedIn</a>' if lead.get("linkedin") else ""

    email = bc.get("email", {})
    subject = email.get("subject", "—")

    pain = bc.get("pain_points", [])
    pain_str = pain[0] if pain else "—"

    objections = bc.get("objections", [])
    obj_str = f"<i>\"{objections[0]['objection']}\"</i>" if objections else "—"

    strat = bc.get("strategy", {})

    msg = f"""{'━'*30}
<b>{rank}. {lead['company']}</b> {tier_star} {ql_emoji}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>{contact}</b>  <i>{title_str}</i>
📍 {region} · {lead.get('industry') or 'Institutional'}{li_link}
📊 MEDDPICC <b>{lead['meddpicc']}/80</b> · Score {lead['priority_score']} · {lead['days_inactive']}d inaktiv

⚡ <b>TRIGGER:</b>
{bc.get('trigger','—')}
"""

    # Mutual connections nur anzeigen wenn vorhanden
    mc = bc.get("mutual_connections", "")
    if mc and "kalt" not in mc.lower() and len(mc) > 5:
        msg += f"\n🤝 <b>INTRO:</b> {mc[:120]}\n"

    # Key contacts / decision makers
    kc = bc.get("key_contacts", "")
    if kc and len(kc) > 5:
        msg += f"\n👥 <b>ENTSCHEIDER:</b> {kc[:150]}\n"

    msg += f"""
🩹 <b>PAIN:</b> {pain_str}

🎯 <b>EDGE:</b>
{bc.get('our_edge','—')[:150]}

⚔️ <b>TOP EINWAND:</b>
{obj_str}

📋 <b>STRATEGIE:</b>
1. {strat.get('step1','—')[:80]}
2. {strat.get('step2','—')[:80]}

✉️ <b>EMAIL DRAFT:</b>
<code>{subject}</code>"""

    return msg

# ── Main ──────────────────────────────────────────────────────────────────────
def run(top_n=5, region=None, dry_run=False, company_filter=None):
    today_str = datetime.now().strftime("%A, %d. %b %Y")
    print(f"\n{BOLD}{'='*60}")
    print(f"  🤖 PIPO BATTLE CARD SYSTEM")
    print(f"  {today_str}")
    print(f"{'='*60}{X}\n")

    if not EXA_KEY:
        print(f"{R}❌ EXA_API_KEY nicht gesetzt — Research nicht möglich{X}")
    if not ANTHROPIC_KEY:
        print(f"{R}❌ ANTHROPIC_API_KEY nicht gesetzt — Battle Card nicht möglich{X}")

    leads = load_top_leads(region=region, top_n=top_n, company_filter=company_filter)
    if not leads:
        print(f"{R}Keine Leads gefunden.{X}")
        return

    all_cards = []
    card_paths = []

    # ── Header Message ─────────────────────────────────────────────────────────
    li_status = "✅ LinkedIn Navigator aktiv" if (LINKEDIN_EMAIL or LINKEDIN_LI_AT) else "⚠️ LinkedIn deaktiviert (li_at nicht gesetzt)"
    header = f"""🤖 <b>PIPO BATTLE CARDS — {today_str}</b>
<a href="{DASHBOARD_URL}">📊 Dashboard</a>

Deep Research für <b>{len(leads)} Leads</b>:
• Exa Web Research (6 Suchen/Lead)
• {li_status}
• Gemeinsame Verbindungen (Mutual Connections)
• Trigger Detection
• Battle Card mit Strategie + Multi-Channel

{'━'*30}"""

    if not dry_run:
        tg_send(header)
    else:
        print(f"\n{BOLD}HEADER:{X}\n{header}\n")

    # ── Per Lead ───────────────────────────────────────────────────────────────
    for i, lead in enumerate(leads, 1):
        company = lead["company"]
        print(f"  [{i}/{len(leads)}] {BOLD}{company}{X}")
        print(f"    → Research (Exa)...", end="", flush=True)
        t0 = time.time()

        research = deep_research(lead)

        total_results = sum(len(v) for v in research.values())
        t1 = time.time()
        print(f" {total_results} Ergebnisse ({t1-t0:.1f}s)")
        print(f"    → Battle Card (Claude)...", end="", flush=True)

        bc = generate_battlecard(lead, research)
        t2 = time.time()
        print(f" {G}✓{X} ({t2-t1:.1f}s)")

        # Save markdown
        card_path = save_battlecard(lead, bc, research)
        card_paths.append(card_path)
        print(f"    → Saved: {card_path}")

        all_cards.append((lead, bc))

        # Send Telegram card
        tg_msg = format_telegram_card(i, lead, bc)
        if not dry_run:
            tg_send(tg_msg)
        else:
            print(f"\n{BOLD}LEAD {i}:{X}\n{tg_msg}\n")

        # Rate limiting
        if i < len(leads):
            time.sleep(1)

    # ── Summary ────────────────────────────────────────────────────────────────
    footer = f"""{'━'*30}
✅ <b>{len(leads)} Battle Cards fertig</b>

Lokal gespeichert:
<code>{BATTLECARD_DIR}/{datetime.now().strftime('%Y-%m-%d')}/</code>

Nächste Schritte:
1. LinkedIn Connect senden (Texts oben)
2. Email senden wenn kein LinkedIn-Connect
3. In 5 Tagen: Follow-up Step 2

<a href="{DASHBOARD_URL}">📊 Dashboard</a> · Powered by Pipo 🤖"""

    if not dry_run:
        tg_send(footer)
    else:
        print(f"\n{BOLD}FOOTER:{X}\n{footer}")

    print(f"\n{G}{BOLD}{'='*60}")
    print(f"  ✅ {len(leads)} Battle Cards generiert")
    print(f"  📁 {BATTLECARD_DIR}/{datetime.now().strftime('%Y-%m-%d')}/")
    print(f"{'='*60}{X}\n")

def main():
    parser = argparse.ArgumentParser(description="Pipo Battle Card System")
    parser.add_argument("--top",     type=int, default=5,   help="Anzahl Leads (default: 5)")
    parser.add_argument("--region",  help="Nur eine Region (z.B. DE, CH, UAE)")
    parser.add_argument("--lead",    help="Nur ein spezifisches Unternehmen")
    parser.add_argument("--dry-run", action="store_true",    help="Kein Telegram — nur Terminal")
    args = parser.parse_args()

    run(
        top_n=args.top,
        region=args.region,
        dry_run=args.dry_run,
        company_filter=args.lead
    )

if __name__ == "__main__":
    main()
