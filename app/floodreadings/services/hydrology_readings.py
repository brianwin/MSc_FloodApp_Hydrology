# app/floodreadings/services/hydrology_readings.py
# Historical readings from the HYDROLOGY API - daily files

# API documentation: https://environment.data.gov.uk/hydrology/doc/reference

import requests
import os

import pandas as pd
import math
import time
from collections import Counter

#from pynput import keyboard
#import threading

from flask import current_app
from sqlalchemy import Date
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import func, distinct, exists, literal_column
from sqlalchemy.sql.expression import cast
from sqlalchemy.dialects.postgresql import insert
#from sqlalchemy import text
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

#from datetime import date, datetime, timedelta, timezone
import datetime
from dateutil.parser import parse

from app import db
from ..models import ReadingHydro
from app.all_stations.models import HydStation   # to get station labels - just a nice to have

import logging
logger = logging.getLogger('floodWatch3')

# annotate the proxy so the IDE knows its real type
from werkzeug.local import LocalProxy
current_app: LocalProxy

#ea_root_url = 'http://environment.data.gov.uk/flood-monitoring'  # original source data (superseded)
ea_root_url = 'http://environment.data.gov.uk/hydrology'          # source data for extended history

# Define stop_event globally
#stop_event = threading.Event()

#def on_press(key):
#    try:
#        if key.char == 'q':
#            print("Detected 'q' — will stop after completing the current task.")
#            stop_event.set()
#    except AttributeError:
#        pass  # Handles special keys like shift, ctrl, etc.


station_labels = None
def get_station_labels(worker_id:int=0):
    """Lazily load station labels on first access."""
    global station_labels
    if station_labels is None:
        #logger.debug(f'(T{worker_id}):Lazy loading station labels')
        try:
            station_labels = {
                row.notation: row.label
                for row in db.session.query(HydStation.notation, HydStation.label).all()
            }
        except Exception as e:
            logger.exception(f'(T{worker_id}):get_station_labels: failed with error: {e}')
        logger.info(f'(T{worker_id}):Loaded {len(station_labels)} station labels into memory cache')
    return station_labels


# for local machine working
# save_basefolder: str = "data/archive",
def get_hydrology_readings (datestr: str,
                            save_basefolder: str = "f:",
                            force_replace:bool = False
                           ) -> pd.DataFrame|None:
    """
    Retrieve a file from the EA HYDROLOGY API corresponding to all readings for one day.
    :param datestr:
    :param save_basefolder:
    :param force_replace:
    :return:
    """

    '''
    measure = {id}
    date = {yyyy-mm-dd}
    min-date = {yyyy-mm-dd}
    mineq-date = {yyyy-mm-dd}
    max-date = {yyyy-mm-dd}
    maxeq-date = {yyyy-mm-dd}
    earliest = {}
    latest = {}
    station = {guid}
    station.RLOIid = {id}
    station.wiskiID = {id}
    observationType = {Qualified|Measured}
    observedProperty = {
        waterFlow|waterLevel|rainfall|groundwaterLevel|
        dissolved-oxygen|fdom|bga|turbidity|chlorophyll|conductivity|temperature|ammonium|nitrate|ph
    }
    period = {number}
    _view = {default|flow|full|min}
    '''

    url = f'{ea_root_url}/data/readings.csv?_view=full&_limit=1000000&date={datestr}'
    save_folder = f'{save_basefolder}/hydrology/'
    filename = f'hydro-{datestr}.csv'

    os.makedirs(save_folder, exist_ok=True)  # Ensure the folder exists
    filepath = os.path.join(save_folder, filename)

    if os.path.exists(filepath):
        if force_replace:
            os.remove(filepath)
            logger.info(f"Removed existing file: {filepath}")
        else:
            if os.path.getsize(filepath) == 0:
                logger.warning(f"File exists, but is empty: {filepath}")
                os.remove(filepath)
                logger.info(f"Removed existing file: {filepath}")
            else:
                df = pd.read_csv(filepath, low_memory=False, dtype=str)
                if df.empty or df.shape[1] == 0:
                    logger.warning(f"File exists, but has no data or columns: {filepath}")
                    os.remove(filepath)
                    logger.info(f"Removed existing file: {filepath}")
                else:
                    logger.info(f"Using existing local file: {filepath}")
                    return df

    # Download if the file doesn't exist after optional deletion
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

    df = pd.read_csv(filepath, low_memory=False, dtype=str)
    return df


def get_hydrology_readings_loop(upto:int = 3,
                                days_per_task:int = 1, max_workers:int = 1,
                                gaps_only:bool = False,
                                app = None,
                                force_start_date: datetime.date = None,
                                force_end_date: datetime.date = None,
                                force_replace:bool = False
                               ):
    #import torch
    #logger.info(f"torch version:   {torch.__version__}")
    #logger.info(f"torch available: {torch.cuda.is_available()}")
    #logger.info(f"torch device:    {torch.cuda.get_device_name(0)}")

    if gaps_only:
        db_start_date, db_end_date = get_db_min_max_dates()
        # If force_start_date is provided, pick the latest of the two
        if force_start_date:
            start_date = max(db_start_date, force_start_date)
        else:
            start_date = db_start_date
        # If force_end_date is provided, pick the earliest of the two
        if force_end_date:
            end_date = min(db_end_date, force_end_date)
        else:
            end_date = db_end_date
    else:
        if force_start_date:
            start_date = force_start_date
            if force_end_date:
                end_date = force_end_date
                logger.info(f"(hydro) Processing for {start_date}  to {end_date}")
            else:
                end_date = start_date
                logger.info(f"(hydro) Processing for {start_date} only")

            #delete_readings_by_r_datetime(start_date, end_date)
        else:
            start_date, end_date = get_start_end_dates(upto=upto)
            if end_date >= start_date:
                logger.info(f"(hydro) Fetching from {start_date} to {end_date}")
            else:
                logger.info(f"(hydro) No new days to fetch")

    def date_in_db(d_date) -> bool:
        """Check if a specific date exists in the ReadingHydro table."""
        return db.session.query(exists().where(cast(ReadingHydro.r_date, Date) == d_date)).scalar()

    all_ranges = []
    # Build a list of eligible dates to process
    current = start_date
    while current <= end_date:
        chunk_end = min(current + datetime.timedelta(days=days_per_task - 1), end_date)

        if gaps_only and date_in_db(current):
            current = chunk_end + datetime.timedelta(days=1)
            continue

        all_ranges.append((current, chunk_end))
        current = chunk_end + datetime.timedelta(days=1)

    def worker(p_start_date, p_end_date, p_worker_id, xapp=None):
        with (xapp.app_context()):
            current_date = p_start_date
            while current_date <= p_end_date:
                #if stop_event.is_set():
                #    #logger.warning(f"(T{p_worker_id}): Stop signal received — exiting early at {current_date}")
                #    return  # Exit cleanly

                datestr = current_date.strftime('%Y-%m-%d')
                #logger.debug(f"++++ Loading data for {datestr}")
                df = get_hydrology_readings(datestr, force_replace=force_replace)
                #logger.debug(f"Obtained {len(df)} rows")

                if df is not None:
                    logger.info(
                            f"(T{p_worker_id}):Loading hydrology data for {datestr} - {len(df)} rows")
                    t0 = time.perf_counter()
                    # if the date does not exist in the database then it's safe to perform a (much faster) bulk load
                    status_summary, insupd_summary = threaded_insert(
                                                      df,
                                                      chunk_size=20000, max_workers=32,
                                                      ea_datasource=f"hydro-{datestr}",
                                                      app=app,
                                                      worker_id=p_worker_id,
                                                      bulk_load= not date_in_db(datestr)
                                                     )
                    t1 = time.perf_counter()
                    logger.info(f"(T{p_worker_id}):Status summary for {datestr}: {dict(sorted(status_summary.items()))}")
                    logger.info(f"(T{p_worker_id}):Action summary for {datestr}: {dict(sorted(insupd_summary.items()))}")
                    logger.info(f"(T{p_worker_id}):Process time   for {datestr}: {(t1 - t0):.1f}s - {int(len(df) / (t1 - t0))} rows/sec")
                    # logger.debug('Test load only')
                else:
                    logger.warning(
                        f"(T{p_worker_id}):No hydrology data available for {datestr}")
                current_date += datetime.timedelta(days=1)


    # Start listener in background
    #listener = keyboard.Listener(on_press=on_press)
    #listener.start()

    if len(all_ranges) > 0:
        logger.info(f"Kicking off {len(all_ranges)} parallel tasks")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for worker_id, (start, end) in enumerate(all_ranges):
                #print ('True' if stop_event.is_set() else 'False')
                #if stop_event.is_set():
                #    logger.warning("User requested stop — no more tasks will be submitted.")
                #    break  # stop submitting new tasks
                executor.submit(worker, start, end, worker_id, xapp=app)
                #time.sleep(0.2)  #TEMP: allows time for 'q' to be detected
    #listener.stop()
    logger.info("Completed processing")


def get_db_max_datetime() -> datetime.datetime:
    logger.debug(f"(hydro) Checking readings in db")
    db.session.remove()
    # Get max r_datetime in the DB
    max_r_datetime = db.session.query(func.max(ReadingHydro.r_datetime)).scalar()
    logger.debug(f"(hydro) Db max_r_datetime : {max_r_datetime}")
    return max_r_datetime


def get_db_min_max_dates() -> [datetime.date, datetime.date]:
    logger.debug(f"(hydro) Checking readings in db")
    db.session.remove()
    # Get min r_date in the DB
    min_r_date = db.session.query(func.min(ReadingHydro.r_datetime)).scalar().date()
    #logger.debug(f"(hydro) min_r_date : {min_r_date}")

    # Get max r_date in the DB
    max_r_date = db.session.query(func.max(ReadingHydro.r_datetime)).scalar().date()
    #logger.debug(f"(hydro) max_r_date : {max_r_date}")

    # Total days in the range (inclusive)
    num_dates = (max_r_date - min_r_date).days  # +1 ???
    #logger.debug(f"(hydro) num_dates : {num_dates}")

    # Count unique days present in the DB
    present_dates = db.session.query(func.count(distinct(func.date(ReadingHydro.r_date)))).scalar()
    #logger.debug(f"(hydro) present_dates : {present_dates}")

    # Calc the number of missing dates
    missing_dates = num_dates - present_dates
    #logger.debug(f"(hydro) missing_dates : {missing_dates}")

    logger.debug(f"(hydro) Db has readings between {min_r_date} and {max_r_date} - {num_dates} days range ({missing_dates} missing)")
    return [min_r_date, max_r_date]


def get_start_end_dates(upto:int = 7) -> [datetime.date, datetime.date]:
    # logger.debug(f"getting database max_r_date")
    # Step 1: Get max r_date in the DB
    db.session.remove()
    #max_r_date = db.session.query(func.max(Reading_Hydro.r_datetime)).scalar()
    _, max_r_date = get_db_min_max_dates()

    logger.debug(f"(hydro) Database max_r_date : {max_r_date}")
    if not max_r_date:
        logger.warning("(hydro) No readings found in DB – starting from default date")
        # Set loop range start (a date)
        start_date = datetime.date(2022, 1, 1)  # or any fallback start date
    else:
        # Set loop range start (a date)
        start_date = max_r_date + datetime.timedelta(days=1)

    # Step 2: Set loop range end
    end_date = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=upto))
    logger.debug(f"{start_date} to {end_date}")
    return [start_date, end_date]

def delete_readings_by_r_datetime(start_date, end_date):
    # the beginning of the day at start_date, UTC aware
    start_dt = date_to_utc_datetime(start_date, end_of_day=False)
    # the end of the day at end_date, UTC aware
    end_dt = date_to_utc_datetime(end_date, end_of_day=True)

    date_range = start_date if end_date == start_date else f"{start_date} to {end_date}"
    model = ReadingHydro

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


def threaded_insert(df:pd.DataFrame,
                    chunk_size:int = 500, max_workers:int = 16,
                    ea_datasource:str = 'EA',
                    app = None, worker_id = 0,
                    bulk_load:bool = False
                   ) -> (int, int):
    logmark = f"(T{worker_id}):f{ea_datasource[-10:].replace('-', '')}"
    chunks = [df.iloc[i:i + chunk_size] for i in range(0, len(df), chunk_size)]
    logger.info(f'{logmark}: {len(chunks)} chunks to be processed ({"bulk load" if bulk_load else "ins/upd"})')

    # Save the current app context
    if app is None:
        # noinspection PyProtectedMember
        app = current_app._get_current_object()
    status_res = [None] * len(chunks)
    insupd_res = [None] * len(chunks)

    with app.app_context():
        stn_labels = get_station_labels(worker_id=worker_id)  # load once

    def run_in_app_context(chunk, chunk_num, labels, source:str = 'EA'):
        with app.app_context():
            #logger.debug(f'{logmark}: Going to insert_chunk({chunk_num})')
            status_res[chunk_num], insupd_res[chunk_num] = insert_chunk(chunk, chunk_num, stn_labels=labels, ea_datasource=source, bulk_load=bulk_load)
            #if status_results[0] != 500:
            #    logger.info(f'{logmark}: chunk {chunk_num} status= {status_results}')

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        with tqdm(total=len(chunks), desc="Processing chunks", unit="chunk", ncols=133) as pbar:
            futures = [
                executor.submit(run_in_app_context, chunk, i, stn_labels, ea_datasource)
                for i, chunk in enumerate(chunks)
            ]
            for future in futures:
                future.result()
                #logger.info(f'{logmark}: chunk {i} to be inserted')
                #executor.submit(insert_chunk_full, chunk, i)
                pbar.update(1)
        logger.info(f"{logmark}: All parallel tasks have completed.")

    # Aggregate all counters
    total_status = Counter()
    for status in status_res:
        if status:
            total_status.update(status)

    total_insupd = Counter()
    for status in insupd_res:
        if status:
            total_insupd.update(status)

    return total_status, total_insupd





def get_scoped_session():
    session_factory = sessionmaker(bind=db.engine)
    return scoped_session(session_factory)


def parse_float_safe(val: str, min_val: float =-9999999.0, max_val:float =9999999.0) -> (float|None, int) :
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
                 bulk_load:bool = False
                ) -> (dict, dict):
    #from . import get_fieldvalue_for_db  # string converter

    session = get_scoped_session()
    #logger.info(f"Inserting chunk {chunk_num} using scoped session")
    status_counter = Counter()
    insupd_counter = Counter()
    try:
        readings = []
        for _, row in chunk_df.iterrows():

            dtm = row.get("dateTime")
            if isinstance(dtm, str):  # a string (as it is when read from a csv file)
                r_datetime = parse(dtm)
            elif pd.notnull(dtm):
                r_datetime = dtm  # already a datetime (as it is when read from a database table)
            else:
                r_datetime = None

            r_month = r_datetime.replace(day=1).date() if r_datetime else None
            #r_date  = r_datetime.date() if r_datetime else None

            measure = row.get("measure", '')
            notation = measure.replace(f'{ea_root_url}/id/measures/', '').strip() if isinstance(measure, str) else None

            parsed = parse_notation(notation)
            label = stn_labels.get(parsed.get("station_id")) if stn_labels else None

            val, status = parse_float_safe(row.get("value"))
            status_counter[status] += 1

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

            reading = {
                'source' : ea_datasource,
                'r_datetime' : r_datetime,
                'r_month' : r_month,
                'r_date' : row.get("date"),

                'measure' : measure,
                'notation' : notation,
                'label' : label,

                # Value
                'value' : val,

                # Data quality attributes
                'completeness' : row.get("completeness"),
                'quality' : row.get("quality"),
                'qcode' : row.get("qcode"),
                'valid' : row.get("valid"),
                'invalid' : row.get("invalid"),
                'missing' : row.get("missing"),

                # Parsed "notation" fields (from "measure" in sources data)
                'station_id': parsed.get("station_id") if parsed else None,
                'parameter_name': parsed.get("parameter_name") if parsed else None,
                'parameter': parsed.get("parameter") if parsed else None,
                'qualifier': parsed.get("qualifier") if parsed else None,
                'value_type': parsed.get("value_type") if parsed else None,
                'period_name': parsed.get("period_name") if parsed else None,
                'unit_name': parsed.get("unit_name") if parsed else None,
                'observation_type': parsed.get("observation_type") if parsed else None,
                'updated': None
            }

            readings.append(reading)

        #logger.info(f'Chunk {chunk_num}: generated - {len(readings)} records')
        #logger.debug(f"Readings generated: {readings[:2]}")  # Print first two for inspection
        #t0 = time.perf_counter()
        ##session.add_all(readings)

        #logger.debug(f"Starting bulk insert for chunk {chunk_num}")

        if bulk_load:
            # Just bulk insert all rows available in the datafile
            session.bulk_insert_mappings(ReadingHydro, readings)  # type: ignore   #Tells type checker: ReadingHydro is a mapped class
        else:
            stmt = insert(ReadingHydro).values(readings)

            update_fields = ['value', 'completeness', 'quality', 'qcode', 'valid', 'invalid', 'missing']
            update_dict = {field: stmt.excluded[field] for field in update_fields}
            update_dict['updated'] = func.now()  # set updated timestamp on actual update

            # Optimisation: Put most frequently changed columns first to reduce comparisons
            where_clause = (
                    (ReadingHydro.quality.is_distinct_from(stmt.excluded.quality)) |
                    (ReadingHydro.completeness.is_distinct_from(stmt.excluded.completeness)) |
                    (ReadingHydro.qcode.is_distinct_from(stmt.excluded.qcode)) |
                    (ReadingHydro.value.is_distinct_from(stmt.excluded.value)) |
                    (ReadingHydro.valid.is_distinct_from(stmt.excluded.valid)) |
                    (ReadingHydro.invalid.is_distinct_from(stmt.excluded.invalid)) |
                    (ReadingHydro.missing.is_distinct_from(stmt.excluded.missing))
            )

            conflict_stmt = stmt.on_conflict_do_update(
                index_elements=['measure', 'r_datetime'],
                set_=update_dict,
                where=where_clause
            ).returning(literal_column('xmax'))   # PostgreSQL special system column

            #logger.debug(f"Conflict statement: {conflict_stmt}")
            result = session.execute(conflict_stmt)

            # Counts
            rows = result.fetchall()
            # Note: row.xmax is not a reliable way to distinguish between insert and update from an upsert statement
            insupd_counter['inserted'] = sum(1 for row in rows if row.xmax == 0)  # Inserted rows
            insupd_counter['updated']  = sum(1 for row in rows if row.xmax != 0)  # Updated rows
            #logger.debug(f"Chunk {chunk_num}: Inserted rows: {insupd_counter['inserted']}, Updated rows: {insupd_counter['updated']}")

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
        return status_counter, insupd_counter



def parse_notation(notation):
    parts = notation.rsplit('-', 10)
    n_dashes = len(parts) - 1
    try:
        if n_dashes == 3:
            # example
            # E01591A-ph-i-subdaily
            return {
                'station_id': parts[0],
                'parameter': parts[1],
                'value_type': parts[2],
                'period_name': parts[3]
            }
        elif n_dashes == 4:
            # example
            # E02763A-bga-i-subdaily-rfu
            return {
                'station_id': parts[0],
                'parameter': parts[1],
                'value_type': parts[2],
                'period_name': parts[3],
                'unit_name': parts[4]
            }
        elif n_dashes == 9:
            # example
            # ac462a74-4fe2-41d7-a35b-e51ffd6c9a0f-level-i-900-m-qualified
            # 2c14fcb6-21f3-47ca-8e50-14c68d23e5fb_SE52HCL1SS-gw-dipped-i-mAOD-qualified
            if '-'.join(parts[5:7]) == 'gw-dipped':
                return {
                    'station_id': '-'.join(parts[:5]),
                    'parameter': parts[5],
                    'qualifier': parts[6],
                    'value_type': parts[7],
                    'unit_name': parts[8],
                    'observation_type': parts[9]
            }
            else:
                return {
                    'station_id': '-'.join(parts[:5]),
                    'parameter': parts[5],
                    'value_type': parts[6],
                    'period_name': parts[7],
                    'unit_name': parts[8],
                    'observation_type': parts[9]
                }
        elif n_dashes == 10:
            # example
            # 1cdd6e48-7bcb-4f32-b8a8-3500a8a352b0-gw-logged-i-subdaily-mAOD-qualified
            return {
                'station_id': '-'.join(parts[:5]),
                'parameter': parts[5],
                'qualifier': parts[6],
                'value_type': parts[7],
                'period_name': parts[8],
                'unit_name': parts[9],
                'observation_type': parts[10]
            }

        # if it gets this far and has not yet returned a dict, then
        logger.warning(f"Unrecognized notation format: '{notation}' ({n_dashes} dashes)")

    except Exception as e:
        logger.debug(f"Error parsing notation '{notation}': {e}")
    return None  # fallback for unknown format or error
