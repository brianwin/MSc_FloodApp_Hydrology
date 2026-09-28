CREATE TABLE IF NOT EXISTS production.hydrology_load_run (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    command TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    start_date DATE,
    end_date DATE,
    gaps_only BOOLEAN NOT NULL DEFAULT FALSE,
    force_replace_file BOOLEAN NOT NULL DEFAULT FALSE,
    force_replace_db BOOLEAN NOT NULL DEFAULT FALSE,
    requested_dates INTEGER NOT NULL DEFAULT 0,
    completed_dates INTEGER NOT NULL DEFAULT 0,
    failed_dates INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS production.hydrology_daily_profile (
    id BIGSERIAL PRIMARY KEY,
    load_run_id BIGINT REFERENCES production.hydrology_load_run(id) ON DELETE SET NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    profile_kind TEXT NOT NULL DEFAULT 'post_load',
    r_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'succeeded',
    before_row_count BIGINT,
    source_row_count BIGINT,
    after_row_count BIGINT,
    station_count INTEGER,
    measure_count INTEGER,
    first_reading_at TIMESTAMPTZ,
    last_reading_at TIMESTAMPTZ,
    rows_deleted BIGINT NOT NULL DEFAULT 0,
    rows_inserted BIGINT NOT NULL DEFAULT 0,
    rows_updated BIGINT NOT NULL DEFAULT 0,
    rows_affected BIGINT NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS hydrology_daily_profile_date_idx
    ON production.hydrology_daily_profile (r_date, recorded_at);
CREATE INDEX IF NOT EXISTS hydrology_daily_profile_run_idx
    ON production.hydrology_daily_profile (load_run_id);

ALTER TABLE production.hydrology_load_run OWNER TO wmon;
ALTER TABLE production.hydrology_daily_profile OWNER TO wmon;
