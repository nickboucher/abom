from sys import argv as sysargv, exit
from shlex import split as shlex_split
from helpers import hash_hex

def abom_hash(cmd: str|None = None) -> None:
    ''' Default entrypoint for calculating an ABOM hash. '''
    # Rewrite compile command if unittesting
    if cmd is not None:
        argv = shlex_split(cmd)
    else:
        argv = sysargv
    # Validate arguments
    if len(argv) != 2:
        exit("Usage: abom-hash <file>")
    # Calculate hash
    print(hash_hex(argv[1]))