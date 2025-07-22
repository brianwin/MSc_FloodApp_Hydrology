from flask import Blueprint

bp = Blueprint('floodalerts', __name__,
               static_folder='static',
               template_folder='templates')

from . import routes