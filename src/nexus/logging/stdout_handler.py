import logging
import sys
from typing import ClassVar

from injector import singleton


@singleton
class StdoutHandler(logging.StreamHandler):
    """Default console handler.

    To customize the format, subclass and override `format_string`, then bind
    the subclass in place of StdoutHandler:

        class JsonStdoutHandler(StdoutHandler):
            format_string = '{"ts":"%(asctime)s","level":"%(levelname)s",...}'

        DI_CONFIG = {StdoutHandler: JsonStdoutHandler}
    """

    format_string: ClassVar[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __init__(self):
        super().__init__(sys.stdout)
        self.setFormatter(logging.Formatter(self.format_string))
