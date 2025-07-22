create table if not exists production.station
(
    station_id         integer not null
        primary key
        constraint fk_station_station_id
            references ea_source.station_json
            on delete cascade,
    created            timestamp default CURRENT_TIMESTAMP,
    "EnvAgy_id"        varchar(256),
    "RLOIid"           integer,
    "catchmentName"    varchar(256),
    "dateOpened"       timestamp,
    northing           double precision,
    easting            double precision,
    label              varchar(256),
    lat                double precision,
    long               double precision,
    notation           varchar(256),
    "riverName"        varchar(256),
    "stationReference" varchar(256),
    status             varchar(256),
    town               varchar(256),
    "wiskiID"          varchar(256),
    "gridReference"    varchar(256),
    "datumOffset"      double precision,
    "stageScale"       varchar(256),
    "downstageScale"   varchar(256),
    geom4326           geometry(Point, 4326),
    geom27700          geometry(Point, 27700)
);

alter table station
    owner to wmon;

