CREATE TABLE IF NOT EXISTS production.reading_concise (
	created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NULL,
	"source" TEXT NOT NULL,
	r_datetime TIMESTAMPTZ NOT NULL,
	r_month date,
	r_date date,
	measure TEXT NOT NULL,
	x_measure TEXT NOT NULL,
	station TEXT,
	"label" TEXT,
	stationreference TEXT,
	"parameter" TEXT,
	qualifier TEXT,
	datumtype TEXT,
	"period" int4 ,
	unitname TEXT,
	valuetype TEXT,
	value numeric(15, 3)
);


alter table reading_concise
    owner to wmon;

ALTER TABLE reading_concise ADD CONSTRAINT reading_concise_pk PRIMARY KEY (x_measure, r_datetime);

create index if not exists reading_concise_r_datetime_idx on reading_concise (r_datetime desc);
create index if not exists reading_concise_r_date_idx on reading_concise (r_date desc);

-- Make it a hypertable (TimescaleDB)
SELECT create_hypertable('production.reading_concise', 'r_datetime', if_not_exists => TRUE);
