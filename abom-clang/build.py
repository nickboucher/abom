import re
import warnings
from sys import argv as sysargv, exit
from subprocess import run
from shlex import split as shlex_split, join as shlex_join
from os import environ
from bloom_filter2 import BloomFilter
from hashlib import file_digest
from tempfile import NamedTemporaryFile
from os.path import isfile
from zlib import compress, decompress
from helpers import AbomMissingWarning

# Define constants
clang_cmds = ['clang', 'clang++', 'cc', 'c++']
ar_cmds = ['ar', 'llvm-ar']
bf_max_elements = 100000
bf_error_rate = 1e-7

# Set verbosity
verbose = environ.get('ABOM_VERBOSE') == '1'


def build(cmd=None):
    """ Defauly entrypoint for building an ABOM. """
    # Rewrite compile command if unittesting
    if cmd is not None:
        argv = shlex_split(cmd)
    else:
        argv = sysargv
    # Validate arguments
    if len(argv) <= 1:
        exit("Usage: abom <clang/ar> [args]")
    elif argv[1] in clang_cmds:
        build_clang(argv)
    elif argv[1] in ar_cmds:
        build_ar(argv)
    else:
        exit("clang and ar are the only supported tools.")
    
def build_clang(argv):
    """ Package an ABOM with a clang compilation. """
    # Get Output File
    cmd = run([argv[1]] + ['-###'] + argv[2:], capture_output=True, text=True)
    cmds = cmd.stderr.rstrip('\n').split('\n')
    if len(cmds) < 1:
        print(cmd.stderr)
        exit("No compiler commands found.")
    last = shlex_split(cmds[-1])
    ld = 'ld' in last[0]
    try:
        idx = last.index('-o')
        if idx+1 > len(last):
            raise ValueError
    except ValueError:
        print(cmd.stderr)
        exit("Output file could not be determined.")
    out = last[idx+1]
    if verbose:
        print("Output: " + out)
    # Gather Dependencies
    o = []
    args = argv[1:]
    n = 0
    while n < len(args):
        # Remove dependency generation flags
        if args[n] in ['-MT', '-MQ', '-MJ', '-MF']:
            n += 1
        elif args[n] not in ['-M', '--dependencies', '-MD', '--write-dependencies', '-MG', '--print-missing-file-dependencies', '-MM', '--user-dependencies', '-MMD', '--write-user-dependencies', '-MP', '-MV']:
            o.append(args[n])
        n += 1
    try:
        idx = o.index('-o')
        if idx+1 > len(o):
            raise ValueError
        o = o[:idx] + o[idx+2:]
    except ValueError:
        pass
    deps = run([o[0]] + ['-M'] + o[1:], capture_output=True, text=True)
    dependencies = set()
    # Parse Dependencies
    for inputs in re.split(r'(?<!\\)\n(?!$)', deps.stdout):
        if inputs == '':
            continue
        inp = re.split(r'\\\n\ \ ', inputs.rstrip('\n'))
        inp = list(map(lambda x: x.rstrip(' '), inp))
        if len(inp) < 1:
            continue
        output,source = inp[0].split(':')
        file_deps = shlex_split(source)
        for dep in inp[1:]:
            file_deps += shlex_split(dep)
        dependencies.update(file_deps)
        if verbose:
            print("\nObject: " + output)
            print("Dependencies:\n" + '\n'.join(map(lambda x: f'\t{x}',file_deps)))
    # Create Bloom Filter
    with NamedTemporaryFile() as bf_file:
        asm = False
        with BloomFilter(max_elements=bf_max_elements, error_rate=bf_error_rate, filename=(bf_file.name,-1)) as bf:
            for dep in dependencies:
                if dep.endswith('.s'):
                    asm = True
                with open(dep, 'rb') as f:
                    hash = file_digest(f, "sha3_256")
                bf.add(hash.hexdigest())
            if ld:
                abom_union(bf, last[1:], out)
        with NamedTemporaryFile() as bf_gz:
            write_abom(bf_file.name, bf_gz)
            # Run Compilation
            for cmd in cmds[4:]:
                if verbose:
                    print(f"\nRunning Command:\n{cmd}\n")
                comp = run(cmd, shell=True, capture_output=True, text=True)
                print(comp.stderr, end='')
            # Remove stale ABOMs
            rm = run(f'llvm-objcopy --remove-section=__ABOM,__abom --remove-section=,__abom {out}', shell=True, capture_output=True)
            if rm.returncode != 0:
               warnings.warn("Failed to remove ABOM sections from dependencies.", category=AbomMissingWarning)
            # Add ABOM to output
            is_obj = run(f'file -b {out}', shell=True, capture_output=True, text=True)
            if is_obj.returncode != 0:
                exit(f"Failed to determine if {out} is executable.")
            if asm:
                cp = run(f'cp {bf_gz.name} {out}.abom', shell=True, capture_output=True)
                if cp.returncode != 0:
                    warnings.warn("Failed to create seperate ABOM file for assembly inputs.", category=AbomMissingWarning)
            elif 'object' in is_obj.stdout:
                add = run(f'ld -r -sectcreate __ABOM __abom {bf_gz.name} {out} -o {out}', shell=True, capture_output=True)
                if add.returncode != 0:
                    warnings.warn("Failed to add ABOM section to object output.", category=AbomMissingWarning)
            else:
                add = run(f'llvm-objcopy --add-section=__ABOM,__abom={bf_gz.name} {out}', shell=True, capture_output=True)
                if add.returncode != 0:
                    warnings.warn("Failed to add ABOM section to executable output.", category=AbomMissingWarning)

def build_ar(argv):
    """ Build an ABOM for an archive operation. """
    ar = run(shlex_join(argv[1:]), shell=True)
    if ar.returncode != 0:
        exit("Skipping ABOM generation due to archive error.")
    out = ''
    n=2
    while n < len(argv):
        if isfile(argv[n]):
            out = argv[n]
            break
        n += 1
    if out == '':
        exit("Output file could not be determined.")
    with NamedTemporaryFile() as bf_file:
        with BloomFilter(max_elements=bf_max_elements, error_rate=bf_error_rate, filename=(bf_file.name,-1)) as bf:
            abom_union(bf, argv[n+1:], out, operation='Archived')
        with open(f'{out}.abom', 'wb') as bf_gz:
            write_abom(bf_file.name, bf_gz)

def abom_union(bf, files, out, operation='Linked'):
    """ Union the bloom filter `bf` with the potential ABOMs in `files` where `out` is the output file and `operation` is the task being performed. """
    with NamedTemporaryFile() as gz:
        for option in files:
            if option != out and isfile(option):
                abom_available = False
                if isfile(f'{option}.abom'):
                    cp = run(f'cp {option}.abom {gz.name}', shell=True, capture_output=True)
                    if cp.returncode == 0:
                        abom_available = True
                        if verbose:
                            print(f"Using dedicated ABOM file instead of embedded binary: {option}.abom")
                    else:
                        warnings.warn(f"Failed to load dedicated ABOM file: {option}.abom", category=AbomMissingWarning)
                if not abom_available:
                    objcopy = run(f'llvm-objcopy --dump-section=__ABOM,__abom={gz.name} {option}', shell=True, capture_output=True)
                    if objcopy.returncode == 0:
                        abom_available = True
                        if verbose:
                            print(f"Merging Linked Object ABOM: {option}")
                if abom_available:
                    with NamedTemporaryFile() as ln:
                        with open(gz.name, 'rb') as comp:
                            if comp.read(6) != b"ABOM\x01\x01":
                                exit("Invalid ABOM Header.")
                            ln.write(decompress(comp.read()))
                            ln.flush()
                            with BloomFilter(max_elements=bf_max_elements, error_rate=bf_error_rate, filename=(ln.name,-1)) as bf2:
                                bf.union(bf2)
                else:
                    warnings.warn(f"{operation} object lacks ABOM: {option}", category=AbomMissingWarning)

def write_abom(bf_filename, f):
    """ Write the bloom filter saved at `bf_filename` to the file handler `f`. """
    # Write ABOM Header ('ABOM',version,num_filters)
    f.write(b"ABOM\x01\x01")
    with open(bf_filename, 'rb') as bf_f:
        # Compress Bloom Filter
        f.write(compress(bf_f.read()))
    f.flush()