# app/__init__.py
from flask import Flask

from app.extensions import db
from app.utils.logger import setup_logging
from config import DevelopmentConfig, ProductionConfig
from .floodreadings.models import Reading_Hydro

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
            Reading_Hydro
        )
        db.create_all()
    logger.info('db models created')
    print(">> AFTER DB CREATE")

    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.floodareas import bp as floodareas_bp
    app.register_blueprint(floodareas_bp, url_prefix='/floodareas')

    from app.floodreadings import bp as floodreadings_bp
    app.register_blueprint(floodreadings_bp, url_prefix='/floodreadings')

    from app.floodstations import bp as floodstations_bp
    app.register_blueprint(floodstations_bp, url_prefix='/floodstations')

    logger.info('Blueprints imported')
    print(">> AFTER BLUEPRINTS")

    @app.route('/test/')
    def test_page():
        return '<h1>Testing the Flask Application Factory Pattern</h1>'

    # Register CLI
    from app.cli import (
        load_station_data_command,
        load_floodarea_data_command,
        get_hydrology_data_command,
        get_hydrology_data_latest_command,
        get_hydrology_data_gaps_command
    )
    app.cli.add_command(load_station_data_command)
    app.cli.add_command(load_floodarea_data_command)
    app.cli.add_command(get_hydrology_data_command)
    app.cli.add_command(get_hydrology_data_latest_command)
    app.cli.add_command(get_hydrology_data_gaps_command)

    logger.info('CLIs registered')
    print(">> AFTER CLI COMMANDS")

    @app.shell_context_processor
    def make_shell_context():
        return {
            'db': db,
            'Reading_Hydro': Reading_Hydro,
            'Station': Station,
            'Floodarea': Floodarea
        }

    @app.teardown_appcontext
    def shutdown_logging_worker(exception=None):
        stop_logging()

    logger.info("Returning app")
    return app

