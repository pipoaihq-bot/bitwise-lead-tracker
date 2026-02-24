#!/usr/bin/env python3
"""
Lead Enrichment Module - Adds missing data for filtering
"""

import sqlite3
from typing import Optional, Dict
from dataclasses import dataclass

@dataclass
class EnrichedData:
    """Additional data fields for filtering"""
    employee_count: Optional[str] = None  # "1-50", "51-200", "201-500", "501-1000", "1000+"
    industry: Optional[str] = None  # "Banking", "Asset Management", "Venture Capital", etc.
    sub_region: Optional[str] = None  # "London", "Zurich", "Frankfurt", etc.
    company_type: Optional[str] = None  # "Public", "Private", "Non-profit"
    funding_stage: Optional[str] = None  # For VCs/Startups: "Series A", "Series B", etc.
    year_founded: Optional[int] = None
    tech_stack: Optional[str] = None  # "Ethereum", "Multi-chain", "Bitcoin", etc.
    staking_readiness: Optional[str] = None  # "High", "Medium", "Low"
    
class LeadEnricher:
    """Enrich leads with additional data for better filtering"""
    
    def __init__(self, db_path: str = "bitwise_leads.db"):
        self.db_path = db_path
        self.init_enrichment_table()
    
    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_enrichment_table(self):
        """Add enrichment columns to leads table"""
        with self.get_connection() as conn:
            # Check if columns exist
            cursor = conn.execute("PRAGMA table_info(leads)")
            existing_cols = {row['name'] for row in cursor.fetchall()}
            
            # Add missing columns
            new_columns = {
                'employee_count': 'TEXT',
                'industry': 'TEXT',
                'sub_region': 'TEXT',
                'company_type': 'TEXT',
                'funding_stage': 'TEXT',
                'year_founded': 'INTEGER',
                'tech_stack': 'TEXT',
                'staking_readiness': 'TEXT',
                'data_enriched': 'BOOLEAN DEFAULT 0',
                'enriched_at': 'TIMESTAMP'
            }
            
            for col, dtype in new_columns.items():
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {dtype}")
                    print(f"✓ Added column: {col}")
            
            conn.commit()
    
    def enrich_from_account_type(self, lead_id: int, account_type: str, category: str):
        """Extract enrichment data from existing Chorus One data"""
        data = {}
        
        # Industry mapping
        type_lower = account_type.lower() if account_type else ''
        cat_lower = category.lower() if category else ''
        
        if 'bank' in type_lower or 'bank' in cat_lower:
            data['industry'] = 'Banking'
            data['company_type'] = 'Public'
            data['employee_count'] = '1000+'
            data['staking_readiness'] = 'High'
        elif 'asset manager' in type_lower or 'hedge fund' in type_lower:
            data['industry'] = 'Asset Management'
            data['company_type'] = 'Private'
            data['employee_count'] = '51-200'
            data['staking_readiness'] = 'High'
        elif 'venture capital' in type_lower or 'vc' in type_lower:
            data['industry'] = 'Venture Capital'
            data['company_type'] = 'Private'
            data['employee_count'] = '1-50'
            data['staking_readiness'] = 'Medium'
        elif 'exchange' in type_lower or 'trading' in type_lower:
            data['industry'] = 'Exchange/Trading'
            data['company_type'] = 'Private'
            data['employee_count'] = '201-500'
            data['staking_readiness'] = 'High'
        elif 'custodian' in type_lower:
            data['industry'] = 'Custody'
            data['company_type'] = 'Private'
            data['employee_count'] = '51-200'
            data['staking_readiness'] = 'High'
        elif 'wallet' in type_lower:
            data['industry'] = 'Wallet Provider'
            data['company_type'] = 'Private'
            data['employee_count'] = '1-50'
            data['staking_readiness'] = 'Medium'
        elif 'infrastructure' in type_lower or 'node operator' in type_lower:
            data['industry'] = 'Infrastructure'
            data['company_type'] = 'Private'
            data['employee_count'] = '1-50'
            data['staking_readiness'] = 'High'
        elif 'web3' in type_lower or 'application' in type_lower:
            data['industry'] = 'Web3/Application'
            data['company_type'] = 'Private'
            data['employee_count'] = '1-50'
            data['staking_readiness'] = 'Medium'
        elif 'foundation' in type_lower or 'network' in type_lower:
            data['industry'] = 'Network Foundation'
            data['company_type'] = 'Non-profit'
            data['employee_count'] = '1-50'
            data['staking_readiness'] = 'High'
        else:
            data['industry'] = 'Other'
            data['company_type'] = 'Private'
            data['employee_count'] = 'Unknown'
            data['staking_readiness'] = 'Medium'
        
        # Tech stack inference
        if any(x in type_lower for x in ['crypto', 'blockchain', 'web3']):
            data['tech_stack'] = 'Multi-chain'
        elif 'bitcoin' in type_lower:
            data['tech_stack'] = 'Bitcoin'
        elif 'ethereum' in type_lower:
            data['tech_stack'] = 'Ethereum'
        else:
            data['tech_stack'] = 'Unknown'
        
        # Update database
        self.update_lead(lead_id, data)
        return data
    
    def update_lead(self, lead_id: int, data: Dict):
        """Update lead with enriched data"""
        if not data:
            return
        
        fields = []
        values = []
        for key, value in data.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        fields.append("data_enriched = 1")
        fields.append("enriched_at = CURRENT_TIMESTAMP")
        values.append(lead_id)
        
        query = f"UPDATE leads SET {', '.join(fields)} WHERE id = ?"
        
        with self.get_connection() as conn:
            conn.execute(query, values)
            conn.commit()
    
    def enrich_all_leads(self):
        """Enrich all leads based on existing data"""
        with self.get_connection() as conn:
            leads = conn.execute(
                "SELECT id, pain_points FROM leads WHERE data_enriched = 0 OR data_enriched IS NULL"
            ).fetchall()
        
        total = len(leads)
        print(f"Enriching {total} leads...")
        
        for i, lead in enumerate(leads):
            lead_id = lead['id']
            pain_points = lead['pain_points'] or ''
            
            # Extract account type from pain_points (stored during import)
            account_type = ''
            if 'Type:' in pain_points:
                account_type = pain_points.replace('Type:', '').strip()
            
            self.enrich_from_account_type(lead_id, account_type, '')
            
            if (i + 1) % 100 == 0:
                print(f"  ✓ Enriched {i + 1}/{total} leads")
        
        print(f"✓ Enrichment complete! {total} leads updated.")
    
    def get_filter_options(self) -> Dict:
        """Get available filter options for dashboard"""
        with self.get_connection() as conn:
            # Industries
            industries = conn.execute(
                "SELECT DISTINCT industry FROM leads WHERE industry IS NOT NULL ORDER BY industry"
            ).fetchall()
            
            # Employee counts
            emp_counts = conn.execute(
                "SELECT DISTINCT employee_count FROM leads WHERE employee_count IS NOT NULL ORDER BY employee_count"
            ).fetchall()
            
            # Staking readiness
            readiness = conn.execute(
                "SELECT DISTINCT staking_readiness FROM leads WHERE staking_readiness IS NOT NULL"
            ).fetchall()
            
            # Company types
            comp_types = conn.execute(
                "SELECT DISTINCT company_type FROM leads WHERE company_type IS NOT NULL"
            ).fetchall()
            
            return {
                'industries': [row['industry'] for row in industries],
                'employee_counts': [row['employee_count'] for row in emp_counts],
                'staking_readiness': [row['staking_readiness'] for row in readiness],
                'company_types': [row['company_type'] for row in comp_types]
            }

if __name__ == '__main__':
    enricher = LeadEnricher()
    enricher.enrich_all_leads()
    
    # Show filter options
    print("\n" + "="*60)
    print("AVAILABLE FILTER OPTIONS")
    print("="*60)
    filters = enricher.get_filter_options()
    for key, values in filters.items():
        print(f"\n{key.upper()}:")
        for v in values:
            print(f"  - {v}")
