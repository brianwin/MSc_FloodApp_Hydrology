import click
from flask.cli import with_appcontext
from flask import current_app

from .floodstations.services import load_station_data_from_ea
from .floodareas.services import load_floodarea_data_from_ea
from .floodreadings.services import validate_date, load_h_readings, load_h_readings_para, merge_pending_days
from .floodreadings.services import get_hydrology_readings_loop

import logging
logger=logging.getLogger('floodWatch2')

# annotate the proxy so the IDE knows its real type
from werkzeug.local import LocalProxy
current_app: LocalProxy


@click.command("load-station-data")   # ← This is the CLI command name you will use in terminal
@with_appcontext
def load_station_data_command():
    """Load EA station data into the database."""
    load_station_data_from_ea()

@click.command("load-floodarea-data")   # ← This is the CLI command name you will use in terminal
@with_appcontext
def load_floodarea_data_command():
    """Load EA flood area data into the database."""
    load_floodarea_data_from_ea()

@click.command("load-floodarea-metrics")   # ← This is the CLI command name you will use in terminal
@with_appcontext
def load_floodarea_metrics_command():
    """Load EA flood area data into the database."""
    #load_floodarea_metrics()

@click.command('update-hist-reading-data-concise')
@with_appcontext
def update_hist_reading_data_concise_command():
    """Update readings table to now minus (n days). n is hardcoded"""
    #logger.info('in update_hist_reading_data_concise_command()')
    #load_and_insert_hist_readings(concise=True)
    load_h_readings(concise=True)

@click.command('update-hist-reading-data-full')
@with_appcontext
def update_hist_reading_data_full_command():
    """Update readings table to now minus (n days). n is hardcoded"""
    load_h_readings(concise=False)


def process_end_date(ctx, param, value):
    # if user passed nothing, pull in force_start_date
    if not value:
        end_val = ctx.params.get('force_start_date')
    else:
        end_val = value
    # run it through your validator so format is enforced
    return validate_date(ctx, param, end_val)

@click.command('parallel-update-hist-reading-data-concise')
@click.option('--force_start_date',
              prompt='Force a start date to replace existing values (YYYY-MM-DD)',
              callback=validate_date,
              default="", show_default=False)
@click.option('--force_end_date',
              prompt='Force an end date  to replace existing values (YYYY-MM-DD)',
              callback=process_end_date,
              default="", show_default=False)
@click.option('--force_replace',
              prompt='Force upload of EA data and replace existing file (Y/n)',
              default=False, show_default=True)
@with_appcontext
def parallel_update_hist_reading_data_concise_command(force_start_date, force_end_date, force_replace):
    """Update readings table to now minus (n days). n is hardcoded"""
    # noinspection PyProtectedMember
    app = current_app._get_current_object()
    with app.app_context():
        load_h_readings_para(concise=True, app=app,
                             force_start_date=force_start_date,
                             force_end_date=force_end_date,
                             force_replace=force_replace
                             )


@click.command('parallel-update-hist-reading-data-full')
@click.option('--force_start_date',
              prompt='Force a start date to replace existing values (YYYY-MM-DD)',
              callback=validate_date,
              default="", show_default=False)
@click.option('--force_end_date',
              prompt='Force an end date  to replace existing values (YYYY-MM-DD)',
              callback=process_end_date,
              default="", show_default=False)
@click.option('--force_replace',
              prompt='Force upload of EA data and replace existing file (Y/n)',
              default=False, show_default=True)
@with_appcontext
def parallel_update_hist_reading_data_full_command(force_start_date, force_end_date, force_replace):
    """Update readings table to now minus (n days). n is hardcoded"""
    # noinspection PyProtectedMember
    app = current_app._get_current_object()
    with app.app_context():
        load_h_readings_para(concise=False, app=app,
                             force_start_date=force_start_date,
                             force_end_date=force_end_date,
                             force_replace=force_replace
                             )


@click.command('merge-pending-days')
@with_appcontext
def merge_pending_days_command():
    """Merge reading and reading_concise downloaded data into reading_merged table"""
    click.echo("Merging pending days")
    merge_pending_days()

@click.command('update-recent-readings')
@with_appcontext
def update_recent_readings_command():
    """Expand the rows previously inserted (by the database scheduler) into readings_recent."""
    # noinspection PyProtectedMember
    app = current_app._get_current_object()
    with app.app_context():
        load_h_readings_para(concise=True, update_recent=True, app=app)

# This is for the hydrology API
@click.command('get-hydrology-readings-data')
@click.option('--force_start_date',
              prompt='Force a start date to replace existing values (YYYY-MM-DD)',
              callback=validate_date,
              default="", show_default=False)
@click.option('--force_end_date',
              prompt='Force an end date  to replace existing values (YYYY-MM-DD)',
              callback=process_end_date,
              default="", show_default=False)
@click.option('--force_replace',
              prompt='Force upload of EA data and replace existing file (Y/n)',
              default=False, show_default=True)
@with_appcontext
def get_hydrology_data_command(force_start_date, force_end_date, force_replace):
    """Get readings data from the hydrology API"""
    # noinspection PyProtectedMember
    app = current_app._get_current_object()
    with app.app_context():
        get_hydrology_readings_loop(app=app,
                                    force_start_date=force_start_date,
                                    force_end_date=force_end_date,
                                    force_replace=force_replace
                                   )

