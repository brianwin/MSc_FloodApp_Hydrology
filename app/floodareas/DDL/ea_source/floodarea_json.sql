create table if not exists ea_source.floodarea_json
(
    floodarea_id      serial
        primary key,
    created           timestamp default CURRENT_TIMESTAMP,
    floodarea_meta_id integer
        constraint fk_floodarea_json_floodarea_meta_id
            references ea_source.floodarea_meta
            on delete cascade,
    floodarea_data    jsonb
);

alter table ea_source.floodarea_json
    owner to wmon;

create index if not exists idx_floodarea_json_floodarea_meta_id
    on ea_source.floodarea_json (floodarea_meta_id);

