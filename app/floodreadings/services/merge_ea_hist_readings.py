from app import db

from flask import current_app
from sqlalchemy import text
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from . import load_h_readings_para

import logging
logger=logging.getLogger('floodWatch2')

# Parameters
MAX_WORKERS = 8        # Adjust based on CPU & I/O capacity
RETRY_LIMIT = 2        # Retry each failed day this many times


def call_merge_day(app, day, attempt=1):
    """Calls the merge procedure for a single day, wrapped in app context."""
    with app.app_context():
        try:
            start_time = time.time()
            db.session.execute(text("CALL production.merge_reading_for_day(:day);"), {'day': day})
            db.session.commit()
            duration = time.time() - start_time
            logger.info(f"Merged {day} in {duration:.2f} sec (attempt {attempt})")
            return True
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Day {day} failed on attempt {attempt}: {e}")
            if attempt < RETRY_LIMIT:
                return call_merge_day(app, day, attempt + 1)
            return False


def merge_pending_days():
    """Run merge_reading_for_day() in parallel for all pending days."""
    # noinspection PyProtectedMember
    app = current_app._get_current_object()

    # bring the two "source" tables up to date
    load_h_readings_para(concise=True , app=app, upto=3)
    load_h_readings_para(concise=False, app=app, upto=3)
    # update "reading_merge_log" with new dates if available
    db.session.execute(text("CALL production.init_reading_merge_log();"))
    db.session.commit()
    days = db.session.execute(text("SELECT merge_day FROM production.reading_merge_log WHERE status = 'pending'")).scalars().all()

    if not days:
        logger.info(f"No pending days to merge.")
        return

    logger.info(f"Merging {len(days)} days in parallel with {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        #logger.debug(f"DEBUG: days to process: {days}")
        future_map = {executor.submit(call_merge_day, app, day, 1): day for day in days}

        for future in as_completed(future_map):
            day = future_map[future]
            try:
                future.result()
            except Exception as e:
                logger.exception(f"Error merging {day}: {e}")

    db.session.commit()
    logger.info(f"Merge completed.")
