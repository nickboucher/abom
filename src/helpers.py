import warnings
from termcolor import colored
from logging import getLogger, Logger, Formatter, StreamHandler, INFO, WARNING
from bitarray import bitarray
from hashlib import file_digest
from abom import ABOM


warnings.formatwarning = lambda message, *_: f"{colored('Warning', 'red')}: {message}\n"

logger = getLogger('ABOM')
log = logger.info

INDEX_BITS = (ABOM.m.bit_length() - 1) * ABOM.k
INDEX_BYTES = (INDEX_BITS + 7) // 8
# If the last hex nibble is not used, remove it
TRAILING_NIBBLE = INDEX_BITS % 8 + 1 <= 5


class AbomMissingWarning(Warning):
    """ Linked or output object lacks ABOM. """
    pass


def set_verbose(verbose: bool) -> Logger:
    logger.setLevel(INFO if verbose else WARNING)
    h = StreamHandler()
    h.setFormatter(Formatter('%(message)s'))
    logger.addHandler(h)

def hash(file: str) -> bitarray:
    """ Returns the SHAKE128 hash of `file` with the digest length needed for ABOM. """
    with open(file, 'rb') as f:
        h = bitarray()
        h.frombytes(file_digest(f, "shake_128").digest(INDEX_BYTES))
    return h[:INDEX_BITS]

def hash_hex(file: str) -> str:
    """ Returns the zero-padded SHAKE128 hash of `file` as a hex string with the digest length needed for ABOM. """
    h = hash(file).tobytes().hex()
    if TRAILING_NIBBLE:
        h = h[:-1]
    return h

def hash_bits(hex: str) -> bitarray:
    """ Returns the SHAKE128 hash of `hex` with the digest length needed for ABOM. """
    h = bitarray()
    if TRAILING_NIBBLE and len(hex) % 2:
        hex += '0'
    b = bytes.fromhex(hex)
    if len(b) != INDEX_BYTES:
        raise ValueError(f"Hash must be {INDEX_BYTES} bytes.")
    h.frombytes(b)
    return h[:INDEX_BITS]