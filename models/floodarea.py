from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
db = SQLAlchemy()

class Floodarea(db.Model):
    __tablename__ = 'floodarea'
    floodarea_meta_id = db.Column(db.INTEGER, primary_key=True, nullable=False)
    floodarea_id = db.Column(db.INTEGER, primary_key=True, nullable=False)
    created = db.Column(db.TIMESTAMP (timezone=False), server_default=text('CURRENT_TIMESTAMP'))
    envagy_id = db.Column(db.VARCHAR(256), )
    county = db.Column(db.VARCHAR(256), )
    description = db.Column(db.VARCHAR(1024), )
    eaareaname = db.Column(db.VARCHAR(256), )
    earegionname = db.Column(db.VARCHAR(256), )
    floodwatcharea = db.Column(db.VARCHAR(256), )
    fwdcode = db.Column(db.VARCHAR(256), )
    label = db.Column(db.VARCHAR(256), )
    lat = db.Column(db.NUMERIC(8, 6), )
    long = db.Column(db.NUMERIC(7, 6), )
    notation = db.Column(db.VARCHAR(256), )
    polygon = db.Column(db.VARCHAR(2048), )
    quickdialnumber = db.Column(db.VARCHAR(256), )
    riverorsea = db.Column(db.VARCHAR(1024), )

class FloodareaPolygon(db.Model):
    __tablename__ = 'floodarea_polygons'
    fwdcode = db.Column(db.VARCHAR(256), primary_key=True, nullable=False)
    lat = db.Column(db.NUMERIC(8, 6), )
    long = db.Column(db.NUMERIC(7, 6), )
    polygon_json = db.Column(db.JSONB, )

