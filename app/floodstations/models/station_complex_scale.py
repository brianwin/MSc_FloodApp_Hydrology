from app.extensions import db
from sqlalchemy import text

class StationComplexScale(db.Model):
    __tablename__ = 'station_complex_scale'
    __table_args__ = {'schema': 'production'}

    station_scale_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    station_id = db.Column(db.Integer, db.ForeignKey('production.station_complex.station_id', ondelete='CASCADE'))

    EnvAgy_id = db.Column(db.String(256))

    highestRecent_id = db.Column(db.String(256))
    highestRecent_dateTime = db.Column(db.DateTime)
    highestRecent_value = db.Column(db.Numeric(8, 3))

    maxOnRecord_id = db.Column(db.String(256))
    maxOnRecord_dateTime = db.Column(db.DateTime)
    maxOnRecord_value = db.Column(db.Numeric(8, 3))

    minOnRecord_id = db.Column(db.String(256))
    minOnRecord_dateTime = db.Column(db.DateTime)
    minOnRecord_value = db.Column(db.Numeric(8, 3))

    scaleMax = db.Column(db.Integer)
    typicalRangeHigh = db.Column(db.Numeric(8, 3))
    typicalRangeLow = db.Column(db.Numeric(8, 3))

    # Relationship
    station = db.relationship('StationComplex', backref=db.backref('scales', lazy=True))
