from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

class HydStationJson(db.Model):
    __tablename__ = 'station_json'
    __table_args__ = (
        db.Index('idx_hyd_station_json_station_meta_id', 'station_meta_id'),
        {'schema': 'ea_source'}
    )

    station_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    station_meta_id = db.Column(
        db.Integer,
        db.ForeignKey('ea_source.station_meta.station_meta_id', ondelete='CASCADE'),
        nullable=False
    )
    station_data = db.Column(JSONB)