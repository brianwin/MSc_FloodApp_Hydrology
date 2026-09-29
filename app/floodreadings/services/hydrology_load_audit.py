import datetime

from sqlalchemy import distinct, func

from app.extensions import db
from ..models import HydrologyDailyProfile, HydrologyLoadRun, ReadingHydro


def create_load_run(
    *, command, start_date, end_date, requested_dates=0, gaps_only=False,
    force_replace_file=False, force_replace_db=False
):
    run = HydrologyLoadRun(
        command=command,
        status="running",
        start_date=start_date,
        end_date=end_date,
        gaps_only=gaps_only,
        force_replace_file=force_replace_file,
        force_replace_db=force_replace_db,
        requested_dates=requested_dates,
    )
    db.session.add(run)
    db.session.commit()
    return run.id


def finish_load_run(run_id, *, status, completed_dates, failed_dates, error_message=None):
    run = db.session.get(HydrologyLoadRun, run_id)
    if run is None:
        raise RuntimeError(f"Hydrology load run {run_id} does not exist")
    run.finished_at = datetime.datetime.now(datetime.timezone.utc)
    run.status = status
    run.completed_dates = completed_dates
    run.failed_dates = failed_dates
    run.error_message = error_message
    db.session.commit()


def get_daily_row_count(r_date):
    return (
        db.session.query(func.count(ReadingHydro.r_datetime))
        .filter(ReadingHydro.r_date == r_date)
        .scalar()
    ) or 0


def _daily_statistics(r_date):
    return (
        db.session.query(
            func.count(ReadingHydro.r_datetime).label("row_count"),
            func.count(distinct(ReadingHydro.station_id)).label("station_count"),
            func.count(distinct(ReadingHydro.notation)).label("measure_count"),
            func.min(ReadingHydro.r_datetime).label("first_reading_at"),
            func.max(ReadingHydro.r_datetime).label("last_reading_at"),
        )
        .filter(ReadingHydro.r_date == r_date)
        .one()
    )


def capture_daily_profile(
    *, r_date, load_run_id=None, profile_kind="post_load", status="succeeded",
    before_row_count=None, source_row_count=None, source_sha256=None,
    rows_deleted=0, rows_inserted=0, rows_updated=0, rows_affected=0,
    error_message=None
):
    stats = _daily_statistics(r_date)
    profile = HydrologyDailyProfile(
        load_run_id=load_run_id,
        profile_kind=profile_kind,
        r_date=r_date,
        status=status,
        before_row_count=before_row_count,
        source_row_count=source_row_count,
        source_sha256=source_sha256,
        after_row_count=stats.row_count,
        station_count=stats.station_count,
        measure_count=stats.measure_count,
        first_reading_at=stats.first_reading_at,
        last_reading_at=stats.last_reading_at,
        rows_deleted=rows_deleted,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        rows_affected=rows_affected,
        error_message=error_message,
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def capture_historical_baseline(start_date=None, end_date=None):
    """Capture all matching dates with one aggregate scan and one audit run."""
    query = db.session.query(
        ReadingHydro.r_date.label("r_date"),
        func.count(ReadingHydro.r_datetime).label("row_count"),
        func.count(distinct(ReadingHydro.station_id)).label("station_count"),
        func.count(distinct(ReadingHydro.notation)).label("measure_count"),
        func.min(ReadingHydro.r_datetime).label("first_reading_at"),
        func.max(ReadingHydro.r_datetime).label("last_reading_at"),
    ).filter(ReadingHydro.r_date.isnot(None))

    if start_date:
        query = query.filter(ReadingHydro.r_date >= start_date)
    if end_date:
        query = query.filter(ReadingHydro.r_date <= end_date)

    rows = query.group_by(ReadingHydro.r_date).order_by(ReadingHydro.r_date).all()
    effective_start = start_date or (rows[0].r_date if rows else None)
    effective_end = end_date or (rows[-1].r_date if rows else None)
    run_id = create_load_run(
        command="profile-hydrology-readings",
        start_date=effective_start,
        end_date=effective_end,
        requested_dates=len(rows),
    )

    try:
        profiles = [
            HydrologyDailyProfile(
                load_run_id=run_id,
                profile_kind="baseline",
                r_date=row.r_date,
                status="succeeded",
                before_row_count=row.row_count,
                after_row_count=row.row_count,
                station_count=row.station_count,
                measure_count=row.measure_count,
                first_reading_at=row.first_reading_at,
                last_reading_at=row.last_reading_at,
            )
            for row in rows
        ]
        db.session.bulk_save_objects(profiles)
        db.session.commit()
        finish_load_run(
            run_id, status="succeeded", completed_dates=len(rows), failed_dates=0
        )
        return run_id, len(rows)
    except Exception as exc:
        db.session.rollback()
        finish_load_run(
            run_id, status="failed", completed_dates=0, failed_dates=len(rows),
            error_message=str(exc)[:4000]
        )
        raise
