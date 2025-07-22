from flask import render_template
from app.floodreadings import bp


@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/categories/')
def categories():
    return render_template('categories.html')

