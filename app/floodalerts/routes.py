from flask import render_template
from app.floodalerts import bp

@bp.route('/')
def index():
    floodalerts = None #FloodalertsView.query.all()
    return render_template('index.html', floodalertss=floodalerts)

@bp.route('/categories/')
def categories():
    return render_template('categories.html')

