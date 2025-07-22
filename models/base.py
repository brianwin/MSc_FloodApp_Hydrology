from flask_sqlalchemy import SQLAlchemy

# Shared DB object
db = SQLAlchemy()

class Base(db.Model):
    __abstract__ = True
