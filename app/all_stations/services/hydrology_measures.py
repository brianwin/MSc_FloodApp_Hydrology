# services/hydrology_measures.py
import requests

from sqlalchemy import text
import time
#from datetime import datetime

from app import db
from ..models import( HydMeasureMeta, HydMeasureJson, HydMeasure)

import logging
logger = logging.getLogger('floodWatch3')

ea_root_url = 'http://environment.data.gov.uk/hydrology'          # source data for extended history

def load_measure_data_from_ea(truncate_all=True):
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
        measure_meta_id = save_hyd_measure_meta(data['meta'])
        count_items = load_measures_from_json(measure_meta_id, data['items'])

        # Get counts within the same transaction
        measure_count = db.session.query(HydMeasure).count()

        logger.info(f'Input items : {count_items}')
        logger.info(f'Loaded items: {measure_count} measures')
        logger.info(f'Elapsed= {int(time.time() - start_time)} seconds')


#def save_hyd_measure_meta_and_measure(meta: dict, items: list) -> int:
def load_measures_from_json(measure_meta_id:int, items) -> int:
    count_items = 0
    for item in items:
        count_items += 1
        if count_items % 5000 == 0:
            logger.info(f'Loaded {count_items} measures')

        # Create the Measure record
        hyd_measure = HydMeasure(
            meta_id      = measure_meta_id,
            json_id      = item.get("@id"),
            label        = item.get("label"),
            parameter    = item.get("parameter"),
            parameterName= item.get("parameterName"),
            notation     = item.get("notation"),
            qualifier    = item.get("qualifier"),
            period       = item.get("period"),
            periodName   = item.get("periodName"),
            hasTelemetry = item.get("hasTelemetry"),
            valueType    = item.get("valueType"),
            datumType    = item.get("datumType"),
            timeseriesID = item.get("timeseriesID"),
            unit         = (item.get("unit") or {}).get("@id"),
            unitName     = item.get("unitName"),
            valueStatistic_id    = (item.get("valueStatistic") or {}).get("@id"),
            valueStatistic_label = (item.get("valueStatistic") or {}).get("label"),
            observationType_id   = (item.get("observationType") or {}).get("@id"),
            observationType_label= (item.get("observationType") or {}).get("label"),
            observedProperty_id  = (item.get("observedProperty") or {}).get("@id"),
            observedProperty_label = (item.get("observedProperty") or {}).get("label"),
            station_id           = (item.get("station") or {}).get("@id"),
            station_label        = (item.get("station") or {}).get("label"),
            station_wiskiID      = (item.get("station") or {}).get("wiskiID"),
            station_stationReference = (item.get("station") or {}).get("stationReference"),
            station_RLOIid = (
                    ( item.get("station") or {}).get("RLOIid")
                        if not isinstance((item.get("station") or {}).get("RLOIid"), list)
                        else ",".join((item.get("station") or {}).get("RLOIid")
                    )
                )
        )
        #try:
        db.session.add(hyd_measure)
        #except Exception as e:
        #    logger.exception(f"Invalid input at item {count_items}", e)
        db.session.flush()
    return count_items


def truncate_all_measures():
    # Truncate *meta - all other tables will cascade delete
    count = db.session.query(HydMeasure).count()
    logger.info(f'measures - row count: {count}')
    db.session.execute (text('TRUNCATE TABLE ea_source.hyd_measure_meta CASCADE'))
    db.session.commit()
    logger.info(f'ea_source.hyd_measure_meta truncated (cascade)')
    count = db.session.query(HydMeasure).count()
    db.session.commit()
    logger.info(f'measures - row count: {count}')


def save_hyd_measure_meta(meta: dict) -> int:
    # Insert meta
    hyd_measure_meta = HydMeasureMeta(
        json_id=meta.get('@id'),
        publisher = meta.get('publisher'),
        license = meta.get('license'),
        licenseName = meta.get('licenseName'),
        documentation = meta.get('documentation'),
        version = meta.get('version'),
        comment = meta.get('comment'),
        hasFormat = meta.get('hasFormat')
    )
    db.session.add(hyd_measure_meta)
    db.session.flush()  # To get hyd_measure_meta.id
    return hyd_measure_meta.id


def save_measure_json(measure_id: int, item):
    # Save full JSON
    measure_json = HydMeasureJson(
        measure_id=measure_id,
        measure_data=item
    )
    db.session.add(measure_json)
    db.session.flush()
