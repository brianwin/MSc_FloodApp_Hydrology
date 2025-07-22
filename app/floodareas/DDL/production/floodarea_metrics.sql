create table if not exists production.floodarea_metrics
(
    floodarea_id          integer not null
        primary key
        constraint fk_floodarea_metrics_floodarea_id
            references floodarea
            on delete cascade,
    created               timestamp default CURRENT_TIMESTAMP,
    "fwdCode"             varchar(256),
    bbox_wgs84_min_lat    double precision,
    bbox_wgs84_min_long   double precision,
    bbox_wgs84_max_lat    double precision,
    bbox_wgs84_max_long   double precision,
    bcen_wgs84_lat        double precision,
    bcen_wgs84_long       double precision,
    mpoly_cent_wgs84_lat  double precision,
    mpoly_cent_wgs84_long double precision,
    geom_bbox_wgs84       geometry(Polygon, 4326),
    geom_bcen_wgs84       geometry(Point, 4326),
    geom_mpoly_cent_wgs84 geometry(Point, 4326),
    bbox_bng_min_lat      double precision,
    bbox_bng_min_long     double precision,
    bbox_bng_max_lat      double precision,
    bbox_bng_max_long     double precision,
    bcen_bng_lat          double precision,
    bcen_bng_long         double precision,
    mpoly_cent_bng_lat    double precision,
    mpoly_cent_bng_long   double precision,
    geom_bbox_bng         geometry(Polygon, 27700),
    geom_bcen_bng         geometry(Point, 27700),
    geom_mpoly_cent_bng   geometry(Point, 27700),
    area_km2              double precision,
    area_m2               double precision,
    rank                  integer
);

alter table floodarea_metrics
    owner to wmon;

