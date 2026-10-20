# Hydrology load monitoring

The hydrology loaders append an audit row for every invocation and a daily
profile for every date they process. The profile records row, station and
measure counts before and after loading, the SHA-256 checksum of the exact
source CSV, along with failures and affected-row counts.

## Install the audit tables

After deploying this branch, run the existing Flask schema command once:

```bash
flask init-db
```

`init-db` only creates missing tables; it does not drop or empty existing
tables. SQLAlchemy's `create_all` does not add columns to an existing table,
so upgrade an existing monitoring installation once with:

```sql
ALTER TABLE production.hydrology_daily_profile
    ADD COLUMN IF NOT EXISTS source_sha256 VARCHAR(64);
ALTER TABLE production.hydrology_daily_profile
    ADD COLUMN IF NOT EXISTS previous_source_row_count BIGINT;
ALTER TABLE production.hydrology_daily_profile
    ADD COLUMN IF NOT EXISTS source_delta_added BIGINT;
ALTER TABLE production.hydrology_daily_profile
    ADD COLUMN IF NOT EXISTS source_delta_changed BIGINT;
ALTER TABLE production.hydrology_daily_profile
    ADD COLUMN IF NOT EXISTS source_delta_deleted BIGINT;
ALTER TABLE production.hydrology_daily_profile
    ADD COLUMN IF NOT EXISTS reconciliation_method TEXT;
ALTER TABLE production.hydrology_daily_profile
    ADD COLUMN IF NOT EXISTS delta_eligible BOOLEAN;
ALTER TABLE production.hydrology_daily_profile
    ADD COLUMN IF NOT EXISTS delta_fallback_reason TEXT;
```

New installations receive the column from the model and DDL automatically.

## Capture the initial baseline

Before deleting or reloading historical days, capture the current state:

```bash
flask profile-hydrology-readings
```

An optional inclusive date range can reduce the initial scan:

```bash
flask profile-hydrology-readings \
  --start-date 2026-01-01 \
  --end-date 2026-09-28
```

The normal hydrology load, latest and gaps commands then create profiles
automatically.

## Useful Grafana PostgreSQL queries

Daily row counts (latest profile for each reading date):

```sql
SELECT DISTINCT ON (r_date)
       r_date AS "time",
       after_row_count AS rows,
       station_count AS stations,
       measure_count AS measures
FROM production.hydrology_daily_profile
WHERE status = 'succeeded'
  AND $__timeFilter(r_date)
ORDER BY r_date, recorded_at DESC, id DESC;
```

Daily row count as a percentage of the preceding 28-day average:

```sql
WITH latest AS (
    SELECT DISTINCT ON (r_date)
           r_date, recorded_at, after_row_count
    FROM production.hydrology_daily_profile
    WHERE status = 'succeeded'
    ORDER BY r_date, recorded_at DESC, id DESC
), scored AS (
    SELECT r_date,
           after_row_count,
           avg(after_row_count) OVER (
               ORDER BY r_date
               ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING
           ) AS previous_28_day_average
    FROM latest
)
SELECT r_date AS "time",
       100.0 * after_row_count / NULLIF(previous_28_day_average, 0) AS value
FROM scored
WHERE $__timeFilter(r_date)
ORDER BY r_date;
```

A practical first alert is `value < 80` for two consecutive evaluations. Tune
that threshold after observing the normal weekday, seasonal and outage-related
variation in the graph.

Recent failed or partial loader runs:

```sql
SELECT started_at AS "time",
       command,
       status,
       requested_dates,
       completed_dates,
       failed_dates,
       error_message
FROM production.hydrology_load_run
WHERE status IN ('failed', 'partial')
  AND $__timeFilter(started_at)
ORDER BY started_at DESC;
```


## Source-file checksums

Every successfully read local or downloaded daily CSV is hashed with SHA-256.
The digest is stored in `production.hydrology_daily_profile.source_sha256`.

Before changing database rows, the loader compares the source digest with the
latest successful checksum profile for that date. It skips deletion and import
only when the digest matches, the date currently exists in the database, and
the live database row count still matches the audited row count. The loader
records the decision as an `unchanged` daily profile with zero affected rows.
A changed checksum, missing profile, missing database date, or row-count
mismatch follows the normal load/replacement path.

Compare successive versions of a date with:

```sql
SELECT r_date,
       recorded_at,
       status,
       source_row_count,
       source_sha256
FROM production.hydrology_daily_profile
WHERE r_date = DATE '2025-09-01'
ORDER BY recorded_at DESC, id DESC;
```


## Backfill checksums for existing source files

After adding the database column, existing local daily CSV files can be hashed
without downloading them again or changing `production.reading_hydro`:

```bash
flask backfill-hydrology-source-checksums
```

Use an inclusive range for a small test or a bounded backfill:

```bash
flask backfill-hydrology-source-checksums \
  --start-date 2025-09-01 \
  --end-date 2025-09-03
```

The default source root is
`readings_hydrology_tn/hydrology`; override it with `--source-root` when
needed. The command appends `checksum_backfill` profiles, copies the latest
successful database statistics for each date, counts rows in the current CSV,
and records its SHA-256 digest. It skips a file when the latest successful
profile already contains the same checksum.

Files without a prior successful database profile are reported and skipped.
This prevents a checksum-only record with null database counts from becoming
the latest Grafana datapoint.


## Safe source-file replacement

Hydrology downloads are written to a temporary `.part` file in the same
directory as the archive file. Before publication, the temporary file must:

- parse successfully as CSV;
- contain at least one data row;
- include `measure`, `dateTime`, `date`, and `value`;
- contain only the requested reading date;
- produce a SHA-256 checksum.

Only then does `os.replace` atomically publish it as the daily archive CSV.
When refreshing an existing date, the previous archive file remains untouched
until the replacement has passed every validation. Failed temporary downloads
are removed, while the previous file is retained.


## Experimental CSV delta reconciliation

Changed source checksums do not necessarily mean that every reading changed. EA
often appends a relatively small number of readings to an otherwise stable
daily file. The loader therefore supports three explicit reconciliation modes:

- `full` (default): retain the established delete-and-bulk-reload behavior.
- `shadow`: compare the old and new CSV files and audit the predicted delta,
  but still use the established full database replacement.
- `incremental`: apply only added and materially changed rows, delete source
  keys removed by EA, and automatically fall back to full replacement whenever
  the provenance checks fail.

Use `shadow` during the observation period:

```bash
flask get-hydrology-readings-data-latest \
  --num_days_before_last_reading 30 \
  --reconciliation-mode shadow
```

A manual single-day comparison uses:

```bash
flask get-hydrology-readings-data \
  --force_start_date 2026-07-20 \
  --force_end_date 2026-07-20 \
  --force_replace true \
  --reconciliation-mode shadow
```

Incremental mode is opt-in and should not become the scheduled production
default until shadow results have been reviewed:

```bash
flask get-hydrology-readings-data \
  --force_start_date 2026-07-20 \
  --force_end_date 2026-07-20 \
  --force_replace true \
  --reconciliation-mode incremental
```

The source comparison key is `(measure, dateTime)`. Material changes are
detected in `value`, `completeness`, `quality`, `qcode`, `valid`,
`invalid`, and `missing`.

Incremental application is allowed only when:

- the previous archive parses and has unique source keys;
- its checksum matches the latest successful checksum-linked database profile;
- its row count matches that profile;
- the current database row count matches the previous archive.

Any failure records `delta_fallback_reason` and uses full replacement.

Review recent shadow evidence with:

```sql
SELECT r_date,
       recorded_at,
       reconciliation_method,
       previous_source_row_count AS old_file_rows,
       source_row_count AS new_file_rows,
       source_delta_added,
       source_delta_changed,
       source_delta_deleted,
       delta_eligible,
       delta_fallback_reason,
       rows_deleted,
       rows_inserted,
       after_row_count
FROM production.hydrology_daily_profile
WHERE reconciliation_method IN (
    'shadow_full',
    'incremental',
    'incremental_fallback_full'
)
ORDER BY recorded_at DESC, r_date DESC;
```

For a valid delta, the expected new count is:

```text
previous_source_row_count + source_delta_added - source_delta_deleted
```

That value should equal both `source_row_count` and `after_row_count`.


### Source refresh interval

Existing validated daily CSV files are downloaded again only when their archive
modification time is at least seven days old. The interval does not apply to
data dates within 14 days of the newest date known to the database/request:
those recent dates are always downloaded because EA commonly adds or amends
readings during that period.

The default can be changed per run:

```bash
flask get-hydrology-readings-data \
  --force_start_date 2026-06-01 \
  --force_end_date 2026-10-17 \
  --force_replace true \
  --reconciliation-mode incremental \
  --refresh-after-days 7
```

Use `--refresh-after-days 0` to bypass the interval and download every
requested source file. Use `--always-refresh-recent-days 0` to disable the
recent-data exception, or another positive value to change its window. A
cached file is always parsed and validated before reuse; an invalid cached file
is not protected by the interval and is replaced only after a valid download
is ready.
