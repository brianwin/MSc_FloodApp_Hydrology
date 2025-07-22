from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class FloodalertsHist(db.Model):
    __tablename__ = 'floodalerts_hist'
    alert_date = db.Column(db.DATE, )
    area = db.Column(db.TEXT, )
    fwdcode = db.Column(db.TEXT, )
    alert_area = db.Column(db.TEXT, )
    type = db.Column(db.TEXT, )

