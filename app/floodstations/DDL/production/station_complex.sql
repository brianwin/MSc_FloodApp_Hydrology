create table if not exists production.station_complex
(
    station_id         integer not null
        primary key
        constraint fk_station_complex_station_id
            references ea_source.station_json
            on delete cascade,
    created            timestamp default CURRENT_TIMESTAMP,
    "EnvAgy_id"        varchar(256),
    "RLOIid"           jsonb,
    "catchmentName"    varchar(256),
    "dateOpened"       timestamp,
    northing           jsonb,
    easting            jsonb,
    label              jsonb,
    lat                jsonb,
    long               jsonb,
    notation           varchar(256),
    "riverName"        varchar(256),
    "stationReference" varchar(256),
    status             jsonb,
    town               varchar(256),
    "wiskiID"          varchar(256),
    "gridReference"    varchar(256),
    "datumOffset"      double precision,
    "stageScale"       varchar(256),
    "downstageScale"   varchar(256),
    geom4326           geometry(Point, 4326),
    geom27700          geometry(Point, 27700)
);

alter table station_complex
    owner to wmon;

