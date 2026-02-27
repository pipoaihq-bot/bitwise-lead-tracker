-- StakeStream Schema für Supabase
-- Ausführen in: Supabase → SQL Editor → New Query → Run

-- 1. Leads
CREATE TABLE IF NOT EXISTS leads (
    id BIGSERIAL PRIMARY KEY,
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
    employee_count TEXT,
    industry TEXT,
    sub_region TEXT,
    company_type TEXT,
    funding_stage TEXT,
    year_founded INTEGER,
    tech_stack TEXT,
    staking_readiness TEXT,
    data_enriched BOOLEAN DEFAULT FALSE,
    enriched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. MEDDPICC Scores
CREATE TABLE IF NOT EXISTS meddpicc_scores (
    id BIGSERIAL PRIMARY KEY,
    lead_id BIGINT UNIQUE NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
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
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Activities
CREATE TABLE IF NOT EXISTS activities (
    id BIGSERIAL PRIMARY KEY,
    lead_id BIGINT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    activity_type TEXT,
    notes TEXT,
    outcome TEXT,
    next_steps TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'P2',
    category TEXT DEFAULT 'OUTREACH',
    target_company TEXT,
    target_contact TEXT,
    due_date TEXT,
    linkedin_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Disable RLS für alle Tabellen (für jetzt)
ALTER TABLE leads DISABLE ROW LEVEL SECURITY;
ALTER TABLE meddpicc_scores DISABLE ROW LEVEL SECURITY;
ALTER TABLE activities DISABLE ROW LEVEL SECURITY;
ALTER TABLE tasks DISABLE ROW LEVEL SECURITY;

-- 6. Index für Performance
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
CREATE INDEX IF NOT EXISTS idx_leads_region ON leads(region);
CREATE INDEX IF NOT EXISTS idx_leads_meddpicc ON meddpicc_scores(total_score DESC);
