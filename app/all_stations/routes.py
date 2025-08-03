#app\all_stations\routes.py
from flask import render_template
from . import bp
from app.extensions import db

@bp.route('/')
def index():
    all_stations = []  #Hydstations.query.all()
    return render_template('all_stations/index.html', stations=all_stations)