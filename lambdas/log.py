# -*- coding: utf-8 -*-
"""
    Log
    ---

    Module used to setup structured (JSON) logging

"""

import logging
import sys

import structlog
from pythonjsonlogger import jsonlogger

# Setup jsonlogger to print JSON
json_handler = logging.StreamHandler(sys.stdout)
json_handler.setFormatter(jsonlogger.JsonFormatter())
root_logger = logging.getLogger()
root_logger.addHandler(json_handler)

logging.basicConfig(
    format="%(message)s", handlers=[json_handler], level=logging.INFO,
)

processors = [
    structlog.stdlib.filter_by_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
    structlog.processors.TimeStamper(),
    structlog.stdlib.render_to_log_kwargs,
]

# Configure structlog
structlog.configure(
    processors=processors,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()
