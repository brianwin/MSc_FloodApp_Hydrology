--Table: hyd_station
--(Represents the main object inside each item.)
CREATE TABLE hyd_station (
    id                  SERIAL PRIMARY KEY,
    json_id             TEXT UNIQUE,          -- maps to "@id"
    label               TEXT,
    notation            TEXT,
    easting             TEXT,
    northing            TEXT,
    lat                 TEXT,
    long                TEXT,
    catchment_name      TEXT,
    river_name          TEXT,
    town                TEXT,
    station_guid        TEXT,
    station_reference   TEXT,
    wiski_id            TEXT,
    rloi_id             TEXT,
    rloi_station_link   TEXT,
    catchment_area      NUMERIC,
    date_opened         TEXT,
    date_closed         TEXT,
    nrfa_station_id     TEXT,
    nrfa_station_url    TEXT,
    datum               NUMERIC,
    borehole_depth      NUMERIC,
    aquifer             TEXT,
    status_reason       TEXT,
    data_quality_message TEXT,
    data_quality_statement TEXT, -- denormalized for now, see below
    sample_of_id        TEXT,    -- foreign key if normalized
    sample_of_label     TEXT
);

--Table: hyd_station_type
--(Multiple types per station, each with an @id.)
CREATE TABLE hyd_station_type (
    station_id      INTEGER REFERENCES hyd_station(id),
    type_id         TEXT,  -- maps to "@id"
    PRIMARY KEY (station_id, type_id)
);

--Table: hyd_station_observed_prop
--(Multiple observed properties per station.)
CREATE TABLE hyd_station_observed_prop (
    station_id      INTEGER REFERENCES hyd_station(id),
    property_id     TEXT,  -- maps to "@id"
    PRIMARY KEY (station_id, property_id)
);

--Table: hyd_station_status
--(Status can be multiple, with nested label.)
CREATE TABLE hyd_station_status (
    station_id      INTEGER REFERENCES hyd_station(id),
    status_id       TEXT,  -- maps to "@id"
    status_label_id TEXT,  -- maps to label["@id"]
    PRIMARY KEY (station_id, status_id)
);

--Table: hyd_station_measure
--(Multiple measures per station.)
CREATE TABLE hyd_station_measure (
    id              SERIAL PRIMARY KEY,
    station_id      INTEGER REFERENCES hyd_station(id),
    measure_id      TEXT,       -- maps to "@id"
    parameter       TEXT,
    period          INTEGER,
    value_statistic_id TEXT     -- maps to valueStatistic["@id"]
);

--Table: hyd_station_colocated
--(Other stations colocated with this one.)
CREATE TABLE hyd_station_colocated (
    station_id      INTEGER REFERENCES hyd_station(id),
    colocated_id    TEXT,   -- maps to "@id"
    PRIMARY KEY (station_id, colocated_id)
);
