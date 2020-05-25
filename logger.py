from datetime import datetime
import logging
import os
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
  def add_fields(self, log_record, record, message_dict):
    super(CustomJsonFormatter, self).add_fields(
        log_record, record, message_dict)
    if not log_record.get('timestamp'):
      # this doesn't use record.created, so it is slightly off
      now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
      log_record['timestamp'] = now
    if log_record.get('level'):
      log_record['level'] = log_record['level'].upper()
    else:
      log_record['level'] = record.levelname


formatter = CustomJsonFormatter('(timestamp) (level) (name) (message)')

# init the logger as usual
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'DEBUG'))
logHandler = logging.StreamHandler()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)