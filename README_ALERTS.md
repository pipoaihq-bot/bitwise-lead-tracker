# EMEA Sales Alert System - Setup Guide

## Übersicht

Das Alert System überwacht deine Sales Pipeline und sendet automatisch Telegram-Nachrichten bei:
- Prioritären Leads (MEDDPICC ≥60, lange inaktiv)
- Churn-Risks (MEDDPICC ≥50, >7 Tage keine Activity)
- Manuellen Commands (/next, /hot, /stale)

## Architektur

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  SQLite DB      │────▶│  Alert Service   │────▶│  Telegram       │
│  (Lead Tracker) │     │  (Python)        │     │  (OpenClaw)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Cron Jobs       │
                       │  (Scheduled)     │
                       └──────────────────┘
```

## Dateien

| Datei | Zweck |
|-------|-------|
| `alert_service.py` | Haupt-Service mit SQL Queries & Formatting |
| `bot_handler.py` | Telegram Command Handler |
| `README_ALERTS.md` | Diese Datei |

## 1. Installation

### Voraussetzungen
- Python 3.9+
- SQLite (bereits vorhanden)
- OpenClaw Gateway läuft

### Environment Variables (optional)

```bash
export DB_PATH="/Users/philippsandor/.openclaw/workspace/bitwise/leadtracker/bitwise_leads.db"
export TELEGRAM_CHAT_ID="671208506"
```

## 2. Cron-Job Setup

### Option A: OpenClaw Scheduler (empfohlen)

Füge zu deinem OpenClaw `HEARTBEAT.md` hinzu:

```markdown
## Sales Alert Schedule

### Morning Alert (9:00 CET)
```cron
0 9 * * * cd /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker && /usr/bin/python3 alert_service.py morning
```

### Periodic Check (alle 4 Stunden)
```cron
0 */4 * * * cd /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker && /usr/bin/python3 alert_service.py stale
```
```

### Option B: System crontab

```bash
# Öffne crontab
EDITOR=nano crontab -e

# Füge hinzu:
# 9:00 Uhr Morgen-Alert
0 9 * * * cd /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker && /usr/bin/python3 alert_service.py morning >> /tmp/sales_alerts.log 2>&1

# Alle 4 Stunden Check
0 */4 * * * cd /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker && /usr/bin/python3 alert_service.py stale >> /tmp/sales_alerts.log 2>&1
```

## 3. Telegram Bot Commands

### Manuelles Testen

```bash
# Morgen-Alert testen
cd /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker
python3 alert_service.py morning

# Commands testen
python3 alert_service.py next
python3 alert_service.py hot
python3 alert_service.py stale
```

### OpenClaw Integration

Erstelle einen neuen Agent in OpenClaw für Telegram Commands:

**prompt:**
```
Wenn der User einen der folgenden Commands sendet:
- /next
- /hot  
- /stale
- /help

Führe aus:
python3 /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker/bot_handler.py [command]

Und sende die Ausgabe zurück an den User.
```

### Oder: Direkte Integration in bestehenden Agent

Füge zu deinem main Agent die Command-Handler Logik hinzu.

## 4. SQL Queries Referenz

### Top Prioritäten (MEDDPICC ≥60, inaktiv)

```sql
SELECT 
    l.id, l.company, l.region, l.stage, l.contact_person,
    COALESCE(m.total_score, 0) as meddpicc_total,
    COALESCE(m.qualification_status, 'UNQUALIFIED') as qualification,
    COALESCE(
        (SELECT MAX(created_at) FROM activities WHERE lead_id = l.id),
        l.updated_at,
        l.created_at
    ) as last_activity_date
FROM leads l
LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
WHERE COALESCE(m.total_score, 0) >= 60
  AND l.stage NOT IN ('closed_won', 'closed_lost')
ORDER BY meddpicc_total DESC, last_activity_date ASC
```

### Churn Risk (MEDDPICC ≥50, >7 Tage inaktiv)

```sql
SELECT 
    l.company, l.region, l.contact_person,
    COALESCE(m.total_score, 0) as meddpicc_total,
    COALESCE(
        (SELECT MAX(created_at) FROM activities WHERE lead_id = l.id),
        l.updated_at,
        l.created_at
    ) as last_activity_date
FROM leads l
LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
WHERE COALESCE(m.total_score, 0) >= 50
  AND l.stage NOT IN ('closed_won', 'closed_lost')
  AND COALESCE(
        (SELECT MAX(created_at) FROM activities WHERE lead_id = l.id),
        l.updated_at
      ) < date('now', '-7 days')
ORDER BY last_activity_date ASC
```

### Top Opportunities

```sql
SELECT 
    l.company, l.region, l.stage, l.contact_person,
    l.expected_deal_size_millions,
    COALESCE(m.total_score, 0) as meddpicc_total,
    COALESCE(m.qualification_status, 'UNQUALIFIED') as qualification
FROM leads l
LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
WHERE l.stage NOT IN ('closed_won', 'closed_lost')
ORDER BY meddpicc_total DESC
LIMIT 5
```

## 5. Anpassung der Alert-Logik

Editiere `alert_service.py` und passe die Parameter an:

```python
# In get_high_priority_leads()
min_meddpicc = 60  # Mindest-Score für Alerts
stale_days = 3     # Tage ohne Activity für "stale"

# In get_churn_risk_leads()
max_inactive_days = 7  # Churn-Risk nach X Tagen
```

## 6. Monitoring & Logs

### Logs überprüfen

```bash
# Cron Logs (macOS)
tail -f /var/mail/$(whoami)

# Custom Logs
tail -f /tmp/sales_alerts.log
```

### Manuelles Debuggen

```bash
cd /Users/philippsandor/.openclaw/workspace/bitwise/leadtracker
python3 -c "
from alert_service import AlertService
svc = AlertService()
priorities = svc.get_high_priority_leads()
print(f'Found {len(priorities)} high priority leads')
for p in priorities:
    print(f'  - {p.company}: {p.meddpicc_score}/80')
"
```

## 7. Telegram Nachrichten Format

### Morning Alert
```
🎯 EMEA Sales Alert - 25.02.2026

🔥 Top 3 Prioritäten heute:

1. Company X (DE)
   🟢 MEDDPICC: 75/80 | QUALIFIED
   👤 Contact Person
   ⏰ Letzte Activity: 5 Tage (email)
   🎯 📞 Discovery Call buchen

🚨 Churn Risk Alert:
• Company Y (UAE)
  MEDDPICC: 65/80 | Inaktiv: 12 Tage

📊 Übersicht:
   2224 Leads | 45 Qualifiziert | 120 Probable
   Pipeline: €2.4B
```

### /next Command
```
🎯 Nächste Priorität

Company X (DE)
🟢 MEDDPICC: 75/80 | Stage: discovery
👤 Contact Person

🔗 LinkedIn: https://linkedin.com/in/...

⏰ Letzte Activity: email (5 Tage her)
📊 Gesamt Activities: 3

🎯 Empfohlene Action:
📞 Discovery Call buchen
```

## 8. Troubleshooting

### Problem: Keine Alerts
- Prüfe DB_PATH: `ls -la $DB_PATH`
- Teste Query manuell: `sqlite3 bitwise_leads.db "SELECT COUNT(*) FROM leads"`
- Prüfe OpenClaw Gateway Status

### Problem: Falsche Zeitzone
Cron verwendet System-Zeit. Für CET:
```bash
# Zeitzone setzen in crontab
CRON_TZ=Europe/Berlin
0 9 * * * ...
```

### Problem: Telegram sendet nicht
- OpenClaw Gateway läuft? `openclaw gateway status`
- Chat ID korrekt? `echo $TELEGRAM_CHAT_ID`
- Manuelles Test: `openclaw message send --target 671208506 --message "Test"`

## 9. Nächste Schritte / Erweiterungen

- [ ] Integration mit Kalender für Follow-up Reminders
- [ ] Weekly Pipeline Report (Sonntags)
- [ ] Deal Velocity Tracking (Zeit pro Stage)
- [ ] Automatische LinkedIn Profile Updates
- [ ] Integration mit E-Mail für Outreach-Tracking

---

**Deploy Status:** Ready for Production
**Last Updated:** 2026-02-25
