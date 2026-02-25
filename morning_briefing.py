#!/usr/bin/env python3
"""
Smart Morning Briefing Service für Bitwise EMEA Sales
Generiert jeden Morgen eine kuratierte Top 5 Liste basierend auf:
- MEDDPICC Score
- Deal Size
- Activity Recency
- Region/Strategic Priority
- Stage Progression
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json

# Configuration
DB_PATH = os.environ.get("DB_PATH", "/Users/philippsandor/.openclaw/workspace/bitwise/leadtracker/bitwise_leads.db")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "671208506")
STATE_FILE = "/tmp/morning_briefing_state.json"

@dataclass
class ScoredLead:
    """Lead mit berechnetem Prioritäts-Score"""
    lead_id: int
    company: str
    region: str
    stage: str
    contact_person: str
    title: str
    linkedin: Optional[str]
    meddpicc_score: int
    qualification: str
    deal_size: float
    days_inactive: int
    last_activity_type: str
    priority_score: float  # Berechneter Score 0-100
    reason: str  # Warum dieser Lead in Top 5
    suggested_action: str

class SmartMorningBriefing:
    """
    Intelligentes Morning Briefing System
    
    Priorisierungs-Algorithmus:
    - MEDDPICC (40%): Höherer Score = höhere Priorität
    - Deal Size (25%): Größere Deals = höhere Priorität
    - Activity Recency (20%): Länger inaktiv = höhere Priorität (aber mit Decay)
    - Stage Urgency (10%): Spätere Stages = höhere Priorität
    - Strategic Value (5%): Regionale/Strategische Priorität
    """
    
    # Stage Gewichtung (spätere Stages = höher)
    STAGE_WEIGHTS = {
        'negotiation': 1.0,
        'validation': 0.9,
        'solutioning': 0.8,
        'discovery': 0.6,
        'prospecting': 0.4,
        'closed_won': 0.0,
        'closed_lost': 0.0
    }
    
    # Regionale Prioritäten (kann angepasst werden)
    REGION_PRIORITY = {
        'UAE': 1.1,    # High priority market
        'DE': 1.0,     # Core market
        'CH': 1.0,     # Core market
        'UK': 0.95,    # Secondary
        'NORDICS': 0.9 # Secondary
    }
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def calculate_priority_score(
        self, 
        meddpicc: int, 
        deal_size: float, 
        days_inactive: int,
        stage: str,
        region: str
    ) -> Tuple[float, str]:
        """
        Berechnet Prioritäts-Score (0-100) und gibt Grund an
        
        Returns: (score, reason)
        """
        # 1. MEDDPICC Score (40% weight, max 40 points)
        meddpicc_component = (meddpicc / 80) * 40
        
        # 2. Deal Size (25% weight, max 25 points)
        # Normalisiert: €50M = max points, logarithmic scale
        if deal_size >= 50:
            deal_component = 25
        elif deal_size >= 20:
            deal_component = 20
        elif deal_size >= 10:
            deal_component = 15
        elif deal_size >= 5:
            deal_component = 10
        else:
            deal_component = min(5, deal_size) if deal_size else 0
        
        # 3. Activity Recency (20% weight)
        # Urgency peaks at 7-14 days, then decays
        if days_inactive <= 2:
            activity_component = 5  # Recently active, low urgency
        elif days_inactive <= 5:
            activity_component = 15  # Getting stale
        elif days_inactive <= 10:
            activity_component = 20  # Peak urgency
        elif days_inactive <= 21:
            activity_component = 15  # Still urgent but decaying
        else:
            activity_component = 10  # Very stale, might be dead
        
        # 4. Stage Urgency (10% weight)
        stage_weight = self.STAGE_WEIGHTS.get(stage.lower(), 0.5)
        stage_component = stage_weight * 10
        
        # 5. Strategic Value (5% weight)
        region_multiplier = self.REGION_PRIORITY.get(region.upper(), 0.9)
        strategic_component = 5 * region_multiplier
        
        # Total Score
        total_score = (
            meddpicc_component + 
            deal_component + 
            activity_component + 
            stage_component + 
            strategic_component
        )
        
        # Determine primary reason
        components = [
            ("MEDDPICC", meddpicc_component),
            ("Deal Size", deal_component),
            ("Inaktivität", activity_component),
            ("Stage", stage_component)
        ]
        primary_reason = max(components, key=lambda x: x[1])[0]
        
        return round(total_score, 1), primary_reason
    
    def get_suggested_action(self, stage: str, days_inactive: int, meddpicc: int) -> str:
        """Schlägt nächste Action basierend auf Kontext vor"""
        
        # Wenn lange inaktiv und guter Score = dringend reaktivieren
        if days_inactive > 10 and meddpicc >= 60:
            return "🔥 Dringend reaktivieren - Qualifizierter Deal kühlt aus"
        
        # Stage-basierte Actions
        actions = {
            'prospecting': [
                "📧 Cold Email senden",
                "💬 LinkedIn Connection Request",
                "📞 Erster Anruf planen"
            ],
            'discovery': [
                "📞 Discovery Call buchen",
                "📋 Needs Assessment durchführen",
                "👥 Stakeholder Mapping"
            ],
            'solutioning': [
                "📊 Solution Presentation vorbereiten",
                "🎯 Technical Demo anbieten",
                "📄 Proposal Draft erstellen"
            ],
            'validation': [
                "✅ POC Timeline definieren",
                "🔍 Due Diligence Support",
                "📞 Champion Check-in"
            ],
            'negotiation': [
                "🤝 Vertragsgespräch führen",
                "💰 Pricing Finalisierung",
                "✍️ Terms & Conditions klären"
            ]
        }
        
        stage_actions = actions.get(stage.lower(), ["📞 Follow-up"])
        
        # Rotate suggested actions based on day of week for variety
        day_index = datetime.now().weekday()
        return stage_actions[day_index % len(stage_actions)]
    
    def get_top_5_leads(self) -> List[ScoredLead]:
        """
        Holt und scored alle relevanten Leads, gibt Top 5 zurück
        """
        query = """
        SELECT 
            l.id,
            l.company,
            l.region,
            l.stage,
            l.contact_person,
            l.title,
            l.linkedin,
            l.expected_deal_size_millions,
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
        ORDER BY l.id DESC
        """
        
        with self.get_connection() as conn:
            rows = conn.execute(query).fetchall()
        
        scored_leads = []
        
        for row in rows:
            # Parse last activity
            last_activity = self._parse_datetime(row['last_activity_date'])
            days_inactive = (datetime.now() - last_activity).days if last_activity else 999
            
            # Skip if very stale (probably dead deal) unless high MEDDPICC
            if days_inactive > 30 and row['meddpicc_total'] < 50:
                continue
            
            # Calculate priority score
            priority_score, reason = self.calculate_priority_score(
                meddpicc=row['meddpicc_total'],
                deal_size=row['expected_deal_size_millions'] or 0,
                days_inactive=days_inactive,
                stage=row['stage'],
                region=row['region']
            )
            
            # Get suggested action
            suggested_action = self.get_suggested_action(
                stage=row['stage'],
                days_inactive=days_inactive,
                meddpicc=row['meddpicc_total']
            )
            
            scored_leads.append(ScoredLead(
                lead_id=row['id'],
                company=row['company'],
                region=row['region'],
                stage=row['stage'],
                contact_person=row['contact_person'] or 'N/A',
                title=row['title'] or 'N/A',
                linkedin=row['linkedin'],
                meddpicc_score=row['meddpicc_total'],
                qualification=row['qualification'],
                deal_size=row['expected_deal_size_millions'] or 0,
                days_inactive=days_inactive,
                last_activity_type=row['last_activity_type'],
                priority_score=priority_score,
                reason=reason,
                suggested_action=suggested_action
            ))
        
        # Sort by priority score and return top 5
        scored_leads.sort(key=lambda x: x.priority_score, reverse=True)
        return scored_leads[:5]
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        """Parst verschiedene Datetime-Formate"""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except:
            try:
                return datetime.strptime(str(value), '%Y-%m-%d %H:%M:%S')
            except:
                return None
    
    def format_morning_briefing(self, top_5: List[ScoredLead]) -> str:
        """
        Formatiert die Morning Briefing Nachricht für Telegram
        """
        today = datetime.now().strftime("%A, %d.%m.%Y")
        
        # Header mit Motivations-Quote basierend auf Tag
        quotes = {
            0: "🎯 Neue Woche, neue Deals!",
            1: "⚡ Montag = Momentum", 
            2: "🔥 Dienstag ist für Action",
            3: "📈 Mitte der Woche, voller Fokus",
            4: "🏁 Donnerstag = Closing Day",
            5: "🎉 Freitag = Follow-up Friday",
            6: "🌅 Sonntag = Planungs-Modus"
        }
        weekday = datetime.now().weekday()
        header_quote = quotes.get(weekday, "🎯 Guten Morgen!")
        
        message = f"{header_quote}\n\n"
        message += f"📊 *Deine Top 5 für {today}*\n"
        message += "_Intelligent priorisiert nach Score, Deal-Size & Aktivität_\n\n"
        message += "═══════════════════\n\n"
        
        for i, lead in enumerate(top_5, 1):
            # Medal for top 3
            rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            
            # Qualification indicator
            qual_emoji = "🟢" if lead.qualification == "QUALIFIED" else "🟡" if lead.qualification == "PROBABLE" else "⚪"
            
            # Deal size formatting
            deal_display = f"€{lead.deal_size:.0f}M" if lead.deal_size >= 1 else "TBD"
            
            # Activity urgency
            if lead.days_inactive <= 3:
                activity_indicator = "🟢"
            elif lead.days_inactive <= 7:
                activity_indicator = "🟡"
            else:
                activity_indicator = "🔴"
            
            message += f"{rank_emoji} *{lead.company}* ({lead.region})\n"
            message += f"   {qual_emoji} MEDDPICC: {lead.meddpicc_score}/80 | 💰 {deal_display}\n"
            message += f"   👤 {lead.contact_person}, {lead.title}\n"
            message += f"   {activity_indicator} Letzte Activity: {lead.days_inactive} Tage ({lead.last_activity_type})\n"
            message += f"   📍 Stage: {lead.stage}\n"
            message += f"   🎯 *{lead.suggested_action}*\n"
            
            if lead.linkedin:
                message += f"   🔗 [LinkedIn]({lead.linkedin})\n"
            
            message += f"   _Priorität: {lead.priority_score}/100 ({lead.reason})_\n\n"
            message += "──────────────────\n\n"
        
        # Summary Stats
        total_pipeline = sum(l.deal_size for l in top_5 if l.deal_size)
        avg_meddpicc = sum(l.meddpicc_score for l in top_5) / len(top_5) if top_5 else 0
        
        message += "═══════════════════\n\n"
        message += f"📈 *Zusammenfassung Top 5:*\n"
        message += f"   Gesamt-Pipeline: €{total_pipeline:.0f}M\n"
        message += f"   Ø MEDDPICC: {avg_meddpicc:.0f}/80\n"
        message += f"   Dringendste: {top_5[0].company if top_5 else 'N/A'}\n\n"
        
        # Footer with actions
        message += "💡 *Schnell-Actions:*\n"
        message += "   `/next` - Nächste Aktivität anzeigen\n"
        message += "   `/hot` - Alle Hot Opportunities\n"
        message += "   `/stale` - Schlummernde Deals\n\n"
        message += "🌐 [Dashboard öffnen](https://pipo-bitwise-lead-tracker.streamlit.app)"
        
        return message
    
    def check_and_send(self) -> bool:
        """
        Hauptfunktion: Holt Top 5 und sendet Briefing
        """
        print(f"[{datetime.now()}] Generating Morning Briefing...")
        
        top_5 = self.get_top_5_leads()
        
        if not top_5:
            message = "🌅 *Guten Morgen!*\n\n"
            message += "Heute keine dringenden Prioritäten. Zeit für:\n"
            message += "• Neue Prospecting-Listen durchgehen\n"
            message += "• LinkedIn Outreach\n"
            message += "• Bestehende Beziehungen pflegen\n\n"
            message += "🌐 [Dashboard öffnen](https://pipo-bitwise-lead-tracker.streamlit.app)"
        else:
            message = self.format_morning_briefing(top_5)
        
        # Save state
        self._save_state(top_5)
        
        # Send via Telegram
        return self._send_telegram(message)
    
    def _save_state(self, top_5: List[ScoredLead]):
        """Speichert den aktuellen Zustand für Tracking"""
        state = {
            'last_run': datetime.now().isoformat(),
            'top_5': [
                {
                    'company': l.company,
                    'score': l.priority_score,
                    'meddpicc': l.meddpicc_score
                }
                for l in top_5
            ]
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    
    def _send_telegram(self, message: str) -> bool:
        """Sendet Nachricht via OpenClaw"""
        try:
            import subprocess
            result = subprocess.run(
                ['openclaw', 'message', 'send', '--target', TELEGRAM_CHAT_ID, '--message', message],
                capture_output=True,
                text=True,
                timeout=30
            )
            success = result.returncode == 0
            if success:
                print(f"✅ Morning Briefing sent successfully")
            else:
                print(f"❌ Failed: {result.stderr}")
            return success
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def preview(self) -> str:
        """Zeigt Preview ohne zu senden (für Testing)"""
        top_5 = self.get_top_5_leads()
        return self.format_morning_briefing(top_5)


def main():
    """Entry point für Cron"""
    briefing = SmartMorningBriefing()
    success = briefing.check_and_send()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        # Preview mode - don't send, just print
        briefing = SmartMorningBriefing()
        print(briefing.preview())
    else:
        # Normal mode - send briefing
        exit(main())
