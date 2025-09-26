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

from sqlalchemy.sql import func
from .utils import validate_date

import logging
logger=logging.getLogger('floodWatch3')

# annotate the proxy so the IDE knows its real type
from werkzeug.local import LocalProxy
current_app: LocalProxy

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
                                    force_replace=force_replace
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
@click.option('--force-start-date', type=click.DateTime(formats=["%Y-%m-%d"]), callback=validate_date,
              required=False, help="Start date (YYYY-MM-DD)"
             )
@click.option('--force-end-date',   type=click.DateTime(formats=["%Y-%m-%d"]), callback=validate_date,
              required=False, help="End date (YYYY-MM-DD)"
             )
@click.option('--force-replace', is_flag=True, default=False, help="Force replace existing data files from source")

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
