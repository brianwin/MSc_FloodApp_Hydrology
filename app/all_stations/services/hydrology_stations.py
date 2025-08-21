# services/hydrology_stations.py
import requests

from sqlalchemy import text
import time
from datetime import datetime
from ...utils import get_geoms
from ...utils import parse_date

from app import db
from ..models import( HydStationMeta, HydStationJson,
                      HydStation, HydStationType, HydStationObservedProp,
                      HydStationStatus, HydStationMeasure, HydStationColocated
                    )
import logging
logger = logging.getLogger('floodWatch3')

ea_root_url = 'http://environment.data.gov.uk/hydrology'          # source data for extended history

def load_hyd_station_data_from_ea(truncate_all=True):
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
        station_meta_id = save_hyd_station_meta(data['meta'])
        count_items = load_hyd_stations_from_json(station_meta_id, data['items'])

        # Get counts within the same transaction
        station_count = db.session.query(HydStation).count()
        station_measure_count = db.session.query(HydStationMeasure).count()

        logger.info(f'Input items : {count_items}')
        logger.info(f'Loaded items: {station_count} stations, {station_measure_count} measures')
        logger.info(f'Elapsed= {int(time.time() - start_time)} seconds')


def load_hyd_stations_from_json(station_meta_id:int, items) -> int:
    count_items = 0
    for item in items:
        count_items += 1
        if count_items % 500 == 0:
            logger.info(f'Loaded {count_items} stations')

        geom4326, geom27700 = get_geoms(item.get('lat'), item.get('long'))

        # Handle rloi_id - convert this list to string if needed
        rloi_id = item.get('RLOIid')
        if isinstance(rloi_id, list):
            rloi_id = ','.join(rloi_id)  # or rloi_id[0] if you want just the first one

        # Handle rloi_station_link - extract URLs
        rloi_links = item.get('rloiStationLink', [])
        if isinstance(rloi_links, dict):
            rloi_links = [rloi_links]  # convert single dict to list
        rloi_station_link = ','.join(link.get('@id', '') for link in rloi_links) if rloi_links else None

        #TODO Remember this kind of thing ....
        # status = (station.get('status') or '').replace(ea_root_url, '{root}'),

        # Create the Station record
        hyd_station = HydStation(
            meta_id = station_meta_id,
            json_id = item.get('@id'),
            label = item.get('label'),
            notation = item.get('notation'),
            easting = float(item.get('easting')) if item.get('easting') is not None else None,
            northing = float(item.get('northing')) if item.get('northing') is not None else None,
            lat=float(item.get('lat')) if item.get('lat') is not None else None,
            long=float(item.get('long')) if item.get('long') is not None else None,
            catchment_name = item.get('catchmentName'),
            river_name = item.get('riverName'),
            town = item.get('town'),
            station_guid = item.get('stationGuid'),
            station_reference = item.get('stationReference'),
            wiski_id = item.get('wiskiID'),
            rloi_id=rloi_id,  # Use processed rloi_id
            rloi_station_link=rloi_station_link,  # Use processed rloi_station_link
            catchment_area = float(item.get('catchmentArea') or 0),
            date_opened = parse_date(item.get('dateOpened')),
            date_closed = parse_date(item.get('dateClosed')),
            nrfa_station_id = item.get('nrfaStationID'),
            nrfa_station_url = item.get('nrfaStationURL'),
            datum = int(item.get('datum') or 0),
            borehole_depth = float(item.get('boreholeDepth') or 0),
            aquifer = item.get('aquifer'),
            status_reason = item.get('statusReason'),
            data_quality_message = item.get('dataQualityMessage'),
            data_quality_statement = (
                item.get('dataQualityStatement', {}).get('@id')
                if isinstance(item.get('dataQualityStatement'), dict)
                else None
            ),
            sample_of_id = (
                item.get('sampleOf', {}).get('@id')
                if isinstance(item.get('sampleOf'), dict)
                else None
            ),
            sample_of_label = (
                item.get('sampleOf', {}).get('label')
                if isinstance(item.get('sampleOf'), dict)
                else None
            ),
            geom4326=geom4326,
            geom27700=geom27700,
        )
        db.session.add(hyd_station)
        db.session.flush()  # So station.id is available

        # OK, this is a little bit "cart before the horse"
        # Save the raw item data row to the "json" table, given the station_id
        save_hyd_station_json(hyd_station.id, item)

        # Types
        for t in item.get('type', []):
            stype = HydStationType(
                station_id=hyd_station.id,
                type_id=t.get('@id'),
            )
            db.session.add(stype)

        # Observed Properties
        for prop in item.get('observedProperty', []):
            op = HydStationObservedProp(
                station_id=hyd_station.id,
                property_id=prop.get('@id')
            )
            db.session.add(op)

        # Statuses
        for status in item.get('status', []):
            label = status.get('label')
            if isinstance(label, dict):
                status_label_id = label.get('@id')
            elif isinstance(label, str):
                status_label_id = label
            else:
                status_label_id = None

            ss = HydStationStatus(
                station_id=hyd_station.id,
                status_id=status.get('@id'),
                status_label_id=status_label_id
            )
            db.session.add(ss)

        # Measures
        for measure in item.get('measures', []):
            m = HydStationMeasure(
                station_id=hyd_station.id,
                measure_id=measure.get('@id'),
                parameter=measure.get('parameter'),
                period=measure.get('period'),
                value_statistic_id=(
                    measure.get('valueStatistic', {}).get('@id')
                    if isinstance(measure.get('valueStatistic'), dict)
                    else None
                )
            )
            db.session.add(m)

        # Colocated stations
        for coloc in item.get('colocatedStation', []):
            coloc_rec = HydStationColocated(
                station_id=hyd_station.id,
                colocated_id=coloc.get('@id')
            )
            db.session.add(coloc_rec)

    #TODO What happened to ['stageScale', 'downstageScale']
    return count_items  # Return the count for logging


def truncate_all_stations():
    # Truncate *meta - all other tables will cascade delete
    count = db.session.query(HydStation).count()
    logger.info(f'stations - row count: {count}')
    db.session.execute (text('TRUNCATE TABLE ea_source.hyd_station_meta CASCADE'))
    db.session.commit()
    logger.info(f'ea_source.hyd_station_meta truncated (cascade)')
    count = db.session.query(HydStation).count()
    db.session.commit()
    logger.info(f'stations - row count: {count}')


def save_hyd_station_meta(meta: dict) -> int:
    # Insert meta
    station_meta = HydStationMeta(
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
    db.session.flush()  # To get hyd_station_meta.id
    return station_meta.id


def save_hyd_station_json(station_id: int, item):
    # Save full JSON
    station_json = HydStationJson(
        station_id=station_id,
        station_data=item
    )
    db.session.add(station_json)
    db.session.flush()



