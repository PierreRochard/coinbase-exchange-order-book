import logging
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler('log.csv', 'a', 10 * 1024 * 1024, 100)
file_handler.setFormatter(logging.Formatter('%(asctime)s, %(levelname)s, %(message)s'))
file_handler.setLevel(logging.INFO)

file_logger = logging.getLogger('file_log')
file_logger.addHandler(file_handler)
file_logger.setLevel(logging.INFO)