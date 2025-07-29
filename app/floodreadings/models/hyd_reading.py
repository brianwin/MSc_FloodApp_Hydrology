from app.extensions import db
from sqlalchemy import PrimaryKeyConstraint

class ReadingHydro(db.Model):
    __tablename__ = 'hyd_reading_ht'
    __table_args__ = (
        PrimaryKeyConstraint('notation', 'r_datetime', name='hyd_reading_ht_pk'),
        {'schema': 'production'}
    )

    created      = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'))
    source       = db.Column(db.String)
    r_datetime   = db.Column(db.DateTime(timezone=True))  # Timescale hypertable column
    r_month      = db.Column(db.Date)
    r_date       = db.Column(db.Date)
    measure      = db.Column(db.String)
    notation     = db.Column(db.String)

    station_id      = db.Column(db.String)
    parameter_name  = db.Column(db.String)
    parameter       = db.Column(db.String)
    qualifier       = db.Column(db.String)
    value_type      = db.Column(db.String)
    period_name     = db.Column(db.String)
    period          = db.Column(db.Integer)
    unit_name       = db.Column(db.String)
    observation_type= db.Column(db.String)
    datumtype       = db.Column(db.String)
    label           = db.Column(db.String)
    stationreference= db.Column(db.String)

    value        = db.Column(db.Numeric(15, 3))

    completeness = db.Column(db.String)
    quality      = db.Column(db.String)
    qcode        = db.Column(db.String)
    valid        = db.Column(db.String)
    invalid      = db.Column(db.String)
    missing      = db.Column(db.String)
    updated      = db.Column(db.DateTime(timezone=True))
