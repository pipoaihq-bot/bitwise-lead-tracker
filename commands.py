"""
CLI Commands for Bitwise Lead Tracker
"""

import click
from tabulate import tabulate
from datetime import datetime
from typing import Optional

from database import Database
from models import Lead, Activity, MEDDPICCScore, Region, Tier, Stage

# Initialize database
db = Database()

@click.group()
def cli():
    """Bitwise EMEA Lead Tracker - MEDDPICC-aligned sales pipeline management"""
    pass

# Lead Management Commands
@cli.command()
@click.option('--company', required=True, help='Company name')
@click.option('--region', required=True, type=click.Choice(['DE', 'CH', 'UK', 'UAE', 'NORDICS']), 
              help='Region (DE, CH, UK, UAE, NORDICS)')
@click.option('--tier', required=True, type=click.IntRange(1, 4), 
              help='Tier (1=€50B+, 2=€10-50B, 3=€1-10B, 4=<€1B)')
@click.option('--aum', required=True, type=float, help='Estimated AUM in millions €')
@click.option('--contact', required=True, help='Contact person name')
@click.option('--title', required=True, help='Contact title')
@click.option('--email', help='Contact email')
@click.option('--linkedin', help='LinkedIn URL')
@click.option('--stage', default='prospecting', 
              type=click.Choice(['prospecting', 'discovery', 'solutioning', 'validation', 
                               'negotiation', 'closed_won', 'closed_lost']),
              help='Sales stage')
@click.option('--pain', help='Pain points identified')
@click.option('--use-case', help='Use case / opportunity')
@click.option('--deal-size', type=float, default=0, help='Expected deal size in millions €')
@click.option('--exp-yield', 'expected_yield', type=float, default=0, help='Expected yield %')
def add_lead(company, region, tier, aum, contact, title, email, linkedin, stage, 
             pain, use_case, deal_size, expected_yield):
    """Add a new lead to the pipeline"""
    
    region_enum = Region(region)
    tier_enum = Tier(tier)
    stage_enum = Stage(stage)
    
    lead = Lead(
        id=None,
        company=company,
        region=region_enum,
        tier=tier_enum,
        aum_estimate_millions=aum,
        contact_person=contact,
        title=title,
        email=email,
        linkedin=linkedin,
        stage=stage_enum,
        pain_points=pain or '',
        use_case=use_case or '',
        expected_deal_size_millions=deal_size,
        expected_yield=expected_yield
    )
    
    lead_id = db.create_lead(lead)
    click.echo(f"✓ Lead created: {company} (ID: {lead_id})")
    
    # Initialize MEDDPICC score
    score = MEDDPICCScore(lead_id=lead_id)
    db.set_meddpicc_score(lead_id, score)
    click.echo(f"✓ MEDDPICC score initialized (run 'meddpicc-score {lead_id}' to update)")

@cli.command()
@click.option('--region', type=click.Choice(['DE', 'CH', 'UK', 'UAE', 'NORDICS']), 
              help='Filter by region')
@click.option('--stage', type=click.Choice(['prospecting', 'discovery', 'solutioning', 
                                           'validation', 'negotiation', 'closed_won', 'closed_lost']), 
              help='Filter by stage')
@click.option('--tier', type=click.IntRange(1, 4), help='Filter by tier (1-4)')
def list(region, stage, tier):
    """List all leads with optional filters"""
    
    leads = db.get_all_leads(region=region, stage=stage, tier=tier)
    
    if not leads:
        click.echo("No leads found.")
        return
    
    # Prepare table data
    headers = ['ID', 'Company', 'Region', 'Tier', 'AUM (M€)', 'Contact', 'Title', 'Stage']
    rows = []
    
    for lead in leads:
        rows.append([
            lead.id,
            lead.company[:30],
            lead.region.value,
            lead.tier.value,
            f"{lead.aum_estimate_millions:.0f}",
            lead.contact_person[:20],
            lead.title[:25],
            lead.stage.value
        ])
    
    click.echo(tabulate(rows, headers=headers, tablefmt='simple'))
    click.echo(f"\nTotal: {len(leads)} leads")

@cli.command()
@click.argument('lead_id', type=int)
@click.option('--stage', required=True, 
              type=click.Choice(['prospecting', 'discovery', 'solutioning', 
                               'validation', 'negotiation', 'closed_won', 'closed_lost']),
              help='New stage')
def update_stage(lead_id, stage):
    """Update lead stage"""
    
    lead = db.get_lead(lead_id)
    if not lead:
        click.echo(f"✗ Lead {lead_id} not found")
        return
    
    old_stage = lead.stage.value
    success = db.update_lead_stage(lead_id, stage)
    
    if success:
        click.echo(f"✓ Lead {lead_id} ({lead.company}): {old_stage} → {stage}")
    else:
        click.echo(f"✗ Failed to update lead {lead_id}")

@cli.command()
@click.argument('lead_id', type=int)
def show(lead_id):
    """Show detailed lead information"""
    
    lead = db.get_lead(lead_id)
    if not lead:
        click.echo(f"✗ Lead {lead_id} not found")
        return
    
    # Get MEDDPICC score
    meddpicc = db.get_meddpicc_score(lead_id)
    
    # Get activities
    activities = db.get_activities(lead_id)
    
    # Display lead info
    click.echo("\n" + "="*60)
    click.echo(f"LEAD: {lead.company}")
    click.echo("="*60)
    click.echo(f"ID: {lead.id}")
    click.echo(f"Region: {lead.region.value} | Tier: {lead.tier.value} | Stage: {lead.stage.value}")
    click.echo(f"AUM Estimate: €{lead.aum_estimate_millions:.0f}M")
    click.echo(f"\nContact: {lead.contact_person} ({lead.title})")
    if lead.email:
        click.echo(f"Email: {lead.email}")
    if lead.linkedin:
        click.echo(f"LinkedIn: {lead.linkedin}")
    
    if lead.pain_points:
        click.echo(f"\nPain Points: {lead.pain_points}")
    if lead.use_case:
        click.echo(f"Use Case: {lead.use_case}")
    
    click.echo(f"\nExpected Deal: €{lead.expected_deal_size_millions:.0f}M @ {lead.expected_yield:.1f}% yield")
    click.echo(f"Potential Annual Yield: €{(lead.expected_deal_size_millions * lead.expected_yield / 100):.1f}M")
    
    # Display MEDDPICC
    if meddpicc:
        click.echo("\n" + "-"*60)
        click.echo(f"MEDDPICC SCORE: {meddpicc.total_score}/80 ({meddpicc.qualification_status})")
        click.echo("-"*60)
        click.echo(f"  Metrics:          {meddpicc.metrics}/10")
        click.echo(f"  Economic Buyer:   {meddpicc.economic_buyer}/10")
        click.echo(f"  Decision Process: {meddpicc.decision_process}/10")
        click.echo(f"  Decision Criteria:{meddpicc.decision_criteria}/10")
        click.echo(f"  Paper Process:    {meddpicc.paper_process}/10")
        click.echo(f"  Pain:             {meddpicc.pain}/10")
        click.echo(f"  Champion:         {meddpicc.champion}/10")
        click.echo(f"  Competition:      {meddpicc.competition}/10")
    
    # Display activities
    click.echo("\n" + "-"*60)
    click.echo(f"ACTIVITY HISTORY ({len(activities)} entries)")
    click.echo("-"*60)
    
    if activities:
        for act in activities[:5]:  # Show last 5
            date_str = act.created_at.strftime('%Y-%m-%d') if act.created_at else 'N/A'
            click.echo(f"[{date_str}] {act.activity_type}: {act.outcome}")
            if act.notes:
                click.echo(f"  Notes: {act.notes[:80]}...")
            if act.next_steps:
                click.echo(f"  Next: {act.next_steps[:60]}...")
            click.echo()
    else:
        click.echo("No activities recorded. Use 'add-activity' to log interactions.")

@cli.command()
@click.argument('lead_id', type=int)
@click.confirmation_option(prompt='Are you sure you want to delete this lead?')
def delete(lead_id):
    """Delete a lead and all related data"""
    
    lead = db.get_lead(lead_id)
    if not lead:
        click.echo(f"✗ Lead {lead_id} not found")
        return
    
    success = db.delete_lead(lead_id)
    if success:
        click.echo(f"✓ Lead {lead_id} ({lead.company}) deleted")
    else:
        click.echo(f"✗ Failed to delete lead {lead_id}")

# MEDDPICC Commands
@cli.command()
@click.argument('lead_id', type=int)
@click.option('--metrics', type=click.IntRange(0, 10), help='Metrics score (0-10)')
@click.option('--eb', '--economic-buyer', type=click.IntRange(0, 10), help='Economic Buyer score (0-10)')
@click.option('--dp', '--decision-process', type=click.IntRange(0, 10), help='Decision Process score (0-10)')
@click.option('--dc', '--decision-criteria', type=click.IntRange(0, 10), help='Decision Criteria score (0-10)')
@click.option('--pp', '--paper-process', type=click.IntRange(0, 10), help='Paper Process score (0-10)')
@click.option('--pain', type=click.IntRange(0, 10), help='Pain score (0-10)')
@click.option('--champion', type=click.IntRange(0, 10), help='Champion score (0-10)')
@click.option('--competition', type=click.IntRange(0, 10), help='Competition score (0-10)')
def meddpicc_score(lead_id, metrics, eb, dp, dc, pp, pain, champion, competition):
    """Update MEDDPICC score for a lead"""
    
    lead = db.get_lead(lead_id)
    if not lead:
        click.echo(f"✗ Lead {lead_id} not found")
        return
    
    # Get existing score or create new
    existing = db.get_meddpicc_score(lead_id)
    
    score = MEDDPICCScore(
        lead_id=lead_id,
        metrics=metrics if metrics is not None else (existing.metrics if existing else 0),
        economic_buyer=eb if eb is not None else (existing.economic_buyer if existing else 0),
        decision_process=dp if dp is not None else (existing.decision_process if existing else 0),
        decision_criteria=dc if dc is not None else (existing.decision_criteria if existing else 0),
        paper_process=pp if pp is not None else (existing.paper_process if existing else 0),
        pain=pain if pain is not None else (existing.pain if existing else 0),
        champion=champion if champion is not None else (existing.champion if existing else 0),
        competition=competition if competition is not None else (existing.competition if existing else 0)
    )
    
    db.set_meddpicc_score(lead_id, score)
    
    click.echo(f"✓ MEDDPICC score updated for {lead.company}")
    click.echo(f"  Total: {score.total_score}/80 ({score.qualification_status})")

# Activity Commands
@cli.command()
@click.argument('lead_id', type=int)
@click.option('--type', 'activity_type', required=True, 
              type=click.Choice(['email', 'call', 'meeting', 'demo', 'proposal', 'linkedin', 'other']),
              help='Activity type')
@click.option('--notes', required=True, help='Activity notes')
@click.option('--outcome', required=True, 
              type=click.Choice(['positive', 'neutral', 'negative', 'scheduled', 'no_response']),
              help='Outcome')
@click.option('--next-steps', help='Next steps / follow-up')
def add_activity(lead_id, activity_type, notes, outcome, next_steps):
    """Add activity to a lead"""
    
    lead = db.get_lead(lead_id)
    if not lead:
        click.echo(f"✗ Lead {lead_id} not found")
        return
    
    activity = Activity(
        id=None,
        lead_id=lead_id,
        activity_type=activity_type,
        notes=notes,
        outcome=outcome,
        next_steps=next_steps or ''
    )
    
    activity_id = db.add_activity(activity)
    click.echo(f"✓ Activity added to {lead.company} (ID: {activity_id})")

# Pipeline & Reporting Commands
@cli.command()
def pipeline():
    """Show pipeline summary by stage"""
    
    by_stage = db.get_pipeline_by_stage()
    
    click.echo("\n" + "="*60)
    click.echo("PIPELINE BY STAGE")
    click.echo("="*60)
    
    headers = ['Stage', 'Count', 'Total Value (M€)']
    rows = []
    total_count = 0
    total_value = 0
    
    stage_order = ['prospecting', 'discovery', 'solutioning', 'validation', 'negotiation', 'closed_won']
    
    for stage in stage_order:
        if stage in by_stage:
            data = by_stage[stage]
            rows.append([
                stage.upper(),
                data['count'],
                f"€{data['total_value_millions']:.1f}M"
            ])
            total_count += data['count']
            total_value += data['total_value_millions']
    
    click.echo(tabulate(rows, headers=headers, tablefmt='simple'))
    click.echo("-"*60)
    click.echo(f"TOTAL: {total_count} deals, €{total_value:.1f}M pipeline")

@cli.command()
def regions():
    """Show pipeline summary by region"""
    
    by_region = db.get_pipeline_by_region()
    
    click.echo("\n" + "="*60)
    click.echo("PIPELINE BY REGION")
    click.echo("="*60)
    
    headers = ['Region', 'Count', 'Total Value (M€)']
    rows = []
    total_count = 0
    total_value = 0
    
    for region, data in sorted(by_region.items()):
        rows.append([
            region,
            data['count'],
            f"€{data['total_value_millions']:.1f}M"
        ])
        total_count += data['count']
        total_value += data['total_value_millions']
    
    click.echo(tabulate(rows, headers=headers, tablefmt='simple'))
    click.echo("-"*60)
    click.echo(f"TOTAL: {total_count} deals, €{total_value:.1f}M pipeline")

@cli.command()
@click.option('--min-score', default=50, help='Minimum MEDDPICC score (default: 50)')
def qualified(min_score):
    """Show all qualified deals (by MEDDPICC score)"""
    
    deals = db.get_qualified_deals(min_score)
    
    if not deals:
        click.echo(f"No deals with MEDDPICC score >= {min_score}")
        return
    
    click.echo(f"\n{'='*60}")
    click.echo(f"QUALIFIED DEALS (Score >= {min_score})")
    click.echo(f"{'='*60}")
    
    headers = ['ID', 'Company', 'Region', 'Stage', 'Deal (M€)', 'MEDDPICC', 'Status']
    rows = []
    
    for deal in deals:
        rows.append([
            deal['id'],
            deal['company'][:25],
            deal['region'],
            deal['stage'],
            f"€{deal['expected_deal_size_millions']:.0f}M",
            deal['total_score'],
            deal['qualification_status']
        ])
    
    click.echo(tabulate(rows, headers=headers, tablefmt='simple'))
    click.echo(f"\nTotal: {len(deals)} qualified deals")

@cli.command()
@click.argument('filepath')
def export(filepath):
    """Export all data to JSON file"""
    
    db.export_to_json(filepath)
    click.echo(f"✓ Data exported to {filepath}")

# Quick Commands
@cli.command()
@click.argument('company')
def quick_add(company):
    """Quick add lead with minimal info (edit later with 'show' and 'update')"""
    
    click.echo(f"\nQuick add for: {company}")
    click.echo("Enter basic info (you can update details later):")
    
    region = click.prompt('Region', type=click.Choice(['DE', 'CH', 'UK', 'UAE', 'NORDICS']))
    tier = click.prompt('Tier (1-4)', type=click.IntRange(1, 4))
    aum = click.prompt('AUM Estimate (M€)', type=float)
    contact = click.prompt('Contact Name')
    title = click.prompt('Contact Title')
    
    lead = Lead(
        id=None,
        company=company,
        region=Region(region),
        tier=Tier(tier),
        aum_estimate_millions=aum,
        contact_person=contact,
        title=title
    )
    
    lead_id = db.create_lead(lead)
    
    # Init MEDDPICC
    score = MEDDPICCScore(lead_id=lead_id)
    db.set_meddpicc_score(lead_id, score)
    
    click.echo(f"\n✓ Lead created: {company} (ID: {lead_id})")
    click.echo(f"  Run 'show {lead_id}' to view/edit details")

if __name__ == '__main__':
    cli()
