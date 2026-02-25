"""
Database operations
"""
import sqlite3
from typing import Optional, List
from models import Lead, MEDDPICCScore, Region, Tier, Stage

class Database:
    def __init__(self, db_path: str = "bitwise_leads.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        with self.get_connection() as conn:
            # Leads table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    region TEXT DEFAULT 'DE',
                    tier INTEGER DEFAULT 2,
                    aum_estimate_millions REAL DEFAULT 0,
                    contact_person TEXT,
                    title TEXT,
                    email TEXT,
                    linkedin TEXT,
                    stage TEXT DEFAULT 'prospecting',
                    pain_points TEXT,
                    use_case TEXT,
                    expected_deal_size_millions REAL DEFAULT 0,
                    expected_yield REAL DEFAULT 0,
                    industry TEXT,
                    staking_readiness TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # MEDDPICC table
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
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                )
            """)
            
            # Tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'todo',
                    priority TEXT DEFAULT 'P2',
                    category TEXT DEFAULT 'OUTREACH',
                    target_company TEXT,
                    target_contact TEXT,
                    due_date TEXT,
                    linkedin_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def create_lead(self, lead: Lead) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO leads (company, region, tier, aum_estimate_millions,
                                 contact_person, title, email, linkedin, stage,
                                 pain_points, use_case, expected_deal_size_millions,
                                 expected_yield, industry, staking_readiness)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (lead.company, lead.region.value, lead.tier.value,
                  lead.aum_estimate_millions, lead.contact_person, lead.title,
                  lead.email, lead.linkedin, lead.stage.value, lead.pain_points,
                  lead.use_case, lead.expected_deal_size_millions,
                  lead.expected_yield, lead.industry, lead.staking_readiness))
            conn.commit()
            return cursor.lastrowid
    
    def get_all_leads(self) -> List[Lead]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
            return [self._row_to_lead(row) for row in rows]
    
    def get_lead(self, lead_id: int) -> Optional[Lead]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
            return self._row_to_lead(row) if row else None
    
    def update_lead_stage(self, lead_id: int, stage: str):
        with self.get_connection() as conn:
            conn.execute("UPDATE leads SET stage = ? WHERE id = ?", (stage, lead_id))
            conn.commit()
    
    def set_meddpicc_score(self, lead_id: int, score: MEDDPICCScore):
        with self.get_connection() as conn:
            existing = conn.execute("SELECT id FROM meddpicc_scores WHERE lead_id = ?", (lead_id,)).fetchone()
            
            if existing:
                conn.execute("""
                    UPDATE meddpicc_scores SET
                        metrics = ?, economic_buyer = ?, decision_process = ?,
                        decision_criteria = ?, paper_process = ?, pain = ?,
                        champion = ?, competition = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE lead_id = ?
                """, (score.metrics, score.economic_buyer, score.decision_process,
                      score.decision_criteria, score.paper_process, score.pain,
                      score.champion, score.competition, lead_id))
            else:
                conn.execute("""
                    INSERT INTO meddpicc_scores 
                    (lead_id, metrics, economic_buyer, decision_process,
                     decision_criteria, paper_process, pain, champion, competition)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (lead_id, score.metrics, score.economic_buyer, score.decision_process,
                      score.decision_criteria, score.paper_process, score.pain,
                      score.champion, score.competition))
            conn.commit()
    
    def get_meddpicc_score(self, lead_id: int) -> Optional[MEDDPICCScore]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM meddpicc_scores WHERE lead_id = ?", (lead_id,)).fetchone()
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
    
    def _row_to_lead(self, row) -> Lead:
        return Lead(
            id=row['id'],
            company=row['company'],
            region=Region(row['region']),
            tier=Tier(row['tier']),
            aum_estimate_millions=row['aum_estimate_millions'],
            contact_person=row['contact_person'] or '',
            title=row['title'] or '',
            email=row['email'],
            linkedin=row['linkedin'],
            stage=Stage(row['stage']),
            pain_points=row['pain_points'] or '',
            use_case=row['use_case'] or '',
            expected_deal_size_millions=row['expected_deal_size_millions'],
            expected_yield=row['expected_yield'],
            industry=row['industry'] or '',
            staking_readiness=row['staking_readiness'] or ''
        )
