from app.extensions import db
from geoalchemy2 import Geometry
from sqlalchemy import text

class Station(db.Model):
    __tablename__ = 'station'
    __table_args__ = {'schema': 'production'}

    station_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    EnvAgy_id = db.Column(db.String(256))
    RLOIid = db.Column(db.Integer)
    catchmentName = db.Column(db.String(256))
    dateOpened = db.Column(db.DateTime)
    northing = db.Column(db.Float)
    easting = db.Column(db.Float)
    label = db.Column(db.String(256))
    lat = db.Column(db.Float)
    long = db.Column(db.Float)
    notation = db.Column(db.String(256))
    riverName = db.Column(db.String(256))
    stationReference = db.Column(db.String(256))
    status = db.Column(db.String(256))
    town = db.Column(db.String(256))
    wiskiID = db.Column(db.String(256))
    gridReference = db.Column(db.String(256))
    datumOffset = db.Column(db.Float)
    stageScale = db.Column(db.String(256))
    downstageScale = db.Column(db.String(256))
    geom4326 = db.Column(Geometry(geometry_type='POINT', srid=4326))
    geom27700 = db.Column(Geometry(geometry_type='POINT', srid=27700))