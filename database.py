"""
Database operations for Bitwise Lead Tracker
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from models import Lead, Activity, MEDDPICCScore, Region, Tier, Stage

class Database:
    def __init__(self, db_path: str = None):
        # Allow custom path for Streamlit Cloud
        if db_path is None:
            self.db_path = "bitwise_leads.db"
        else:
            self.db_path = db_path
        self.init_db()
    
    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database with tables"""
        with self.get_connection() as conn:
            # Leads table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    region TEXT NOT NULL,
                    tier INTEGER NOT NULL,
                    aum_estimate_millions REAL DEFAULT 0,
                    contact_person TEXT NOT NULL,
                    title TEXT NOT NULL,
                    email TEXT,
                    linkedin TEXT,
                    stage TEXT DEFAULT 'prospecting',
                    pain_points TEXT,
                    use_case TEXT,
                    expected_deal_size_millions REAL DEFAULT 0,
                    expected_yield REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Activities table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    notes TEXT,
                    outcome TEXT,
                    next_steps TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                )
            """)
            
            # MEDDPICC scores table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meddpicc_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER UNIQUE NOT NULL,
                    metrics INTEGER DEFAULT 0,
                    economic_buyer INTEGER DEFAULT 0,
                    decision_process INTEGER DEFAULT 0,
                    decision_criteria INTEGER DEFAULT 0,
                    paper_process INTEGER DEFAULT 0,
                    pain INTEGER DEFAULT 0,
                    champion INTEGER DEFAULT 0,
                    competition INTEGER DEFAULT 0,
                    total_score INTEGER DEFAULT 0,
                    qualification_status TEXT DEFAULT 'UNQUALIFIED',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                )
            """)
            
            conn.commit()
    
    # Lead operations
    def create_lead(self, lead: Lead) -> int:
        """Create new lead, return ID"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO leads (company, region, tier, aum_estimate_millions, 
                                 contact_person, title, email, linkedin, stage,
                                 pain_points, use_case, expected_deal_size_millions, 
                                 expected_yield)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead.company, lead.region.value, lead.tier.value, 
                lead.aum_estimate_millions, lead.contact_person, lead.title,
                lead.email, lead.linkedin, lead.stage.value,
                lead.pain_points, lead.use_case, lead.expected_deal_size_millions,
                lead.expected_yield
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_lead(self, lead_id: int) -> Optional[Lead]:
        """Get lead by ID"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM leads WHERE id = ?", (lead_id,)
            ).fetchone()
            if row:
                return self._row_to_lead(row)
            return None
    
    def get_all_leads(self, region: Optional[str] = None, 
                     stage: Optional[str] = None,
                     tier: Optional[int] = None) -> List[Lead]:
        """Get all leads with optional filters"""
        query = "SELECT * FROM leads WHERE 1=1"
        params = []
        
        if region:
            query += " AND region = ?"
            params.append(region)
        if stage:
            query += " AND stage = ?"
            params.append(stage)
        if tier:
            query += " AND tier = ?"
            params.append(tier)
        
        query += " ORDER BY created_at DESC"
        
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_lead(row) for row in rows]
    
    def update_lead_stage(self, lead_id: int, stage: str) -> bool:
        """Update lead stage"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE leads SET stage = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (stage, lead_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def update_lead(self, lead_id: int, **kwargs) -> bool:
        """Update lead fields"""
        if not kwargs:
            return False
        
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [lead_id]
        
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                UPDATE leads SET {fields}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_lead(self, lead_id: int) -> bool:
        """Delete lead and related data"""
        with self.get_connection() as conn:
            # Delete related records first
            conn.execute("DELETE FROM activities WHERE lead_id = ?", (lead_id,))
            conn.execute("DELETE FROM meddpicc_scores WHERE lead_id = ?", (lead_id,))
            cursor = conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Activity operations
    def add_activity(self, activity: Activity) -> int:
        """Add activity to lead"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO activities (lead_id, activity_type, notes, outcome, next_steps)
                VALUES (?, ?, ?, ?, ?)
            """, (activity.lead_id, activity.activity_type, activity.notes,
                  activity.outcome, activity.next_steps))
            conn.commit()
            return cursor.lastrowid
    
    def get_activities(self, lead_id: int) -> List[Activity]:
        """Get all activities for a lead"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM activities WHERE lead_id = ?
                ORDER BY created_at DESC
            """, (lead_id,)).fetchall()
            return [self._row_to_activity(row) for row in rows]
    
    # MEDDPICC operations
    def set_meddpicc_score(self, lead_id: int, score: MEDDPICCScore) -> bool:
        """Set or update MEDDPICC score"""
        with self.get_connection() as conn:
            # Check if score exists
            existing = conn.execute(
                "SELECT id FROM meddpicc_scores WHERE lead_id = ?", (lead_id,)
            ).fetchone()
            
            if existing:
                conn.execute("""
                    UPDATE meddpicc_scores SET
                        metrics = ?, economic_buyer = ?, decision_process = ?,
                        decision_criteria = ?, paper_process = ?, pain = ?,
                        champion = ?, competition = ?, total_score = ?,
                        qualification_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE lead_id = ?
                """, (score.metrics, score.economic_buyer, score.decision_process,
                      score.decision_criteria, score.paper_process, score.pain,
                      score.champion, score.competition, score.total_score,
                      score.qualification_status, lead_id))
            else:
                conn.execute("""
                    INSERT INTO meddpicc_scores 
                    (lead_id, metrics, economic_buyer, decision_process,
                     decision_criteria, paper_process, pain, champion, competition,
                     total_score, qualification_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (lead_id, score.metrics, score.economic_buyer, score.decision_process,
                      score.decision_criteria, score.paper_process, score.pain,
                      score.champion, score.competition, score.total_score,
                      score.qualification_status))
            
            conn.commit()
            return True
    
    def get_meddpicc_score(self, lead_id: int) -> Optional[MEDDPICCScore]:
        """Get MEDDPICC score for lead"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM meddpicc_scores WHERE lead_id = ?
            """, (lead_id,)).fetchone()
            
            if row:
                return MEDDPICCScore(
                    lead_id=row['lead_id'],
                    metrics=row['metrics'],
                    economic_buyer=row['economic_buyer'],
                    decision_process=row['decision_process'],
                    decision_criteria=row['decision_criteria'],
                    paper_process=row['paper_process'],
                    pain=row['pain'],
                    champion=row['champion'],
                    competition=row['competition']
                )
            return None
    
    # Pipeline reporting
    def get_pipeline_by_stage(self) -> dict:
        """Get pipeline summary by stage"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT stage, COUNT(*) as count, 
                       SUM(expected_deal_size_millions) as total_value
                FROM leads
                WHERE stage != 'closed_lost'
                GROUP BY stage
            """).fetchall()
            
            return {
                row['stage']: {
                    'count': row['count'],
                    'total_value_millions': row['total_value'] or 0
                }
                for row in rows
            }
    
    def get_pipeline_by_region(self) -> dict:
        """Get pipeline summary by region"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT region, COUNT(*) as count,
                       SUM(expected_deal_size_millions) as total_value
                FROM leads
                WHERE stage != 'closed_lost'
                GROUP BY region
            """).fetchall()
            
            return {
                row['region']: {
                    'count': row['count'],
                    'total_value_millions': row['total_value'] or 0
                }
                for row in rows
            }
    
    def get_qualified_deals(self, min_score: int = 50) -> List[dict]:
        """Get all deals with MEDDPICC score above threshold"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT l.*, m.total_score, m.qualification_status
                FROM leads l
                JOIN meddpicc_scores m ON l.id = m.lead_id
                WHERE m.total_score >= ?
                ORDER BY m.total_score DESC
            """, (min_score,)).fetchall()
            
            return [dict(row) for row in rows]
    
    # Export
    def export_to_json(self, filepath: str):
        """Export all data to JSON"""
        data = {
            'leads': [],
            'activities': [],
            'meddpicc_scores': []
        }
        
        with self.get_connection() as conn:
            # Export leads
            rows = conn.execute("SELECT * FROM leads").fetchall()
            data['leads'] = [dict(row) for row in rows]
            
            # Export activities
            rows = conn.execute("SELECT * FROM activities").fetchall()
            data['activities'] = [dict(row) for row in rows]
            
            # Export MEDDPICC scores
            rows = conn.execute("SELECT * FROM meddpicc_scores").fetchall()
            data['meddpicc_scores'] = [dict(row) for row in rows]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    # Helper methods
    def _row_to_lead(self, row) -> Lead:
        lead = Lead(
            id=row['id'],
            company=row['company'],
            region=Region(row['region']),
            tier=Tier(row['tier']),
            aum_estimate_millions=row['aum_estimate_millions'],
            contact_person=row['contact_person'],
            title=row['title'],
            email=row['email'],
            linkedin=row['linkedin'],
            stage=Stage(row['stage']),
            pain_points=row['pain_points'] or '',
            use_case=row['use_case'] or '',
            expected_deal_size_millions=row['expected_deal_size_millions'],
            expected_yield=row['expected_yield'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )
        
        # Add enrichment fields if they exist
        if 'industry' in row.keys():
            lead.industry = row['industry']
        if 'employee_count' in row.keys():
            lead.employee_count = row['employee_count']
        if 'company_type' in row.keys():
            lead.company_type = row['company_type']
        if 'staking_readiness' in row.keys():
            lead.staking_readiness = row['staking_readiness']
        if 'tech_stack' in row.keys():
            lead.tech_stack = row['tech_stack']
        if 'sub_region' in row.keys():
            lead.sub_region = row['sub_region']
        
        return lead
    
    def _row_to_activity(self, row) -> Activity:
        return Activity(
            id=row['id'],
            lead_id=row['lead_id'],
            activity_type=row['activity_type'],
            notes=row['notes'] or '',
            outcome=row['outcome'] or '',
            next_steps=row['next_steps'] or '',
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )
