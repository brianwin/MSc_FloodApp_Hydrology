create table if not exists production.station_complex_scale
(
    station_scale_id         serial
        primary key,
    created                  timestamp default CURRENT_TIMESTAMP,
    station_id               integer
        constraint fk_station_complex_scale_station_id
            references station_complex
            on delete cascade,
    "EnvAgy_id"              varchar(256),
    "highestRecent_id"       varchar(256),
    "highestRecent_dateTime" timestamp,
    "highestRecent_value"    numeric(8, 3),
    "maxOnRecord_id"         varchar(256),
    "maxOnRecord_dateTime"   timestamp,
    "maxOnRecord_value"      numeric(8, 3),
    "minOnRecord_id"         varchar(256),
    "minOnRecord_dateTime"   timestamp,
    "minOnRecord_value"      numeric(8, 3),
    "scaleMax"               integer,
    "typicalRangeHigh"       numeric(8, 3),
    "typicalRangeLow"        numeric(8, 3)
);

alter table station_complex_scale
    owner to wmon;

create index if not exists idx_station_complex_scale_station_id
    on station_complex_scale (station_id);

