import logging
import sys

from injector import inject, singleton

from nexus_kit.logging.log_formatter import LogFormatter


@singleton
class StdoutHandler(logging.StreamHandler):
    """Writes log records to the console. Formatting is a separate concern —
    see LogFormatter."""

    @inject
    def __init__(self, formatter: LogFormatter):
        super().__init__(sys.stdout)
        self.setFormatter(formatter)
