create view v_floodareaview
            (floodarea_id, "fwdCode", "eaAreaName", county, description, label, "riverOrSea", lat, long,
             bbox_wgs84_min_lat, bbox_wgs84_min_long, bbox_wgs84_max_lat, bbox_wgs84_max_long, bcen_bng_lat,
             bcen_bng_long, mpoly_cent_wgs84_lat, mpoly_cent_wgs84_long, area_m2, area_km2, rank, polygon_json)
as
SELECT f.floodarea_id,
       f."fwdCode",
       f."eaAreaName",
       f.county,
       f.description,
       f.label,
       f."riverOrSea",
       fp.lat,
       fp.long,
       fm.bbox_wgs84_min_lat,
       fm.bbox_wgs84_min_long,
       fm.bbox_wgs84_max_lat,
       fm.bbox_wgs84_max_long,
       fm.bcen_bng_lat,
       fm.bcen_bng_long,
       fm.mpoly_cent_wgs84_lat,
       fm.mpoly_cent_wgs84_long,
       fm.area_m2,
       fm.area_km2,
       fm.rank,
       fp.polygon_json
FROM floodarea f
         LEFT JOIN floodarea_polygons fp ON f.floodarea_id = fp.floodarea_id
         LEFT JOIN floodarea_metrics fm ON f.floodarea_id = fm.floodarea_id;

alter table v_floodareaview
    owner to wmon;

