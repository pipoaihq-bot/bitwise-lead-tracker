#!/usr/bin/env python3
"""
Improved Region Mapping for Chorus One Prospects
"""

import sqlite3
from typing import Dict, List

# Comprehensive domain/country to region mapping
DOMAIN_REGION_MAP = {
    # Germany
    '.de': 'DE',
    'germany': 'DE',
    'berlin': 'DE',
    'munich': 'DE',
    'frankfurt': 'DE',
    'hamburg': 'DE',
    'cologne': 'DE',
    'stuttgart': 'DE',
    'dusseldorf': 'DE',
    'dresden': 'DE',
    'leipzig': 'DE',
    'nuremberg': 'DE',
    'darmstadt': 'DE',
    'mainz': 'DE',
    'heidelberg': 'DE',
    'karlsruhe': 'DE',
    'mannheim': 'DE',
    'freiburg': 'DE',
    'konstanz': 'DE',
    'augsburg': 'DE',
    'bochum': 'DE',
    'dortmund': 'DE',
    'essen': 'DE',
    'duisburg': 'DE',
    'wuppertal': 'DE',
    'bielefeld': 'DE',
    'bonn': 'DE',
    'munster': 'DE',
    'wiesbaden': 'DE',
    'kiel': 'DE',
    'schwerin': 'DE',
    'magdeburg': 'DE',
    'potsdam': 'DE',
    'erfurt': 'DE',
    'saarbrucken': 'DE',
    
    # Switzerland
    '.ch': 'CH',
    'switzerland': 'CH',
    'swiss': 'CH',
    'zurich': 'CH',
    'geneva': 'CH',
    'basel': 'CH',
    'bern': 'CH',
    'lausanne': 'CH',
    'lugano': 'CH',
    'st-gallen': 'CH',
    'stgallen': 'CH',
    'winterthur': 'CH',
    'lucerne': 'CH',
    'luzern': 'CH',
    'zug': 'CH',  # Crypto Valley
    'crypto-valley': 'CH',
    'cryptovalley': 'CH',
    
    # UK
    '.uk': 'UK',
    '.co.uk': 'UK',
    'united kingdom': 'UK',
    'britain': 'UK',
    'british': 'UK',
    'london': 'UK',
    'england': 'UK',
    'manchester': 'UK',
    'birmingham': 'UK',
    'leeds': 'UK',
    'glasgow': 'UK',
    'sheffield': 'UK',
    'bradford': 'UK',
    'liverpool': 'UK',
    'edinburgh': 'UK',
    'bristol': 'UK',
    'cardiff': 'UK',
    'belfast': 'UK',
    'newcastle': 'UK',
    'nottingham': 'UK',
    'cambridge': 'UK',
    'oxford': 'UK',
    
    # UAE / GCC
    '.ae': 'UAE',
    'uae': 'UAE',
    'dubai': 'UAE',
    'abudhabi': 'UAE',
    'abu-dhabi': 'UAE',
    'sharjah': 'UAE',
    'ajman': 'UAE',
    'fujairah': 'UAE',
    'ras-alkhaimah': 'UAE',
    'saudi': 'UAE',  # Often grouped with UAE for business
    'saudi-arabia': 'UAE',
    'qatar': 'UAE',
    'bahrain': 'UAE',
    'kuwait': 'UAE',
    'oman': 'UAE',
    
    # Nordics
    '.no': 'NORDICS',
    '.se': 'NORDICS',
    '.dk': 'NORDICS',
    '.fi': 'NORDICS',
    '.is': 'NORDICS',
    'norway': 'NORDICS',
    'sweden': 'NORDICS',
    'denmark': 'NORDICS',
    'finland': 'NORDICS',
    'iceland': 'NORDICS',
    'nordic': 'NORDICS',
    'oslo': 'NORDICS',
    'stockholm': 'NORDICS',
    'copenhagen': 'NORDICS',
    'helsinki': 'NORDICS',
    'reykjavik': 'NORDICS',
    'gothenburg': 'NORDICS',
    'malmo': 'NORDICS',
    'aarhus': 'NORDICS',
    'tampere': 'NORDICS',
    'turku': 'NORDICS',
    'uppsala': 'NORDICS',
    'bergen': 'NORDICS',
    'stavanger': 'NORDICS',
    'trondheim': 'NORDICS',
    
    # Other European (map to DE as default EMEA)
    '.at': 'DE',  # Austria
    'austria': 'DE',
    'vienna': 'DE',
    'wien': 'DE',
    '.nl': 'DE',  # Netherlands
    'netherlands': 'DE',
    'holland': 'DE',
    'amsterdam': 'DE',
    'rotterdam': 'DE',
    'hague': 'DE',
    '.be': 'DE',  # Belgium
    'belgium': 'DE',
    'brussels': 'DE',
    'bruxelles': 'DE',
    '.lu': 'DE',  # Luxembourg
    'luxembourg': 'DE',
    '.fr': 'DE',  # France
    'france': 'DE',
    'paris': 'DE',
    'lyon': 'DE',
    'marseille': 'DE',
    '.it': 'DE',  # Italy
    'italy': 'DE',
    'milan': 'DE',
    'milano': 'DE',
    'rome': 'DE',
    'roma': 'DE',
    '.es': 'DE',  # Spain
    'spain': 'DE',
    'madrid': 'DE',
    'barcelona': 'DE',
    '.pt': 'DE',  # Portugal
    'portugal': 'DE',
    'lisbon': 'DE',
    'lisboa': 'DE',
    '.pl': 'DE',  # Poland
    'poland': 'DE',
    'warsaw': 'DE',
    'warszawa': 'DE',
    '.cz': 'DE',  # Czech
    'czech': 'DE',
    'prague': 'DE',
    'praha': 'DE',
    '.hu': 'DE',  # Hungary
    'hungary': 'DE',
    'budapest': 'DE',
    '.ro': 'DE',  # Romania
    'romania': 'DE',
    'bucharest': 'DE',
    '.bg': 'DE',  # Bulgaria
    'bulgaria': 'DE',
    'sofia': 'DE',
    '.hr': 'DE',  # Croatia
    'croatia': 'DE',
    'zagreb': 'DE',
    '.si': 'DE',  # Slovenia
    'slovenia': 'DE',
    'ljubljana': 'DE',
    '.sk': 'DE',  # Slovakia
    'slovakia': 'DE',
    'bratislava': 'DE',
    '.ee': 'DE',  # Estonia
    'estonia': 'DE',
    'tallinn': 'DE',
    '.lv': 'DE',  # Latvia
    'latvia': 'DE',
    'riga': 'DE',
    '.lt': 'DE',  # Lithuania
    'lithuania': 'DE',
    'vilnius': 'DE',
    '.ie': 'DE',  # Ireland
    'ireland': 'DE',
    'dublin': 'DE',
    '.mt': 'DE',  # Malta
    'malta': 'DE',
    'valletta': 'DE',
    '.cy': 'DE',  # Cyprus
    'cyprus': 'DE',
    'nicosia': 'DE',
    '.gr': 'DE',  # Greece
    'greece': 'DE',
    'athens': 'DE',
}

def determine_region_improved(website: str, linkedin: str, company_name: str) -> str:
    """Improved region detection based on domain and keywords"""
    text = f"{website} {linkedin} {company_name}".lower()
    
    for keyword, region in DOMAIN_REGION_MAP.items():
        if keyword in text:
            return region
    
    return 'DE'  # Default to Germany for European prospects

def update_all_regions(db_path: str = "bitwise_leads.db"):
    """Update region for all leads"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get all leads
    leads = conn.execute("SELECT id, company, linkedin FROM leads").fetchall()
    
    updated = 0
    for lead in leads:
        lead_id = lead['id']
        company = lead['company'] or ''
        linkedin = lead['linkedin'] or ''
        
        # Determine new region
        new_region = determine_region_improved('', linkedin, company)
        
        # Update if different
        conn.execute(
            "UPDATE leads SET region = ? WHERE id = ?",
            (new_region, lead_id)
        )
        updated += 1
    
    conn.commit()
    conn.close()
    
    print(f"✓ Updated {updated} leads with improved region mapping")
    
    # Show distribution
    conn = sqlite3.connect(db_path)
    distribution = conn.execute(
        "SELECT region, COUNT(*) as count FROM leads GROUP BY region ORDER BY count DESC"
    ).fetchall()
    conn.close()
    
    print("\nRegion Distribution:")
    for row in distribution:
        print(f"  {row['region']}: {row['count']} leads")

if __name__ == '__main__':
    update_all_regions()
