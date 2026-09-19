# climatology/services/climatology.py

from app import db, climatology
#from ..models.climatology import Climatology12h, Climatology12hBaseline
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import ARRAY, TEXT

import numpy as np
import pandas as pd
from scipy.stats import weibull_min  # heavyweight (slow)
from scipy.special import gamma      # lightweight ("orderss of magnitude faster")

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import time

import logging
logger = logging.getLogger('floodWatch3')

_WEIBULL_CV = None
_WEIBULL_SHAPES = None
_WEIBULL_ORDER = None

# The creation of this climatology started by importing rows into a dataframe and building statistical summaries of location
# (mean, median) and spread (stddev, percentiles) in python before writing the reults back to the database for persistence
# This proved to be very costly in terms of network resources and on both database and python server cpu utilisation.
#
# The current version uses an SQL query to push all the work back to the database, both for the 12h intermediate table and
# for the 10 year summaries. Furthermore, this can by pseudo-parallellised by running multiple instances of this script
# simultaneously, each with a different start/end date range.
#
# The result is a "long" style database table where each statistic has its own time series

def run_climatology_range(start_date: str, end_date: str, worker_id: int = 1,) -> int:
    """
    Execute the climatology insert SQL (12h periods) for a given start/end date range.
    Each call runs in its own DB session.
    """

    CLIMATOLOGY_SQL =("""
        WITH raw AS (
          SELECT
            hr.notation,
            hr.parameter,   -- returns ('flow','level','rainfall', 'gw')  << NOTE 'gw'
            --hr.r_datetime AT TIME ZONE 'UTC' AS ts_utc,
            time_bucket('12 hours', hr.r_datetime AT TIME ZONE 'UTC', '09:00:00'::time) AS bucket_start,
            time_bucket('12 hours', hr.r_datetime AT TIME ZONE 'UTC', '09:00:00'::time)  + INTERVAL '12 hours' AS bucket_end,
            --hr.value
            COUNT(*) AS n_obs,
            -- flow (tends to have diurnal and seasonal patterns)
            MIN(value) FILTER (WHERE hr.parameter = 'flow') AS flow_min,
            MAX(value) FILTER (WHERE hr.parameter = 'flow') AS flow_max,
            AVG(value) FILTER (WHERE hr.parameter = 'flow') AS flow_mean,
            STDDEV(value) FILTER (WHERE hr.parameter = 'flow') AS flow_stddev,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY value) FILTER (WHERE hr.parameter = 'flow') AS flow_p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) FILTER (WHERE hr.parameter = 'flow') AS flow_p95,
            -- level
            MIN(value) FILTER (WHERE hr.parameter = 'level') AS level_min,
            MAX(value) FILTER (WHERE hr.parameter = 'level') AS level_max,
            AVG(value) FILTER (WHERE hr.parameter = 'level') as level_mean,
            STDDEV(value) FILTER (WHERE hr.parameter = 'level') AS level_stddev,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY value) FILTER (WHERE hr.parameter = 'level') AS level_p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) FILTER (WHERE hr.parameter = 'level') AS level_p95,
            -- rainfall
            SUM(value) FILTER (WHERE hr.parameter = 'rainfall') AS rainfall_total,
            AVG(value) FILTER (WHERE hr.parameter = 'rainfall') AS rainfall_mean,
            STDDEV(value) FILTER (WHERE hr.parameter = 'rainfall') AS rainfall_stddev,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY value) FILTER (WHERE hr.parameter = 'rainfall') AS rainfall_p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) FILTER (WHERE hr.parameter = 'rainfall') AS rainfall_p95,
            -- groundwater
            MIN(value) FILTER (WHERE hr.parameter = 'gw') AS gw_min,
            MAX(value) FILTER (WHERE hr.parameter = 'gw') AS gw_max,
            AVG(value) FILTER (WHERE hr.parameter = 'gw') as gw_mean,
            STDDEV(value) FILTER (WHERE hr.parameter = 'gw') AS gw_stddev,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY value) FILTER (WHERE hr.parameter = 'gw') AS gw_p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) FILTER (WHERE hr.parameter = 'gw') AS gw_p95
          FROM hyd_reading_ht hr,
               hyd_measure    hm
          WHERE hr.notation = hm.notation
            and hr.r_datetime >= CAST(:start_date AS date)
            AND hr.r_datetime <  (CAST(:end_date  AS date) + INTERVAL '1 day')
            AND hm.parameter IN ('flow','level','rainfall')   -- level includes measures for both "water level" and "groundwater level"
            and hm.period = 900
            AND hm."valueType" in ('instantaneous', 'total')  -- instantaneous and (rainfall) total /raw
          GROUP BY hr.notation, hr.parameter, bucket_start
        ),
        unnest_agg AS (
          SELECT notation, parameter, bucket_start, bucket_end, n_obs,
                 unnest(ARRAY[
                    'flow_min','flow_max','flow_mean','flow_stddev','flow_p90','flow_p95',
                    'level_min','level_max','level_mean','level_stddev','level_p90','level_p95',
                    'rainfall_total','rainfall_mean','rainfall_stddev','rainfall_p90','rainfall_p95',
                    'gw_min','gw_max','gw_mean','gw_stddev','gw_p90','gw_p95'
                 ]) AS agg_kind,
                 unnest(ARRAY[
                    flow_min ,flow_max ,flow_mean    ,flow_stddev    ,flow_p90    ,flow_p95,
                    level_min,level_max,level_mean   ,level_stddev   ,level_p90   ,level_p95,
                    rainfall_total     ,rainfall_mean,rainfall_stddev,rainfall_p90,rainfall_p95,
                    gw_min   ,gw_max   ,gw_mean      ,gw_stddev      ,gw_p90      ,gw_p95
                 ]) AS value,
                 -- A bonus calc here - adjusted doy
                 CASE
                    WHEN EXTRACT(month FROM bucket_end) = 2 AND EXTRACT(day FROM bucket_end) = 29
                        THEN 59   -- force into Feb 28
                        -- A clever little trick to get doy from 2001 (non leap year). Ensures that all days
                        -- after Feb 29 (eg Mar 01) have the same doy regardless of whether year is leap or not
                    ELSE EXTRACT(doy FROM make_date(
                            2001,
                            EXTRACT(month FROM bucket_end)::int,
                            EXTRACT(day FROM bucket_end)::int
                            ))::int
                 END AS doy
          FROM raw
        )
        INSERT INTO production.climatology_12h (
          notation, parameter, bucket_start, bucket_end, 
          year, doy, tod, agg_kind, value, n_obs, sin_doy, cos_doy
        )
        SELECT
          notation,
          parameter,
          bucket_start,
          bucket_end,
          EXTRACT(year FROM bucket_end),
          doy,
          bucket_end::time AS tod,
          agg_kind,
          value,
          n_obs,
          SIN(2 * pi() * doy / 365.0) AS sin_doy,
          COS(2 * pi() * doy / 365.0) AS cos_doy
        FROM unnest_agg
        WHERE value IS NOT NULL
        ON CONFLICT (notation, parameter, bucket_start, agg_kind)
        DO UPDATE SET
          value   = EXCLUDED.value,
          n_obs   = EXCLUDED.n_obs,
          sin_doy = EXCLUDED.sin_doy,
          cos_doy = EXCLUDED.cos_doy;
        """)

    with db.engine.begin() as conn:
        result = conn.execute(
            text(CLIMATOLOGY_SQL),
            {"start_date": start_date, "end_date": end_date}
        )
        rowcount = result.rowcount
    return rowcount


def run_climatology_baseline(
        baseline_start_date: str,
        baseline_end_date: str,
        parameter: str | None = None,
        worker_id = 1
    ) -> int:
    """
    Execute the climatology insert SQL (n year aggregates) for a given baseline date range.
    """
    param_filter = ""
    if parameter:
        param_filter = "AND m.parameter = :param"

    CLIMBASE_SQL =f"""
    WITH
        -- 1) Pooled means (weighted by n_obs)
        pooled_means AS (
            SELECT
                notation,
                parameter,
                doy,
                tod,
                agg_kind,
                SUM(n_obs * value) / NULLIF(SUM(n_obs),0) AS pooled_value,
                SUM(n_obs) AS total_n
            FROM climatology_12h m
            WHERE year >= EXTRACT(YEAR FROM CAST(:baseline_start_date AS date))
              AND year <= EXTRACT(YEAR FROM CAST(:baseline_end_date AS date))
              {param_filter}
              AND ( agg_kind LIKE '%_mean'
                   OR agg_kind LIKE '%_min'
                   OR agg_kind LIKE '%_max'
                   OR agg_kind LIKE '%_total'
                  )
            GROUP BY notation, parameter, doy, tod, agg_kind
        ),
        -- 2) Pair mean + stddev for each notation/parameter/doy/tod/agg_kind(_type)
        joined AS (
            SELECT
                m.notation,
                m.parameter,
                m.doy,
                m.tod,
                replace(m.agg_kind,'_mean','') AS var_prefix,
                m.year,
                m.n_obs,
                m.value AS mean_val,
                s.value AS stddev_val
            FROM climatology_12h m
            JOIN climatology_12h s
                ON m.notation = s.notation
                AND m.parameter = s.parameter
                AND m.doy = s.doy
                AND m.tod = s.tod
                AND m.year = s.year
                AND replace(m.agg_kind,'_mean','') = replace(s.agg_kind,'_stddev','')
            WHERE m.year >= EXTRACT(YEAR FROM CAST(:baseline_start_date AS date))
              AND m.year <= EXTRACT(YEAR FROM CAST(:baseline_end_date AS date))
              {param_filter}
              AND m.agg_kind LIKE '%_mean'
              AND s.agg_kind LIKE '%_stddev'
        ),
        -- 3) Compute pooled mean per var_prefix
        prefix_means AS (
          SELECT
            notation, parameter, doy, tod, var_prefix,
            SUM(n_obs * mean_val) / SUM(n_obs) AS pooled_mean
          FROM joined
          GROUP BY notation, parameter, doy, tod, var_prefix
        ),
        -- 4) Compute pooled stddev with correct formula
        pooled_std AS (
          SELECT
            j.notation,
            j.parameter,
            j.doy,
            j.tod,
            j.var_prefix || '_stddev' AS agg_kind,
            SQRT(
              SUM((n_obs - 1) * stddev_val^2 + n_obs * (mean_val - pm.pooled_mean)^2)
              / NULLIF(SUM(n_obs) - 1, 0)
            ) AS pooled_value,
            SUM(n_obs) AS total_n
          FROM joined j
          JOIN prefix_means pm
            ON j.notation = pm.notation
           AND j.parameter = pm.parameter
           AND j.doy = pm.doy
           AND j.tod = pm.tod
           AND j.var_prefix = pm.var_prefix
          GROUP BY j.notation, j.parameter, j.doy, j.tod, j.var_prefix
        ),
        -- 5) Combine pooled means + stddevs
        all_pooled AS (
          SELECT * FROM pooled_means
          UNION ALL
          SELECT * FROM pooled_std
        )
        -- 6) Insert into your final climatology table
        INSERT INTO production.climatology_12h_baseline (
            notation, parameter, doy, tod,
            pooled_min, pooled_max, pooled_total,
            pooled_mean, pooled_stddev,
            approx_p90, approx_p95,
            pooled_p90, pooled_p95,
            total_n,
            baseline_start, baseline_end,
            sin_doy, cos_doy,
            created_at, updated_at
        )
        SELECT
            notation,
            parameter,
            doy,
            tod,
            MAX(CASE WHEN agg_kind LIKE '%_min'     THEN pooled_value END) AS pooled_min,
            MAX(CASE WHEN agg_kind LIKE '%_max'     THEN pooled_value END) AS pooled_max,
            MAX(CASE WHEN agg_kind LIKE '%_total'   THEN pooled_value END) AS pooled_total,
            MAX(CASE WHEN agg_kind LIKE '%_mean'    THEN pooled_value END) AS pooled_mean,
            MAX(CASE WHEN agg_kind LIKE '%_stddev'  THEN pooled_value END) AS pooled_stddev,
            -- approximate percentiles
            MAX(CASE WHEN agg_kind LIKE '%_mean'    THEN pooled_value END)
            + 1.282 * MAX(CASE WHEN agg_kind LIKE '%_stddev' THEN pooled_value END) AS approx_p90,
            MAX(CASE WHEN agg_kind LIKE '%_mean'    THEN pooled_value END)
            + 1.645 * MAX(CASE WHEN agg_kind LIKE '%_stddev' THEN pooled_value END) AS approx_p95,
            NULL AS pooled_p90,   -- to backfill later
            NULL AS pooled_p95,   -- to backfill later
            MAX(total_n) AS total_n,
            CAST(:baseline_start_date AS date),
            CAST(:baseline_end_date AS date),
            SIN(2 * pi() * doy / 365.0) AS sin_doy,
            COS(2 * pi() * doy / 365.0) AS cos_doy,
            now() AS created_at,
            now() AS updated_at
        FROM all_pooled
        GROUP BY notation, parameter, doy, tod
        ON CONFLICT (notation, parameter, doy, tod, baseline_start, baseline_end)
        DO UPDATE SET
            pooled_min   = EXCLUDED.pooled_min,
            pooled_max   = EXCLUDED.pooled_max,
            pooled_total = EXCLUDED.pooled_total,
            pooled_mean  = EXCLUDED.pooled_mean,
            pooled_stddev= EXCLUDED.pooled_stddev,
            approx_p90   = EXCLUDED.approx_p90,
            approx_p95   = EXCLUDED.approx_p95,
            pooled_p90   = EXCLUDED.pooled_p90,
            pooled_p95   = EXCLUDED.pooled_p95,
            total_n      = EXCLUDED.total_n,
            baseline_start = EXCLUDED.baseline_start,
            baseline_end   = EXCLUDED.baseline_end,
            sin_doy      = EXCLUDED.sin_doy,
            cos_doy      = EXCLUDED.cos_doy,
            updated_at   = now();
    """

    bind_params = {
        "baseline_start_date": baseline_start_date,
        "baseline_end_date": baseline_end_date,
    }
    if parameter:
        bind_params["param"] = parameter

    with db.engine.begin() as conn:
        result = conn.execute(text(CLIMBASE_SQL), bind_params)
        return result.rowcount



def fit_weibull_slow(values):
    """Fit 2-parameter Weibull distribution safely."""
    values = np.asarray(values, dtype=float)
    if len(values) < 5 or np.all(values <= 0):
        return None, None  # not enough data or invalid

    try:
        shape, loc, scale = weibull_min.fit(values, floc=0)
        # sanity checks
        if not np.isfinite(shape) or not np.isfinite(scale):
            return None, None
        if shape <= 0 or scale <= 0:
            return None, None
        if shape < 0.01 or scale > 1e12:  # extreme/unrealistic fits
            return None, None
        return shape, scale
    except Exception as e:
        logger.debug(f"⚠️ Weibull fit failed: {e}")
        return None, None


def weibull_percentiles(shape, scale, probs=[0.5, 0.9, 0.95]):
    """Return dict of percentiles from Weibull params safely."""
    if shape is None or scale is None or shape <= 0 or scale <= 0:
        return {p: None for p in probs}

    out = {}
    for p in probs:
        try:
            val = float(scale * (-np.log(1 - p)) ** (1.0 / shape))
            if np.isfinite(val):
                out[p] = val
            else:
                out[p] = None
        except (FloatingPointError, OverflowError, ZeroDivisionError):
            out[p] = None
    return out


def run_climatology_baseline_weibull(baseline_start,
                                     baseline_end,
                                     param=None,
                                     worker_id=1,
                                     inner_workers=10,
                                     batch_size=1_000,
                                     progress=None,
                                     task_id=None,
                                     app=None
                                    ) -> int:
    """
    Run Weibull climatology for a parameter with optional inner parallelism
    (splits key list into inner_workers chunks).
    """
    key_sql = text("""
        SELECT DISTINCT notation, parameter, doy, tod
        FROM climatology_12h
        WHERE year >= EXTRACT(YEAR FROM CAST(:baseline_start AS date))
          AND year <= EXTRACT(YEAR FROM CAST(:baseline_end AS date))
          AND (:param IS NULL OR parameter = :param)
          AND agg_kind LIKE '%_mean'
    """)

    # grab all keys for this parameter
    with app.app_context():
        with db.engine.begin() as conn:
            keys = conn.execute(key_sql, {
                "baseline_start": baseline_start,
                "baseline_end": baseline_end,
                "param": param
            }).fetchall()

    logger.info(f"[T{worker_id}] Found {len(keys)} distinct groups for param={param}")

    if not keys:
        return 0

    # === Split into sub-chunks for inner_workers ===
    if inner_workers > 1:
        key_chunks = np.array_split(keys, inner_workers)
        total_rows = 0
        with ThreadPoolExecutor(max_workers=inner_workers) as ex:
            futures = [
                ex.submit(
                    process_keys_chunk,
                    app,
                    chunk,
                    baseline_start,
                    baseline_end,
                    param,
                    worker_id,
                    iw,
                    batch_size,
                    progress,
                    task_id
                )
                for iw, chunk in enumerate(key_chunks, start=1)
            ]
            for f in as_completed(futures):
                total_rows += f.result() or 0
        return total_rows
    else:
        return process_keys_chunk(app, keys, baseline_start, baseline_end,
                                  param, worker_id, 1, batch_size,
                                  progress, task_id)


def process_keys_chunk_v0(app, batch, baseline_start, baseline_end,
                       param, worker_id, iw, batch_size=10_000, progress=None, task_id=None):
    """
    Process a batch of (notation, parameter, doy, tod) keys inside its own connection.
    """
    # SQL templates kept local for clarity
    value_sql = text("""
        SELECT value
        FROM climatology_12h
        WHERE year >= EXTRACT(YEAR FROM CAST(:baseline_start AS date))
          AND year <= EXTRACT(YEAR FROM CAST(:baseline_end AS date))
          AND notation = :notation
          AND parameter = :parameter
          AND doy = :doy
          AND tod = :tod
          AND agg_kind like '%_mean'
    """)

    insert_sql = text("""
        INSERT INTO production.climatology_12h_weibull
        (notation, parameter, doy, tod, baseline_start, baseline_end,
         shape, scale, p50, p90, p95, n_obs, created_at, updated_at)
        VALUES (:notation, :parameter, :doy, :tod, :baseline_start, :baseline_end,
                :shape, :scale, :p50, :p90, :p95, :n_obs, now(), now())
        ON CONFLICT (notation, parameter, doy, tod, baseline_start, baseline_end)
        DO UPDATE SET
            shape = EXCLUDED.shape,
            scale = EXCLUDED.scale,
            p50   = EXCLUDED.p50,
            p90   = EXCLUDED.p90,
            p95   = EXCLUDED.p95,
            n_obs = EXCLUDED.n_obs,
            updated_at = now();
    """)

    logger.info(f"👉 Starting chunk {iw} for {param}, size={len(batch)}")

    buffer, total_rows = [], 0
    with app.app_context():
        with db.engine.begin() as conn:
            for (notation, parameter, doy, tod) in batch:
                values = pd.read_sql(value_sql, conn, params={
                    "baseline_start": baseline_start,
                    "baseline_end": baseline_end,
                    "notation": notation,
                    "parameter": parameter,
                    "doy": doy,
                    "tod": tod
                })["value"].values

                if len(values) < 5:
                    if progress and task_id:
                        progress.update(task_id, advance=1)
                    continue

                shape, scale = fit_weibull(values)
                if shape is None or scale is None:
                    if progress and task_id:
                        progress.update(task_id, advance=1)
                    continue

                pcts = weibull_percentiles(shape, scale)
                #logger.info(pcts)

                buffer.append({
                    "notation": notation,
                    "parameter": parameter,
                    "doy": int(doy),
                    "tod": tod,
                    "baseline_start": baseline_start,
                    "baseline_end": baseline_end,
                    "shape": shape,
                    "scale": scale,
                    "p50": pcts[0.5],
                    "p90": pcts[0.9],
                    "p95": pcts[0.95],
                    "n_obs": len(values)
                })

                if len(buffer) >= 500:  #batch_size:
                    conn.execute(insert_sql, buffer)
                    total_rows += len(buffer)
                    logger.info(f"[T{worker_id}.{iw}] total_rows={total_rows} for {param}")
                    buffer.clear()

                if progress and task_id is not None:
                    #logger.info(f"👉 Updating progress for task {task_id}...")
                    progress.update(task_id, advance=1)

            # flush leftovers
            if buffer:
                conn.execute(insert_sql, buffer)
                total_rows += len(buffer)

    logger.info(f"[T{worker_id}.{iw}] Finished chunk, rows={total_rows}")
    return total_rows


def process_keys_chunk_v0(app, batch, baseline_start, baseline_end,
                       param, worker_id, iw, batch_size=10_000,
                       progress=None, task_id=None):
    """
    Process a batch of (notation, parameter, doy, tod) keys inside its own connection.
    Uses array_agg to fetch all values per key in one query instead of row-per-value.
    """

    insert_sql = text("""
        INSERT INTO production.climatology_12h_weibull
        (notation, parameter, doy, tod, baseline_start, baseline_end,
         shape, scale, p50, p90, p95, n_obs, created_at, updated_at)
        VALUES (:notation, :parameter, :doy, :tod, :baseline_start, :baseline_end,
                :shape, :scale, :p50, :p90, :p95, :n_obs, now(), now())
        ON CONFLICT (notation, parameter, doy, tod, baseline_start, baseline_end)
        DO UPDATE SET
            shape = EXCLUDED.shape,
            scale = EXCLUDED.scale,
            p50   = EXCLUDED.p50,
            p90   = EXCLUDED.p90,
            p95   = EXCLUDED.p95,
            n_obs = EXCLUDED.n_obs,
            updated_at = now();
    """)

    logger.info(f"👉 Starting chunk {iw} for {param}, size={len(batch)}")

    buffer, total_rows = [], 0

    # Build a single query for this batch
    key_tuples = [(n, p, d, t) for (n, p, d, t) in batch]
    with app.app_context():
        with db.engine.begin() as conn:
            sql = text("""
                SELECT
                    notation,
                    parameter,
                    doy,
                    tod,
                    array_agg(value) AS values
                FROM climatology_12h
                WHERE year >= EXTRACT(YEAR FROM CAST(:baseline_start AS date))
                  AND year <= EXTRACT(YEAR FROM CAST(:baseline_end AS date))
                  AND (notation, parameter, doy, tod) IN :key_batch
                GROUP BY notation, parameter, doy, tod
            """)

            rows = conn.execute(sql, {
                "baseline_start": baseline_start,
                "baseline_end": baseline_end,
                "key_batch": tuple(key_tuples)
            }).fetchall()

            for notation, parameter, doy, tod, values in rows:
                values = np.array(values, dtype=float)
                if len(values) < 5:
                    if progress and task_id:
                        progress.update(task_id, advance=1)
                    continue

                shape, scale = fit_weibull(values)
                if shape is None or scale is None:
                    if progress and task_id:
                        progress.update(task_id, advance=1)
                    continue

                try:
                    pcts = weibull_percentiles(shape, scale)
                except Exception:
                    if progress and task_id:
                        progress.update(task_id, advance=1)
                    continue

                buffer.append({
                    "notation": notation,
                    "parameter": parameter,
                    "doy": int(doy),
                    "tod": tod,
                    "baseline_start": baseline_start,
                    "baseline_end": baseline_end,
                    "shape": shape,
                    "scale": scale,
                    "p50": pcts[0.5],
                    "p90": pcts[0.9],
                    "p95": pcts[0.95],
                    "n_obs": len(values)
                })

                if len(buffer) >= batch_size:
                    conn.execute(insert_sql, buffer)
                    total_rows += len(buffer)
                    logger.info(f"[T{worker_id}.{iw}] total_rows={total_rows} for {param}")
                    buffer.clear()

                if progress and task_id is not None:
                    progress.update(task_id, advance=1)

            # flush leftovers
            if buffer:
                conn.execute(insert_sql, buffer)
                total_rows += len(buffer)

    logger.info(f"[T{worker_id}.{iw}] Finished chunk, rows={total_rows}")
    return total_rows

def process_keys_chunk(app, batch, baseline_start, baseline_end,
                       param, worker_id, iw, batch_size=10_000,
                       progress=None, task_id=None):
    """
    Process a batch of (notation, parameter, doy, tod) keys using a TEMP table
    to avoid enormous IN(...) clauses. Pulls values with array_agg, fits Weibull,
    and writes in batches.
    """
    insert_sql = text("""
        INSERT INTO production.climatology_12h_weibull
        (notation, parameter, doy, tod, baseline_start, baseline_end,
         shape, scale, p50, p90, p95, n_obs, created_at, updated_at)
        VALUES (:notation, :parameter, :doy, :tod, :baseline_start, :baseline_end,
                :shape, :scale, :p50, :p90, :p95, :n_obs, now(), now())
        ON CONFLICT (notation, parameter, doy, tod, baseline_start, baseline_end)
        DO UPDATE SET
            shape = EXCLUDED.shape,
            scale = EXCLUDED.scale,
            p50   = EXCLUDED.p50,
            p90   = EXCLUDED.p90,
            p95   = EXCLUDED.p95,
            n_obs = EXCLUDED.n_obs,
            updated_at = now();
    """)

    logger.info(f"👉 Starting chunk {iw} for {param}, size={len(batch)}")

    with app.app_context():
        buffer, total_rows = [], 0
        with db.engine.begin() as conn:
            # 1) Stage keys into a per-connection TEMP table
            conn.exec_driver_sql("""
                CREATE TEMP TABLE tmp_keys (
                    notation  text,
                    parameter text,
                    doy       int,
                    tod       time without time zone
                ) ON COMMIT DROP;
            """)

            insert_keys = text("""
                INSERT INTO tmp_keys (notation, parameter, doy, tod)
                VALUES (:notation, :parameter, :doy, :tod)
            """)
            key_records = [
                {"notation": n, "parameter": p, "doy": int(d), "tod": t}
                for (n, p, d, t) in batch
            ]
            if key_records:
                conn.execute(insert_keys, key_records)

            # 2) Pull all values per key in one shot via JOIN + array_agg
            agg_sql = text("""
                SELECT
                    c.notation,
                    c.parameter,
                    c.doy,
                    c.tod,
                    array_agg(c.value) AS values
                FROM climatology_12h c
                JOIN tmp_keys k
                  ON  k.notation  = c.notation
                  AND k.parameter = c.parameter
                  AND k.doy       = c.doy
                  AND k.tod       = c.tod
                WHERE c.year >= EXTRACT(YEAR FROM CAST(:baseline_start AS date))
                  AND c.year <= EXTRACT(YEAR FROM CAST(:baseline_end AS date))
                  AND c.agg_kind LIKE '%_mean'
                GROUP BY c.notation, c.parameter, c.doy, c.tod
            """)

            rows = conn.execute(agg_sql, {
                "baseline_start": baseline_start,
                "baseline_end": baseline_end
            }).mappings()

            # 3) Fit Weibull, compute percentiles, batch insert
            for row in rows:
                notation  = row["notation"]
                parameter = row["parameter"]
                doy       = int(row["doy"])
                tod       = row["tod"]
                vals      = row["values"] or []

                # guardrails (skip tiny / pathological groups)
                if len(vals) < 5:
                    if progress and task_id: progress.update(task_id, advance=1)
                    continue

                # Convert to float array (array_agg can return Decimal)
                values = np.asarray(vals, dtype=float)
                if values.size < 5 or np.all(values <= 0):
                    if progress and task_id: progress.update(task_id, advance=1)
                    continue

                shape, scale = fit_weibull_fast(values)
                if not (shape and scale) or not np.isfinite(shape) or not np.isfinite(scale):
                    if progress and task_id: progress.update(task_id, advance=1)
                    continue

                pcts = weibull_percentiles(shape, scale)

                buffer.append({
                    "notation": notation,
                    "parameter": parameter,
                    "doy": doy,
                    "tod": tod,  # ensure this matches column type (time)
                    "baseline_start": baseline_start,
                    "baseline_end": baseline_end,
                    "shape": float(shape),
                    "scale": float(scale),
                    "p50": float(pcts[0.5]),
                    "p90": float(pcts[0.9]),
                    "p95": float(pcts[0.95]),
                    "n_obs": int(values.size),
                })

                if len(buffer) >= batch_size:
                    conn.execute(insert_sql, buffer)
                    total_rows += len(buffer)
                    buffer.clear()

                if progress and task_id:
                    progress.update(task_id, advance=1)

            # flush leftovers
            if buffer:
                conn.execute(insert_sql, buffer)
                total_rows += len(buffer)

    logger.info(f"[T{worker_id}.{iw}] Finished chunk, rows={total_rows}")
    return total_rows





def _init_weibull_cv_lut():
    """Precompute cv(k) over a fine grid of k for fast interpolation."""
    global _WEIBULL_CV, _WEIBULL_SHAPES, _WEIBULL_ORDER
    if _WEIBULL_CV is not None:
        return
    ks = np.linspace(0.2, 12.0, 6000)  # wide shape range; adjust if needed
    g1 = gamma(1.0 + 1.0/ks)
    g2 = gamma(1.0 + 2.0/ks)
    cv = np.sqrt(np.maximum(g2 - g1**2, 0.0)) / g1  # guard tiny negatives
    _WEIBULL_SHAPES = ks
    _WEIBULL_CV = cv
    _WEIBULL_ORDER = np.argsort(cv)  # cv decreases with k, ensure monotone

def _weibull_shape_from_cv(cv_val: float) -> float:
    _init_weibull_cv_lut()
    cv = np.clip(cv_val, _WEIBULL_CV.min(), _WEIBULL_CV.max())
    return float(np.interp(cv, _WEIBULL_CV[_WEIBULL_ORDER], _WEIBULL_SHAPES[_WEIBULL_ORDER]))

def fit_weibull_fast(values):
    """Very fast Weibull(k, λ) from sample mean/std via cv lookup (no optimizer)."""
    v = np.asarray(values, dtype=float)
    v = v[v > 0]  # Weibull needs positive support
    if v.size < 5:
        return None, None
    mu = v.mean()
    if not np.isfinite(mu) or mu <= 0:
        return None, None
    sd = v.std(ddof=1)
    if not np.isfinite(sd) or sd <= 0:
        return None, None
    cv = sd / mu
    k = _weibull_shape_from_cv(cv)
    lam = mu / float(gamma(1.0 + 1.0/k))
    if not (np.isfinite(k) and np.isfinite(lam) and k > 0 and lam > 0):
        return None, None
    return k, lam

