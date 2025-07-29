from app.extensions import db

class HydStationMeta(db.Model):
    __tablename__ = 'hyd_station_meta'
    __table_args__ = ({'schema': 'ea_source'})

    station_meta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created         = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'))
    source          = db.Column(db.String)
    publisher       = db.Column(db.String)
    licence         = db.Column(db.String)
    licenceName     = db.Column(db.String)
    documentation   = db.Column(db.String)
    version         = db.Column(db.String)
    comment         = db.Column(db.String)
    hasFormat       = db.Column(db.String)

    # Relationship
    stations = db.relationship('StationJson', backref='hyd_station_meta', cascade='all, delete-orphan')

