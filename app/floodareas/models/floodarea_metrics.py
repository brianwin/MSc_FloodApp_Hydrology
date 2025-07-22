from app.extensions import db
#from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
#from sqlalchemy import text


class FloodareaMetrics(db.Model):
    __tablename__ = 'floodarea_metrics'
    __table_args__ = {'schema': 'production'}

    floodarea_id = db.Column(db.Integer, db.ForeignKey('production.floodarea.floodarea_id', ondelete='CASCADE'), primary_key=True)
    fwdCode = db.Column(db.String(256))

    bbox_wgs84_min_lat = db.Column(db.Float)
    bbox_wgs84_min_long = db.Column(db.Float)
    bbox_wgs84_max_lat = db.Column(db.Float)
    bbox_wgs84_max_long = db.Column(db.Float)

    bcen_wgs84_lat = db.Column(db.Float)
    bcen_wgs84_long = db.Column(db.Float)
    mpoly_cent_wgs84_lat = db.Column(db.Float)
    mpoly_cent_wgs84_long = db.Column(db.Float)

    geom_bbox_wgs84 = db.Column(Geometry("POLYGON", 4326))
    geom_bcen_wgs84 = db.Column(Geometry("POINT", 4326))
    geom_mpoly_cent_wgs84 = db.Column(Geometry("POINT", 4326))

    bbox_bng_min_lat = db.Column(db.Float)
    bbox_bng_min_long = db.Column(db.Float)
    bbox_bng_max_lat = db.Column(db.Float)
    bbox_bng_max_long = db.Column(db.Float)

    bcen_bng_lat = db.Column(db.Float)
    bcen_bng_long = db.Column(db.Float)
    mpoly_cent_bng_lat = db.Column(db.Float)
    mpoly_cent_bng_long = db.Column(db.Float)

    geom_bbox_bng = db.Column(Geometry("POLYGON", 27700))
    geom_bcen_bng = db.Column(Geometry("POINT", 27700))
    geom_mpoly_cent_bng = db.Column(Geometry("POINT", 27700))

    area_km2 = db.Column(db.Float)
    area_m2 = db.Column(db.Float)
    rank = db.Column(db.Integer)