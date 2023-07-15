import warnings
from termcolor import colored

warnings.formatwarning = lambda message, *_: f"{colored('Warning', 'red')}: {message}\n"


class AbomMissingWarning(Warning):
    """ Linked or output object lacks ABOM. """
    pass