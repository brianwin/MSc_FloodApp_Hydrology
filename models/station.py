from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
db = SQLAlchemy()

class Station(db.Model):
    __tablename__ = 'station'
    station_meta_id = db.Column(db.INTEGER, primary_key=True, nullable=False)
    station_id = db.Column(db.INTEGER, primary_key=True, nullable=False)
    created = db.Column(db.TIMESTAMP (timezone=False), server_default=text('CURRENT_TIMESTAMP'))
    envagy_id = db.Column(db.VARCHAR(256), )
    rloiid = db.Column(db.INTEGER, )
    catchmentname = db.Column(db.VARCHAR(256), )
    dateopened = db.Column(db.TIMESTAMP (timezone=False), )
    northing = db.Column(db.NUMERIC(12, 5), )
    easting = db.Column(db.NUMERIC(11, 5), )
    label = db.Column(db.VARCHAR(256), )
    lat = db.Column(db.NUMERIC(8, 6), )
    long = db.Column(db.NUMERIC(7, 6), )
    notation = db.Column(db.VARCHAR(256), )
    rivername = db.Column(db.VARCHAR(256), )
    stationreference = db.Column(db.VARCHAR(256), )
    status = db.Column(db.VARCHAR(256), )
    town = db.Column(db.VARCHAR(256), )
    wiskiid = db.Column(db.VARCHAR(256), )
    gridreference = db.Column(db.VARCHAR(256), )
    datumoffset = db.Column(db.NUMERIC(6, 3), )
    stagescale = db.Column(db.VARCHAR(256), )
    downstagescale = db.Column(db.VARCHAR(256), )

class StationScale(db.Model):
    __tablename__ = 'station_scale'
    station_meta_id = db.Column(db.INTEGER, primary_key=True, nullable=False)
    station_id = db.Column(db.INTEGER, primary_key=True, nullable=False)
    station_scale_id = db.Column(db.INTEGER, primary_key=True, nullable=False, server_default=text("nextval('station_scale_station_scale_id_seq'::regclass)"))
    created = db.Column(db.TIMESTAMP (timezone=False), server_default=text('CURRENT_TIMESTAMP'))
    envagy_id = db.Column(db.VARCHAR(256), )
    highestrecent_id = db.Column(db.VARCHAR(256), )
    highestrecent_datetime = db.Column(db.TIMESTAMP (timezone=False), )
    highestrecent_value = db.Column(db.NUMERIC(8, 3), )
    maxonrecord_id = db.Column(db.VARCHAR(256), )
    maxonrecord_datetime = db.Column(db.TIMESTAMP (timezone=False), )
    maxonrecord_value = db.Column(db.NUMERIC(8, 3), )
    minonrecord_id = db.Column(db.VARCHAR(256), )
    minonrecord_datetime = db.Column(db.TIMESTAMP (timezone=False), )
    minonrecord_value = db.Column(db.NUMERIC(8, 3), )
    scalemax = db.Column(db.INTEGER, )
    typicalrangehigh = db.Column(db.NUMERIC(8, 3), )
    typicalrangelow = db.Column(db.NUMERIC(8, 3), )

class StationMeasure(db.Model):
    __tablename__ = 'station_measure'
    station_meta_id = db.Column(db.INTEGER, primary_key=True, nullable=False)
    station_id = db.Column(db.INTEGER, primary_key=True, nullable=False)
    station_measure_id = db.Column(db.INTEGER, primary_key=True, nullable=False, server_default=text("nextval('station_measure_station_measure_id_seq'::regclass)"))
    created = db.Column(db.TIMESTAMP (timezone=False), server_default=text('CURRENT_TIMESTAMP'))
    envagy_id = db.Column(db.VARCHAR(256), )
    parameter = db.Column(db.VARCHAR(256), )
    parametername = db.Column(db.VARCHAR(256), )
    period = db.Column(db.INTEGER, )
    qualifier = db.Column(db.VARCHAR(256), )
    unitname = db.Column(db.VARCHAR(256), )

