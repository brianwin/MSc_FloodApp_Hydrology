#app\floodstations\routes.py
from flask import render_template
from . import bp
from app.extensions import db

@bp.route('/')
def index():
    floodstations = []  #Floodstations.query.all()
    return render_template('floodstations/index.html', floodstations=floodstations)