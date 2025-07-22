#app\floodstations\__init__.py
from flask import Blueprint

bp = Blueprint('stations', __name__,
               static_folder='static',
               template_folder='templates')

from . import routes