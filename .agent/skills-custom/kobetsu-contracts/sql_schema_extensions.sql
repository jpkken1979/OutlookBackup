-- SQL Schema Extensions for Kobetsu Contracts Generator
-- Individual Dispatch Contract (個別派遣契約) storage

CREATE TABLE IF NOT EXISTS kobetsu_contracts (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    contract_number TEXT NOT NULL UNIQUE,
    contract_date DATE NOT NULL,
    effective_date DATE NOT NULL,
    expiration_date DATE,

    dispatch_company TEXT DEFAULT 'UNS',
    client_company TEXT,
    job_title TEXT NOT NULL,

    work_location TEXT NOT NULL,
    work_hours_daily REAL DEFAULT 8.0,
    work_days_weekly INTEGER DEFAULT 5,

    hourly_rate_jpy REAL NOT NULL,
    monthly_minimum_hours REAL,

    benefits TEXT,
    terms_conditions TEXT,
    notes TEXT,

    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    template_version TEXT DEFAULT '1.0',

    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_kobetsu_employee_id ON kobetsu_contracts(employee_id);
CREATE INDEX IF NOT EXISTS idx_kobetsu_contract_number ON kobetsu_contracts(contract_number);
CREATE INDEX IF NOT EXISTS idx_kobetsu_expiration ON kobetsu_contracts(expiration_date);

-- Audit table for contract version tracking
CREATE TABLE IF NOT EXISTS kobetsu_contracts_audit (
    id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    previous_value TEXT,
    new_value TEXT,
    changed_by TEXT,

    FOREIGN KEY (contract_id) REFERENCES kobetsu_contracts(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_contract_id ON kobetsu_contracts_audit(contract_id);
