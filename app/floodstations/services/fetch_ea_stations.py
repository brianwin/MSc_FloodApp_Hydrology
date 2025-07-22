# scripts/fetch_ea_stations.py
import requests
import json

from sqlalchemy import text
import time

from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from shapely.ops import transform
from pyproj import Transformer

from app import db
from ..models import (
    StationMeta, StationJson, Station, StationComplex,
    StationScale, StationMeasure
)

import logging
logger = logging.getLogger('floodWatch2')

ea_root_url = 'http://environment.data.gov.uk/flood-monitoring'

def load_station_data_from_ea(truncate_all=True):
    url = f'{ea_root_url}/id/stations?_view=full'
    response = requests.get(url)
    data = response.json()
    logger.info(f'Fetched {url}')
    logger.info(f'Response {response.status_code}')

    if truncate_all:
        truncate_all_stations()

    with db.session.begin():
        # save the "meta" table contents
        station_meta_id = save_station_meta(data.get('@context'), data['meta'])

        count_items = 0
        start_time = time.time()
        for station in data['items']:
            count_items += 1
            if count_items % 500 == 0:
                logger.info(f'Committed {count_items} stations - elapsed= {int(time.time() - start_time)} seconds')

            # save the raw item data row to the "json" table
            station_id = save_station_json(station_meta_id, station)
            RLOIid = station.get('RLOIid')

            # there are 2x occurrences where a string(list) is presented for several parameters
            # save to table StationComplex, effectively ignored for this application
            if isinstance(RLOIid, list):
                complex_station = StationComplex(
                    station_id=station_id,
                    EnvAgy_id=station.get('@id'),
                    RLOIid=json.dumps(station.get('RLOIid')),
                    catchmentName=station.get('catchmentName'),
                    dateOpened=station.get('dateOpened'),
                    northing=json.dumps(station.get('northing')),
                    easting=json.dumps(station.get('easting')),
                    label=json.dumps(station.get('label')),
                    lat=json.dumps(station.get('lat')),
                    long=json.dumps(station.get('long')),
                    notation=station.get('notation'),
                    riverName=station.get('riverName'),
                    stationReference=station.get('stationReference'),
                    status=json.dumps(station.get('status')),
                    town=station.get('town'),
                    wiskiID=station.get('wiskiID'),
                    gridReference=station.get('gridReference'),
                    datumOffset=int(station.get('datumOffset', 0)),
                    #stageScale=station.get('stageScale'),
                    #downstageScale=station.get('downstageScale'),
                    #geom4326=geom4326,
                    #geom27700=geom27700
                )
                db.session.add(complex_station)

            else:
                geom4326, geom27700 = get_geoms(station.get('lat'), station.get('long'))

                norm_station = Station(
                    station_id=station_id,
                    EnvAgy_id=station.get('@id', '').replace(ea_root_url, '{root}'),
                    RLOIid=RLOIid,
                    catchmentName=station.get('catchmentName'),
                    dateOpened=station.get('dateOpened'),
                    northing=int(station.get('northing') or 0),
                    easting=int(station.get('easting') or 0),
                    label=station.get('label'),
                    lat=float(station.get('lat') or 0),
                    long=float(station.get('long') or 0),
                    notation=station.get('notation'),
                    riverName=station.get('riverName'),
                    stationReference=station.get('stationReference'),
                    status=(station.get('status') or '').replace(ea_root_url, '{root}'),
                    town=station.get('town'),
                    wiskiID=station.get('wiskiID'),
                    gridReference=station.get('gridReference'),
                    datumOffset=int(station.get('datumOffset', 0)),
                    #stageScale=station.get('stageScale'),
                    #downstageScale=station.get('downstageScale'),
                    geom4326=geom4326,
                    geom27700=geom27700
                )
                db.session.add(norm_station)

                for scale_key in ['stageScale', 'downstageScale']:
                    scale = station.get(scale_key)
                    if scale and not isinstance(scale, str):
                        scale_obj = StationScale(
                            station_id=station_id,
                            EnvAgy_id=scale.get('@id', '').replace(ea_root_url, '{root}'),
                            highestRecent_id=scale.get('highestRecent', {}).get('@id', '').replace(ea_root_url, '{root}'),
                            highestRecent_dateTime=scale.get('highestRecent', {}).get('dateTime'),
                            highestRecent_value=scale.get('highestRecent', {}).get('value'),
                            maxOnRecord_id=scale.get('maxOnRecord', {}).get('@id', '').replace(ea_root_url, '{root}'),
                            maxOnRecord_dateTime=scale.get('maxOnRecord', {}).get('dateTime'),
                            maxOnRecord_value=scale.get('maxOnRecord', {}).get('value'),
                            minOnRecord_id=scale.get('minOnRecord', {}).get('@id', '').replace(ea_root_url, '{root}'),
                            minOnRecord_dateTime=scale.get('minOnRecord', {}).get('dateTime'),
                            minOnRecord_value=scale.get('minOnRecord', {}).get('value'),
                            scaleMax=scale.get('scaleMax'),
                            typicalRangeHigh=scale.get('typicalRangeHigh'),
                            typicalRangeLow=scale.get('typicalRangeLow')
                        )
                        db.session.add(scale_obj)

                # Insert measures
                for measure in station.get('measures', []):
                    measure_obj = StationMeasure(
                        station_id=station_id,
                        EnvAgy_id=measure.get('@id', '').replace(ea_root_url, '{root}'),
                        parameter=measure.get('parameter'),
                        parameterName=measure.get('parameterName'),
                        period=measure.get('period'),
                        qualifier=measure.get('qualifier'),
                        unitName=measure.get('unitName')
                    )
                    db.session.add(measure_obj)

    db.session.commit()
    station_count = db.session.query(Station).count()
    station_measure_count = db.session.query(StationMeasure).count()
    station_scale_count = db.session.query(StationScale).count()
    logger.info(f'Station data loaded successfully - {station_count} stations, {station_measure_count} measures {station_scale_count} scales')
    logger.info(f'Elapsed= {int(time.time() - start_time)} seconds')


def truncate_all_stations():
    # Truncate *meta - all other tables will cascade delete
    count = db.session.query(Station).count()
    logger.info(f'stations - row count: {count}')
    db.session.execute (text('TRUNCATE TABLE ea_source.station_meta CASCADE'))
    db.session.commit()
    logger.info(f'ea_source.station_meta truncated (cascade)')
    count = db.session.query(Station).count()
    db.session.commit()
    logger.info(f'stations - row count: {count}')


def save_station_meta(context: str, meta: dict) -> int:
    # Insert meta
    station_meta = StationMeta(
        context = context,
        publisher = meta.get('publisher'),
        licence = meta.get('licence'),
        documentation = meta.get('documentation'),
        version = float(meta.get('version')),
        comment = meta.get('comment'),
        hasFormat = meta.get('hasFormat')
    )
    db.session.add(station_meta)
    db.session.flush()  # To get station_meta.id
    return station_meta.station_meta_id


def save_station_json(station_meta_id: int, station: dict) -> int:
    # Save full JSON
    station_json = StationJson(
        station_meta_id=station_meta_id,
        station_data=station
    )
    db.session.add(station_json)
    db.session.flush()
    return station_json.station_id


def get_geoms(lat: float, long: float) -> [WKBElement, WKBElement]:
    if lat is not None and long is not None:
        lat = float(lat)
        long = float(long)

        point_4326 = Point(long, lat)
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
        point_27700 = transform(transformer.transform, point_4326)

        geom4326 = from_shape(point_4326, srid=4326)
        geom27700 = from_shape(point_27700, srid=27700)
    else:
        geom4326 = None
        geom27700 = None
    return geom4326, geom27700
