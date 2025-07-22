from app.extensions import db
from sqlalchemy import text, PrimaryKeyConstraint, Column, DateTime, Date, String, Numeric

class Reading_Hydro(db.Model):
    __tablename__ = 'reading_hydro'
    __table_args__ = (
        PrimaryKeyConstraint('notation', 'r_datetime', name='reading_hydro_pk'),
        {'schema': 'production'}
    )

    created      = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    source       = Column(String)
    r_datetime   = Column(DateTime(timezone=True))  # Timescale hypertable column
    r_month      = Column(Date)
    r_date       = Column(Date)
    measure      = Column(String)
    notation     = Column(String)
    value        = Column(Numeric(15, 3))
    completeness = Column(String)
    quality      = Column(String)
    qcode        = Column(String)
    valid        = Column(String)
    invalid      = Column(String)
    missing      = Column(String)