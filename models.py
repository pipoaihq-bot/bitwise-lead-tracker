"""
Bitwise EMEA Lead Tracker
MEDDPICC-aligned sales pipeline management for Head of EMEA Onchain Solutions
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List
from enum import Enum

class Region(Enum):
    GERMANY = "DE"
    SWITZERLAND = "CH"
    UK = "UK"
    UAE = "UAE"
    NORDICS = "NORDICS"

class Tier(Enum):
    TIER_1 = 1  # €50B+ AUM
    TIER_2 = 2  # €10B-50B AUM
    TIER_3 = 3  # €1B-10B AUM
    TIER_4 = 4  # <€1B AUM

class Stage(Enum):
    PROSPECTING = "prospecting"
    DISCOVERY = "discovery"
    SOLUTIONING = "solutioning"
    VALIDATION = "validation"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"

@dataclass
class MEDDPICCScore:
    """MEDDPICC scoring for deal qualification"""
    lead_id: int
    metrics: int = 0  # 0-10: Quantified business case
    economic_buyer: int = 0  # 0-10: Access to EB
    decision_process: int = 0  # 0-10: Understanding of process
    decision_criteria: int = 0  # 0-10: Known criteria
    paper_process: int = 0  # 0-10: Contract/compliance clarity
    pain: int = 0  # 0-10: Pain identified & validated
    champion: int = 0  # 0-10: Champion built
    competition: int = 0  # 0-10: Competitive position known
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
    
    def to_dict(self):
        return {
            **asdict(self),
            'total_score': self.total_score,
            'qualification_status': self.qualification_status
        }

@dataclass
class Lead:
    """Sales lead representation"""
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
    created_at: datetime = None
    updated_at: datetime = None
    
    # Enrichment fields (optional)
    industry: Optional[str] = None
    employee_count: Optional[str] = None
    sub_region: Optional[str] = None
    company_type: Optional[str] = None
    funding_stage: Optional[str] = None
    year_founded: Optional[int] = None
    tech_stack: Optional[str] = None
    staking_readiness: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self):
        result = {
            'id': self.id,
            'company': self.company,
            'region': self.region.value if isinstance(self.region, Region) else self.region,
            'tier': self.tier.value if isinstance(self.tier, Tier) else self.tier,
            'aum_estimate_millions': self.aum_estimate_millions,
            'contact_person': self.contact_person,
            'title': self.title,
            'email': self.email,
            'linkedin': self.linkedin,
            'stage': self.stage.value if isinstance(self.stage, Stage) else self.stage,
            'pain_points': self.pain_points,
            'use_case': self.use_case,
            'expected_deal_size_millions': self.expected_deal_size_millions,
            'expected_yield': self.expected_yield,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Add enrichment fields if they exist
        if self.industry:
            result['industry'] = self.industry
        if self.employee_count:
            result['employee_count'] = self.employee_count
        if self.sub_region:
            result['sub_region'] = self.sub_region
        if self.company_type:
            result['company_type'] = self.company_type
        if self.funding_stage:
            result['funding_stage'] = self.funding_stage
        if self.year_founded:
            result['year_founded'] = self.year_founded
        if self.tech_stack:
            result['tech_stack'] = self.tech_stack
        if self.staking_readiness:
            result['staking_readiness'] = self.staking_readiness
            
        return result

@dataclass
class Activity:
    """Sales activity log"""
    id: Optional[int]
    lead_id: int
    activity_type: str  # email, call, meeting, demo, proposal, etc.
    notes: str
    outcome: str  # positive, neutral, negative, scheduled
    next_steps: str = ""
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'activity_type': self.activity_type,
            'notes': self.notes,
            'outcome': self.outcome,
            'next_steps': self.next_steps,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
