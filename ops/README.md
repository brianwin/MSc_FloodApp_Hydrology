# Scheduled hydrology reconciliation observation

This schedule runs on `deeplearn2` in the Europe/London timezone.

- Daily refresh: 03:00 from 20 October through 18 November 2026.
- Data window: 28 inclusive dates ending two days before each run.
- Reconciliation: incremental.
- Historical file refresh interval: seven days.
- Mutable data tail: newest 14 database data dates.
- Review: 04:00 on 19 November 2026.

Because 03:00 has already passed on 20 October, start the service manually
after installation. That manual execution is observation run 1; the timer
provides the remaining 29 runs through 18 November.

## Install

From the repository root:

```bash
git pull --ff-only
python -m compileall -q app

sudo install -m 0644 ops/systemd/hydrology-refresh.service \
  /etc/systemd/system/hydrology-refresh.service
sudo install -m 0644 ops/systemd/hydrology-refresh.timer \
  /etc/systemd/system/hydrology-refresh.timer
sudo install -m 0644 ops/systemd/hydrology-reconciliation-review.service \
  /etc/systemd/system/hydrology-reconciliation-review.service
sudo install -m 0644 ops/systemd/hydrology-reconciliation-review.timer \
  /etc/systemd/system/hydrology-reconciliation-review.timer

sudo systemctl daemon-reload
sudo systemctl enable --now hydrology-refresh.timer
sudo systemctl enable --now hydrology-reconciliation-review.timer
sudo systemctl start hydrology-refresh.service
```

## Verify

```bash
systemctl list-timers \
  hydrology-refresh.timer \
  hydrology-reconciliation-review.timer

systemctl status hydrology-refresh.timer --no-pager
journalctl -u hydrology-refresh.service -n 100 --no-pager
```

Follow a running refresh with:

```bash
journalctl -fu hydrology-refresh.service
```

The runner exits without loading after 18 November even though the repeating
timer remains installed. Disable it after the review:

```bash
sudo systemctl disable --now hydrology-refresh.timer
sudo systemctl disable --now hydrology-reconciliation-review.timer
```

## Review

The one-shot review service runs at 04:00 on 19 November. Read its report with:

```bash
journalctl -u hydrology-reconciliation-review.service --no-pager
```

The review reports run statuses, reconciliation methods, source changes,
database changes, fallbacks and integrity mismatches. It exits unsuccessfully
when any profile fails its source-count or delta-arithmetic checks.

The report can also be run manually:

```bash
flask review-hydrology-reconciliation \
  --start-date 2026-10-20 \
  --end-date 2026-11-18
```
