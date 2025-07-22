import logging
from logging.handlers import TimedRotatingFileHandler    #' RotatingFileHandler

from .db_logger import PostgresWorker, QueuePostgresHandler
from queue import Queue
from threading import Event

# Global objects for queue-based logging (to a persistent open db connection)
_log_queue = Queue()
_stop_event = Event()
_worker = None  # Will be set in setup_logging()


def get_dsn_kwargs() -> dict:
    # TODO: Use app wide db object here if possible. Obfuscate db credentials
    return {
        "dbname": "watermonitor",
        "user": "wmon",
        "password": "abc123",
        "host": "192.168.101.12",
        "port": 5432,
    }

def setup_logging():
    # Create a logger object
    logger = logging.getLogger('floodWatch3')
    logger.setLevel(logging.DEBUG)  # You can control the global level here

    # Start background DB writer
    worker = PostgresWorker(dsn_kwargs=get_dsn_kwargs(), queue=_log_queue, stop_event=_stop_event)
    worker.start()

    # Formatter: include timestamp, level, and message
    #formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    #formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
    #formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s')
    formatter = logging.Formatter('%(asctime)-24s - %(levelname)-8s - %(filename)-15s:%(lineno)-4d - %(funcName)-30s - %(message)s')

    # ---- File Handler ----
    #file_handler = logging.FileHandler('floodWatch.log')
    #file_handler = RotatingFileHandler('floodWatch.log', maxBytes=5*1024*1024, backupCount=3) # 5MB per file, keep last 3 backups
    file_handler = TimedRotatingFileHandler('floodWatch3.log', when='midnight', interval=1, backupCount=7)  # Rotate every midnight, keep last 7 days
    file_handler.setLevel(logging.INFO)  # Only log INFO and above to file
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ---- Console Handler ----
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Log everything to console
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Queue handler for DB logging
    db_handler = QueuePostgresHandler(_log_queue)
    db_handler.setLevel(logging.DEBUG)
    db_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(db_handler)

    return logger
    # ---- Usage Example ----
    # noinspection PyUnreachableCode
    logger.debug('Debug message')
    logger.info('Info message')
    logger.warning('Warning message')
    logger.error('Error message')
    logger.critical('Critical message')
    return logger

def stop_logging():
    """Gracefully stop the background logging worker."""
    _stop_event.set()
    if _worker:
        # noinspection PyUnresolvedReferences
        _worker.join()  # Waits for thread to finish cleanly