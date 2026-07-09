-- COSMO CONSTITUTIONAL LEDGER SCHEMA
-- Phase 0: truth substrate for the Republic

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS market_entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT,
    physical_inputs TEXT,
    dependent_companies TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ledger (
    proposal_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    bill_type TEXT NOT NULL,
    justification TEXT NOT NULL,
    evidence_class TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS graveyard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    cause_of_death TEXT NOT NULL,
    kill_date TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    audit_log_ref TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    proposal_type TEXT NOT NULL,
    target_entity TEXT,
    thesis TEXT NOT NULL,
    evidence_json TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposal_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    vote TEXT NOT NULL,
    rationale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposal_id) REFERENCES proposals(id)
);

CREATE TABLE IF NOT EXISTS governance_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL UNIQUE,
    rule_definition TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- REALITY LEDGER: Ground Truth for Causal Reasoning
-- Logs every human decision and its outcome for Ghost listener to learn from
CREATE TABLE IF NOT EXISTS reality_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ticker TEXT NOT NULL,
    
    -- The Causal Thesis (The Mechanism)
    trigger_event TEXT NOT NULL,           -- e.g., "Macro_War_Oil_Cascade"
    causal_mechanism TEXT NOT NULL,        -- e.g., "AI-HBM-Copper-Melt"
    
    -- Physical Realities (Pillar 11 Overlay)
    physical_dependency TEXT,              -- e.g., "Gallium_Magnesium_Squeeze"
    
    -- Evidence Classification
    evidence_tag TEXT NOT NULL,            -- [MEASURED] [LITERATURE] [HYPOTHESIS] [DELETED]
    evidence_json TEXT,                    -- Supporting data
    
    -- Reasoning Trace (Chain of Thought)
    reasoning_trace TEXT,                  -- Full trace from human or council
    action_taken TEXT NOT NULL,            -- BUY, SELL, HOLD, PASS
    
    -- Outcome (Ground Truth)
    outcome_1d REAL,                       -- 1-day return %
    outcome_5d REAL,                       -- 5-day return %
    outcome_end_period REAL,               -- End of defined period return %
    
    -- Accountability
    truth_score REAL,                      -- Graded vs Reality (0.0-1.0)
    notes TEXT,                            -- Human notes on why this succeeded/failed
    
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reality_ledger_ticker ON reality_ledger(ticker);
CREATE INDEX IF NOT EXISTS idx_reality_ledger_causal_mechanism ON reality_ledger(causal_mechanism);
CREATE INDEX IF NOT EXISTS idx_reality_ledger_trigger_event ON reality_ledger(trigger_event);
