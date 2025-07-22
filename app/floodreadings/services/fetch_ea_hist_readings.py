# app/floodreadings/services/fetch_ea_hist_readings.py
# Historical readings in csv files from the daily archive

import requests
import os

import pandas as pd
import math
import time
from collections import Counter

from flask import current_app
import click
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import func
from sqlalchemy import text
from concurrent.futures import ThreadPoolExecutor

#from datetime import date, datetime, timedelta, timezone
import datetime
from dateutil.parser import parse

from app import db
from ..models import Reading, Reading_Concise, Reading_Recent
from app.floodstations.models.station import Station

import logging
logger = logging.getLogger('floodWatch2')

# annotate the proxy so the IDE knows its real type
from werkzeug.local import LocalProxy
current_app: LocalProxy

ea_root_url = 'http://environment.data.gov.uk/flood-monitoring'

station_labels = None
def get_station_labels(worker_id:int=0):
    """Lazily load station labels on first access."""
    global station_labels
    if station_labels is None:
        logger.debug(f'(T{worker_id}):Lazy loading station labels')
        try:
            station_labels = {
                row.stationReference: row.label
                for row in db.session.query(Station.stationReference, Station.label).all()
            }
        except Exception as e:
            logger.exception(f'(T{worker_id}):get_station_labels: failed with error: {e}')
        logger.info(f'(T{worker_id}):Loaded {len(station_labels)} station labels into memory cache')
    return station_labels


def load_hist_reading_data_from_ea(datestr: str, concise:bool = True,
                                   save_basefolder: str = "data/archive",
                                   force_replace:bool = False
                                  ) -> pd.DataFrame|None:
    if concise:
        url = f'{ea_root_url}/archive/readings-{datestr}.csv'
        save_folder = f'{save_basefolder}/concise/'
        filename = f'readings-{datestr}.csv'
    else:
        url = f'{ea_root_url}/archive/readings-full-{datestr}.csv'
        save_folder = f'{save_basefolder}/full/'
        filename = f'readings-full-{datestr}.csv'

    os.makedirs(save_folder, exist_ok=True)  # Ensure the folder exists
    filepath = os.path.join(save_folder, filename)

    if os.path.exists(filepath):
        if force_replace:
            os.remove(filepath)
            logger.info(f"Removed existing file: {filepath}")
        else:
            logger.info(f"Using existing local file: {filepath}")
            return pd.read_csv(filepath, low_memory=False, dtype=str)

    # Download if file doesn't exist after optional deletion
    response = requests.get(url, stream=True, timeout=60)
    if response.status_code == 200:
        logger.info(f'Fetched {url}')

        # Save the file to local os
        with open(filepath, 'wb') as f:   # the file auto-closes when we exit this "with context"
            #for chunk in response.iter_content(chunk_size=8192):          # 8k chunk writes
            for chunk in response.iter_content(chunk_size=1024 * 1024):   # 1Mb chunks reduces syscalls and i/o overhead
                f.write(chunk)
        logger.info(f"Saved: {filepath}")
    else:
        logger.warning(f'Response {response.status_code}: Failed to fetch data from {url}')
        return None

    return pd.read_csv(filepath, low_memory=False, dtype=str)


def get_scoped_session():
    session_factory = sessionmaker(bind=db.engine)
    return scoped_session(session_factory)


def parse_float_safe(val: str, min_val: float =-9999999.0, max_val:float =9999999.0) -> [float|None, int] :
    try:
        # Catch actual NaN objects (e.g., from pandas, float('nan'), numpy.nan)
        if pd.isna(val):
            return None, 1  # actual NaN detected

        # Handle string "nan" explicitly
        if isinstance(val, str):
            val = val.strip()
            if val.lower() == "nan":
                return None, 2

        f = float(val)
        if math.isnan(f):
            return None, 3  # float('nan') slipped through

        # noinspection PyUnreachableCode
        if 1==1:  #min_val <= f <= max_val:
            return f, 0     # normal - the vast majority will return from here
        else:
            logger.error(f"Out-of-range value: {val}")
            return None, 4  # Out-of-range value
    except (TypeError, ValueError):
        try:
            if isinstance(val, str) and "|" in val:
                val = val.split("|")[-1]  # get last part after '|'
            else:
                logger.error(f"Invalid float value: {val}")
                return None, 5  # Invalid float value

            f = float(val)
            if min_val <= f <= max_val:
                return f, 6    # split: normal
            else:
                logger.error(f"Out-of-range value: {val}")
                return None, 7  # split: Out-of-range value
        except (TypeError, ValueError):
            logger.exception(f"Invalid float value: {val}")
            return None, 8      # split: Out-of-range value


def insert_chunk(chunk_df: pd.DataFrame,
                 chunk_num: int,
                 stn_labels = None,
                 ea_datasource:str = 'EA',
                 concise: bool =True,
                 update_recent=False
                ) -> dict:
    from . import get_fieldvalue_for_db

    session = get_scoped_session()
    #logger.info(f"Inserting chunk {chunk_num} using scoped session")
    status_counter = Counter()
    try:
        readings = []
        for _, row in chunk_df.iterrows():

            dtm = row.get("dateTime")
            if isinstance(dtm, str):  # as it is when read from a csv file
                r_datetime = parse(dtm)
            elif pd.notnull(dtm):
                r_datetime = dtm  # already a datetime (as it is when read from database table)
            else:
                r_datetime = None

            #r_datetime = parse(row["dateTime"]) if row.get("dateTime") else None
            r_month = r_datetime.replace(day=1).date() if r_datetime else None
            r_date  = r_datetime.date() if r_datetime else None

            measure = row.get("measure", '')
            x_measure = measure.replace(f'{ea_root_url}/id/measures/', '').strip() if isinstance(measure, str) else None

            val, status = parse_float_safe(row.get("value"))
            status_counter[status] += 1

            if concise:
                x_measure_parsed = x_measure.rsplit('-', 6)

                # pop() pops from the end of the string -
                # Note: pop(0) pops from the front, but not used here as some stationreference values contain hyphens
                unitname = x_measure_parsed.pop()
                datumtype = get_fieldvalue_for_db('datumtype', unitname )

                period_str = x_measure_parsed.pop()
                period = get_fieldvalue_for_db('period', period_str )

                valuetype_str = x_measure_parsed.pop()
                valuetype = get_fieldvalue_for_db('valuetype', valuetype_str )

                qualifier_str = x_measure_parsed.pop()
                qualifier = get_fieldvalue_for_db('qualifier', qualifier_str )

                parameter = x_measure_parsed.pop()

                stationreference = x_measure_parsed.pop()
                station = f'{{root}}/id/stations/{stationreference}'
                label = stn_labels.get(stationreference) if stn_labels else None

                if update_recent:
                    reading = Reading_Recent(
                        source=ea_datasource,
                        r_datetime = r_datetime,
                        r_month = r_month,
                        r_date = r_date,
                        measure = measure,
                        x_measure = x_measure,
                        station = station,
                        label = label,
                        stationreference = stationreference,
                        parameter = parameter,
                        qualifier = qualifier,
                        datumtype = datumtype,
                        period = period,
                        unitname = unitname,
                        valuetype = valuetype,
                        value=val,
                    )
                else:
                    reading = Reading_Concise(
                        source=ea_datasource,
                        r_datetime = r_datetime,
                        r_month = r_month,
                        r_date = r_date,
                        measure = measure,
                        x_measure = x_measure,
                        station = station,
                        label = label,
                        stationreference = stationreference,
                        parameter = parameter,
                        qualifier = qualifier,
                        datumtype = datumtype,
                        period = period,
                        unitname = unitname,
                        valuetype = valuetype,
                        value=val,
                    )
            else:

                # handles missing or None/NaN values in period column - sets all of these to 0
                period_str = row.get("period", 0)
                try:
                    # handle NaN or missing
                    if pd.isna(period_str):
                        period = 0
                    else:
                        period = int(float(period_str))
                except (ValueError, TypeError):
                    period = 0

                reading = Reading(
                    source=ea_datasource,
                    r_datetime = r_datetime,
                    r_month= r_month,
                    r_date=row.get("date"),
                    measure = measure,
                    x_measure = x_measure,
                    station=row.get("station").replace(ea_root_url, '{root}'),
                    label=row.get("label"),
                    stationreference=row.get("stationReference"),
                    parameter=row.get("parameter"),
                    qualifier=row.get("qualifier"),
                    datumtype=row.get("datumType").replace(ea_root_url, '{root}') if isinstance(row.get("datumType"), str) else None,
                    period = period,
                    unitname=row.get("unitName"),
                    valuetype=row.get("valueType"),
                    value=val,
                )

            readings.append(reading)  # whether "reading" came from "concise" or "full" section

        #logger.info(f'Chunk {chunk_num}: generated')
        #logger.debug(f"Readings generated: {readings[:2]}")  # Print first two for inspection
        #t0 = time.perf_counter()
        #session.add_all(readings)
        if update_recent:
            # convert to a dict of update values for the update (to immutable object) mechanism to work here
            #logger.info(f"Converting to dict")
            update_dicts = [
                {
                    "stationreference": r.stationreference,
                    "r_datetime": r.r_datetime,
                    "measure": r.measure,
                    "x_measure": r.x_measure,
                    "value": r.value,
                    "label": r.label,
                    "parameter": r.parameter,
                    "qualifier": r.qualifier,
                    "datumtype": r.datumtype,
                    "period": r.period,
                    "unitname": r.unitname,
                    "valuetype": r.valuetype,
                    "source": r.source,
                    "r_date": r.r_date,
                    "r_month": r.r_month,
                    "station": r.station,
                }
                for r in readings
            ]
            session.bulk_update_mappings(Reading_Recent, update_dicts)
        else:
            session.bulk_save_objects(readings)
        session.commit()
        #t1 = time.perf_counter()
        #logger.info(f"DB insert time for chunk {chunk_num}: {t1 - t0:.2f}s")
        #logger.info(f"Chunk {chunk_num}: inserted {len(readings)} records")
    except Exception as e:
        session.rollback()
        logger.exception(f"Chunk {chunk_num}: failed with error: {e}")
    finally:
        session.remove()
        #logger.info(f"Chunk {chunk_num} value statuses: {dict(status_counter)}")
        return status_counter


def threaded_insert(df:pd.DataFrame,
                    chunk_size:int = 500, max_workers:int = 16,
                    ea_datasource:str = 'EA',
                    concise:bool = True, update_recent:bool = False, app = None, worker_id = 0
                   ):
    logmark = f"(T{worker_id}):f{ea_datasource[-10:].replace('-', '')}"
    chunks = [df.iloc[i:i + chunk_size] for i in range(0, len(df), chunk_size)]
    logger.info(f'{logmark}: {len(chunks)} chunks to be inserted')

    # Save the current app context
    if app is None:
        # noinspection PyProtectedMember
        app = current_app._get_current_object()
    results = [None] * len(chunks)

    with app.app_context():
        stn_labels = get_station_labels(worker_id=worker_id)  # load once

    def run_in_app_context(chunk, chunk_num, labels, source:str = 'EA',
                           is_concise:bool = True, is_update_recent:bool = False
                          ):
        with app.app_context():
            #logger.debug(f'{logmark}: Going to insert_chunk({chunk_num})')
            status_results = insert_chunk(chunk, chunk_num, stn_labels=labels, ea_datasource=source,
                                          concise=is_concise, update_recent=is_update_recent)
            results[chunk_num] = status_results
            #if status_results[0] != 500:
            #    logger.info(f'{logmark}: chunk {chunk_num} status= {status_results}')

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(run_in_app_context, chunk, i, stn_labels, ea_datasource, concise, update_recent)
            for i, chunk in enumerate(chunks)
        ]
        for future in futures:
            future.result()
            #logger.info(f'{logmark}: chunk {i} to be inserted')
            #executor.submit(insert_chunk_full, chunk, i)
        logger.info(f"{logmark}: All parallel tasks have completed.")

    # Aggregate all counters
    total_status = Counter()
    for status in results:
        if status:
            total_status.update(status)

    return total_status


def delete_readings_by_r_datetime(start_date, end_date, concise:bool = True):
    # the beginning of the day at start_date, UTC aware
    start_dt = date_to_utc_datetime(start_date, end_of_day=False)
    # the end of the day at end_date, UTC aware
    end_dt = date_to_utc_datetime(end_date, end_of_day=True)

    date_range = start_date if end_date == start_date else f"{start_date} to {end_date}"
    if concise:
        model = Reading_Concise
    else:
        model = Reading

    try:
        logger.info(f"Deleting rows from {model.__name__} for {date_range}")
        deleted = db.session.query(model).filter(
            model.r_datetime >= start_dt,
            model.r_datetime <= end_dt
        ).delete(synchronize_session=False)
        db.session.commit()
        logger.info(f"Deleted {deleted} rows from {model.__name__} for {date_range}")
    except Exception as e:
        db.session.rollback()
        logger.info(f"Error deleting rows from {model.__name__} for {date_range}: {e}")


def get_start_end_dates(concise:bool = True, upto:int = 7) -> [datetime.date, datetime.date]:
    # logger.debug(f"getting database max_r_date")
    # Step 1: Get max r_date in the DB
    db.session.remove()
    if concise:
        max_r_date = db.session.query(func.max(Reading_Concise.r_datetime)).scalar()
    else:
        max_r_date = db.session.query(func.max(Reading.r_datetime)).scalar()

    logger.debug(f"({'concise' if concise else 'full   '}) Database max_r_date : {max_r_date}")
    if not max_r_date:
        logger.warning("No readings found in DB – starting from default date")
        # Set loop range start (a date)
        start_date = datetime.date(2024, 5, 12)  # or any fallback start date
    else:
        # Set loop range start (a date)
        start_date = max_r_date.date() + datetime.timedelta(days=1)

    # Step 2: Set loop range end
    end_date = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=upto))
    logger.debug(f"{start_date} to {end_date}")
    return start_date, end_date

def date_to_utc_datetime(d: datetime.date, end_of_day:bool = False) -> datetime.datetime|None:
    """
    Turn a date into a timezone-aware datetime at 00:00:00 UTC.
    If `d` is None, returns None.
    """
    if d is None:
        return None
    # beginning (min) or end (max) of that date, with UTC tzinfo
    t = datetime.time.max if end_of_day else datetime.time.min
    return datetime.datetime.combine(d, t, tzinfo=datetime.timezone.utc)


def load_hist_readings(concise:bool = True, upto:int = 7, force_replace:bool = False):
    """Launch single task (one day of source data) to process historic readings. Each file is multi-chunked"""
    start_date, end_date = get_start_end_dates(concise=concise, upto=upto)
    logger.info(f"Fetching from {start_date} to {end_date}")

    # Step 3: Loop over each day
    current_date = start_date
    while current_date <= end_date:
        datestr = current_date.strftime('%Y-%m-%d')  # suitable for EA
        #logger.info(f"Loading data for {datestr}")

        df = load_hist_reading_data_from_ea(datestr, concise, force_replace=force_replace)
        if df is not None:
            logger.info(f"Loading {'concise' if concise else 'full   '} data for {datestr} - {len(df)} rows")
            t0 = time.perf_counter()
            status_summary = threaded_insert(df,
                                             chunk_size=5000, max_workers=16,
                                             ea_datasource=f"EA{'' if concise else '_full_'}{datestr}",
                                             concise=concise
                                            )
            t1 = time.perf_counter()
            logger.info(f"Status summary for {datestr}: {dict(sorted(status_summary.items()))}")
            logger.info(f"Process time   for {datestr}: {(len(df)/(t1 - t0)):.2f} rows/sec")
            #logger.debug('Test load only')
        else:
            logger.warning(f"No {'concise' if concise else 'full   '} data available for {datestr}")
        current_date += datetime.timedelta(days=1)


def parallel_load_hist_readings(concise:bool = True,
                                update_recent:bool = False,
                                upto:int = 3,
                                days_per_task:int = 1, max_workers:int = 1,
                                app = None,
                                force_start_date: datetime.date = None,
                                force_end_date: datetime.date = None,
                                force_replace:bool = False
                               ):
    """Launch multiple parallel tasks (one per day of source data) to process historic readings. Each file is multi-chunked"""
    if force_start_date:
        start_date = force_start_date
        if force_end_date:
            end_date = force_end_date
            logger.info(f"({'concise' if concise else 'full   '}) Processing for {start_date}  to {end_date}")
        else:
            end_date = start_date
            logger.info(f"({'concise' if concise else 'full   '}) Processing for {start_date} only")

        delete_readings_by_r_datetime(start_date, end_date, concise=concise)
    elif update_recent:
        row = db.session.execute(
                     text("SELECT date_trunc('day', min(r_datetime))::DATE, date_trunc('day', max(r_datetime))::DATE FROM production.reading_recent WHERE r_date is null;")
                    ).first()

        if row and all(row):
            start_date, end_date = row

            # Set a minimum start_date.
            # There appears to be a lot of rows with dates up to a month before the main attraction.
            # These may be corrections to earlier readings, but ignored here for now.
            # TODO Investigate early dated stray rows in readings "latest" files - corrections?
            #start_date = max(start_date, datetime.date(2025, 6, 18))

            if end_date >= start_date:
                logger.info(f"(recent ) Updating rows in reading_recent from {start_date} to {end_date}")
            else:
                logger.info(f"(recent ) No rows in reading_recent to update")
        else:
            #start_date, end_date = None, None
            logger.info(f"(recent ) No rows in reading_recent to update - Ending")
            return

    else:
        start_date, end_date = get_start_end_dates(concise=concise, upto=upto)
        if end_date >= start_date:
            logger.info(f"({'concise' if concise else 'full   '}) Fetching from {start_date} to {end_date}")
        else:
            logger.info(f"({'concise' if concise else 'full   '}) No new days to fetch")

    all_ranges = []
    current = start_date
    while current <= end_date:
        chunk_end = min(current + datetime.timedelta(days=days_per_task - 1), end_date)
        all_ranges.append((current, chunk_end))
        current = chunk_end + datetime.timedelta(days=1)

    def worker(p_start_date, p_end_date, p_worker_id, xapp=None):
        with xapp.app_context():
            current_date = p_start_date
            while current_date <= p_end_date:
                datestr = current_date.strftime('%Y-%m-%d')
                #logger.info(f"Loading data for {datestr}")

                if update_recent:
                    query = """
                    SELECT *
                    FROM reading_recent
                    WHERE r_date IS NULL
                      AND date_trunc('day', r_datetime)::DATE = %(target_date)s
                    """
                    #logger.info(f"Loading data from reading_recent for {datestr}")
                    try:
                        df = pd.read_sql(query, db.engine, params={"target_date": current_date})
                        # change the r_datetime column name to dateTime to replicate a download from EA
                        df.rename(columns={"r_datetime": "dateTime"}, inplace=True)
                        df=df[["dateTime", "measure", "value"]]

                        #pd.set_option('display.max_columns', None)  # Show all columns
                        #pd.set_option('display.width', None)  # Prevent line breaks
                        #pd.set_option('display.max_colwidth', None)  # Show full column content if needed
                        #logger.info(df.head(3))
                    except Exception as e:
                        logger.exception(f"Error loading readings for {current_date}: {e}")
                        df = None
                else:
                    df = load_hist_reading_data_from_ea(datestr, concise, force_replace=force_replace)

                if df is not None:
                    if update_recent:
                        logger.info(f"(T{p_worker_id}):Loaded data from reading_recent for {datestr} - {len(df)} rows")
                    else:
                        logger.info(f"(T{p_worker_id}):Loading {'concise' if concise else 'full'} data for {datestr} - {len(df)} rows")
                    t0 = time.perf_counter()
                    status_summary = threaded_insert(df,
                                                     chunk_size=5000, max_workers=16,
                                                     ea_datasource=f"EA{'' if concise else '_full_'}{datestr}",
                                                     concise=concise, update_recent=update_recent, app=app, worker_id=p_worker_id
                                                    )
                    t1 = time.perf_counter()
                    logger.info(f"(T{p_worker_id}):Status summary for {datestr}: {dict(sorted(status_summary.items()))}")
                    logger.info(f"(T{p_worker_id}):Process time   for {datestr}: {(t1 - t0):.1f}s - {int(len(df) / (t1 - t0))} rows/sec")
                    # logger.debug('Test load only')
                else:
                    logger.warning(f"(T{p_worker_id}):No {'concise' if concise else 'full'} data available for {datestr}")
                current_date += datetime.timedelta(days=1)

    if len(all_ranges) > 0:
        logger.info(f"Kicking off {len(all_ranges)} parallel tasks")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for worker_id, (start, end) in enumerate(all_ranges):
                executor.submit(worker, start, end, worker_id, xapp=app)


def validate_date(_ctx, _param, value):
    """
    Click callback to validate YYYY-MM-DD dates.
    `_ctx` and `_param` are required by Click but intentionally unused.
    """
    # 1) Already a date? just return it.
    if isinstance(value, datetime.date):
        return value

    #if value is None or (isinstance(value, str) and value.strip() == ""):
    if not value:
        #print ('help me here')  #Interesting - this is called twice?
        return None

    # Ensure it’s a string (CLI always gives strings)
    val = value.strip()
    try:
        return datetime.datetime.strptime(val, '%Y-%m-%d').date()
    except ValueError:
        raise click.BadParameter("Date must be in format YYYY-MM-DD")


