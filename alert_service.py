"""
EMEA Sales Alert System
Telegram Alert Service für Bitwise Lead Tracker
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

# Configuration
DB_PATH = os.environ.get("DB_PATH", "/Users/philippsandor/.openclaw/workspace/bitwise/leadtracker/bitwise_leads.db")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "671208506")

@dataclass
class PriorityLead:
    company: str
    meddpicc_score: int
    qualification: str
    region: str
    stage: str
    days_since_activity: int
    next_action: str
    contact_person: str
    last_activity_type: str

@dataclass
class ChurnRiskLead:
    company: str
    meddpicc_score: int
    days_since_activity: int
    region: str
    contact_person: str
    last_activity_type: str

class AlertService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ============================================
    # SQL QUERIES für Alert-Logik
    # ============================================
    
    def get_high_priority_leads(self, min_meddpicc: int = 60, stale_days: int = 3) -> List[PriorityLead]:
        """
        Top Prioritäten: MEDDPICC >= 60 UND keine Activity seit X Tagen
        
        SQL Logik:
        1. Join leads + meddpicc_scores
        2. LEFT JOIN mit letzter Activity pro Lead
        3. Filter: MEDDPICC >= 60, Stage nicht closed
        4. Sortiert nach MEDDPICC (höchste zuerst), dann Aktivität (älteste zuerst)
        """
        query = """
        SELECT 
            l.id,
            l.company,
            l.region,
            l.stage,
            l.contact_person,
            COALESCE(m.total_score, 0) as meddpicc_total,
            COALESCE(m.qualification_status, 'UNQUALIFIED') as qualification,
            COALESCE(
                (SELECT MAX(created_at) FROM activities WHERE lead_id = l.id),
                l.updated_at,
                l.created_at
            ) as last_activity_date,
            COALESCE(
                (SELECT activity_type FROM activities 
                 WHERE lead_id = l.id 
                 ORDER BY created_at DESC LIMIT 1),
                'No Activity'
            ) as last_activity_type
        FROM leads l
        LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
        WHERE COALESCE(m.total_score, 0) >= ?
          AND l.stage NOT IN ('closed_won', 'closed_lost')
        ORDER BY meddpicc_total DESC, last_activity_date ASC
        LIMIT 10
        """
        
        cutoff_date = datetime.now() - timedelta(days=stale_days)
        
        with self.get_connection() as conn:
            rows = conn.execute(query, (min_meddpicc,)).fetchall()
        
        results = []
        for row in rows:
            last_activity = self._parse_datetime(row['last_activity_date'])
            days_since = (datetime.now() - last_activity).days if last_activity else 999
            
            # Nur wenn stale (keine Activity seit X Tagen)
            if days_since >= stale_days:
                results.append(PriorityLead(
                    company=row['company'],
                    meddpicc_score=row['meddpicc_total'],
                    qualification=row['qualification'],
                    region=row['region'],
                    stage=row['stage'],
                    days_since_activity=days_since,
                    next_action=self._determine_next_action(row['stage']),
                    contact_person=row['contact_person'] or 'N/A',
                    last_activity_type=row['last_activity_type']
                ))
        
        return results[:3]  # Top 3
    
    def get_churn_risk_leads(self, min_meddpicc: int = 50, max_inactive_days: int = 7) -> List[ChurnRiskLead]:
        """
        Churn Risk Alert: MEDDPICC > 50 aber keine Activity seit 7 Tagen
        """
        query = """
        SELECT 
            l.id,
            l.company,
            l.region,
            l.contact_person,
            COALESCE(m.total_score, 0) as meddpicc_total,
            COALESCE(
                (SELECT MAX(created_at) FROM activities WHERE lead_id = l.id),
                l.updated_at,
                l.created_at
            ) as last_activity_date,
            COALESCE(
                (SELECT activity_type FROM activities 
                 WHERE lead_id = l.id 
                 ORDER BY created_at DESC LIMIT 1),
                'No Activity'
            ) as last_activity_type
        FROM leads l
        LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
        WHERE COALESCE(m.total_score, 0) >= ?
          AND l.stage NOT IN ('closed_won', 'closed_lost')
        ORDER BY last_activity_date ASC
        """
        
        with self.get_connection() as conn:
            rows = conn.execute(query, (min_meddpicc,)).fetchall()
        
        results = []
        for row in rows:
            last_activity = self._parse_datetime(row['last_activity_date'])
            days_since = (datetime.now() - last_activity).days if last_activity else 999
            
            if days_since >= max_inactive_days:
                results.append(ChurnRiskLead(
                    company=row['company'],
                    meddpicc_score=row['meddpicc_total'],
                    days_since_activity=days_since,
                    region=row['region'],
                    contact_person=row['contact_person'] or 'N/A',
                    last_activity_type=row['last_activity_type']
                ))
        
        return results
    
    def get_next_activity(self) -> Optional[Dict]:
        """
        Empfiehlt nächste Aktivität basierend auf:
        1. Höchster MEDDPICC Score mit längster Inaktivität
        2. Oder Leads ohne jede Activity
        """
        query = """
        SELECT 
            l.id,
            l.company,
            l.region,
            l.stage,
            l.contact_person,
            l.linkedin,
            COALESCE(m.total_score, 0) as meddpicc_total,
            COALESCE(
                (SELECT MAX(created_at) FROM activities WHERE lead_id = l.id),
                l.created_at
            ) as last_activity_date,
            COALESCE(
                (SELECT activity_type FROM activities 
                 WHERE lead_id = l.id 
                 ORDER BY created_at DESC LIMIT 1),
                'No Activity'
            ) as last_activity_type,
            (SELECT COUNT(*) FROM activities WHERE lead_id = l.id) as activity_count
        FROM leads l
        LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
        WHERE l.stage NOT IN ('closed_won', 'closed_lost')
        ORDER BY 
            COALESCE(m.total_score, 0) DESC,
            last_activity_date ASC
        LIMIT 1
        """
        
        with self.get_connection() as conn:
            row = conn.execute(query).fetchone()
        
        if row:
            last_activity = self._parse_datetime(row['last_activity_date'])
            days_since = (datetime.now() - last_activity).days if last_activity else 999
            
            return {
                'lead_id': row['id'],
                'company': row['company'],
                'region': row['region'],
                'stage': row['stage'],
                'contact': row['contact_person'],
                'linkedin': row['linkedin'],
                'meddpicc': row['meddpicc_total'],
                'last_activity': row['last_activity_type'],
                'days_inactive': days_since,
                'activity_count': row['activity_count'],
                'next_action': self._determine_next_action(row['stage'])
            }
        return None
    
    def get_top_opportunities(self, limit: int = 5) -> List[Dict]:
        """
        Top 5 Opportunities nach MEDDPICC Score
        """
        query = """
        SELECT 
            l.company,
            l.region,
            l.stage,
            l.contact_person,
            l.expected_deal_size_millions,
            COALESCE(m.total_score, 0) as meddpicc_total,
            COALESCE(m.qualification_status, 'UNQUALIFIED') as qualification,
            COALESCE(
                (SELECT MAX(created_at) FROM activities WHERE lead_id = l.id),
                l.updated_at
            ) as last_activity_date
        FROM leads l
        LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
        WHERE l.stage NOT IN ('closed_won', 'closed_lost')
        ORDER BY meddpicc_total DESC
        LIMIT ?
        """
        
        with self.get_connection() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
        
        return [
            {
                'company': row['company'],
                'region': row['region'],
                'stage': row['stage'],
                'contact': row['contact_person'],
                'deal_size': row['expected_deal_size_millions'],
                'meddpicc': row['meddpicc_total'],
                'qualification': row['qualification'],
                'last_activity': self._parse_datetime(row['last_activity_date'])
            }
            for row in rows
        ]
    
    def get_stale_deals(self, days: int = 7) -> List[Dict]:
        """
        Deals die schlummern - keine Activity seit X Tagen
        """
        query = """
        SELECT 
            l.company,
            l.region,
            l.stage,
            l.contact_person,
            COALESCE(m.total_score, 0) as meddpicc_total,
            COALESCE(m.qualification_status, 'UNQUALIFIED') as qualification,
            COALESCE(
                (SELECT MAX(created_at) FROM activities WHERE lead_id = l.id),
                l.updated_at,
                l.created_at
            ) as last_activity_date,
            COALESCE(
                (SELECT activity_type FROM activities 
                 WHERE lead_id = l.id 
                 ORDER BY created_at DESC LIMIT 1),
                'No Activity'
            ) as last_activity_type
        FROM leads l
        LEFT JOIN meddpicc_scores m ON l.id = m.lead_id
        WHERE l.stage NOT IN ('closed_won', 'closed_lost')
        ORDER BY last_activity_date ASC
        LIMIT 50
        """
        
        with self.get_connection() as conn:
            rows = conn.execute(query).fetchall()
        
        results = []
        for row in rows:
            last_activity = self._parse_datetime(row['last_activity_date'])
            days_since = (datetime.now() - last_activity).days if last_activity else 999
            
            if days_since >= days:
                results.append({
                    'company': row['company'],
                    'region': row['region'],
                    'stage': row['stage'],
                    'contact': row['contact_person'],
                    'meddpicc': row['meddpicc_total'],
                    'qualification': row['qualification'],
                    'days_inactive': days_since,
                    'last_activity': row['last_activity_type']
                })
        
        return results[:10]
    
    # ============================================
    # Helper Methods
    # ============================================
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        """Parst verschiedene Datetime-Formate aus SQLite"""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            # ISO format mit oder ohne timezone
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except:
            try:
                # SQLite default format
                return datetime.strptime(str(value), '%Y-%m-%d %H:%M:%S')
            except:
                return None
    
    def _determine_next_action(self, stage: str) -> str:
        """Empfiehlt nächsten Schritt basierend auf Stage"""
        actions = {
            'prospecting': "📧 Cold Outreach (Email/LinkedIn)",
            'discovery': "📞 Discovery Call buchen",
            'solutioning': "📋 Solution Presentation",
            'validation': "✅ POC/Validation abschließen",
            'negotiation': "🤝 Vertragsverhandlung",
            'closed_won': "🎉 Onboarding starten",
            'closed_lost': "📊 Learnings dokumentieren"
        }
        return actions.get(stage, "📞 Follow-up")
    
    # ============================================
    # Telegram Message Formatting
    # ============================================
    
    def format_morning_alert(self) -> str:
        """Formatiert die 9:00 Uhr Morgen-Alert Nachricht"""
        priorities = self.get_high_priority_leads()
        churn_risks = self.get_churn_risk_leads()
        stats = self._get_stats()
        
        message = f"🎯 *EMEA Sales Alert - {datetime.now().strftime('%d.%m.%Y')}*\n\n"
        
        # Top 3 Prioritäten
        if priorities:
            message += "*🔥 Top 3 Prioritäten heute:*\n\n"
            for i, lead in enumerate(priorities, 1):
                status_emoji = "🟢" if lead.qualification == "QUALIFIED" else "🟡"
                message += (
                    f"{i}. *{lead.company}* ({lead.region})\n"
                    f"   {status_emoji} MEDDPICC: {lead.meddpicc_score}/80 | {lead.qualification}\n"
                    f"   👤 {lead.contact_person}\n"
                    f"   ⏰ Letzte Activity: {lead.days_since_activity} Tage ({lead.last_activity_type})\n"
                    f"   🎯 *{lead.next_action}*\n\n"
                )
        else:
            message += "✅ Keine dringenden Prioritäten für heute.\n\n"
        
        # Churn Risk Alert
        if churn_risks:
            message += "🚨 *Churn Risk Alert:*\n"
            message += f"_{len(churn_risks)} qualifizierte Deals schlummern:_\n\n"
            for lead in churn_risks[:3]:
                message += (
                    f"• *{lead.company}* ({lead.region})\n"
                    f"  MEDDPICC: {lead.meddpicc_score}/80 | "
                    f"Inaktiv: {lead.days_since_activity} Tage\n"
                )
            message += "\n"
        
        # Zusammenfassung
        message += (
            f"📊 *Übersicht:*\n"
            f"   {stats['total']} Leads | {stats['qualified']} Qualifiziert | "
            f"{stats['probable']} Probable\n"
            f"   Pipeline: €{stats['pipeline_value']:.0f}M"
        )
        
        return message
    
    def format_next_activity(self) -> str:
        """Formatiert /next Command Response"""
        activity = self.get_next_activity()
        
        if not activity:
            return "✅ Alle Leads sind aktiv! Zeit für neues Prospecting. 🎯"
        
        status_emoji = "🟢" if activity['meddpicc'] >= 70 else "🟡" if activity['meddpicc'] >= 50 else "⚪"
        
        message = f"🎯 *Nächste Priorität*\n\n"
        message += f"*{activity['company']}* ({activity['region']})\n"
        message += f"{status_emoji} MEDDPICC: {activity['meddpicc']}/80 | Stage: {activity['stage']}\n"
        message += f"👤 {activity['contact']}\n\n"
        
        if activity['linkedin']:
            message += f"🔗 LinkedIn: {activity['linkedin']}\n\n"
        
        message += f"⏰ Letzte Activity: {activity['last_activity']} ({activity['days_inactive']} Tage her)\n"
        message += f"📊 Gesamt Activities: {activity['activity_count']}\n\n"
        message += f"🎯 *Empfohlene Action:*\n_{activity['next_action']}_"
        
        return message
    
    def format_hot_opportunities(self) -> str:
        """Formatiert /hot Command Response"""
        opportunities = self.get_top_opportunities(5)
        
        if not opportunities:
            return "📊 Keine Opportunities gefunden."
        
        message = "🔥 *Top 5 Hot Opportunities*\n\n"
        
        for i, opp in enumerate(opportunities, 1):
            status_emoji = "🟢" if opp['meddpicc'] >= 70 else "🟡" if opp['meddpicc'] >= 50 else "⚪"
            deal_size = f"€{opp['deal_size']:.0f}M" if opp['deal_size'] else "TBD"
            
            days_since = (datetime.now() - opp['last_activity']).days if opp['last_activity'] else 999
            urgency = "🔥" if days_since > 7 else ""
            
            message += (
                f"{i}. *{opp['company']}* ({opp['region']}) {urgency}\n"
                f"   {status_emoji} MEDDPICC: {opp['meddpicc']}/80 ({opp['qualification']})\n"
                f"   💰 Deal: {deal_size} | Stage: {opp['stage']}\n"
                f"   👤 {opp['contact'] or 'N/A'}\n"
                f"   ⏰ Letzte Activity: {days_since} Tage\n\n"
            )
        
        return message
    
    def format_stale_deals(self) -> str:
        """Formatiert /stale Command Response"""
        stale = self.get_stale_deals(7)
        
        if not stale:
            return "✅ Alle Deals sind aktiv! Keine schlummernden Opportunities."
        
        message = f"😴 *Schlummernde Deals* (>7 Tage inaktiv)\n\n"
        message += f"_{len(stale)} Deals benötigen Attention:_\n\n"
        
        for deal in stale:
            status_emoji = "🚨" if deal['meddpicc'] >= 50 else "⚪"
            message += (
                f"{status_emoji} *{deal['company']}* ({deal['region']})\n"
                f"   MEDDPICC: {deal['meddpicc']}/80 ({deal['qualification']})\n"
                f"   Inaktiv: {deal['days_inactive']} Tage | Last: {deal['last_activity']}\n"
                f"   👤 {deal['contact'] or 'N/A'} | Stage: {deal['stage']}\n\n"
            )
        
        return message
    
    # ============================================
    # Stats Helpers
    # ============================================
    
    def _get_stats(self) -> Dict:
        """Gesamtstatistiken für Dashboard"""
        with self.get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) as count FROM leads").fetchone()['count']
            
            qualified = conn.execute("""
                SELECT COUNT(*) as count FROM leads l
                JOIN meddpicc_scores m ON l.id = m.lead_id
                WHERE m.qualification_status = 'QUALIFIED'
                AND l.stage NOT IN ('closed_won', 'closed_lost')
            """).fetchone()['count']
            
            probable = conn.execute("""
                SELECT COUNT(*) as count FROM leads l
                JOIN meddpicc_scores m ON l.id = m.lead_id
                WHERE m.qualification_status = 'PROBABLE'
                AND l.stage NOT IN ('closed_won', 'closed_lost')
            """).fetchone()['count']
            
            pipeline = conn.execute("""
                SELECT COALESCE(SUM(expected_deal_size_millions), 0) as total 
                FROM leads 
                WHERE stage NOT IN ('closed_won', 'closed_lost')
            """).fetchone()['total']
        
        return {
            'total': total,
            'qualified': qualified,
            'probable': probable,
            'pipeline_value': pipeline
        }


# ============================================
# Telegram Integration via OpenClaw
# ============================================

def send_telegram_message(message: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """
    Sendet Nachricht über OpenClaw Gateway
    """
    try:
        import subprocess
        result = subprocess.run(
            ['openclaw', 'message', 'send', '--target', chat_id, '--message', message],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print(f"✅ Message sent successfully")
            return True
        else:
            print(f"❌ OpenClaw error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Failed to send: {e}")
        return False


# ============================================
# Main Entry Points für Cron/Commands
# ============================================

def run_morning_alert():
    """9:00 CET Daily Alert"""
    service = AlertService()
    message = service.format_morning_alert()
    success = send_telegram_message(message)
    print(f"Morning alert: {'✅ Sent' if success else '❌ Failed'}")
    return success

def cmd_next():
    """/next Command Handler"""
    service = AlertService()
    message = service.format_next_activity()
    success = send_telegram_message(message)
    return message, success

def cmd_hot():
    """/hot Command Handler"""
    service = AlertService()
    message = service.format_hot_opportunities()
    success = send_telegram_message(message)
    return message, success

def cmd_stale():
    """/stale Command Handler"""
    service = AlertService()
    message = service.format_stale_deals()
    success = send_telegram_message(message)
    return message, success


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "morning":
            run_morning_alert()
        elif command == "next":
            cmd_next()
        elif command == "hot":
            cmd_hot()
        elif command == "stale":
            cmd_stale()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python alert_service.py [morning|next|hot|stale]")
    else:
        # Test mode - zeige alle Formatierungen
        print("=" * 60)
        print("TEST MODE - Showing all message formats")
        print("=" * 60)
        
        service = AlertService()
        
        print("\n" + "=" * 60)
        print("MORNING ALERT")
        print("=" * 60)
        print(service.format_morning_alert())
        
        print("\n" + "=" * 60)
        print("NEXT ACTIVITY")
        print("=" * 60)
        print(service.format_next_activity())
        
        print("\n" + "=" * 60)
        print("HOT OPPORTUNITIES")
        print("=" * 60)
        print(service.format_hot_opportunities())
        
        print("\n" + "=" * 60)
        print("STALE DEALS")
        print("=" * 60)
        print(service.format_stale_deals())
