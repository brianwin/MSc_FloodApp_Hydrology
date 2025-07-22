from .base import db

t_col_list = db.Table(
    'col_list', db.metadata,
    db.Column('string_agg', db.Text)
)

t_dynamic_query = db.Table(
    'dynamic_query', db.metadata,
    db.Column('format', db.Text)
)

t_flood_alerts_hist2 = db.Table(
    'flood_alerts_hist2', db.metadata,
    db.Column('DATE', db.Text),
    db.Column('AREA', db.Text),
    db.Column('CODE', db.Text),
    db.Column('WARNING / ALERT AREA NAME', db.Text),
    db.Column('TYPE', db.Text)
)

t_floodalerts_hist = db.Table(
    'floodalerts_hist', db.metadata,
    db.Column('alert_date', db.Date),
    db.Column('area', db.Text),
    db.Column('fwdcode', db.Text),
    db.Column('alert_area', db.Text),
    db.Column('type', db.Text)
)
