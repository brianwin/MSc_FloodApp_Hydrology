create table if not exists ea_source.station_meta
(
    station_meta_id serial
        primary key,
    created         timestamp default CURRENT_TIMESTAMP,
    context         varchar(256),
    publisher       varchar(256),
    licence         varchar(256),
    documentation   varchar(256),
    version         numeric(2, 1),
    comment         varchar(256),
    "hasFormat"     varchar(2048)
);

alter table ea_source.station_meta
    owner to wmon;

