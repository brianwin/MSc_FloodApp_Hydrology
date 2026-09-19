from app.extensions import db

class Climatology12h(db.Model):
    __tablename__ = "climatology_12h"
    __table_args__ = {"schema": "production"}

    notation       = db.Column(db.Text, primary_key=True)
    parameter      = db.Column(db.Text, primary_key=True)
    bucket_start   = db.Column(db.DateTime(timezone=True), primary_key=True)
    agg_kind       = db.Column(db.Text, primary_key=True)
    baseline_start = db.Column(db.Date, primary_key=True)
    baseline_end   = db.Column(db.Date, primary_key=True)

    bucket_end     = db.Column(db.DateTime(timezone=True))
    doy            = db.Column(db.Integer)
    tod            = db.Column(db.Time)
    value          = db.Column(db.Float)
    n_obs          = db.Column(db.Integer)
    sin_doy        = db.Column(db.Float)
    cos_doy        = db.Column(db.Float)


class Climatology12hBaseline(db.Model):
    __tablename__ = "climatology_12h_baseline"
    __table_args__ = {"schema": "production"}

    notation       = db.Column(db.Text, primary_key=True)
    parameter      = db.Column(db.Text, primary_key=True)
    doy            = db.Column(db.Integer, primary_key=True)
    tod            = db.Column(db.Time, primary_key=True)

    pooled_min     = db.Column(db.Float)
    pooled_max     = db.Column(db.Float)
    pooled_total   = db.Column(db.Float)
    pooled_mean    = db.Column(db.Float)
    pooled_stddev  = db.Column(db.Float)

    approx_p50     = db.Column(db.Float)
    approx_p90     = db.Column(db.Float)
    approx_p95     = db.Column(db.Float)
    pooled_p50     = db.Column(db.Float)
    pooled_p90     = db.Column(db.Float)
    pooled_p95     = db.Column(db.Float)

    weibull_k      = db.Column(db.Float)
    weibull_lambda = db.Column(db.Float)

    total_n        = db.Column(db.Integer)
    n_windows      = db.Column(db.Integer)
    n_years        = db.Column(db.Integer)
    baseline_start = db.Column(db.Date, primary_key=True)
    baseline_end = db.Column(db.Date, primary_key=True)
    sin_doy        = db.Column(db.Float)
    cos_doy        = db.Column(db.Float)
