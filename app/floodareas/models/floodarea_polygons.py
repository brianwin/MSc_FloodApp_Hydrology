from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from sqlalchemy import text

class FloodareaPolygon(db.Model):
    __tablename__ = 'floodarea_polygons'
    __table_args__ = {'schema': 'production'}

    floodarea_id = db.Column(db.Integer, db.ForeignKey('production.floodarea.floodarea_id', ondelete='CASCADE'), primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    fwdCode = db.Column(db.String(256))
    lat = db.Column(db.Float)
    long = db.Column(db.Float)
    geom4326 = db.Column(Geometry("POINT", 4326))
    geom27700 = db.Column(Geometry("POINT", 27700))
    polygon_json = db.Column(JSONB)
    polygon_geom = db.Column(Geometry('MULTIPOLYGON', 4326))
