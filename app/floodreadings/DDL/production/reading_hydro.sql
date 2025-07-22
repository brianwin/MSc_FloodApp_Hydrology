CREATE TABLE IF NOT EXISTS production.reading_hydro (
	created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NULL,
	"source" TEXT NOT NULL,
	r_datetime TIMESTAMPTZ NOT NULL,
	r_month date,
	r_date date,
	measure TEXT NOT NULL,
	notation TEXT NOT NULL,

    station_id TEXT,
	parameter_name TEXT,
	"parameter" TEXT,
	qualifier TEXT,
	value_type TEXT,
	period_name TEXT,
    period int,
	unit_name TEXT,
	observation_type TEXT,
    datum_type TEXT,
	"label" TEXT,
	stationreference TEXT,

	value numeric(15, 3),

    completeness TEXT,
    quality TEXT,
    qcode TEXT,
    valid TEXT,
    invalid	TEXT,
    missing TEXT
);


alter table reading_hydro
    owner to wmon;

ALTER TABLE reading_hydro ADD CONSTRAINT reading_hydro_pk PRIMARY KEY (notation, r_datetime);

create index if not exists reading_hydro_r_datetime_idx on reading_hydro (r_datetime desc);
create index if not exists reading_hydro_r_date_idx on reading_hydro (r_date desc);

-- Make it a hypertable (TimescaleDB)
SELECT create_hypertable('production.reading_hydro', 'r_datetime', if_not_exists => TRUE);



create index if not exists idx_reading_hydro_source
    on reading_hydro (source);

create index if not exists idx_reading_hydro_r_datetime_idx
    on reading_hydro (r_datetime desc);
