from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
db = SQLAlchemy()

class Reading(db.Model):
    __tablename__ = 'readings'
    created = db.Column(db.TIMESTAMP (timezone=False), server_default=text('CURRENT_TIMESTAMP'))
    source = db.Column(db.VARCHAR(64), )
    r_datetime = db.Column(db.TIMESTAMP (timezone=False), )
    r_date = db.Column(db.DATE, )
    measure = db.Column(db.VARCHAR(256), )
    station = db.Column(db.VARCHAR(256), )
    label = db.Column(db.VARCHAR(256), )
    stationreference = db.Column(db.VARCHAR(256), )
    parameter = db.Column(db.VARCHAR(32), )
    qualifier = db.Column(db.VARCHAR(256), )
    datumtype = db.Column(db.VARCHAR(32), )
    period = db.Column(db.INTEGER, )
    unitname = db.Column(db.VARCHAR(256), )
    valuetype = db.Column(db.VARCHAR(32), )
    value = db.Column(db.NUMERIC(15, 3), )