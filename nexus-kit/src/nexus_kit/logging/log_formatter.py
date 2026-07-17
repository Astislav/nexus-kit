import logging
from typing import ClassVar

from injector import singleton


@singleton
class LogFormatter(logging.Formatter):
    """Default log line format.

    Subclass and override `format_string`, then bind the subclass in place of
    LogFormatter to change how every handler renders a record — this is
    independent of *where* logs go (see StdoutHandler):

        class JsonFormatter(LogFormatter):
            format_string = '{"ts":"%(asctime)s","level":"%(levelname)s",...}'

        DI_CONFIG = {LogFormatter: JsonFormatter}
    """

    format_string: ClassVar[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __init__(self):
        super().__init__(self.format_string)
