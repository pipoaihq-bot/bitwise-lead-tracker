#!/usr/bin/env python3
"""
pipo_evaluate.py — Pipo Lead Pre-Evaluator
==========================================
Schätzt MEDDPICC-Scores für alle ungescoredeten Leads via Claude-Haiku.
Läuft auf Mac mini, schreibt Ergebnisse direkt nach Supabase.

Usage:
  python3 pipo_evaluate.py                   # Alle ungescoredeten Leads
  python3 pipo_evaluate.py --limit 100       # Nur erste 100
  python3 pipo_evaluate.py --region DE       # Nur eine Region
  python3 pipo_evaluate.py --force           # Auch bereits gescorete neu bewerten
  python3 pipo_evaluate.py --dry-run         # Nur anzeigen, nichts speichern
"""

import os, sys, json, time, argparse, urllib.request, urllib.error

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://cxrhqzggukuqxpsausrd.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BATCH_SIZE = 20        # Leads pro Claude-API-Call
SLEEP_BETWEEN = 0.5   # Sekunden zwischen Batches (Rate-Limit)

# ── Colors ──────────────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; X = "\033[0m"; BOLD = "\033[1m"

# ── Supabase REST helpers ────────────────────────────────────────────────────
def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def sb_upsert(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal"
        }
    )
    with urllib.request.urlopen(req) as r:
        return r.status

# ── Load all leads ───────────────────────────────────────────────────────────
def load_leads(region=None, force=False, limit=None):
    print(f"{B}Loading leads from Supabase...{X}")
    all_leads = []
    offset = 0
    page = 1000
    while True:
        params = f"select=id,company,contact_person,title,industry,region,tier,aum_estimate_millions,expected_deal_size_millions,use_case,stage&order=tier.asc,aum_estimate_millions.desc&offset={offset}&limit={page}"
        if region:
            params += f"&region=eq.{region}"
        chunk = sb_get("leads", params)
        if not chunk:
            break
        all_leads.extend(chunk)
        if len(chunk) < page:
            break
        offset += page

    # Load existing scores
    print(f"  → {len(all_leads)} leads total. Loading existing scores...")
    existing_scores = {}
    offset = 0
    while True:
        chunk = sb_get("meddpicc_scores", f"select=lead_id,total_score&offset={offset}&limit=1000")
        if not chunk:
            break
        for s in chunk:
            existing_scores[s["lead_id"]] = s["total_score"]
        if len(chunk) < 1000:
            break
        offset += 1000

    # Filter
    if not force:
        unscored = [l for l in all_leads if existing_scores.get(l["id"], 0) == 0]
        print(f"  → {len(existing_scores)} bereits gescored | {G}{len(unscored)} unbewertet{X}")
    else:
        unscored = all_leads
        print(f"  → {Y}--force: Alle {len(unscored)} Leads werden neu bewertet{X}")

    if limit:
        unscored = unscored[:limit]
        print(f"  → {Y}--limit: Maximal {limit} Leads{X}")

    return unscored

# ── Pipo MEDDPICC scoring prompt ─────────────────────────────────────────────
SYSTEM_PROMPT = """Du bist Pipo, Pre-Sales KI-Analyst für Bitwise Onchain Solutions (institutionelles ETH-Staking).
Deine Aufgabe: Schätze MEDDPICC-Scores für eine Liste institutioneller Leads.

BITWISE BOS PRODUKT:
- Institutionelles ETH-Staking (Non-Custodial, MiCA-konform)
- ~$5B gestaked | Zero Slashings seit Genesis | 99.984% Uptime
- APR 3.170% (+0.155% vs Benchmark)
- Zielkunden: Asset Manager, Banken, Family Offices, Pension Funds, Hedge Funds, Custodians in EMEA

SCORING-LOGIK für jedes MEDDPICC-Kriterium (0-10 Punkte):
- Metrics (0-10): Kann der Lead klaren ROI messen? (Staking APR, AUM, % gestaked)
- Economic Buyer (0-10): Ist Entscheider identifiziert oder erreichbar? (CEO/CTO/CFO=8-10, Head=5-7, Manager=2-4)
- Decision Process (0-10): Wie klar ist der Kaufprozess? (FS-reguliert=7+, Startup=3-5)
- Decision Criteria (0-10): Passt das Produkt zu den Kriterien? (MiCA-Region=+3, Crypto-affin=+3)
- Paper Process (0-10): Wie schnell kann ein Deal schließen? (Startup=8, Bank=3, Pension=2)
- Pain (0-10): Wie stark ist der Staking-Schmerz? (bereits crypto=7+, nur Aktien=3)
- Champion (0-10): Gibt es einen internen Fürsprecher? (Crypto-Titel=8, Trad-Finance=4)
- Competition (0-10): Wie gut stehen wir vs. Eigenentwicklung/Konkurrenz? (Kein Staking=9, Lido=6)

REGION-MULTIPLIKATOREN (beeinflussen Pain+Decision Process):
- DE, AT, CH: +2 (MiCA-konform, reguliertes Umfeld)
- UAE: +1 (crypto-freundlich)
- UK: 0 (eigenes Regime)
- NORDICS: +1 (progressive Fintech-Kultur)

WICHTIG: Antworte NUR als JSON-Array, exakt dieses Format:
[
  {"lead_id": 123, "metrics": 7, "economic_buyer": 6, "decision_process": 5, "decision_criteria": 8, "paper_process": 4, "pain": 7, "champion": 5, "competition": 6, "reasoning": "Asset Manager DE, CIO kontaktiert, MiCA-Vorteil klar"},
  ...
]
Keine weiteren Erklärungen außerhalb des JSON."""

def score_batch(batch):
    """Sendet einen Batch von Leads an Claude-Haiku und bekommt MEDDPICC-Scores zurück."""
    leads_text = []
    for l in batch:
        leads_text.append(
            f"lead_id={l['id']} | {l.get('company','?')} | "
            f"Kontakt: {l.get('contact_person') or 'unbekannt'} ({l.get('title') or 'Titel unbekannt'}) | "
            f"Industry: {l.get('industry') or 'Institutional'} | "
            f"Region: {l.get('region','?')} | Tier: {l.get('tier','?')} | "
            f"AUM: €{l.get('aum_estimate_millions',0) or 0:.0f}M | "
            f"Stage: {l.get('stage','prospecting')} | "
            f"Use-Case: {(l.get('use_case') or '')[:80]}"
        )

    user_msg = "Bewerte diese Leads:\n\n" + "\n".join(leads_text)
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        method="POST",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())

    text = resp["content"][0]["text"].strip()
    # Extract JSON even if there's surrounding text
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"Kein JSON-Array in Antwort: {text[:200]}")
    return json.loads(text[start:end])

# ── Save scores to Supabase ──────────────────────────────────────────────────
def save_scores(scores):
    rows = []
    for s in scores:
        total = (
            s.get("metrics", 0) + s.get("economic_buyer", 0) +
            s.get("decision_process", 0) + s.get("decision_criteria", 0) +
            s.get("paper_process", 0) + s.get("pain", 0) +
            s.get("champion", 0) + s.get("competition", 0)
        )
        if total >= 70:   ql = "QUALIFIED"
        elif total >= 50: ql = "PROBABLE"
        elif total >= 30: ql = "POSSIBLE"
        else:             ql = "UNQUALIFIED"

        rows.append({
            "lead_id": s["lead_id"],
            "metrics": s.get("metrics", 0),
            "economic_buyer": s.get("economic_buyer", 0),
            "decision_process": s.get("decision_process", 0),
            "decision_criteria": s.get("decision_criteria", 0),
            "paper_process": s.get("paper_process", 0),
            "pain": s.get("pain", 0),
            "champion": s.get("champion", 0),
            "competition": s.get("competition", 0),
            "total_score": total,
            "qualification_status": ql,
            "notes": s.get("reasoning", "Pipo AI-Evaluation")
        })
    sb_upsert("meddpicc_scores", rows)
    return rows

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Pipo Lead Evaluator")
    parser.add_argument("--region",  help="Nur eine Region (z.B. DE, CH, UAE)")
    parser.add_argument("--limit",   type=int, help="Max. Anzahl Leads")
    parser.add_argument("--force",   action="store_true", help="Auch bereits gescorete neu bewerten")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts speichern")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print(f"{R}❌ SUPABASE_KEY nicht gesetzt! Export SUPABASE_KEY=...{X}")
        sys.exit(1)
    if not ANTHROPIC_KEY:
        print(f"{R}❌ ANTHROPIC_API_KEY nicht gesetzt! Export ANTHROPIC_API_KEY=...{X}")
        sys.exit(1)

    print(f"\n{BOLD}{'='*60}")
    print(f"  🤖 PIPO LEAD EVALUATOR")
    print(f"{'='*60}{X}\n")

    leads = load_leads(region=args.region, force=args.force, limit=args.limit)

    if not leads:
        print(f"{G}✅ Alle Leads sind bereits gescored!{X}")
        return

    total = len(leads)
    batches = [leads[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    print(f"\n{BOLD}→ {total} Leads in {len(batches)} Batches à {BATCH_SIZE}{X}\n")

    if args.dry_run:
        print(f"{Y}DRY RUN — Keine Daten werden gespeichert{X}")
        for l in leads[:5]:
            print(f"  • {l['company']} ({l['region']}) — {l.get('title') or '—'}")
        if total > 5:
            print(f"  ... und {total-5} weitere")
        return

    saved_total = 0
    errors = 0
    ql_counts = {"QUALIFIED": 0, "PROBABLE": 0, "POSSIBLE": 0, "UNQUALIFIED": 0}

    for i, batch in enumerate(batches):
        pct = int((i / len(batches)) * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r  [{bar}] {pct}% | Batch {i+1}/{len(batches)} | ✅ {saved_total} gespeichert | ❌ {errors} Fehler", end="", flush=True)

        try:
            scored = score_batch(batch)
            saved = save_scores(scored)
            for row in saved:
                ql_counts[row["qualification_status"]] = ql_counts.get(row["qualification_status"], 0) + 1
            saved_total += len(saved)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            print(f"\n{R}  HTTP {e.code} in Batch {i+1}: {body}{X}")
            errors += len(batch)
        except Exception as e:
            print(f"\n{R}  Fehler in Batch {i+1}: {e}{X}")
            errors += len(batch)

        if i < len(batches) - 1:
            time.sleep(SLEEP_BETWEEN)

    print(f"\n\n{BOLD}{'='*60}")
    print(f"  🎯 ERGEBNIS")
    print(f"{'='*60}{X}")
    print(f"  ✅ Gespeichert: {G}{saved_total}{X} Leads")
    print(f"  ❌ Fehler:      {R}{errors}{X} Leads")
    print(f"\n  Verteilung:")
    print(f"  {G}  QUALIFIED:   {ql_counts.get('QUALIFIED', 0)}{X}")
    print(f"  {B}  PROBABLE:    {ql_counts.get('PROBABLE', 0)}{X}")
    print(f"  {Y}  POSSIBLE:    {ql_counts.get('POSSIBLE', 0)}{X}")
    print(f"     UNQUALIFIED: {ql_counts.get('UNQUALIFIED', 0)}")
    print(f"\n  Dashboard: https://pipo-bitwise-lead-tracker.streamlit.app")
    print(f"{BOLD}{'='*60}{X}\n")

if __name__ == "__main__":
    main()
