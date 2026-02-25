#!/usr/bin/env python3
"""
Task Management Module for Bitwise Lead Tracker
Trello-style task boards integrated into Streamlit
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum

class TaskStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"

class TaskPriority(Enum):
    P1 = "P1"  # Critical - This week
    P2 = "P2"  # High - Next 2 weeks
    P3 = "P3"  # Medium - This month
    P4 = "P4"  # Low - Backlog

class TaskCategory(Enum):
    UAE = "🇦🇪 UAE/GCC"
    GERMANY = "🇩🇪 Germany"
    SWITZERLAND = "🇨🇭 Switzerland"
    UK = "🇬🇧 UK"
    NORDICS = "🇸🇪 Nordics"
    OUTREACH = "📧 Outreach"
    CONTENT = "📝 Content"
    FOLLOW_UP = "🔄 Follow-up"
    RESEARCH = "🔍 Research"

@dataclass
class Task:
    id: Optional[int]
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    category: TaskCategory
    target_company: Optional[str] = None
    target_contact: Optional[str] = None
    due_date: Optional[str] = None
    linkedin_url: Optional[str] = None
    notes: str = ""
    created_at: datetime = None
    updated_at: datetime = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

class TaskManager:
    """Task management with database persistence"""
    
    def __init__(self, db_path: str = "bitwise_leads.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize tasks table"""
        with self.get_connection() as conn:
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
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            conn.commit()
    
    def create_task(self, task: Task) -> int:
        """Create new task"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO tasks (title, description, status, priority, category,
                                 target_company, target_contact, due_date, linkedin_url, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.title, task.description, task.status.value, task.priority.value,
                task.category.value, task.target_company, task.target_contact,
                task.due_date, task.linkedin_url, task.notes
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_tasks(self, status: Optional[str] = None, 
                  priority: Optional[str] = None,
                  category: Optional[str] = None) -> List[Task]:
        """Get tasks with filters"""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY 
            CASE priority 
                WHEN 'P1' THEN 1 
                WHEN 'P2' THEN 2 
                WHEN 'P3' THEN 3 
                ELSE 4 
            END,
            created_at DESC"
        
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(row) for row in rows]
    
    def update_task_status(self, task_id: int, status: str):
        """Update task status"""
        with self.get_connection() as conn:
            if status == 'done':
                conn.execute("""
                    UPDATE tasks SET status = ?, completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (status, task_id))
            else:
                conn.execute("""
                    UPDATE tasks SET status = ?, completed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (status, task_id))
            conn.commit()
    
    def update_task(self, task_id: int, **kwargs):
        """Update task fields"""
        if not kwargs:
            return
        
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [task_id]
        
        with self.get_connection() as conn:
            conn.execute(f"""
                UPDATE tasks SET {fields}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, values)
            conn.commit()
    
    def delete_task(self, task_id: int):
        """Delete task"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
    
    def get_stats(self) -> dict:
        """Get task statistics"""
        with self.get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            todo = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'todo'").fetchone()[0]
            in_progress = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'in_progress'").fetchone()[0]
            done = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'done'").fetchone()[0]
            p1 = conn.execute("SELECT COUNT(*) FROM tasks WHERE priority = 'P1' AND status != 'done'").fetchone()[0]
            
            return {
                'total': total,
                'todo': todo,
                'in_progress': in_progress,
                'done': done,
                'p1_pending': p1
            }
    
    def get_tasks_by_category(self) -> dict:
        """Get tasks grouped by category"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT category, COUNT(*) as count 
                FROM tasks WHERE status != 'done'
                GROUP BY category
                ORDER BY count DESC
            """).fetchall()
            return {row['category']: row['count'] for row in rows}
    
    def _row_to_task(self, row) -> Task:
        return Task(
            id=row['id'],
            title=row['title'],
            description=row['description'] or '',
            status=TaskStatus(row['status']),
            priority=TaskPriority(row['priority']),
            category=TaskCategory(row['category']),
            target_company=row['target_company'],
            target_contact=row['target_contact'],
            due_date=row['due_date'],
            linkedin_url=row['linkedin_url'],
            notes=row['notes'] or '',
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None
        )

# Pre-populated tasks for Bitwise EMEA
def get_default_tasks() -> List[Task]:
    """Get default task list for Philipp"""
    return [
        # P1 - This Week (Critical)
        Task(None, "LinkedIn: Connect with Christoph Richter (ADGM)", 
             "Head of Digital Assets & AI at ADGM. Key gatekeeper for UAE.",
             TaskStatus.TODO, TaskPriority.P1, TaskCategory.UAE,
             "ADGM", "Christoph Richter", linkedin_url="https://www.linkedin.com/in/christoph-richter/"),
        
        Task(None, "LinkedIn: Connect with Wael Raies (SNB)",
             "Head of Group Strategy & Innovation at Saudi National Bank.",
             TaskStatus.TODO, TaskPriority.P1, TaskCategory.UAE,
             "Saudi National Bank", "Wael Raies"),
        
        Task(None, "LinkedIn: Connect with Sabih Behzad (Deutsche Bank)",
             "Head of Digital Assets & Currencies at Deutsche Bank.",
             TaskStatus.TODO, TaskPriority.P1, TaskCategory.GERMANY,
             "Deutsche Bank", "Sabih Behzad"),
        
        Task(None, "LinkedIn: Connect with Fabian Dori (Sygnum)",
             "Head of Asset Management at Sygnum Bank.",
             TaskStatus.TODO, TaskPriority.P1, TaskCategory.SWITZERLAND,
             "Sygnum Bank", "Fabian Dori"),
        
        Task(None, "Post LinkedIn Announcement",
             "First post about joining Bitwise. Use content from LINKEDIN_CONTENT_PLAN.md",
             TaskStatus.TODO, TaskPriority.P1, TaskCategory.CONTENT),
        
        # P2 - Next 2 Weeks (High Priority)
        Task(None, "Research: DWS CIO Alternatives",
             "Find LinkedIn profile of CIO or Head of Alternatives at DWS Group",
             TaskStatus.TODO, TaskPriority.P2, TaskCategory.RESEARCH,
             "DWS Group", None),
        
        Task(None, "Research: Allianz GI Innovation Lead",
             "Find innovation/digital assets lead at Allianz Global Investors",
             TaskStatus.TODO, TaskPriority.P2, TaskCategory.RESEARCH,
             "Allianz Global Investors", None),
        
        Task(None, "Outreach: Send first 5 cold emails",
             "Use OUTREACH_SEQUENZEN.md templates for German Asset Managers",
             TaskStatus.TODO, TaskPriority.P2, TaskCategory.OUTREACH),
        
        Task(None, "LinkedIn: Connect with Lukas Doebelin (Sygnum)",
             "Head of Validator Nodes - technical contact",
             TaskStatus.TODO, TaskPriority.P2, TaskCategory.SWITZERLAND,
             "Sygnum Bank", "Lukas Doebelin"),
        
        Task(None, "Follow-up: Check connection acceptance rates",
             "Review LinkedIn connections sent, follow up with personalized messages",
             TaskStatus.TODO, TaskPriority.P2, TaskCategory.FOLLOW_UP),
        
        # UAE/GCC Specific
        Task(None, "Research: ADGM upcoming events",
             "Find Fintech Abu Dhabi and other ADGM events for Q1/Q2",
             TaskStatus.TODO, TaskPriority.P2, TaskCategory.UAE,
             "ADGM", None),
        
        Task(None, "LinkedIn: Research Mubadala Investment Team",
             "Find investment team members for infrastructure/staking relevance",
             TaskStatus.TODO, TaskPriority.P2, TaskCategory.UAE,
             "Mubadala", None),
        
        # P3 - This Month
        Task(None, "Technical Deep-Dive: Prepare Chorus One presentation",
             "Create technical deck for CTOs/Infrastructure teams",
             TaskStatus.TODO, TaskPriority.P3, TaskCategory.CONTENT),
        
        Task(None, "Outreach: UK Pension Consultants (WTW, Mercer)",
             "Contact Willis Towers Watson and Mercer for pension fund intros",
             TaskStatus.TODO, TaskPriority.P3, TaskCategory.UK,
             None, None),
        
        Task(None, "Content: Create 'Staking for German Banks' post",
             "LinkedIn post specifically for German banking audience",
             TaskStatus.TODO, TaskPriority.P3, TaskCategory.CONTENT),
        
        # Research
        Task(None, "Research: ZKB Innovation Team",
             "Find Head of Innovation at Zürcher Kantonalbank",
             TaskStatus.TODO, TaskPriority.P3, TaskCategory.RESEARCH,
             "Zürcher Kantonalbank", None),
        
        Task(None, "Research: Vontobel Digital Assets",
             "Find digital assets lead at Vontobel",
             TaskStatus.TODO, TaskPriority.P3, TaskCategory.RESEARCH,
             "Vontobel", None),
    ]

def populate_default_tasks(db_path: str = "bitwise_leads.db"):
    """Populate database with default tasks if empty"""
    manager = TaskManager(db_path)
    
    # Check if tasks exist
    with manager.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    
    if count == 0:
        print("Populating default tasks...")
        for task in get_default_tasks():
            manager.create_task(task)
        print(f"Created {len(get_default_tasks())} default tasks")
    else:
        print(f"Tasks already exist ({count} found)")

if __name__ == "__main__":
    populate_default_tasks()
