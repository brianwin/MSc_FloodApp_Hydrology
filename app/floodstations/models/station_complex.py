from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from sqlalchemy import text

class StationComplex(db.Model):
    __tablename__ = 'station_complex'
    __table_args__ = {'schema': 'production'}

    station_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    EnvAgy_id = db.Column(db.String(256))
    RLOIid = db.Column(JSONB)
    catchmentName = db.Column(db.String(256))
    dateOpened = db.Column(db.DateTime)
    northing = db.Column(JSONB)
    easting = db.Column(JSONB)
    label = db.Column(JSONB)
    lat = db.Column(JSONB)
    long = db.Column(JSONB)
    notation = db.Column(db.String(256))
    riverName = db.Column(db.String(256))
    stationReference = db.Column(db.String(256))
    status = db.Column(JSONB)
    town = db.Column(db.String(256))
    wiskiID = db.Column(db.String(256))
    gridReference = db.Column(db.String(256))
    datumOffset = db.Column(db.Float)
    stageScale = db.Column(db.String(256))
    downstageScale = db.Column(db.String(256))
    geom4326 = db.Column(Geometry(geometry_type='POINT', srid=4326))
    geom27700 = db.Column(Geometry(geometry_type='POINT', srid=27700))