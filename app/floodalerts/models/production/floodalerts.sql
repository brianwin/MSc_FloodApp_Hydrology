create table if not exists production.floodalerts_hist(
	floodalert_id    serial,   -- surrogate pk
    created          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alert_date       date,
    area             text,
    fwdcode          text,
    alert_area       text,
    type             text
);
create index idx_alert_date on floodalerts_hist(alert_date);
create index idx_fwdcode    on floodalerts_hist(fwdcode);
create index idx_area       on floodalerts_hist(area);