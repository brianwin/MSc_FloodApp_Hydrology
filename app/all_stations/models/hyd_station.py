from app.extensions import db
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

class HydStationMeta(db.Model):
    __tablename__ = 'hyd_station_meta'
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
    stations = db.relationship('HydStation', back_populates='meta', cascade='all, delete-orphan')


class HydStationJson(db.Model):
    __tablename__ = 'hyd_station_json'
    __table_args__ = ({'schema': 'ea_source'})

    created         = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    id              = db.Column(db.Integer, primary_key=True)
    station_id      = db.Column(db.Integer, db.ForeignKey('production.hyd_station.id'), unique=True)
    station_data    = db.Column(JSONB)  # db.JSON supposed to map to JSONB in the database (except it doesn't!)

    station = db.relationship('HydStation', back_populates='json_record')


class HydStation(db.Model):
    __tablename__ = "hyd_station"
    __table_args__ = {'schema': 'production'}

    created           = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    id                = db.Column(db.Integer, primary_key=True)
    meta_id           = db.Column(db.Integer, db.ForeignKey('ea_source.hyd_station_meta.id'))

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
    station_guid      = db.Column(db.Text)
    station_reference = db.Column(db.Text)
    wiski_id          = db.Column(db.Text)
    rloi_id           = db.Column(db.Text)
    rloi_station_link = db.Column(db.Text)
    catchment_area    = db.Column(db.Numeric)
    date_opened       = db.Column(db.Date)   # Change to db.Date if the format is YYYY-MM-DD
    date_closed       = db.Column(db.Date)
    nrfa_station_id   = db.Column(db.Text)
    nrfa_station_url  = db.Column(db.Text)
    datum             = db.Column(db.Numeric)
    borehole_depth    = db.Column(db.Numeric)
    aquifer           = db.Column(db.Text)
    status_reason     = db.Column(db.Text)
    data_quality_message   = db.Column(db.Text)
    data_quality_statement = db.Column(db.Text)
    sample_of_id           = db.Column(db.Text)
    sample_of_label        = db.Column(db.Text)
    geom4326          = db.Column(Geometry(geometry_type='POINT', srid=4326))
    geom27700         = db.Column(Geometry(geometry_type='POINT', srid=27700))

    # One-to-one with JSON
    json_record = db.relationship('HydStationJson', uselist=False, back_populates='station', cascade='all, delete-orphan')

    meta = db.relationship('HydStationMeta', back_populates='stations')
    types = db.relationship('HydStationType', back_populates='station', cascade="all, delete-orphan")
    observed_properties = db.relationship('HydStationObservedProp', back_populates='station', cascade="all, delete-orphan")
    statuses = db.relationship('HydStationStatus', back_populates='station', cascade="all, delete-orphan")
    measures = db.relationship('HydStationMeasure', back_populates='station', cascade="all, delete-orphan")
    stations_colocated = db.relationship('HydStationColocated', back_populates='station', cascade="all, delete-orphan")


class HydStationType(db.Model):
    __tablename__ = "hyd_station_type"
    __table_args__ = {'schema': 'production'}

    created       = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    station_id    = db.Column(db.Integer, db.ForeignKey('production.hyd_station.id'), primary_key=True)
    type_id       = db.Column(db.Text, primary_key=True)

    station = db.relationship('HydStation', back_populates='types')


class HydStationObservedProp(db.Model):
    __tablename__ = "hyd_station_observed_prop"
    __table_args__ = {'schema': 'production'}

    created       = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    station_id    = db.Column(db.Integer, db.ForeignKey('production.hyd_station.id'), primary_key=True)
    property_id   = db.Column(db.Text, primary_key=True)

    station = db.relationship('HydStation', back_populates='observed_properties')


class HydStationStatus(db.Model):
    __tablename__ = "hyd_station_status"
    __table_args__ = {'schema': 'production'}

    created       = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    station_id    = db.Column(db.Integer, db.ForeignKey('production.hyd_station.id'), primary_key=True)
    status_id     = db.Column(db.Text, primary_key=True)
    status_label_id = db.Column(db.Text)

    station = db.relationship('HydStation', back_populates='statuses')


class HydStationMeasure(db.Model):
    __tablename__ = "hyd_station_measure"
    __table_args__ = {'schema': 'production'}

    created    = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    id         = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('production.hyd_station.id'))
    measure_id = db.Column(db.Text)
    parameter  = db.Column(db.Text)
    period     = db.Column(db.Integer)
    value_statistic_id = db.Column(db.Text)

    station = db.relationship('HydStation', back_populates='measures')


class HydStationColocated(db.Model):
    __tablename__ = "hyd_station_colocated"
    __table_args__ = {'schema': 'production'}

    created      = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    station_id   = db.Column(db.Integer, db.ForeignKey('production.hyd_station.id'), primary_key=True)
    colocated_id = db.Column(db.Text, primary_key=True)

    station = db.relationship('HydStation', back_populates='stations_colocated')

