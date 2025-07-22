import click
from flask.cli import with_appcontext
from flask import current_app

from .floodstations.services import load_station_data_from_ea
from .floodareas.services import load_floodarea_data_from_ea
from .floodreadings.services import validate_date, get_hydrology_readings_loop

import logging
logger=logging.getLogger('floodWatch3')

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




def process_end_date(ctx, param, value):
    # if user passed nothing, pull in force_start_date
    if not value:
        end_val = ctx.params.get('force_start_date')
    else:
        end_val = value
    # run it through your validator so format is enforced
    return validate_date(ctx, param, end_val)


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

