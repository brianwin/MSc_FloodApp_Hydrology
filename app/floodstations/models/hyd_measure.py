from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB


class HydMeasureMeta(db.Model):
    __tablename__ = 'hyd_measure_meta'
    __table_args__ = {'schema': 'ea_source'}

    created      = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'))
    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    json_id      = db.Column(db.Text, unique=True)  # maps to "@id"
    publisher    = db.Column(db.Text)
    license      = db.Column(db.Text)
    licenseName  = db.Column(db.Text)
    documentation= db.Column(db.Text)
    version      = db.Column(db.Text)
    comment      = db.Column(db.Text)
    hasFormat    = db.Column(JSONB)

    # Relationship to all loaded items
    measures = db.relationship('HydMeasure', back_populates='meta', cascade='all, delete-orphan')


class HydMeasureJson(db.Model):
    __tablename__ = 'hyd_measure_json'
    __table_args__ = ({'schema': 'ea_source'})

    created         = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    id              = db.Column(db.Integer, primary_key=True)
    measure_id      = db.Column(db.Integer, db.ForeignKey('production.hyd_measure.id'), unique=True)
    measure_data    = db.Column(JSONB)

    measure = db.relationship('HydMeasure', back_populates='json_record')


class HydMeasure(db.Model):
    __tablename__ = 'hyd_measure'
    __table_args__ = {'schema': 'production'}

    created       = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'))
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    meta_id       = db.Column(db.Integer, db.ForeignKey('ea_source.hyd_measure_meta.id'))

    json_id               = db.Column(db.Text, unique=True)   # maps to "@id"
    label                 = db.Column(db.Text)
    parameter             = db.Column(db.Text)
    parameterName         = db.Column(db.Text)
    notation              = db.Column(db.Text)
    qualifier             = db.Column(db.Text)
    period                = db.Column(db.Integer)
    periodName            = db.Column(db.Text)
    hasTelemetry          = db.Column(db.Boolean)
    valueType             = db.Column(db.Text)
    datumType             = db.Column(db.Text)
    timeseriesID          = db.Column(db.Text)
    unit                  = db.Column(db.Text)
    unitName              = db.Column(db.Text)

    # Embedded objects, flattened for now
    # (adjust if separate tables are required, but all appear to be 1:1 relationships)
    valueStatistic_id     = db.Column(db.Text)
    valueStatistic_label  = db.Column(db.Text)

    observationType_id    = db.Column(db.Text)
    observationType_label = db.Column(db.Text)

    observedProperty_id   = db.Column(db.Text)
    observedProperty_label= db.Column(db.Text)

    station_id            = db.Column(db.Text)
    station_label         = db.Column(db.Text)
    station_wiskiID       = db.Column(db.Text)
    station_stationReference = db.Column(db.Text)
    station_RLOIid        = db.Column(db.Text)

    # One-to-one with JSON
    json_record = db.relationship('HydMeasureJson', uselist=False, back_populates='measure', cascade='all, delete-orphan')

    meta = db.relationship('HydMeasureMeta', back_populates='measures')
