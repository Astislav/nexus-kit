import logging
from typing import ClassVar

from injector import inject

from nexus.logging.stdout_handler import StdoutHandler


class NamedLogger(logging.Logger):
    """Base for a typed, DI-injectable logger channel.

    Subclass and set `name` (and optionally `level`) — nexus wires the
    handler for you. Each subclass is its own container-resolvable type:
    inject it by type annotation, no string-keyed lookups.

        @singleton
        class SessionLogger(NamedLogger):
            name = "app.session"

        class SessionManager:
            @inject
            def __init__(self, log: SessionLogger): ...

    To add another handler (e.g. a Qt signal sink for a log-view widget),
    override `__init__` and call `super().__init__(handler)` first:

        @singleton
        class SessionLogger(NamedLogger):
            name = "app.session"

            @inject
            def __init__(self, handler: StdoutHandler, qt_handler: QtLogHandler):
                super().__init__(handler)
                self.addHandler(qt_handler)
    """

    name: ClassVar[str]
    level: ClassVar[int] = logging.INFO

    @inject
    def __init__(self, handler: StdoutHandler):
        # Read the class attribute before Logger.__init__ shadows `self.level`
        # with an instance attribute (it defaults to NOTSET if not passed here).
        level = self.level
        super().__init__(self.name, level)
        self.addHandler(handler)
        self.propagate = False
