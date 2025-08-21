from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB


class FldMeasureMeta(db.Model):
    __tablename__ = 'fld_measure_meta'
    __table_args__ = {'schema': 'ea_source'}

    created      = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'))
    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    json_id      = db.Column(db.Text, unique=True)  # maps to "@id"
    publisher    = db.Column(db.Text)
    licence      = db.Column(db.Text)  # note spelling of licence (only in flood measure)
    licenceName  = db.Column(db.Text)  # not used
    documentation= db.Column(db.Text)
    version      = db.Column(db.Text)
    comment      = db.Column(db.Text)
    hasFormat    = db.Column(JSONB)

    # Relationship to all loaded items
    measures = db.relationship('FldMeasure', back_populates='meta', cascade='all, delete-orphan')


class FldMeasureJson(db.Model):
    __tablename__ = 'fld_measure_json'
    __table_args__ = ({'schema': 'ea_source'})

    created         = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    id              = db.Column(db.Integer, primary_key=True)
    measure_id      = db.Column(db.Integer, db.ForeignKey('production.fld_measure.id'), unique=True)
    measure_data    = db.Column(JSONB)

    measure = db.relationship('FldMeasure', back_populates='json_record')


class FldMeasure(db.Model):
    __tablename__ = 'fld_measure'
    __table_args__ = {'schema': 'production'}

    created       = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'))
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    meta_id       = db.Column(db.Integer, db.ForeignKey('ea_source.fld_measure_meta.id'))

    json_id               = db.Column(db.Text, unique=True)   # maps to "@id"
    label                 = db.Column(db.Text)
    parameter             = db.Column(db.Text)
    parameter_name        = db.Column(db.Text)
    notation              = db.Column(db.Text)
    qualifier             = db.Column(db.Text)
    period                = db.Column(db.Integer)
    period_name           = db.Column(db.Text)
    station               = db.Column(db.Text)
    station_reference     = db.Column(db.Text)
    has_telemetry         = db.Column(db.Boolean)
    value_type            = db.Column(db.Text)
    datum_type            = db.Column(db.Text)
    timeseries_id         = db.Column(db.Text)
    unit                  = db.Column(db.Text)
    unit_name             = db.Column(db.Text)

    # Latest Reading fields (embedded field, flattened for query speed)
    latest_reading_id = db.Column(db.Text)
    latest_reading_date = db.Column(db.Date)
    latest_reading_datetime = db.Column(db.DateTime(timezone=True))
    latest_reading_measure = db.Column(db.Text)
    latest_reading_value = db.Column(db.Float)

    # One-to-one with JSON
    json_record = db.relationship('FldMeasureJson', uselist=False, back_populates='measure', cascade='all, delete-orphan')

    meta = db.relationship('FldMeasureMeta', back_populates='measures')
