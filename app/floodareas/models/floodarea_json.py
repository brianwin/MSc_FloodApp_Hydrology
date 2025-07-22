from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

class FloodareaJson(db.Model):
    __tablename__ = 'floodarea_json'
    __table_args__ = (
        db.Index('idx_floodarea_json_floodarea_meta_id', 'floodarea_meta_id'),
        {'schema': 'ea_source'}
    )

    floodarea_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    floodarea_meta_id = db.Column(
        db.Integer,
        db.ForeignKey('ea_source.floodarea_meta.floodarea_meta_id', ondelete='CASCADE'),
        nullable=False
    )
    floodarea_data = db.Column(JSONB)