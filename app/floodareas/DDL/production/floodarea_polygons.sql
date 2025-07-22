create table if not exists production.floodarea_polygons
(
    floodarea_id integer not null
        primary key
        constraint fk_floodarea_polygons_floodarea_id
            references floodarea
            on delete cascade,
    created      timestamp default CURRENT_TIMESTAMP,
    "fwdCode"    varchar(256),
    lat          double precision,
    long         double precision,
    geom4326     geometry(Point, 4326),
    geom27700    geometry(Point, 27700),
    polygon_json jsonb,
    polygon_geom geometry(MultiPolygon, 4326)
);

alter table floodarea_polygons
    owner to wmon;

create index if not exists idx_floodarea_polygons_lat_long
    on floodarea_polygons (lat, long);

