create table if not exists production.station_complex_measure
(
    station_measure_id serial
        primary key,
    created            timestamp default CURRENT_TIMESTAMP,
    station_id         integer
        constraint fk_station_complex_measure_station_id
            references station_complex
            on delete cascade,
    "EnvAgy_id"        varchar(256),
    parameter          varchar(256),
    "parameterName"    varchar(256),
    period             integer,
    qualifier          varchar(256),
    "unitName"         varchar(256)
);

alter table station_complex_measure
    owner to wmon;

create index if not exists idx_station_complex_measure_station_id
    on station_complex_measure (station_id);

