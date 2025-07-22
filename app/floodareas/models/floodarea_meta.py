from app.extensions import db
from sqlalchemy import text

class FloodareaMeta(db.Model):
    __tablename__ = 'floodarea_meta'
    __table_args__ = {'schema': 'ea_source'}

    floodarea_meta_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    context = db.Column(db.String(256))
    publisher = db.Column(db.String(256))
    licence = db.Column(db.String(256))
    documentation = db.Column(db.String(256))
    version = db.Column(db.Numeric(2, 1))
    comment = db.Column(db.String(256))
    hasFormat = db.Column(db.String(2048))

    # Relationship
    stations = db.relationship('FloodareaJson', backref='floodarea_meta', cascade='all, delete-orphan')

