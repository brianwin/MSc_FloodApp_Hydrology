CREATE TABLE IF NOT EXISTS production.reading_recent (
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


alter table reading_recent
    owner to wmon;

ALTER TABLE reading_recent ADD CONSTRAINT reading_recent_pk PRIMARY KEY (x_measure, r_datetime);

create index if not exists reading_recent_r_datetime_idx on reading_recent (r_datetime desc);
create index if not exists reading_recent_r_date_idx on reading_recent (r_date desc);

create index if not exists reading_recent_created_idx on reading_recent (created desc);
create index if not exists reading_recent_created_day_idx on reading_recent (date_trunc('day', created at time zone 'UTC') desc);

-- Make it a hypertable (TimescaleDB)
SELECT create_hypertable('production.reading_recent', 'r_datetime', if_not_exists => TRUE);


/*
create index if not exists idx_reading_recent_source
    on reading (source);

create index if not exists idx_reading_recent_stationreference
    on reading (stationreference);
*/


create view v_reading_recent_by_exec as
select created, min(rr.r_datetime ), max(rr.r_datetime ), count(*), COUNT(DISTINCT rr.measure) AS measure_count
from reading_recent rr
group by created
order by created desc;

drop view v_reading_recent_by_day;
create view v_reading_recent_by_day as
select date_trunc('day', created at time zone 'UTC'), min(rr.r_datetime ), max(rr.r_datetime ), count(*), COUNT(DISTINCT rr.measure) AS measure_count
from reading_recent rr
group by date_trunc('day', created at time zone 'UTC')
order by date_trunc('day', created at time zone 'UTC') desc;
