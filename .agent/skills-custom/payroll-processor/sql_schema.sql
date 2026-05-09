-- Payroll Processor — SQLite Schema
-- UNS Nóminas (給与管理)
-- Created: 2026-04-03
-- PHASE 3: Performance optimization applied

-- ============================================================================
-- PRAGMA: Performance optimizations
-- ============================================================================
-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- WAL mode (Write-Ahead Logging) for better concurrency
PRAGMA journal_mode = WAL;

-- Memory-mapped I/O (30MB for faster reads)
PRAGMA mmap_size = 30000000;

-- Increase page cache size (from default 2000 to 10000 pages)
PRAGMA cache_size = -10000;

-- Synchronous mode: NORMAL (balance between safety and speed)
PRAGMA synchronous = NORMAL;

-- Temporary storage in memory for sorting/joins
PRAGMA temp_store = MEMORY;

-- ============================================================================
-- TABLE: employee_master (従業員マスタ)
-- ============================================================================
CREATE TABLE IF NOT EXISTS employee_master (
    -- Primary key
    id TEXT PRIMARY KEY,                    -- Employee ID (e.g., 'W001', 'W002')

    -- Personal info
    name_jp TEXT NOT NULL,                  -- 氏名 (Japanese name)
    name_en TEXT,                           -- 氏名 (English name)
    email TEXT UNIQUE NOT NULL,             -- メール
    phone TEXT,                             -- 電話番号

    -- Employment details
    contract_type TEXT NOT NULL,            -- 契約タイプ: seishain, hakken, kobetsu, part_time
    status TEXT DEFAULT 'active',           -- ステータス: active, on_leave, suspended, terminated
    hire_date DATE NOT NULL,                -- 入社日
    termination_date DATE,                  -- 退職日

    -- Compensation
    hourly_rate_jpy REAL NOT NULL           -- 時給 (¥)
        CHECK (hourly_rate_jpy > 800),      -- Minimum legal rate in Japan
    monthly_salary_jpy REAL,                -- 月給 (¥) for salaried employees

    -- Tax & Insurance rates (customizable per employee)
    income_tax_rate REAL DEFAULT 0.10,      -- 所得税 (10%)
    social_insurance_rate REAL DEFAULT 0.0985,  -- 社会保険 (9.85%)
    employment_insurance_rate REAL DEFAULT 0.004,  -- 雇用保険 (0.4%)

    -- Organization
    department TEXT,                        -- 部門 (Department)
    manager_id TEXT,                        -- マネージャーID (Manager employee ID)

    -- Bank details (for salary transfer - 振込)
    bank_name TEXT,                         -- 銀行名
    account_number TEXT,                    -- 口座番号
    account_holder TEXT,                    -- 口座名義人

    -- Metadata
    notes TEXT,                             -- 備考 (Notes)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key (manager)
    FOREIGN KEY (manager_id) REFERENCES employee_master(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

-- Create indices for faster queries
-- PHASE 3: Composite indices for common filter combinations
CREATE INDEX IF NOT EXISTS idx_employee_status ON employee_master(status);
CREATE INDEX IF NOT EXISTS idx_employee_department ON employee_master(department);
CREATE INDEX IF NOT EXISTS idx_employee_contract_type ON employee_master(contract_type);
CREATE INDEX IF NOT EXISTS idx_employee_hire_date ON employee_master(hire_date);

-- Composite indices for common query patterns
CREATE INDEX IF NOT EXISTS idx_employee_status_department
    ON employee_master(status, department);
CREATE INDEX IF NOT EXISTS idx_employee_contract_status
    ON employee_master(contract_type, status);
CREATE INDEX IF NOT EXISTS idx_employee_department_hire
    ON employee_master(department, hire_date);

-- ============================================================================
-- TABLE: payroll_records (給与計算記録)
-- ============================================================================
CREATE TABLE IF NOT EXISTS payroll_records (
    -- Primary key
    id TEXT PRIMARY KEY,                    -- Payslip ID (e.g., 'PAYSLIP-20260201-W001')

    -- Reference & Period
    employee_id TEXT NOT NULL,              -- Reference to employee_master
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2099),
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),

    -- Hours worked
    regular_hours REAL DEFAULT 0.0          -- 通常勤務時間 (Regular hours)
        CHECK (regular_hours >= 0 AND regular_hours <= 200),
    overtime_hours REAL DEFAULT 0.0         -- 残業時間 (Overtime hours)
        CHECK (overtime_hours >= 0 AND overtime_hours <= 45),  -- 36協定 limit
    night_shift_hours REAL DEFAULT 0.0,     -- 夜勤時間 (Night shift)

    -- Pay calculation
    regular_pay REAL DEFAULT 0.0,           -- 通常給 (Regular pay)
    overtime_pay REAL DEFAULT 0.0,          -- 残業代 (Overtime pay)
    night_shift_pay REAL DEFAULT 0.0,       -- 夜勤手当 (Night shift premium)
    bonus REAL DEFAULT 0.0,                 -- 賞与 (Bonus)
    other_earnings REAL DEFAULT 0.0,        -- その他支給額 (Other earnings)
    gross_pay REAL NOT NULL,                -- 総支給額 (Total earnings before deductions)

    -- Deductions (控除)
    income_tax REAL DEFAULT 0.0,            -- 所得税 (Income tax)
    social_insurance REAL DEFAULT 0.0,      -- 社会保険 (Social insurance)
    employment_insurance REAL DEFAULT 0.0,  -- 雇用保険 (Employment insurance)
    health_insurance REAL DEFAULT 0.0,      -- 健康保険 (Health insurance)
    pension_contribution REAL DEFAULT 0.0,  -- 厚生年金 (Pension contribution)
    other_deductions REAL DEFAULT 0.0,      -- その他控除 (Other deductions)
    total_deductions REAL DEFAULT 0.0,      -- 控除合計 (Total deductions)

    -- Net pay
    net_pay REAL NOT NULL,                  -- 手取り額 (Net pay = gross - deductions)

    -- Metadata
    notes TEXT,                             -- 備考
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(employee_id, year, month),       -- One payslip per employee per month
    FOREIGN KEY (employee_id) REFERENCES employee_master(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- Create indices for faster queries
CREATE INDEX IF NOT EXISTS idx_payroll_employee_date
    ON payroll_records(employee_id, year, month);
CREATE INDEX IF NOT EXISTS idx_payroll_date
    ON payroll_records(year, month);
CREATE INDEX IF NOT EXISTS idx_payroll_generated
    ON payroll_records(generated_at);

-- ============================================================================
-- TABLE: payroll_history (給与計算履歴)
-- ============================================================================
CREATE TABLE IF NOT EXISTS payroll_history (
    -- Primary key
    id TEXT PRIMARY KEY,                    -- History ID (auto-generated)

    -- Reference
    payslip_id TEXT NOT NULL,               -- Reference to payroll_records

    -- Version control
    version INTEGER DEFAULT 1,              -- Version number (1, 2, 3, ... if revised)
    status TEXT DEFAULT 'draft',            -- draft, approved, paid, archived

    -- Changes tracking
    changed_by TEXT,                        -- User who made changes
    change_reason TEXT,                     -- Reason for change (if correction)

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    paid_at TIMESTAMP,

    -- Foreign key
    FOREIGN KEY (payslip_id) REFERENCES payroll_records(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_payroll_history_payslip
    ON payroll_history(payslip_id, version);

-- ============================================================================
-- VIEW: payroll_summary (給与サマリー)
-- ============================================================================
CREATE VIEW IF NOT EXISTS payroll_summary AS
SELECT
    year,
    month,
    COUNT(DISTINCT employee_id) as employee_count,
    SUM(gross_pay) as total_gross,
    SUM(total_deductions) as total_deductions,
    SUM(net_pay) as total_net_pay,
    AVG(net_pay) as avg_net_pay,
    MIN(net_pay) as min_net_pay,
    MAX(net_pay) as max_net_pay
FROM payroll_records
GROUP BY year, month;

-- ============================================================================
-- TRIGGER: Update employee_master.updated_at on modification
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS employee_master_updated_trigger
AFTER UPDATE ON employee_master
FOR EACH ROW
BEGIN
    UPDATE employee_master
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- ============================================================================
-- TRIGGER: Update payroll_records.updated_at on modification
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS payroll_records_updated_trigger
AFTER UPDATE ON payroll_records
FOR EACH ROW
BEGIN
    UPDATE payroll_records
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- ============================================================================
-- Sample Data (for testing - to be deleted before production)
-- ============================================================================
-- Insert test employee (if not exists)
INSERT OR IGNORE INTO employee_master (
    id, name_jp, name_en, email, contract_type, hire_date, hourly_rate_jpy, department
) VALUES (
    'W001',
    '田中 太郎',
    'Taro Tanaka',
    'tanaka@uns-kikaku.com',
    'hakken',
    DATE('2024-01-01'),
    1250.0,
    'Operations'
);

-- ============================================================================
-- Initialization complete
-- ============================================================================
-- Tables: employee_master, payroll_records, payroll_history
-- Views: payroll_summary
-- Indices: Multiple for performance optimization
-- Triggers: Auto-update timestamps
