from flask import render_template
from app.floodareas import bp

@bp.route('/')
def index():
    floodareas = None #FloodareaView.query.all()
    return render_template('index.html', floodareas=floodareas)

@bp.route('/categories/')
def categories():
    return render_template('categories.html')

