BEGIN;
/*
-- To rebuild the "floodarea" part of the database model from scratch, remove the existing schema objects first (uncomment this section)
--drop table production.floodalerts_hist cascade;
drop table production.floodarea_metrics cascade;
drop table production.floodarea_polygons cascade;
drop table production.floodarea cascade;

drop table ea_source.floodarea_json cascade;
drop table ea_source.floodarea_meta cascade;
*/

/*
-- To retain the structure but remove all data prior to re-population:
--select floodarea_meta_id as pk, count(*) from floodarea_json group by floodarea_meta_id;
-- pick a pk from these results

--delete from floodarea_meta where floodarea_meta_id = <pk from previous results>;
--commit;
*/

\i ea_source/floodarea_meta.sql
\i ea_source/floodarea_json.sql

\i production/floodarea.sql
\i production/floodarea_polygons.sql
\i production/floodarea_metrics.sql

\i production/v_floodareaview.sql

COMMIT;