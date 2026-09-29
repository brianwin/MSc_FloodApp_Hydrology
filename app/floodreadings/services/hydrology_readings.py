# app/floodreadings/services/hydrology_readings.py
# Historical readings from the HYDROLOGY API - daily files

# API documentation: https://environment.data.gov.uk/hydrology/doc/reference

import requests
import os
import csv
import hashlib
import re
from pathlib import Path

import pandas as pd
import math
import time
from collections import Counter

#from pynput import keyboard
#import threading

from flask import current_app
from sqlalchemy import Date
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import select, func, distinct, exists, literal_column
from sqlalchemy.sql.expression import cast
from sqlalchemy.dialects.postgresql import insert
#from sqlalchemy import text
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

#from datetime import date, datetime, timedelta, timezone
import datetime
from dateutil.parser import parse

from app import db
from ..models import HydrologyDailyProfile, ReadingHydro
from app.all_stations.models import HydStation   # to get station labels - just a nice to have
from .hydrology_load_audit import (
    capture_daily_profile,
    create_load_run,
    finish_load_run,
    get_daily_row_count,
)

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


def calculate_file_sha256(filepath: str, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of a source file without loading it into memory."""
    digest = hashlib.sha256()
    with open(filepath, "rb") as source_file:
        for chunk in iter(lambda: source_file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attach_source_checksum(df: pd.DataFrame, filepath: str) -> pd.DataFrame:
    """Attach source-file provenance to a dataframe without changing its columns."""
    source_sha256 = calculate_file_sha256(filepath)
    df.attrs["source_sha256"] = source_sha256
    logger.info(f"Source SHA-256: {source_sha256}")
    return df


_SOURCE_FILE_PATTERN = re.compile(r"^hydro-(\d{4}-\d{2}-\d{2})\.csv$")


def _count_csv_data_rows(filepath: Path) -> int:
    """Count logical CSV records, excluding the header, without loading the file."""
    with filepath.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.reader(source_file)
        next(reader, None)
        return sum(1 for _ in reader)


def backfill_hydrology_source_checksums(
    source_root="readings_hydrology_tn/hydrology",
    start_date=None,
    end_date=None,
):
    """Append checksum_backfill profiles for existing daily source CSV files.

    This operation reads local files only. It does not download source data or
    change production.reading_hydro.
    """
    source_root = Path(source_root)
    if not source_root.is_dir():
        raise FileNotFoundError(f"Hydrology source directory not found: {source_root}")

    candidates = []
    invalid_files = []
    for filepath in sorted(source_root.rglob("hydro-*.csv")):
        match = _SOURCE_FILE_PATTERN.fullmatch(filepath.name)
        if not match:
            invalid_files.append(str(filepath))
            continue
        try:
            r_date = datetime.date.fromisoformat(match.group(1))
        except ValueError:
            invalid_files.append(str(filepath))
            continue
        if start_date and r_date < start_date:
            continue
        if end_date and r_date > end_date:
            continue
        candidates.append((r_date, filepath))

    effective_start = candidates[0][0] if candidates else start_date
    effective_end = candidates[-1][0] if candidates else end_date
    run_id = create_load_run(
        command="backfill-hydrology-source-checksums",
        start_date=effective_start,
        end_date=effective_end,
        requested_dates=len(candidates),
    )

    created = 0
    unchanged = 0
    missing_profile = 0
    failed = 0
    errors = []

    for r_date, filepath in candidates:
        try:
            source_sha256 = calculate_file_sha256(str(filepath))
            latest_profile = (
                db.session.query(HydrologyDailyProfile)
                .filter(
                    HydrologyDailyProfile.r_date == r_date,
                    HydrologyDailyProfile.status == "succeeded",
                    HydrologyDailyProfile.after_row_count.isnot(None),
                )
                .order_by(
                    HydrologyDailyProfile.recorded_at.desc(),
                    HydrologyDailyProfile.id.desc(),
                )
                .first()
            )

            if latest_profile is None:
                missing_profile += 1
                errors.append(f"{r_date}: no successful database profile")
                logger.warning(
                    f"Skipping checksum backfill for {r_date}: "
                    "no successful database profile"
                )
                continue

            if latest_profile.source_sha256 == source_sha256:
                unchanged += 1
                continue

            profile = HydrologyDailyProfile(
                load_run_id=run_id,
                profile_kind="checksum_backfill",
                r_date=r_date,
                status="succeeded",
                before_row_count=latest_profile.after_row_count,
                source_row_count=_count_csv_data_rows(filepath),
                source_sha256=source_sha256,
                after_row_count=latest_profile.after_row_count,
                station_count=latest_profile.station_count,
                measure_count=latest_profile.measure_count,
                first_reading_at=latest_profile.first_reading_at,
                last_reading_at=latest_profile.last_reading_at,
            )
            db.session.add(profile)
            db.session.commit()
            created += 1
        except Exception as exc:
            db.session.rollback()
            failed += 1
            errors.append(f"{r_date}: {exc}")
            logger.exception(f"Checksum backfill failed for {filepath}")

    completed = created + unchanged
    unsuccessful = missing_profile + failed
    status = "succeeded" if unsuccessful == 0 else (
        "partial" if completed else "failed"
    )
    finish_load_run(
        run_id,
        status=status,
        completed_dates=completed,
        failed_dates=unsuccessful,
        error_message="; ".join(errors)[:4000] or None,
    )

    return run_id, {
        "files_found": len(candidates),
        "profiles_created": created,
        "unchanged": unchanged,
        "missing_profile": missing_profile,
        "failed": failed,
        "invalid_files": len(invalid_files),
    }


# for local machine working
# save_basefolder: str = "data/archive",
def _validate_hydrology_dataframe(
    df: pd.DataFrame, datestr: str, source_path: str
) -> None:
    """Reject empty, malformed, or wrong-date hydrology source data."""
    if df.empty:
        raise ValueError(f"Hydrology source file has no data rows: {source_path}")

    required_columns = {"measure", "dateTime", "date", "value"}
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        raise ValueError(
            f"Hydrology source file is missing required columns "
            f"{missing_columns}: {source_path}"
        )

    source_dates = set(df["date"].dropna().unique())
    unexpected_dates = sorted(source_dates.difference({datestr}))
    if not source_dates or unexpected_dates:
        raise ValueError(
            f"Hydrology source file contains unexpected dates "
            f"{sorted(source_dates)}; expected only {datestr}: {source_path}"
        )


# for local machine working
# save_basefolder: str = "data/archive",
def get_hydrology_readings(
    datestr: str,
    save_basefolder: str = "readings_hydrology_tn/hydrology",
    force_replace: bool = False,
) -> pd.DataFrame | None:
    """Retrieve and validate one daily readings file from the EA Hydrology API.

    A replacement download is written beside the archive file with a .part
    suffix. The existing archive file is preserved until the new file has been
    fully written, parsed, validated, and hashed. os.replace then publishes the
    validated file atomically.
    """
    logger.info(f"Processing date: {datestr}")
    logger.info(f"save_basefolder: {save_basefolder}")
    logger.info(f"force_replace  : {force_replace}")

    url = (
        f"{ea_root_url}/data/readings.csv"
        f"?_view=full&_limit=1000000&date={datestr}"
    )
    year = datestr[:4]
    save_folder = os.path.join(save_basefolder, year)
    filename = f"hydro-{datestr}.csv"

    os.makedirs(save_folder, exist_ok=True)
    filepath = os.path.join(save_folder, filename)
    logger.info(f"filepath  : {filepath}")

    if os.path.exists(filepath) and not force_replace:
        logger.info("filepath found; validating existing local file")
        try:
            df = pd.read_csv(filepath, low_memory=False, dtype=str)
            _validate_hydrology_dataframe(df, datestr, filepath)
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            logger.warning(
                f"Existing local file failed validation and will be preserved "
                f"until a valid replacement is available: {filepath}: {exc}"
            )
        else:
            logger.info(f"Using existing validated local file: {filepath}")
            return attach_source_checksum(df, filepath)
    elif os.path.exists(filepath):
        logger.info(
            f"force_replace=True; preserving existing file until a validated "
            f"replacement is ready: {filepath}"
        )

    part_filepath = f"{filepath}.{os.getpid()}.part"
    t0 = time.perf_counter()
    response = requests.get(url, stream=True, timeout=60)
    t1 = time.perf_counter()

    if response.status_code != 200:
        logger.warning(
            f"Response {response.status_code}: Failed to fetch data from {url}"
        )
        return None

    logger.info(f"Fetching {url}")
    nbytes = 0
    try:
        with open(part_filepath, "wb", buffering=1024 * 1024) as part_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                part_file.write(chunk)
                nbytes += len(chunk)
        t2 = time.perf_counter()

        df = pd.read_csv(part_filepath, low_memory=False, dtype=str)
        _validate_hydrology_dataframe(df, datestr, part_filepath)
        attach_source_checksum(df, part_filepath)
        t3 = time.perf_counter()

        os.replace(part_filepath, filepath)
        logger.info(f"Validated and atomically saved: {filepath}")
    except Exception:
        if os.path.exists(part_filepath):
            try:
                os.remove(part_filepath)
            except OSError:
                logger.exception(
                    f"Could not remove failed temporary download: {part_filepath}"
                )
        raise

    write_seconds = max(t2 - t1, 1e-9)
    logger.info(f"GET (headers/conn): {t1 - t0:.3f}s")
    logger.info(
        f"WRITE {nbytes / 1e6:.1f} MB: {write_seconds:.3f}s "
        f" -> {(nbytes / 1e6) / write_seconds:.1f} MB/s"
    )
    logger.info(f"read_csv/validate/hash: {t3 - t2:.3f}s")
    logger.info(
        f"TOTAL: {t3 - t0:.3f}s, "
        f"file size on disk: {os.path.getsize(filepath) / 1e6:.1f} MB"
    )
    return df


def _latest_successful_checksum_profile(r_date):
    """Return the newest successful profile that links source data to DB state."""
    return (
        db.session.query(HydrologyDailyProfile)
        .filter(
            HydrologyDailyProfile.r_date == r_date,
            HydrologyDailyProfile.status == "succeeded",
            HydrologyDailyProfile.source_sha256.isnot(None),
            HydrologyDailyProfile.after_row_count.isnot(None),
        )
        .order_by(
            HydrologyDailyProfile.recorded_at.desc(),
            HydrologyDailyProfile.id.desc(),
        )
        .first()
    )


def _record_unchanged_profile(
    *, r_date, load_run_id, previous_profile, source_row_count, source_sha256
):
    """Record a verified checksum match without rescanning or changing readings."""
    profile = HydrologyDailyProfile(
        load_run_id=load_run_id,
        profile_kind="unchanged",
        r_date=r_date,
        status="succeeded",
        before_row_count=previous_profile.after_row_count,
        source_row_count=source_row_count,
        source_sha256=source_sha256,
        after_row_count=previous_profile.after_row_count,
        station_count=previous_profile.station_count,
        measure_count=previous_profile.measure_count,
        first_reading_at=previous_profile.first_reading_at,
        last_reading_at=previous_profile.last_reading_at,
        rows_deleted=0,
        rows_inserted=0,
        rows_updated=0,
        rows_affected=0,
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def get_hydrology_readings_loop(upto:int = 3,
                                days_per_task:int = 1, max_workers:int = 1,
                                gaps_only:bool = False,
                                app = None,
                                force_start_date: datetime.date = None,
                                force_end_date: datetime.date = None,
                                force_replace:bool = False,
                                force_replace_at_db:bool = False
                               ):
    #import torch
    #logger.info(f"torch version:   {torch.__version__}")
    #logger.info(f"torch available: {torch.cuda.is_available()}")
    #logger.info(f"torch device:    {torch.cuda.get_device_name(0)}")

    if gaps_only:
        db_start_date, db_end_date = get_db_min_max_dates()
        # If force_start_date is provided, pick the latest of the two
        if force_start_date:
            #start_date = max(db_start_date, force_start_date)
            start_date = force_start_date
        else:
            start_date = db_start_date
        # If force_end_date is provided, pick the earliest of the two
        if force_end_date:
            #end_date = min(db_end_date, force_end_date)
            end_date = force_end_date
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
        try:
            date_exists = db.session.query(exists().where(cast(ReadingHydro.r_date, Date) == d_date)).scalar()
            return date_exists
        finally:
            db.session.rollback()

    def delete_for_date(d_date):
        """
        Delete all rows from ReadingHydro where the DATE(r_datetime) = d_date.
        Note: It is much quicker to replace a whole days data than to update/insert from a more recent file
        Args:
            d_date (date): The date to delete for.
        """
        #logger.info(f"(T):delete_for_date {d_date}:  BEGIN")

        if isinstance(d_date, datetime.datetime):
            d_date = d_date.date()
        elif isinstance(d_date, str):
            d_date = datetime.date.fromisoformat(d_date)

        xstart = datetime.datetime.combine(d_date, datetime.datetime.min.time())
        xend = xstart + datetime.timedelta(days=1)

        #logger.info(f"(T):{xstart} to {xend}")
        #count = (
        #    db.session.query(ReadingHydro)
        #    .filter(ReadingHydro.r_datetime >= xstart,
        #            ReadingHydro.r_datetime < xend)
        #    .count()
        #)
        #print(f"Would delete {count} rows")

        ## Begin a transaction
        #trans = db.session.begin_nested()

        rows_deleted = (
            db.session.query(ReadingHydro)
            .filter(ReadingHydro.r_datetime >= xstart,
                    ReadingHydro.r_datetime < xend)
            .delete(synchronize_session=False)
        )

        #logger.info(f"(T):delete_for_date {d_date}:  {rows_deleted} rows")
        ## Rollback to undo the delete
        #trans.rollback()

        db.session.commit()
        return rows_deleted

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

    requested_dates = sum((range_end - range_start).days + 1 for range_start, range_end in all_ranges)
    command = "hydrology-gaps" if gaps_only else (
        "hydrology-replace" if force_replace_at_db else "hydrology-load"
    )
    load_run_id = create_load_run(
        command=command,
        start_date=start_date,
        end_date=end_date,
        requested_dates=requested_dates,
        gaps_only=gaps_only,
        force_replace_file=force_replace,
        force_replace_db=force_replace_at_db,
    )

    def worker(p_start_date, p_end_date, p_worker_id, xapp=None):
        with (xapp.app_context()):
            completed_dates = []
            failed_dates = []
            current_date = p_start_date
            while current_date <= p_end_date:
                #if stop_event.is_set():
                #    #logger.warning(f"(T{p_worker_id}): Stop signal received — exiting early at {current_date}")
                #    return  # Exit cleanly

                datestr = current_date.strftime('%Y-%m-%d')
                before_row_count = get_daily_row_count(current_date)
                source_row_count = None
                source_sha256 = None
                deleted_rows = 0
                try:
                    date_exists = before_row_count > 0
                    logger.debug(f"++++ Loading data for {datestr}")
                    df = get_hydrology_readings(datestr, force_replace=force_replace)
                    if df is None:
                        raise RuntimeError(f"No hydrology source data available for {datestr}")
                    source_row_count = len(df)
                    source_sha256 = df.attrs.get("source_sha256")
                    logger.debug(f"Obtained {source_row_count} rows")

                    previous_profile = _latest_successful_checksum_profile(current_date)
                    checksum_unchanged = (
                        previous_profile is not None
                        and source_sha256 is not None
                        and source_sha256 == previous_profile.source_sha256
                        and before_row_count > 0
                        and before_row_count == previous_profile.after_row_count
                    )
                    if checksum_unchanged:
                        logger.info(
                            f"(T{p_worker_id}):Source checksum unchanged for {datestr}; "
                            f"database already contains {before_row_count} verified rows. "
                            "Skipping delete and reload."
                        )
                        _record_unchanged_profile(
                            r_date=current_date,
                            load_run_id=load_run_id,
                            previous_profile=previous_profile,
                            source_row_count=source_row_count,
                            source_sha256=source_sha256,
                        )
                        completed_dates.append(current_date)
                        current_date += datetime.timedelta(days=1)
                        continue

                    replace_day = False
                    if force_replace_at_db:
                        deleted_rows = delete_for_date(datestr)
                        logger.info(
                            f"(T{p_worker_id}):Deleted from readings table for {datestr}:  {deleted_rows} rows")
                        replace_day = True
                    logger.info(
                        f"(T{p_worker_id}):Loading hydrology data for {datestr} - {len(df)} rows")
                    t0 = time.perf_counter()
                    # if the date does not exist in the database then it's safe to perform a (much faster) bulk load
                    status_summary, insupd_summary = threaded_insert(
                                                      df,
                                                      chunk_size=20000, max_workers=8,  #was 32 (too much WAL bound concurrency)
                                                      ea_datasource=f"hydro-{datestr}",
                                                      app=app,
                                                      worker_id=p_worker_id,
                                                      bulk_load= replace_day or (not date_exists)
                                                     )
                    t1 = time.perf_counter()
                    logger.info(f"(T{p_worker_id}):Status summary for {datestr}: {dict(sorted(status_summary.items()))}")
                    logger.info(f"(T{p_worker_id}):Action summary for {datestr}: {dict(sorted(insupd_summary.items()))}")
                    logger.info(f"(T{p_worker_id}):Process time   for {datestr}: {(t1 - t0):.1f}s - {int(len(df) / (t1 - t0))} rows/sec")
                    capture_daily_profile(
                        r_date=current_date,
                        load_run_id=load_run_id,
                        before_row_count=before_row_count,
                        source_row_count=source_row_count,
                        source_sha256=source_sha256,
                        rows_deleted=deleted_rows,
                        rows_inserted=insupd_summary.get("inserted", 0),
                        rows_updated=insupd_summary.get("updated", 0),
                        rows_affected=insupd_summary.get("affected", 0),
                    )
                    completed_dates.append(current_date)
                except Exception as exc:
                    logger.exception(f"(T{p_worker_id}):Hydrology load failed for {datestr}")
                    db.session.rollback()
                    try:
                        capture_daily_profile(
                            r_date=current_date,
                            load_run_id=load_run_id,
                            status="failed",
                            before_row_count=before_row_count,
                            source_row_count=source_row_count,
                            source_sha256=source_sha256,
                            rows_deleted=deleted_rows,
                            error_message=str(exc)[:4000],
                        )
                    except Exception:
                        db.session.rollback()
                        logger.exception(f"(T{p_worker_id}):Could not record failure profile for {datestr}")
                    failed_dates.append((current_date, str(exc)))
                current_date += datetime.timedelta(days=1)
            return completed_dates, failed_dates


    # Start listener in background
    #listener = keyboard.Listener(on_press=on_press)
    #listener.start()

    completed_dates = []
    failed_dates = []
    try:
        if len(all_ranges) > 0:
            logger.info(f"Kicking off {len(all_ranges)} parallel tasks")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for worker_id, (start, end) in enumerate(all_ranges):
                #print ('True' if stop_event.is_set() else 'False')
                #if stop_event.is_set():
                #    logger.warning("User requested stop — no more tasks will be submitted.")
                #    break  # stop submitting new tasks
                    futures.append(executor.submit(worker, start, end, worker_id, xapp=app))
                #time.sleep(0.2)  #TEMP: allows time for 'q' to be detected
                for future in futures:
                    worker_completed, worker_failed = future.result()
                    completed_dates.extend(worker_completed)
                    failed_dates.extend(worker_failed)
        status = "succeeded" if not failed_dates else (
            "partial" if completed_dates else "failed"
        )
        errors = "; ".join(f"{date}: {message}" for date, message in failed_dates)
        finish_load_run(
            load_run_id,
            status=status,
            completed_dates=len(completed_dates),
            failed_dates=len(failed_dates),
            error_message=errors[:4000] or None,
        )
        if failed_dates:
            raise RuntimeError(
                f"Hydrology load run {load_run_id} failed for {len(failed_dates)} date(s)"
            )
    except Exception as exc:
        db.session.rollback()
        if not failed_dates:
            finish_load_run(
                load_run_id,
                status="failed",
                completed_dates=len(completed_dates),
                failed_dates=max(1, requested_dates - len(completed_dates)),
                error_message=str(exc)[:4000],
            )
        raise
    #listener.stop()
    logger.info(f"Completed processing (audit run {load_run_id})")
    return load_run_id


#def get_db_max_datetime() -> datetime.datetime:
#    logger.debug(f"(hydro) Checking readings in db")
#    db.session.remove()
#    # Get max r_datetime in the DB
#    max_r_datetime = db.session.query(func.max(ReadingHydro.r_datetime)).scalar()
#    logger.debug(f"(hydro) Db max_r_datetime : {max_r_datetime}")
#    return max_r_datetime

def get_db_min_max_dates(show_missing_days = True) -> tuple[datetime.date, datetime.date]:
    logger.debug("(hydro) Checking readings in db")

    # Get min/max r_date in the DB - utilises timescaledb pruning - speedy
    stmt1 = select(
        func.min(ReadingHydro.r_datetime).label("min_dt"),
        func.max(ReadingHydro.r_datetime).label("max_dt")
    )
    with db.engine.connect() as conn:
        row1 = conn.execute(stmt1).one()
        #logger.debug(f"(hydro) row 1 done")

    min_dt = row1.min_dt.date()
    max_dt = row1.max_dt.date()
    num_days = (max_dt - min_dt).days + 1

    if show_missing_days:
        # Get count of unique days present in the DB - scans each timescaledb chunk so a bit long winded - slow for first execution
        stmt2 = select(
            func.count(distinct(ReadingHydro.r_date)).label("present_days")
        )

        with db.engine.connect() as conn:
            row2 = conn.execute(stmt2).one()
            #logger.debug(f"(hydro) row 2 done")

        present_days = row2.present_days
        missing_days = num_days - present_days

        logger.debug(
            f"(hydro) Db has readings between {min_dt} and {max_dt} "
            f"- {num_days} days range ({missing_days} missing)"
        )

    else:
        logger.debug(f"(hydro) Db has readings between {min_dt} and {max_dt} ")
    return min_dt, max_dt


def get_start_end_dates(upto:int = 7) -> [datetime.date, datetime.date]:
    # logger.debug(f"getting database max_r_date")
    # Step 1: Get max r_date in the DB
    _, max_r_date = get_db_min_max_dates(show_missing_days=False)

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
                    chunk_size:int = 500, max_workers:int = 8,
                    ea_datasource:str = 'EA',
                    app = None, worker_id = 0,
                    bulk_load:bool = False
                   ) -> (int, int):
    logmark = f"(T{worker_id}):f{ea_datasource[-10:].replace('-', '')}"

    #chunks = [df.iloc[i:i + chunk_size] for i in range(0, len(df), chunk_size)]  #replaced 10/02/2026
    effective_chunk_size = chunk_size
    if not bulk_load:
        # Avoid parameter explosion on ON CONFLICT
        effective_chunk_size = min(chunk_size, 2000)
    chunks = [df.iloc[i:i + effective_chunk_size] for i in range(0, len(df), effective_chunk_size)]

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

def get_session():
    """Create a new SQLAlchemy session bound to the Flask-SQLAlchemy engine.
    Must be called within an active Flask application context.
    """
    return sessionmaker(bind=db.engine)()

def insert_chunk(chunk_df: pd.DataFrame,
                 chunk_num: int,
                 stn_labels = None,
                 ea_datasource:str = 'EA',
                 bulk_load:bool = False
                ) -> (dict, dict):
    #from . import get_fieldvalue_for_db  # string converter

    #session = get_scoped_session()
    session = get_session()

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
            insupd_counter['inserted'] += len(readings)
            insupd_counter['affected'] += len(readings)
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
            )  #.returning(literal_column('xmax'))   # PostgreSQL special system column

            #logger.debug(f"Conflict statement: {conflict_stmt}")
            result = session.execute(conflict_stmt)

            # PostgreSQL reports the total number inserted or materially updated.
            # It cannot reliably split INSERT from UPDATE without additional
            # per-row bookkeeping, so retain the honest aggregate instead.
            insupd_counter['affected'] += result.rowcount

        session.commit()
        #t1 = time.perf_counter()
        #logger.info(f"DB insert time for chunk {chunk_num}: {t1 - t0:.2f}s")
        #logger.info(f"Chunk {chunk_num}: inserted {len(readings)} records")
    except Exception as e:
        session.rollback()
        logger.exception(f"Chunk {chunk_num}: failed with error: {e}")
        raise
    finally:
        session.close()
    return status_counter, insupd_counter



def parse_notation(notation):
    if not notation or not isinstance(notation, str):
        logger.debug(f"Skipping invalid notation: {notation!r}")
        return None

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
