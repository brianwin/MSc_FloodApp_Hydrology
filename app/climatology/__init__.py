from flask import Blueprint

bp = Blueprint('climatology', __name__,
               static_folder='static',
               template_folder='templates')

#from . import routes