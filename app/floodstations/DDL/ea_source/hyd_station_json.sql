create table if not exists ea_source.hyd_station_json
(
    station_id      serial primary key,
    created         timestamp default CURRENT_TIMESTAMP,
    station_meta_id integer
        constraint fk_station_json_station_meta_id
            references ea_source.hyd_station_meta
            on delete cascade,
    station_data    jsonb
);

alter table ea_source.hyd_station_json
    owner to wmon;

create index if not exists idx_hyd_station_json_station_meta_id
    on ea_source.hyd_station_json (station_meta_id);

