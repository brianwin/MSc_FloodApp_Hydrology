# app/__init__.py
from flask import Flask

from app.extensions import db
from app.utils.logger import setup_logging
from config import DevelopmentConfig, ProductionConfig
from .floodareas.models import Floodarea
from .floodreadings.models import ReadingHydro
from .all_stations.models import HydStation

from .utils.logger import stop_logging
#from utils.db_logger import PostgresWorker
#from utils.logger import  get_dsn_kwargs
#from queue import Queue
#from threading import Event

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__, instance_relative_config=True)  # This enables instance folder support

    # Config
    app.config.from_object(config_class)  # First loads main config.py

    # override with instance/config.py
    app.config.from_pyfile('config.py', silent=False)  # Then loads instance/config.py

    # for logging ALL sql statements sent to the database
    #app.config['SQLALCHEMY_ECHO'] = False

    # Initialize extensions
    db.init_app(app)

    # Setup logging (before doing anything else that uses logging)
    app.logger.handlers.clear()  # Prevent duplicate loggers if reloaded
    logger = setup_logging()
    logger.info('FloodWatch startup')

    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.floodareas import bp as floodareas_bp
    app.register_blueprint(floodareas_bp, url_prefix='/floodareas')

    from app.floodreadings import bp as floodreadings_bp
    app.register_blueprint(floodreadings_bp, url_prefix='/floodreadings')

    from app.all_stations import bp as all_stations_bp
    app.register_blueprint(all_stations_bp, url_prefix='/all_stations')

    #logger.info('Blueprints imported')

    @app.route('/test/')
    def test_page():
        return '<h1>Testing the Flask Application Factory Pattern</h1>'

    @app.route('/debug-config')
    def debug_config():
        if app.debug:
            return {
                'SQLALCHEMY_DATABASE_URI': app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1],  # Show only host/db
                'DEBUG': app.config['DEBUG'],
                'config_source': 'instance/config.py'
            }
        return {'message': 'Only available in debug mode'}

    # Register CLI
    from app.cli import (
        load_station_data_command,
        load_measure_data_command,
        load_floodarea_data_command,
        get_hydrology_data_command,
        get_hydrology_data_latest_command,
        get_hydrology_data_gaps_command,
        init_db_command
    )
    app.cli.add_command(load_station_data_command)
    app.cli.add_command(load_measure_data_command)
    app.cli.add_command(load_floodarea_data_command)
    app.cli.add_command(get_hydrology_data_command)
    app.cli.add_command(get_hydrology_data_latest_command)
    app.cli.add_command(get_hydrology_data_gaps_command)
    app.cli.add_command(init_db_command)

    #logger.info('CLIs registered')

    #@app.shell_context_processor
    #def make_shell_context():
    #    return {
    #        'db': db,
    #        'Reading_Hydro': ReadingHydro,
    #        'Station': Station,
    #        'Floodarea': Floodarea
    #    }

    @app.teardown_appcontext
    def shutdown_logging_worker(exception=None):
        stop_logging()

    return app

