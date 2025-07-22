from app.extensions import db
from sqlalchemy import text

class StationMeta(db.Model):
    __tablename__ = 'station_meta'
    __table_args__ = {'schema': 'ea_source'}

    station_meta_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    context = db.Column(db.String(256))
    publisher = db.Column(db.String(256))
    licence = db.Column(db.String(256))
    documentation = db.Column(db.String(256))
    version = db.Column(db.Numeric(2, 1))
    comment = db.Column(db.String(256))
    hasFormat = db.Column(db.String(2048))

    # Relationship
    stations = db.relationship('StationJson', backref='station_meta', cascade='all, delete-orphan')

