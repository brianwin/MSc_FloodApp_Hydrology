from app.extensions import db
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

class FldStationMeta(db.Model):
    __tablename__ = ('fld_station_meta')
    __table_args__ = ({'schema': 'ea_source'})

    created      = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'))
    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    json_id      = db.Column(db.Text, unique=True)  # maps to "@id"
    publisher    = db.Column(db.Text)
    license      = db.Column(db.Text)
    licenseName  = db.Column(db.Text)
    documentation= db.Column(db.Text)
    version      = db.Column(db.Text)
    comment      = db.Column(db.Text)
    hasFormat    = db.Column(JSONB)  # db.JSON supposed to map to JSONB in the database (except it doesn't!)

    # Relationship
    stations = db.relationship('FldStation', back_populates='meta', cascade='all, delete-orphan')


class FldStationJson(db.Model):
    __tablename__ = 'fld_station_json'
    __table_args__ = ({'schema': 'ea_source'})

    created         = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    id              = db.Column(db.Integer, primary_key=True)
    station_id      = db.Column(db.Integer, db.ForeignKey('production.fld_station.id'), unique=True)
    station_data    = db.Column(JSONB)  # db.JSON supposed to map to JSONB in the database (except it doesn't!)

    station = db.relationship('FldStation', back_populates='json_record')


class FldStation(db.Model):
    __tablename__ = "fld_station"
    __table_args__ = {'schema': 'production'}

    created           = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    id                = db.Column(db.Integer, primary_key=True)
    meta_id           = db.Column(db.Integer, db.ForeignKey('ea_source.fld_station_meta.id'))

    json_id           = db.Column(db.Text, unique=True)   # maps to "@id"
    label             = db.Column(db.Text)
    notation          = db.Column(db.Text)
    easting           = db.Column(db.Float)
    northing          = db.Column(db.Float)
    lat               = db.Column(db.Float)
    long              = db.Column(db.Float)
    catchment_name    = db.Column(db.Text)
    river_name        = db.Column(db.Text)
    town              = db.Column(db.Text)
    station_reference = db.Column(db.Text)
    wiski_id          = db.Column(db.Text)
    rloi_id           = db.Column(db.Text)
    date_opened       = db.Column(db.Date)
    stage_scale       = db.Column(db.Text)
    status            = db.Column(db.Text)
    datum_offset      = db.Column(db.Float)
    geom4326          = db.Column(Geometry(geometry_type='POINT', srid=4326))
    geom27700         = db.Column(Geometry(geometry_type='POINT', srid=27700))

    # One-to-one with JSON
    json_record = db.relationship('FldStationJson', uselist=False, back_populates='station', cascade='all, delete-orphan')

    meta = db.relationship('FldStationMeta', back_populates='stations')
    measures = db.relationship('FldStationMeasure', back_populates='station', cascade="all, delete-orphan")


class FldStationMeasure(db.Model):
    __tablename__ = "fld_station_measure"
    __table_args__ = {'schema': 'production'}

    created    = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    id         = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('production.fld_station.id'))
    json_id    = db.Column(db.Text)  # measure "@id"
    parameter  = db.Column(db.Text)
    parameter_name = db.Column(db.Text)
    period     = db.Column(db.Integer)
    qualifier  = db.Column(db.Text)
    unit_name  = db.Column(db.Text)

    station = db.relationship('FldStation', back_populates='measures')
