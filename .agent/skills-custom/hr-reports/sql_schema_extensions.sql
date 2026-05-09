-- HR Reports Generator - Schema Extensions for WEEK 2
-- Tables for attendance tracking and report generation

-- Attendance records table
CREATE TABLE IF NOT EXISTS attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    date DATE NOT NULL,
    clock_in TIME,
    clock_out TIME,
    hours_worked DECIMAL(5, 2),
    status TEXT DEFAULT 'present',  -- present, absent, late, early_leave, excused_absence
    reason TEXT,
    notes TEXT,
    recorded_by TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, date),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

-- HR reports table for caching/auditing
CREATE TABLE IF NOT EXISTS hr_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,  -- roster, hours, dispatch, absence
    report_name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    generated_by TEXT NOT NULL,
    file_path TEXT,
    file_format TEXT DEFAULT 'xlsx',  -- xlsx, html, csv
    total_records INTEGER DEFAULT 0,
    status TEXT DEFAULT 'completed',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash_value TEXT UNIQUE
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_attendance_employee_date ON attendance_records(employee_id, date);
CREATE INDEX IF NOT EXISTS idx_attendance_date_range ON attendance_records(date);
CREATE INDEX IF NOT EXISTS idx_hr_reports_type ON hr_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_hr_reports_date_range ON hr_reports(start_date, end_date);
