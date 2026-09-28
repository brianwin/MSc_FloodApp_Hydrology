from app.extensions import db


class HydrologyLoadRun(db.Model):
    """One append-only audit record for each hydrology load/profile invocation."""

    __tablename__ = "hydrology_load_run"
    __table_args__ = ({"schema": "production"},)

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    started_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    finished_at = db.Column(db.DateTime(timezone=True))
    command = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False, default="running")
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    gaps_only = db.Column(db.Boolean, nullable=False, default=False)
    force_replace_file = db.Column(db.Boolean, nullable=False, default=False)
    force_replace_db = db.Column(db.Boolean, nullable=False, default=False)
    requested_dates = db.Column(db.Integer, nullable=False, default=0)
    completed_dates = db.Column(db.Integer, nullable=False, default=0)
    failed_dates = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text)


class HydrologyDailyProfile(db.Model):
    """Historical data-quality snapshot for one reading date."""

    __tablename__ = "hydrology_daily_profile"
    __table_args__ = (
        db.Index("hydrology_daily_profile_date_idx", "r_date", "recorded_at"),
        {"schema": "production"},
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    load_run_id = db.Column(
        db.BigInteger,
        db.ForeignKey("production.hydrology_load_run.id", ondelete="SET NULL"),
        index=True,
    )
    recorded_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    profile_kind = db.Column(db.String, nullable=False, default="post_load")
    r_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String, nullable=False, default="succeeded")

    before_row_count = db.Column(db.BigInteger)
    source_row_count = db.Column(db.BigInteger)
    after_row_count = db.Column(db.BigInteger)
    station_count = db.Column(db.Integer)
    measure_count = db.Column(db.Integer)
    first_reading_at = db.Column(db.DateTime(timezone=True))
    last_reading_at = db.Column(db.DateTime(timezone=True))

    rows_deleted = db.Column(db.BigInteger, nullable=False, default=0)
    rows_inserted = db.Column(db.BigInteger, nullable=False, default=0)
    rows_updated = db.Column(db.BigInteger, nullable=False, default=0)
    rows_affected = db.Column(db.BigInteger, nullable=False, default=0)
    error_message = db.Column(db.Text)
