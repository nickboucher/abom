from sys import argv as sysargv, exit
from shlex import split as shlex_split
from os import environ
from os.path import isfile
from subprocess import run
from tempfile import NamedTemporaryFile
from bloom_filter2 import BloomFilter
from zlib import decompress

def check(cmd=None):
    # Rewrite check command if unittesting
    if cmd is not None:
        argv = shlex_split(cmd)
    else:
        argv = sysargv
    # Validate arguments
    if len(argv) != 3:
        exit("Usage: abom-check <binary> <hash>")
    # Set verbosity
    verbose = environ.get('ABOM_VERBOSE') == '1'
    # Extract Bloom Filter from binary
    binary = argv[1]
    with NamedTemporaryFile() as bf_file:
        with NamedTemporaryFile() as bf_gz:
            hash = argv[2]
            abom_available = False
            if isfile(f'{binary}.abom'):
                cp = run(f'cp {binary}.abom {bf_gz.name}', shell=True, capture_output=True)
                if cp.returncode == 0:
                    abom_available = True
                    if verbose:
                        print(f"Using dedicated ABOM file instead of embedded binary: {binary}.abom")
            if not abom_available:
                extract = run(f'llvm-objcopy --dump-section=__ABOM,__abom={bf_gz.name} {binary}', shell=True, capture_output=True)
                if extract.returncode != 0:
                    if verbose:
                        print("Could not extract Bloom Filter.")
                    exit(f"Input lacks ABOM: {binary}")
            with open(bf_gz.name, 'rb') as comp:
                if comp.read(6) != b"ABOM\x01\x01":
                    exit("Invalid ABOM Header.")
                bf_file.write(decompress(comp.read()))
        # Load Bloom Filter
        with BloomFilter(max_elements=100000, error_rate=1e-7, filename=(bf_file.name,-1)) as bf:
            # Check hash
            if hash in bf:
                print("Present")
            else:
                print("Absent")