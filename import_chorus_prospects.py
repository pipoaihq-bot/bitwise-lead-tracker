#!/usr/bin/env python3
"""
Import Chorus One prospects CSV into Bitwise Lead Tracker
"""

import csv
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import Database
from models import Lead, MEDDPICCScore, Region, Tier, Stage

def determine_region(website, linkedin, company_name):
    """Determine region based on domain clues"""
    text = f"{website} {linkedin} {company_name}".lower()
    
    if any(x in text for x in ['.ch', 'swiss', 'switzerland', 'zurich', 'geneva', 'basel']):
        return 'CH'
    elif any(x in text for x in ['.de', 'germany', 'berlin', 'munich', 'frankfurt', 'hamburg']):
        return 'DE'
    elif any(x in text for x in ['.uk', '.co.uk', 'british', 'london', 'england']):
        return 'UK'
    elif any(x in text for x in ['uae', 'dubai', 'abudhabi', '.ae']):
        return 'UAE'
    elif any(x in text for x in ['.no', '.se', '.dk', '.fi', 'norway', 'sweden', 'denmark', 'finland', 'nordic']):
        return 'NORDICS'
    else:
        return 'DE'  # Default to DE for European prospects

def determine_tier(account_type):
    """Determine tier based on account type"""
    type_lower = account_type.lower() if account_type else ''
    
    if any(x in type_lower for x in ['bank', 'asset manager', 'exchange', 'custodian']):
        return Tier.TIER_1  # €50B+ equivalent for major institutions
    elif any(x in type_lower for x in ['venture capital', 'hedge fund', 'foundation']):
        return Tier.TIER_2  # €10-50B
    elif any(x in type_lower for x in ['infrastructure', 'wallet', 'platform']):
        return Tier.TIER_3  # €1-10B
    else:
        return Tier.TIER_4  # <€1B

def import_prospects(csv_path, db_path='bitwise_leads.db'):
    """Import prospects from CSV to database"""
    
    db = Database(db_path)
    
    imported = 0
    skipped = 0
    
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                company = row.get('Account Name', '').strip()
                account_type = row.get('? Account Type', '').strip()
                website = row.get('Website', '').strip()
                linkedin = row.get('LinkedIn', '').strip()
                
                if not company:
                    skipped += 1
                    continue
                
                # Skip Chorus One itself and Bitwise
                if any(x in company.lower() for x in ['chorus one', 'bitwise']):
                    skipped += 1
                    continue
                
                # Determine region
                region_str = determine_region(website, linkedin, company)
                region = Region(region_str)
                
                # Determine tier
                tier = determine_tier(account_type)
                
                # Create lead
                lead = Lead(
                    id=None,
                    company=company,
                    region=region,
                    tier=tier,
                    aum_estimate_millions=0,  # Unknown from CSV
                    contact_person='',
                    title='',
                    email=None,
                    linkedin=linkedin if linkedin else None,
                    stage=Stage.PROSPECTING,
                    pain_points=f"Type: {account_type}",
                    use_case='',
                    expected_deal_size_millions=0,
                    expected_yield=0
                )
                
                lead_id = db.create_lead(lead)
                
                # Initialize MEDDPICC score
                score = MEDDPICCScore(lead_id=lead_id)
                db.set_meddpicc_score(lead_id, score)
                
                imported += 1
                
                if imported % 50 == 0:
                    print(f"✓ Imported {imported} leads...")
                
            except Exception as e:
                print(f"✗ Error importing {company}: {e}")
                skipped += 1
                continue
    
    print(f"\n{'='*60}")
    print(f"IMPORT COMPLETE")
    print(f"{'='*60}")
    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")
    print(f"Total in CSV: {imported + skipped}")
    
    return imported

if __name__ == '__main__':
    csv_file = '/Users/philippsandor/.openclaw/media/inbound/file_7---2156ada9-6311-4e0c-bfb3-8e045d94869b.csv'
    
    print("Chorus One Prospects Import")
    print("="*60)
    print(f"Source: {csv_file}")
    print()
    
    count = import_prospects(csv_file)
    
    print()
    print(f"✓ Successfully imported {count} prospects!")
    print()
    print("Next steps:")
    print("1. Review leads in Dashboard")
    print("2. Update contact information")
    print("3. Set MEDDPICC scores")
    print("4. Move promising leads to 'discovery' stage")
