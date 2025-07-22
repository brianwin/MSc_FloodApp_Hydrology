# app/__init__.py
from flask import Flask

from app.extensions import db
from app.utils.logger import setup_logging
from config import DevelopmentConfig, ProductionConfig
from .floodreadings.models import Reading_Merged, Reading_Recent

from .utils.logger import stop_logging
#from utils.db_logger import PostgresWorker
#from utils.logger import  get_dsn_kwargs
#from queue import Queue
#from threading import Event

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__, instance_relative_config=True)

    # Config
    app.config.from_object(config_class)

    # override with instance/config.py
    app.config.from_pyfile('config.py', silent=True)

    # for logging ALL sql statements sent to the database
    #app.config['SQLALCHEMY_ECHO'] = True

    # Initialize extensions
    db.init_app(app)

    # Setup logging (before doing anything else that uses logging)
    app.logger.handlers.clear()  # Prevent duplicate loggers if reloaded
    logger = setup_logging()
    logger.info('FloodWatch startup')

    with app.app_context():
        # All context-sensitive imports and init
        from app.floodstations.models import (
            StationMeta,
            StationJson,
            Station,
            StationMeasure,
            StationScale,
            StationComplex,
            StationComplexMeasure,
            StationComplexScale
        )
        from app.floodareas.models import (
            FloodareaMeta,
            FloodareaJson,
            Floodarea,
            FloodareaPolygon,
            FloodareaMetrics
        )
        from app.floodreadings.models import (
            Reading,
            Reading_Concise,
            Reading_Merged,
            Reading_Recent
        )
        db.create_all()


    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.floodareas import bp as floodareas_bp
    app.register_blueprint(floodareas_bp, url_prefix='/floodareas')

    from app.floodreadings import bp as floodreadings_bp
    app.register_blueprint(floodreadings_bp, url_prefix='/floodreadings')

    from app.floodstations import bp as floodstations_bp
    app.register_blueprint(floodstations_bp, url_prefix='/floodstations')

    @app.route('/test/')
    def test_page():
        return '<h1>Testing the Flask Application Factory Pattern</h1>'

    # Register CLI
    from app.cli import (
        load_station_data_command,
        load_floodarea_data_command,
        #update_hist_reading_data_concise_command,
        #update_hist_reading_data_full_command,
        parallel_update_hist_reading_data_concise_command,
        parallel_update_hist_reading_data_full_command,
        merge_pending_days_command,
        update_recent_readings_command,
        get_hydrology_data_command
    )
    app.cli.add_command(load_station_data_command)
    app.cli.add_command(load_floodarea_data_command)
    #app.cli.add_command(update_hist_reading_data_concise_command)
    #app.cli.add_command(update_hist_reading_data_full_command)
    app.cli.add_command(parallel_update_hist_reading_data_concise_command)
    app.cli.add_command(parallel_update_hist_reading_data_full_command)
    app.cli.add_command(merge_pending_days_command)
    app.cli.add_command(update_recent_readings_command)
    app.cli.add_command(get_hydrology_data_command)

    @app.teardown_appcontext
    def shutdown_logging_worker(exception=None):
        stop_logging()

    return app

