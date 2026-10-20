#!/usr/bin/env bash
set -euo pipefail

export TZ=Europe/London

observation_end="2026-11-18"
run_day="$(date +%F)"

if [[ "$run_day" > "$observation_end" ]]; then
    echo "Hydrology observation period ended on $observation_end; nothing to run."
    exit 0
fi

end_date="$(date -d "$run_day - 2 days" +%F)"
start_date="$(date -d "$end_date - 27 days" +%F)"

echo "Hydrology refresh window: $start_date to $end_date"

/home/brian/miniforge3/envs/tf312/bin/flask get-hydrology-readings-data \
    --force_start_date "$start_date" \
    --force_end_date "$end_date" \
    --force_replace true \
    --reconciliation-mode incremental \
    --refresh-after-days 7 \
    --always-refresh-recent-days 14
