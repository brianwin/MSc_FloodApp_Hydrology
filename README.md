# 🌊 UK Flood Prediction and Visualization Web App

A Flask-based web application for exploring and analyzing Environment Agency flood areas in the UK. Developed for an MSc Data Science major project, the app includes dynamic maps, AJAX filtering, and a PostgreSQL backend with spatial data.

## 📌 Features

- 🔍 Attribute and spatial filtering of 4,000+ flood areas
- 🔍 Consideration of 6,000+ measuring instruments at 5,000+ monitoring stations
- 🗺️ Interactive Leaflet maps with real-time updates (AJAX)
- 📊 Data tables with Bootstrap 5 styling and filters
- 🧩 Modular Flask application using Blueprints
- 🌐 Cloudflare Tunnel + NGINX Proxy deployment
- 🛠️ Docker + PostgreSQL stack for development and production

## 🧰 Tech Stack

| Layer        | Tools Used                                     |
|--------------|------------------------------------------------|
| Backend      | Python, Flask, SQLAlchemy, PostgreSQL          |
| Frontend     | HTML5, Bootstrap 5, Leaflet.js, AJAX           |
| Mapping      | Leaflet, GeoJSON                               |
| Architecture | Flask Blueprints, Jinja2                       |
| Deployment   | Docker, Cloudflare Tunnel, NGINX Proxy Manager |
| Dev Env      | PyCharm, GitHub, Proxmox                       |

---

## 🚀 Getting Started

### ✅ Step 1: Clone the Repository

<pre><code class="language-bash">
git clone https://github.com/your-username/floodprediction.git
cd floodprediction
</code></pre>

---

### ✅ Step 2: Create and Activate a Virtual Environment

<pre><code class="language-bash">
# Create a virtual environment named 'venv'
python -m venv venv

# Activate it (Linux/macOS)
source venv/bin/activate

# On Windows (CMD):
venv\Scripts\activate

# On Windows (PowerShell):
venv\Scripts\Activate.ps1
</code></pre>

---

### ✅ Step 3: Install Python Dependencies

<pre><code class="language-bash">
pip install -r requirements.txt
</code></pre>

---

### ✅ Step 4: Configure Environment Variables

Create a `.env` file in the project root:

<pre><code class="language-env">
FLASK_APP=run.py
FLASK_ENV=development
SQLALCHEMY_DATABASE_URI=postgresql://user:password@localhost:5432/envagency
SECRET_KEY=your-secret-key
</code></pre>

---

### ✅ Step 5: (Optional) Initialise the Database

<pre><code class="language-bash">
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
</code></pre>

> Or use custom scripts to import flood area shapefiles and metadata directly.

---

### ✅ Step 6: Run the Flask Application

<pre><code class="language-bash">
flask run
</code></pre>

Then open: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

### ✅ Step 7: (Optional) Run the App with Docker

<pre><code class="language-bash">
docker compose up --build
</code></pre>

---

## 🧩 Blueprint-based Application Structure

The app uses Blueprints to keep route logic modular and scalable. The following snippets are outlines for guidance only

```python
# run.py
from flask import Flask
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
```
```python
# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('../config.py')

    db.init_app(app)

    from app.floodareas import bp as floodareas_bp
    app.register_blueprint(floodareas_bp, url_prefix='/floodareas')
    
    return app
```
```python
# app/routes/flood_areas.py
from flask import Blueprint, render_template

flood_areas_bp = Blueprint('flood_areas', __name__, url_prefix="/flood_areas")

@flood_areas_bp.route("/", methods=["GET"])
def show_flood_areas():
    return render_template("flood_areas.html")
```

## 📈 Future Enhancements
- ✅ LSTM-based flood forecasting
- ✅ Real-time updates and monitoring of all measuring instruments
- ✅ Frequent determination of cross-correlation factor and lag between instruments
- ✅ Real-time anomaly detection
- ✅ Rainfall + satellite data integration
- ✅ Public-facing web app (via cloudflare)



