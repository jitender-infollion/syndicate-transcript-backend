import logging
import logging.config
import os

from asgi_correlation_id.context import correlation_id


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = correlation_id.get() or "-"
        return True


def setup_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "console").lower()

    if log_format == "json":
        formatter = {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
        }
    else:
        formatter = {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | req=%(request_id)s | %(message)s",
        }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {"()": RequestIdFilter},
            },
            "formatters": {
                "default": formatter,
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_id"],
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
        }
    )
