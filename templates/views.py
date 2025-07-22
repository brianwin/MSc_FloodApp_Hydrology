from templates import app
from flask import render_template

@app.route('/')
def index():  # put application's code here
    return render_template('index.html')

@app.route('/contact')
def contact():  # put application's code here
    return 'Hello from /contact'

@app.route('/about')
def about():
    return "<h1 style='color: red'>About modified</h1>"
