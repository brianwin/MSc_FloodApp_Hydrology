from app.extensions import db
from geoalchemy2 import Geometry
from sqlalchemy import text

class Floodarea(db.Model):
    __tablename__ = 'floodarea'
    __table_args__ = {'schema': 'production'}

    floodarea_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    EnvAgy_id = db.Column(db.String(256))
    county = db.Column(db.String(256))
    description = db.Column(db.String(1024))
    eaAreaName = db.Column(db.String(256))
    eaRegionName = db.Column(db.String(256))
    floodWatchArea = db.Column(db.String(256))
    fwdCode = db.Column(db.String(256))
    label = db.Column(db.String(256))
    lat = db.Column(db.Float)
    long = db.Column(db.Float)
    notation = db.Column(db.String(256))
    polygon = db.Column(db.String(2048))
    quickDialNumber = db.Column(db.String(256))
    riverOrSea = db.Column(db.String(1024))
    geom4326 = db.Column(Geometry("POINT", 4326))
    geom27700 = db.Column(Geometry("POINT", 27700))

    # Relationships
    polygons = db.relationship("FloodareaPolygon", backref="floodarea", cascade="all, delete-orphan")
    metrics = db.relationship("FloodareaMetrics", backref="floodarea", cascade="all, delete-orphan")
