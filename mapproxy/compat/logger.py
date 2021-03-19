import logging
import sys


class _Logger(logging.Logger):
    """ Add support for 'lastResort' handler introduced in Python 3.2. """

    def callHandlers(self, record):
        # this is the same as Python 3's logging.Logger.callHandlers
        c = self
        found = 0
        while c:
            for hdlr in c.handlers:
                found = found + 1
                if record.levelno >= hdlr.level:
                    hdlr.handle(record)
            if not c.propagate:
                c = None    #break out
            else:
                c = c.parent
        if (found == 0):
            if logging.lastResort:
                if record.levelno >= logging.lastResort.level:
                    logging.lastResort.handle(record)
            elif logging.raiseExceptions and not self.manager.emittedNoHandlerWarning:
                sys.stderr.write("No handlers could be found for logger"
                                 " \"%s\"\n" % self.name)
                self.manager.emittedNoHandlerWarning = True


class _StderrHandler(logging.StreamHandler):
    def __init__(self, level=logging.NOTSET):
        """
        Initialize the handler.
        """
        logging.Handler.__init__(self, level)

    @property
    def stream(self):
        return sys.stderr


if not hasattr(logging, 'lastResort'):
    # https://docs.python.org/3/howto/logging.html#what-happens-if-no-configuration-is-provided
    logging.lastResort = _StderrHandler(logging.WARNING)
    logging.setLoggerClass(_Logger)
