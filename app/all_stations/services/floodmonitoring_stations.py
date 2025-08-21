# services/floodmonitoring_stations.py
import requests

from sqlalchemy import text
import time
from datetime import datetime
from ...utils import get_geoms
from ...utils import parse_date

from app import db
from ..models import (FldStationMeta, FldStationJson, FldStation, FldStationMeasure)
import logging
logger = logging.getLogger('floodWatch3')

ea_root_url = 'http://environment.data.gov.uk/flood-monitoring'

def load_fld_station_data_from_ea(truncate_all=True):
    url = f'{ea_root_url}/id/stations?_limit=20000'
    response = requests.get(url)
    data = response.json()
    #print (data['meta'])
    logger.info(f'Fetched {url}')
    logger.info(f'Response {response.status_code}')

    if truncate_all:
        truncate_all_stations()

    start_time = time.time()

    with db.session.begin():
        # save the "meta" table contents
        station_meta_id = save_fld_station_meta(data['meta'])
        count_items = load_fld_stations_from_json(station_meta_id, data['items'])

        # Get counts within the same transaction
        station_count = db.session.query(FldStation).count()
        station_measure_count = db.session.query(FldStationMeasure).count()

        logger.info(f'Input items : {count_items}')
        logger.info(f'Loaded items: {station_count} stations, {station_measure_count} measures')
        logger.info(f'Elapsed= {int(time.time() - start_time)} seconds')


def load_fld_stations_from_json(station_meta_id:int, items) -> int:
    count_items = 0
    for item in items:
        count_items += 1
        if count_items % 500 == 0:
            logger.info(f'Loaded {count_items} stations')

        lat = safe_float(item.get('lat'))
        long = safe_float(item.get('long'))
        geom4326, geom27700 = get_geoms(lat, long)

        # Handle rloi_id - convert this list to string if needed
        rloi_id = item.get('RLOIid')
        if isinstance(rloi_id, list):
            rloi_id = ','.join(rloi_id)  # or rloi_id[0] if you want just the first one

        # Create the Station record
        fld_station = FldStation(
            meta_id = station_meta_id,
            json_id = item.get('@id'),
            label = item.get('label'),
            notation = item.get('notation'),

            #easting = float(item.get('easting')) if item.get('easting') is not None else None,
            easting = safe_float(item.get('easting')),
            #northing = float(item.get('northing')) if item.get('northing') is not None else None,
            northing = safe_float(item.get('easting')),

            #lat = float(item.get('lat')) if item.get('lat') is not None else None,
            #lat = safe_float(item.get('lat')),
            lat = lat,
            #long = float(item.get('long')) if item.get('long') is not None else None,
            #long = safe_float(item.get('long')),
            long = long,

            catchment_name = item.get('catchmentName'),
            river_name = item.get('riverName'),
            town = item.get('town'),
            station_reference = item.get('stationReference'),
            wiski_id = item.get('wiskiID'),
            rloi_id = rloi_id,  # Use processed rloi_id
            date_opened = parse_date(item.get('dateOpened')),
            stage_scale = item.get('stageScale'),
            status =item.get('status'),
            datum_offset = float(item.get('datumOffset')) if item.get('datumOffset') is not None else None,
            geom4326=geom4326,
            geom27700=geom27700,
        )
        db.session.add(fld_station)
        db.session.flush()  # So station.id is available

        # OK, this is a little bit "cart before the horse"
        # Save the raw item data row to the "json" table, given the station_id
        save_fld_station_json(fld_station.id, item)


        # Measures
        for measure in item.get('measures', []):
            m = FldStationMeasure(
                station_id=fld_station.id,
                json_id=measure.get('@id'),
                parameter=measure.get('parameter'),
                parameter_name=measure.get('parameterName'),
                period=measure.get('period'),
                qualifier=measure.get('qualifier'),
                unit_name=measure.get('unitName')
            )
            db.session.add(m)

    return count_items  # Return the count for logging


def truncate_all_stations():
    # Truncate *meta - all other tables will cascade delete
    count = db.session.query(FldStation).count()
    logger.info(f'stations - row count: {count}')
    db.session.execute (text('TRUNCATE TABLE ea_source.fld_station_meta CASCADE'))
    db.session.commit()
    logger.info(f'ea_source.fld_station_meta truncated (cascade)')
    count = db.session.query(FldStation).count()
    db.session.commit()
    logger.info(f'stations - row count: {count}')


def save_fld_station_meta(meta: dict) -> int:
    # Insert meta
    station_meta = FldStationMeta(
        json_id=meta.get('@id'),
        publisher = meta.get('publisher'),
        license = meta.get('license'),
        licenseName = meta.get('licenseName'),
        documentation = meta.get('documentation'),
        version = meta.get('version'),
        comment = meta.get('comment'),
        hasFormat = meta.get('hasFormat')
    )
    db.session.add(station_meta)
    db.session.flush()  # To get fld_station_meta.id
    return station_meta.id


def save_fld_station_json(station_id: int, item):
    # Save full JSON
    station_json = FldStationJson(
        station_id=station_id,
        station_data=item
    )
    db.session.add(station_json)
    db.session.flush()



def get_first_value(val):
    """If val is a list, return the first non-None element. Else, return val."""
    if isinstance(val, list):
        # Skip over Nones and empty strings
        for v in val:
            if v not in (None, ''):
                return v
        return None  # All elements were None or ''
    return val

def safe_float(val):
    try:
        val = get_first_value(val)
        return float(val)
    except (TypeError, ValueError):
        return None

def safe_str(val):
    val = get_first_value(val)
    if val is None:
        return None
    return str(val)

