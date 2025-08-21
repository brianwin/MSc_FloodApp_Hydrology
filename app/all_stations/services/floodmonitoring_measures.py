# services/floodmonitoring_measures.py
import requests

from sqlalchemy import text
import time
#from datetime import datetime

from app import db
from ..models import( FldMeasureMeta, FldMeasureJson, FldMeasure)
from ...utils import parse_date, parse_datetime

import logging
logger = logging.getLogger('floodWatch3')

ea_root_url = 'http://environment.data.gov.uk/flood-monitoring'

def load_fld_measure_data_from_ea(truncate_all=True):
    url = f'{ea_root_url}/id/measures?_limit=50000'
    response = requests.get(url)
    data = response.json()
    #print (data['meta'])
    logger.info(f'Fetched {url}')
    logger.info(f'Response {response.status_code}')

    if truncate_all:
        truncate_all_measures()

    start_time = time.time()

    with db.session.begin():
        # save the "meta" table contents
        measure_meta_id = save_fld_measure_meta(data['meta'])
        count_items = load_fld_measures_from_json(measure_meta_id, data['items'])

        # Get counts within the same transaction
        measure_count = db.session.query(FldMeasure).count()

        logger.info(f'Input items : {count_items}')
        logger.info(f'Loaded items: {measure_count} measures')
        logger.info(f'Elapsed= {int(time.time() - start_time)} seconds')


#def save_fld_measure_meta_and_measure(meta: dict, items: list) -> int:
def load_fld_measures_from_json(measure_meta_id:int, items) -> int:
    count_items = 0
    for item in items:
        count_items += 1
        if count_items % 5000 == 0:
            logger.info(f'Loaded {count_items} measures')

        latest = item.get('latestReading', {})
        # Create the Measure record
        fld_measure = FldMeasure(
            meta_id        = measure_meta_id,
            json_id        = item.get("@id"),
            label          = item.get("label"),
            parameter      = item.get("parameter"),
            parameter_name = item.get("parameterName"),
            notation       = item.get("notation"),
            qualifier      = item.get("qualifier"),
            period         = item.get("period"),
            period_name    = item.get("periodName"),
            station        = item.get("station"),
            station_reference= item.get("stationReference"),
            has_telemetry  = item.get("hasTelemetry"),
            value_type     = item.get("valueType"),
            datum_type     = item.get("datumType"),
            unit           = item.get("unit"),
            unit_name      = item.get("unitName"),
            latest_reading_id      = latest.get('@id'),
            latest_reading_date    = parse_date(latest.get('date')),
            latest_reading_datetime= parse_datetime(latest.get('dateTime')),
            latest_reading_measure = latest.get('measure'),
            latest_reading_value   = latest.get('value'),
        )
        #try:
        db.session.add(fld_measure)
        #except Exception as e:
        #    logger.exception(f"Invalid input at item {count_items}", e)
        db.session.flush()

        # OK, this is a little bit "cart before the horse"
        # Save the raw item data row to the "json" table, given the station_id
        save_fld_measure_json(fld_measure.id, item)

    return count_items


def truncate_all_measures():
    # Truncate *meta - all other tables will cascade delete
    count = db.session.query(FldMeasure).count()
    logger.info(f'measures - row count: {count}')
    db.session.execute (text('TRUNCATE TABLE ea_source.fld_measure_meta CASCADE'))
    db.session.commit()
    logger.info(f'ea_source.fld_measure_meta truncated (cascade)')
    count = db.session.query(FldMeasure).count()
    db.session.commit()
    logger.info(f'measures - row count: {count}')


def save_fld_measure_meta(meta: dict) -> int:
    # Insert meta
    measure_meta = FldMeasureMeta(
        json_id=meta.get('@id'),
        publisher = meta.get('publisher'),
        licence = meta.get('licence'),         # note spelling of licence (only in flood measure)
        licenceName = meta.get('licenceName'), # not used
        documentation = meta.get('documentation'),
        version = meta.get('version'),
        comment = meta.get('comment'),
        hasFormat = meta.get('hasFormat')
    )
    db.session.add(measure_meta)
    db.session.flush()  # To get fld_measure_meta.id
    return measure_meta.id


def save_fld_measure_json(measure_id: int, item):
    # Save full JSON
    measure_json = FldMeasureJson(
        measure_id=measure_id,
        measure_data=item
    )
    db.session.add(measure_json)
    db.session.flush()
