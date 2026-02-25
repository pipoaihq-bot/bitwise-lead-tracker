"""
Task management
"""
import sqlite3
from typing import List, Optional
from models import Task

class TaskManager:
    def __init__(self, db_path: str = "bitwise_leads.db"):
        self.db_path = db_path
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_task(self, task: Task) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO tasks (title, description, status, priority, category,
                                 target_company, target_contact, due_date, linkedin_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task.title, task.description, task.status, task.priority,
                  task.category, task.target_company, task.target_contact,
                  task.due_date, task.linkedin_url))
            conn.commit()
            return cursor.lastrowid
    
    def get_tasks(self, status: Optional[str] = None) -> List[Task]:
        query = "SELECT * FROM tasks"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC"
        
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(row) for row in rows]
    
    def update_task_status(self, task_id: int, status: str):
        with self.get_connection() as conn:
            conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
            conn.commit()
    
    def get_stats(self) -> dict:
        with self.get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            todo = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'todo'").fetchone()[0]
            in_progress = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'in_progress'").fetchone()[0]
            done = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'done'").fetchone()[0]
            return {'total': total, 'todo': todo, 'in_progress': in_progress, 'done': done}
    
    def _row_to_task(self, row) -> Task:
        return Task(
            id=row['id'],
            title=row['title'],
            description=row['description'] or '',
            status=row['status'],
            priority=row['priority'],
            category=row['category'],
            target_company=row['target_company'],
            target_contact=row['target_contact'],
            due_date=row['due_date'],
            linkedin_url=row['linkedin_url']
        )

def populate_default_tasks(db_path: str = "bitwise_leads.db"):
    """Create default tasks if none exist"""
    manager = TaskManager(db_path)
    
    with manager.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    
    if count == 0:
        default_tasks = [
            Task(None, "LinkedIn: Christoph Richter (ADGM)", "Head of Digital Assets & AI at ADGM - Key gatekeeper for UAE", "todo", "P1", "UAE", "ADGM", "Christoph Richter"),
            Task(None, "LinkedIn: Wael Raies (SNB)", "Head of Group Strategy & Innovation at Saudi National Bank", "todo", "P1", "UAE", "Saudi National Bank", "Wael Raies"),
            Task(None, "LinkedIn: Sabih Behzad (Deutsche Bank)", "Head of Digital Assets & Currencies at Deutsche Bank", "todo", "P1", "GERMANY", "Deutsche Bank", "Sabih Behzad"),
            Task(None, "LinkedIn: Fabian Dori (Sygnum)", "Head of Asset Management at Sygnum Bank", "todo", "P1", "SWITZERLAND", "Sygnum Bank", "Fabian Dori"),
            Task(None, "Post LinkedIn Announcement", "First post about joining Bitwise - use content plan", "todo", "P1", "CONTENT"),
            Task(None, "Research: DWS CIO Alternatives", "Find LinkedIn profile of CIO at DWS Group", "todo", "P2", "RESEARCH", "DWS Group"),
            Task(None, "Research: Allianz GI Innovation Lead", "Find innovation/digital assets lead at Allianz", "todo", "P2", "RESEARCH", "Allianz Global Investors"),
            Task(None, "Send first 5 cold emails", "Use outreach templates for German Asset Managers", "todo", "P2", "OUTREACH"),
        ]
        
        for task in default_tasks:
            manager.create_task(task)
        print(f"Created {len(default_tasks)} default tasks")
