create table if not exists production.floodarea
(
    floodarea_id      integer not null
        primary key
        constraint fk_floodarea_floodarea_id
            references ea_source.floodarea_json
            on delete cascade,
    created           timestamp default CURRENT_TIMESTAMP,
    "EnvAgy_id"       varchar(256),
    county            varchar(256),
    description       varchar(1024),
    "eaAreaName"      varchar(256),
    "eaRegionName"    varchar(256),
    "floodWatchArea"  varchar(256),
    "fwdCode"         varchar(256),
    label             varchar(256),
    lat               double precision,
    long              double precision,
    notation          varchar(256),
    polygon           varchar(2048),
    "quickDialNumber" varchar(256),
    "riverOrSea"      varchar(1024),
    geom4326          geometry(Point, 4326),
    geom27700         geometry(Point, 27700)
);

alter table floodarea
    owner to wmon;

create index if not exists idx_floodarea_fwdcode
    on floodarea ("fwdCode");

create index if not exists idx_floodarea_lat_long
    on floodarea (lat, long);

