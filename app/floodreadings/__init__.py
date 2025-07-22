#app\floodreadings\__init__.py
from flask import Blueprint

bp = Blueprint('readings', __name__,
               static_folder='static',
               template_folder='templates')

from . import routes