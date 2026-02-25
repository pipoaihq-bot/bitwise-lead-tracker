"""
Data models for Bitwise Lead Tracker
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

class Region(Enum):
    DE = "DE"
    CH = "CH"
    UK = "UK"
    UAE = "UAE"
    NORDICS = "NORDICS"

class Tier(Enum):
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4

class Stage(Enum):
    PROSPECTING = "prospecting"
    DISCOVERY = "discovery"
    SOLUTIONING = "solutioning"
    VALIDATION = "validation"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

@dataclass
class Lead:
    id: Optional[int]
    company: str
    region: Region
    tier: Tier
    aum_estimate_millions: float
    contact_person: str
    title: str
    email: Optional[str] = None
    linkedin: Optional[str] = None
    stage: Stage = Stage.PROSPECTING
    pain_points: str = ""
    use_case: str = ""
    expected_deal_size_millions: float = 0.0
    expected_yield: float = 0.0
    industry: str = ""
    staking_readiness: str = ""
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

@dataclass
class MEDDPICCScore:
    lead_id: int
    metrics: int = 0
    economic_buyer: int = 0
    decision_process: int = 0
    decision_criteria: int = 0
    paper_process: int = 0
    pain: int = 0
    champion: int = 0
    competition: int = 0
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    @property
    def total_score(self) -> int:
        return (self.metrics + self.economic_buyer + self.decision_process + 
                self.decision_criteria + self.paper_process + self.pain + 
                self.champion + self.competition)
    
    @property
    def qualification_status(self) -> str:
        if self.total_score >= 70:
            return "QUALIFIED"
        elif self.total_score >= 50:
            return "PROBABLE"
        elif self.total_score >= 30:
            return "POSSIBLE"
        else:
            return "UNQUALIFIED"

@dataclass
class Task:
    id: Optional[int]
    title: str
    description: str
    status: str = "todo"
    priority: str = "P2"
    category: str = "OUTREACH"
    target_company: Optional[str] = None
    target_contact: Optional[str] = None
    due_date: Optional[str] = None
    linkedin_url: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
