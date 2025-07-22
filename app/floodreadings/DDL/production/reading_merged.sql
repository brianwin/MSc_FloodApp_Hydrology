CREATE TABLE IF NOT EXISTS production.reading_merged (
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


alter table reading_merged
    owner to wmon;

ALTER TABLE reading_merged ADD CONSTRAINT reading_merged_pk PRIMARY KEY (x_measure, r_datetime);

create index if not exists reading_merged_r_datetime_idx on reading_merged (r_datetime desc);
create index if not exists reading_merged_r_date_idx on reading_merged (r_date desc);

-- Make it a hypertable (TimescaleDB)
SELECT create_hypertable('production.reading_merged', 'r_datetime', if_not_exists => TRUE);



create index if not exists idx_reading_source
    on reading (source);

create index if not exists idx_reading_stationreference
    on reading (stationreference);

create index if not exists idx_reading_r_datetime_idx
    on reading (r_datetime desc);
