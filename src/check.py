from sys import argv as sysargv, exit
from shlex import split as shlex_split
from os import environ
from os.path import isfile
from subprocess import run
from tempfile import NamedTemporaryFile
from abom import ABOM, AbomError
from helpers import set_verbose, log, hash_bits

# Set verbosity
set_verbose(environ.get('ABOM_VERBOSE') == '1')

def check(cmd: str|None = None) -> None:
    # Rewrite check command if unittesting
    if cmd is not None:
        argv = shlex_split(cmd)
    else:
        argv = sysargv
    # Validate arguments
    if len(argv) != 3:
        exit("Usage: abom-check <binary> <hash>")
    # Extract Bloom Filter from binary
    binary = argv[1]
    with NamedTemporaryFile() as af:
        try:
            h = hash_bits(argv[2])
        except ValueError:
            exit(f"Invalid hash: {argv[2]}.")
        abom = None
        if isfile(f'{binary}.abom'):
            with open(f'{binary}.abom', 'rb') as af:
                try:
                    abom = ABOM.load(af)
                    log(f"Using dedicated ABOM file instead of embedded binary: {binary}.abom")
                except AbomError:
                    log(f'Error loading dedicated ABOM file: {binary}.abom')
        if abom is None:
            extract = run(f'llvm-objcopy --dump-section=__ABOM,__abom={af.name} {binary}', shell=True, capture_output=True)
            if extract.returncode != 0:
                log("Could not extract embedded Bloom Filter.")
                exit(f"Input lacks ABOM: {binary}")
            try:
                abom = ABOM.load(af.name)
            except AbomError:
                log("Could not load embedded Bloom Filter.")
                exit(f"Input lacks ABOM: {binary}")
    # Check hash
    if h in abom:
        print("Present")
    else:
        print("Absent")