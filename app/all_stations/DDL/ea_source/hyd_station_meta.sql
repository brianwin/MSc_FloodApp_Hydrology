create table if not exists ea_source.hyd_station_meta
(
    station_meta_id serial primary key,
    created         timestamp default CURRENT_TIMESTAMP,
    source          TEXT,
    publisher       TEXT,
    license         TEXT,
    "licenseName"   TEXT,
    documentation   TEXT,
    version         TEXT,
    comment         TEXT,
    "hasFormat"     TEXT
);

alter table ea_source.hyd_station_meta
    owner to wmon;

