import warnings
from termcolor import colored
from logging import getLogger, Logger, Formatter, StreamHandler, INFO, WARNING


warnings.formatwarning = lambda message, *_: f"{colored('Warning', 'red')}: {message}\n"

logger = getLogger('ABOM')
log = logger.info


class AbomMissingWarning(Warning):
    """ Linked or output object lacks ABOM. """
    pass


def set_verbose(verbose: bool) -> Logger:
    logger.setLevel(INFO if verbose else WARNING)
    h = StreamHandler()
    h.setFormatter(Formatter('%(message)s'))
    logger.addHandler(h)