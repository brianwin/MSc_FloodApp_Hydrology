BEGIN;
/*
-- To rebuild the "station" part of the database model from scratch, remove the existing schema objects first (uncomment this section)
drop table production.station_complex_scale cascade;
drop table production.station_complex_measure cascade;
drop table production.station_complex cascade;

drop table production.station_scale cascade;
drop table production.station_measure cascade;
drop table production.station cascade;

drop table ea_source.station_json cascade;
drop table ea_source.station_meta cascade;
*/

/*
-- To retain the structure but remove all data prior to re-population:
--select station_meta_id as pk, count(*) from station_json group by station_meta_id;
-- pick a pk from these results

--delete from station_meta where station_meta_id = <pk from previous results>;
--commit;

OR alternatively (in this order)

truncate table production.station_complex_scale;
truncate table production.station_complex_measure;
truncate table production.station_complex;

truncate table production.station_scale;
truncate table production.station_measure;
truncate table production.station;

truncate table ea_source.station_json;
truncate table ea_source.station_meta;
*/

\i ea_source/station_meta.sql
\i ea_source/station_json.sql

\i production/station.sql
\i production/station_measure.sql
\i production/station_scale.sql

\i production/station_complex.sql
\i production/station_complex_measure.sql
\i production/station_complex_scale.sql

COMMIT;