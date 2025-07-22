from app.extensions import db
from sqlalchemy import text

class StationMeasure(db.Model):
    __tablename__ = 'station_measure'
    __table_args__ = {'schema': 'production'}

    station_measure_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    station_id = db.Column(db.Integer, db.ForeignKey('production.station.station_id', ondelete='CASCADE'))

    EnvAgy_id = db.Column(db.String(256))
    parameter = db.Column(db.String(256))
    parameterName = db.Column(db.String(256))
    period = db.Column(db.Integer)
    qualifier = db.Column(db.String(256))
    unitName = db.Column(db.String(256))

    # Relationship
    station = db.relationship('Station', backref=db.backref('measures', lazy=True))
