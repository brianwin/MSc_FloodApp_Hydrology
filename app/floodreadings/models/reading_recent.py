from app.extensions import db
from sqlalchemy import text, PrimaryKeyConstraint, Column, DateTime, Date, String, Integer, Numeric

class Reading_Recent(db.Model):
    __tablename__ = 'reading_recent'
    __table_args__ = (
        PrimaryKeyConstraint('x_measure', 'r_datetime', name='reading_recent_pk'),
        {'schema': 'production'}
    )

    created    = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    source     = Column(String)
    r_datetime = Column(DateTime(timezone=True))  # Timescale hypertable column
    r_month    = Column(Date)
    r_date     = Column(Date)
    measure    = Column(String)
    x_measure  = Column(String)
    station    = Column(String)
    label      = Column(String)
    stationreference = Column(String)
    parameter  = Column(String)
    qualifier  = Column(String)
    datumtype  = Column(String)
    period     = Column(Integer)
    unitname   = Column(String)
    valuetype  = Column(String)
    value      = Column(Numeric(15, 3))
