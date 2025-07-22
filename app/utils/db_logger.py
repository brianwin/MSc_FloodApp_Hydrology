# app/utils/db_logger.py
import logging
import psycopg2
from queue import Queue, Empty
from threading import Thread, Event
from datetime import datetime, timezone


class PostgresWorker(Thread):
    def __init__(self, dsn_kwargs, queue: Queue, stop_event: Event):
        super().__init__(daemon=True)
        self.queue = queue
        self.stop_event = stop_event
        self.conn = psycopg2.connect(**dsn_kwargs)
        self.cur = self.conn.cursor()

    def run(self):
        while not self.stop_event.is_set():
            try:
                record = self.queue.get(timeout=1)
                self.insert_log(record)
            except Empty:
                continue
            except Exception as e:
                print(f"Logging worker error: {e}")

        self.conn.commit()
        self.cur.close()
        self.conn.close()

    def insert_log(self, record):
        message = record.getMessage()
        try:
            self.cur.execute("""
                INSERT INTO zlogging (
                    asctime, created, filename, "funcName",
                    levelname, levelno, lineno, message,
                    module, msecs, "loggerName",
                    pathname, process, "processName", "relativeCreated",
                    thread, "threadName")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datetime.fromtimestamp(record.created, tz=timezone.utc),
                record.created,
                record.filename,
                record.funcName,
                record.levelname,
                record.levelno,
                record.lineno,
                message,
                record.module,
                record.msecs,
                record.name,     # maps to `loggerName` in db
                record.pathname,
                record.process,
                record.processName,
                record.relativeCreated,
                record.thread,
                record.threadName
            ))
            self.conn.commit()
        except Exception as e:
            print(f"DB insert error during db logging: {e}")

# app/utils/db_logger.py continued
class QueuePostgresHandler(logging.Handler):
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            self.queue.put_nowait(record)
        except Exception:
            self.handleError(record)

