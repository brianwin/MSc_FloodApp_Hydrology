# app/cli.py
import click
from flask.cli import with_appcontext
from flask import current_app
from app.extensions import db
import datetime

from .all_stations.services import load_hyd_station_data_from_ea, load_hyd_measure_data_from_ea
from .all_stations.services import load_fld_station_data_from_ea, load_fld_measure_data_from_ea
from .floodareas.services import load_floodarea_data_from_ea
from .floodreadings.services import get_hydrology_readings_loop
from .floodreadings.models import ReadingHydro
from .climatology.services import run_climatology_range, run_climatology_baseline, run_climatology_baseline_weibull

from sqlalchemy.sql import func
from .utils import validate_date

import logging
logger=logging.getLogger('floodWatch3')

# annotate the proxy so the IDE knows its real type
from werkzeug.local import LocalProxy
current_app: LocalProxy
from concurrent.futures import ThreadPoolExecutor
from rich.progress import Progress


@click.command("init-db")
@with_appcontext
def init_db_command():
    # db.create_all() will create tables for all models that have been previously imported.
    # Therefore, it is not necessary to import models here

    # All context-sensitive imports and init for building the database schema
    #from .all_stations.models import (     # noqa  (suppress 'Unused'warning)
    #    HydStationMeta, HydStationJson,
    #    HydStation, HydStationType, HydStationObservedProp,
    #    HydStationStatus, HydStationMeasure, HydStationColocated,
    #    HydMeasureMeta, HydMeasure
    #)
    #from .floodareas.models import (     # noqa  (suppress 'Unused'warning)
    #    FloodareaMeta,
    #    FloodareaJson,
    #    Floodarea,
    #    FloodareaPolygon,
    #    FloodareaMetrics
    #)
    #from .floodreadings.models import (ReadingHydro)

    print(f'The following tables will be created if they do not already exist')
    for table in sorted(db.metadata.sorted_tables, key=lambda t: (t.schema or '', t.name)):
        print(f'{table.schema}.{table.name}')

    db.create_all()
    click.echo("✅ Database tables created.")


@click.command("load-hyd-station-data")   # ← This is the CLI command name you will use in the terminal
@with_appcontext
def load_hyd_station_data_command():
    """Load EA station data into the database."""
    load_hyd_station_data_from_ea()

@click.command("load-hyd-measure-data")   # ← This is the CLI command name you will use in the terminal
@with_appcontext
def load_hyd_measure_data_command():
    """Load EA measure data into the database."""
    load_hyd_measure_data_from_ea()

@click.command("load-fld-station-data")   # ← This is the CLI command name you will use in the terminal
@with_appcontext
def load_fld_station_data_command():
    """Load EA station data into the database."""
    load_fld_station_data_from_ea()

@click.command("load-fld-measure-data")   # ← This is the CLI command name you will use in the terminal
@with_appcontext
def load_fld_measure_data_command():
    """Load EA measure data into the database."""
    load_fld_measure_data_from_ea()




@click.command("load-floodarea-data")   # ← This is the CLI command name you will use in the terminal
@with_appcontext
def load_floodarea_data_command():
    """Load EA flood area data into the database."""
    load_floodarea_data_from_ea()

@click.command("load-floodarea-metrics")   # ← This is the CLI command name you will use in the terminal
@with_appcontext
def load_floodarea_metrics_command():
    """Load EA flood area data into the database."""
    #load_floodarea_metrics()



# This is for the hydrology API
@click.command('get-hydrology-readings-data')
@click.option('--force_start_date',
              prompt='Force a start date to replace existing values (YYYY-MM-DD)',
              callback=validate_date,
              default="", show_default=False)
@click.option('--force_end_date',
              prompt='Force an end date  to replace existing values (YYYY-MM-DD)',
              callback=validate_date,
              default="", show_default=False)
@click.option('--force_replace',
              prompt='Force upload of EA data and replace existing file (Y/n)',
              default=False, show_default=True)
@with_appcontext
def get_hydrology_data_command(force_start_date, force_end_date, force_replace):
    """Get 'reading' data from the hydrology API"""
    if not force_end_date:
        force_end_date = force_start_date

    # noinspection PyProtectedMember
    app = current_app._get_current_object()
    with app.app_context():
        get_hydrology_readings_loop(app=app,
                                    force_start_date=force_start_date,
                                    force_end_date=force_end_date,
                                    force_replace=force_replace,
                                    force_replace_at_db=True
                                   )


@click.command('get-hydrology-readings-data-latest')
# These command line options are set in PyCharm CLI run configuration parameters
@click.option('--num_days_before_last_reading', default=14, help="Update changes, insert new data")
@with_appcontext
def get_hydrology_data_latest_command(num_days_before_last_reading):
    """Get 'reading' data from the hydrology API"""
    # noinspection PyProtectedMember
    app = current_app._get_current_object()
    with app.app_context():
        #TODO This needs to start 14 days prior to latest r_date from ReadingHydro
        force_end_date = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1))
        force_start_date = db.session.query(func.max(ReadingHydro.r_datetime)).scalar().date()- datetime.timedelta(days=num_days_before_last_reading)
        get_hydrology_readings_loop(app=app,
                                    force_start_date=force_start_date,
                                    force_end_date=force_end_date,
                                    force_replace=True,
                                    force_replace_at_db=True
                                   )


@click.command('get-hydrology-readings-data-gaps')
# These command line options are set in PyCharm CLI run configuration parameters
@click.option('--gaps-only', is_flag=True, default=True, help="Process only gaps")
@click.option('--force_start_date', type=click.DateTime(formats=["%Y-%m-%d"]), callback=validate_date,
              required=False, help="Start date (YYYY-MM-DD)"
             )
@click.option('--force_end_date',   type=click.DateTime(formats=["%Y-%m-%d"]), callback=validate_date,
              required=False, help="End date (YYYY-MM-DD)"
             )
@click.option('--force_replace', is_flag=True, default=False, help="Force replace existing data files from source")

@with_appcontext
def get_hydrology_data_gaps_command(gaps_only, force_start_date, force_end_date, force_replace):
    """Get 'reading' data from the hydrology API"""
    # noinspection PyProtectedMember
    app = current_app._get_current_object()
    with app.app_context():
        get_hydrology_readings_loop(app=app,
                                    gaps_only=gaps_only,
                                    force_start_date=force_start_date.date() if force_start_date is not None else None,
                                    force_end_date  =force_end_date.date() if force_end_date  is not None else None,
                                    force_replace=force_replace
                                   )


def run_climatology_with_context(app, start_date, end_date, worker_id):
    """Wrap run_climatology_range with an app context and worker logging."""
    with app.app_context():
        logger.info(f"[T{worker_id}]: Starting climatology {start_date} → {end_date}")

        t0=datetime.datetime.now()
        rowcount = run_climatology_range(start_date, end_date, worker_id=worker_id)
        t1=datetime.datetime.now()

        logger.info(f"[T{worker_id}]: Finished climatology {start_date} → {end_date}  Rows: {rowcount}  Elapsed: {(t1 - t0).total_seconds():.1f}s")
        return rowcount

@click.command("build-climatology-12h")
@click.option("--workers", default=10, help="Number of parallel workers")
@with_appcontext
def build_climatology_12h_command(workers):
    """
    Build climatology (12h) in parallel for multiple baseline windows.
    """
    # Define your baseline ranges here (example: 5-year blocks)
    ranges = [
        ("2009-01-01", "2009-12-31"),
        ("2010-01-01", "2010-12-31"),
        ("2011-01-01", "2011-12-31"),
        ("2012-01-01", "2012-12-31"),
        ("2013-01-01", "2013-12-31"),
        ("2014-01-01", "2014-12-31"),
        ("2015-01-01", "2015-12-31"),
        ("2016-01-01", "2016-12-31"),
        ("2017-01-01", "2017-12-31"),
        ("2018-01-01", "2018-12-31"),
    ]

    logger.info(f"Launching {len(ranges)} climatology (12h) jobs with {workers} workers...")
    # noinspection PyProtectedMember
    app = current_app._get_current_object()

    total_rows = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for worker_id, (start, end) in enumerate(ranges, start=1):
            futures.append(
                executor.submit(run_climatology_with_context, app, start, end, worker_id)
            )

        # wait for all workers and raise exceptions if any
        for f in futures:
            try:
                total_rows += f.result() or 0
            except Exception as e:
                #click.echo(f"❌ Worker failed: {e}", err=True)
                logger.exception(f"❌ Worker failed: {e}")
                raise
    logger.info(f"✅ All climatology (12h) windows complete. Total rows: {total_rows}")



def run_climatology_baseline_with_context(app, baseline_start_date, baseline_end_date, param, worker_id):
        """Wrap run_climatology_range with an app context and worker logging."""
        with (app.app_context()):
            logger.info(
                f"[T{worker_id}]: Starting climatology baseline {baseline_start_date} → {baseline_end_date} for param {param}")

            t0 = datetime.datetime.now()
            rowcount = run_climatology_baseline(baseline_start_date, baseline_end_date, param, worker_id=worker_id)
            t1 = datetime.datetime.now()

            logger.info(
                f"[T{worker_id}]: Finished climatology baseline {baseline_start_date} → {baseline_end_date} for param {param}  Rows: {rowcount}  Elapsed: {(t1 - t0).total_seconds():.1f}s")
            return rowcount

@click.command("build-climatology-12h-baseline")
# @click.option('--baseline_start_date', default="2009-01-01", show_default=True, type=click.DateTime(formats=["%Y-%m-%d"]), callback=validate_date,
#              required=True, help="Baseline start date (YYYY-MM-DD)"
#             )
# @click.option('--baseline_end_date', default="2018-12-31", show_default=True, type=click.DateTime(formats=["%Y-%m-%d"]), callback=validate_date,
#              required=True, help="Baseline end date   (YYYY-MM-DD)"
#             )
@with_appcontext
def build_climatology_12h_baseline_command(baseline_start_date='2009-01-01', baseline_end_date  ='2018-12-31'):
    """
    Build climatology (12h_baseline) in parallel for multiple baseline windows.
    This is the final "wide format" climatology table for merging
    with the 15 min wide format model input to LSTM and other models.
    """
    # Define the concurrency split divisions
    params = ["flow", "level", "gw", "rainfall"]
    workers = 4

    logger.info(f"Launching {len(params)} climatology (12h) jobs with {workers} workers...")
    # noinspection PyProtectedMember
    app = current_app._get_current_object()

    total_rows = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for worker_id, (param) in enumerate(params, start=1):
            futures.append(
                executor.submit(run_climatology_baseline_with_context, app,
                                baseline_start_date, baseline_end_date,
                                param, worker_id
                               )
            )

        # wait for all workers and raise exceptions if any
        for f in futures:
            try:
                total_rows += f.result() or 0
            except Exception as e:
                # click.echo(f"❌ Worker failed: {e}", err=True)
                logger.exception(f"❌ Worker failed: {e}")
                raise

    logger.info(f"✅ All climatology (12h) baseline sessions complete. Total rows: {total_rows}")



def build_weibull_climatology_with_context(app, baseline_start_date, baseline_end_date,
                                           param, worker_id, inner_workers=1, progress=None, task_id=None):
    """Wrap run_climatology_range with an app context and worker logging."""
    with (app.app_context()):
        logger.info(
            f"[T{worker_id}]: Starting climatology baseline (weibull) {baseline_start_date} → {baseline_end_date} for param {param}  with {inner_workers} inner workers")

        t0 = datetime.datetime.now()
        rowcount = run_climatology_baseline_weibull(
            baseline_start_date, baseline_end_date,
            param, worker_id, inner_workers=inner_workers,
            progress=progress, task_id=task_id,
            app=app
        )
        t1 = datetime.datetime.now()

        logger.info(
            f"[T{worker_id}]: Finished climatology baseline (weibull) {baseline_start_date} → {baseline_end_date} for param {param}  Rows: {rowcount}  Elapsed: {(t1 - t0).total_seconds():.1f}s")
        return rowcount


@click.command("build-climatology-12h-baseline-weibull")
@click.option("--baseline_start_date", default="2009-01-01", help="Baseline start date")
@click.option("--baseline_end_date", default="2018-12-31", help="Baseline end date")
@click.option("--params", default="flow,level,gw,rainfall",
              help="Comma-separated list of parameters to run (default: all)")
@click.option("--workers", default=4, show_default=True,
              help="Number of outer workers (per param)")
@click.option("--inner-workers", default=40, show_default=True,
              help="Number of inner workers per param")
@with_appcontext
def build_climatology_12h_baseline_weibull_command(baseline_start_date,
                                                   baseline_end_date,
                                                   params,
                                                   workers,
                                                   inner_workers):
    """
    Build climatology (12h_baseline) with Weibull fitting.
    Outer parallelism = per parameter.
    Inner parallelism = per param key-chunks.
    """
    params = [p.strip() for p in params.split(",") if p.strip()]
    logger.info(f"Launching {len(params)} params with {workers} workers "
                f"(inner_workers={inner_workers})...")

    app = current_app._get_current_object()
    total_rows = 0

    with Progress() as progress:
        # make one task per param
        task_map = {param: progress.add_task(f"Weibull[{param}]", total=None) for param in params}

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for worker_id, param in enumerate(params, start=1):
                futures.append(
                    executor.submit(
                        build_weibull_climatology_with_context,
                        app,
                        baseline_start_date,
                        baseline_end_date,
                        param,
                        worker_id,
                        inner_workers,    # pass through
                        progress,
                        task_map[param]
                    )
                )
            for f in futures:
                try:
                    total_rows += f.result() or 0
                except Exception as e:
                    logger.exception(f"❌ Worker failed: {e}")
                    raise

    logger.info(f"✅ All climatology (12h) baseline (weibull) sessions complete. Total rows: {total_rows}")
