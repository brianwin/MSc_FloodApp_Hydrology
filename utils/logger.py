import logging
from logging.handlers import RotatingFileHandler,TimedRotatingFileHandler

def setup_logging():
    # Create a logger object
    logger = logging.getLogger('floodWatch')
    logger.setLevel(logging.DEBUG)  # You can control the global level here

    # Formatter: include timestamp, level, and message
    #formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    #formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
    #formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s')
    formatter = logging.Formatter('%(asctime)-24s - %(levelname)-8s - %(filename)-15s:%(lineno)-4d - %(funcName)-28s - %(message)s')

    # ---- File Handler ----
    #file_handler = logging.FileHandler('floodWatch.log')
    #file_handler = RotatingFileHandler('floodWatch.log', maxBytes=5*1024*1024, backupCount=3) # 5MB per file, keep last 3 backups
    file_handler = TimedRotatingFileHandler('floodWatch.log', when='midnight', interval=1, backupCount=7)  # Rotate every midnight, keep last 7 days
    file_handler.setLevel(logging.INFO)  # Only log INFO and above to file
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ---- Console Handler ----
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Log everything to console
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
    # ---- Usage Example ----
    logger.debug('Debug message')
    logger.info('Info message')
    logger.warning('Warning message')
    logger.error('Error message')
    logger.critical('Critical message')
    return logger
