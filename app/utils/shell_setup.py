# app/utils/shell_setup.py

from app import create_app
from flask import current_app

def setup_console():
    """Creates the app, pushes the context, and loads the shell context."""
    app = create_app()
    ctx = app.app_context()
    ctx.push()

    print(f"✅ Flask app '{app.name}' created and context pushed.")
    print(f"Instance path: {app.instance_path}")

    from app.extensions import db
    #from app.all_stations.models import Station
    from app.floodreadings.models import ReadingHydro
    #from app.floodareas.models import Floodarea
    print("🔁 Shell context populated with: db, Station, Reading_Hydro, Floodarea")

    # Load and inject shell context
    context = app.shell_context_processor(lambda: {})()
    globals().update(context)

    return app
