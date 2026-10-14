import logging
from logging.handlers import RotatingFileHandler

from nexo.security import redact_secrets

LOG_FILE = "log.txt"
LOG_LEVEL = "INFO"

FORMAT = "[%(asctime)s - %(levelname)s] - %(name)s - %(message)s"
DATEFMT = "%d-%b-%y %H:%M:%S"

logging.basicConfig(
    level=LOG_LEVEL,
    format=FORMAT,
    datefmt=DATEFMT,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(LOG_FILE, maxBytes=10_000_000, backupCount=3, encoding="utf-8"),
    ],
)

for lib, level in [
    ("httpx", logging.ERROR),
    ("pyrogram", logging.ERROR),
    ("pytgcalls", logging.ERROR),
    ("pymongo", logging.ERROR),
    ("ntgcalls", logging.CRITICAL),
]:
    logging.getLogger(lib).setLevel(level)


class SecretRedactionFilter(logging.Filter):
    @staticmethod
    def _clean(value):
        # numbers / bool / None ko as-is rakho taaki %d, %f, %i format chale.
        # (bool int ka subclass hai, isliye alag se check karne ki zarurat nahi)
        if value is None or isinstance(value, (int, float)):
            return value
        return redact_secrets(str(value))

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._clean(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._clean(a) for a in record.args)
            else:
                record.args = (self._clean(record.args),)
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(SecretRedactionFilter())


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
