import re
import warnings
from sys import argv, exit
from subprocess import run
from shlex import split as shlex_split, join
from os import environ
from bloom_filter2 import BloomFilter
from hashlib import file_digest
from tempfile import NamedTemporaryFile
from os.path import isfile
from termcolor import colored
from zlib import compress, decompress

warnings.formatwarning = lambda message, *_: f"{colored('Warning', 'red')}: {message}\n"

def compile():
    # Validate arguments
    if len(argv) <= 1:
        exit("Usage: abom <clang> [clang-args]")
    if 'clang' not in argv[1]:
        exit("clang is only supported compiler.")
    # Set verbosity
    verbose = environ.get('ABOM_VERBOSE') == '1'
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
    o = argv[1:]
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
        input = re.split(r'\ \\\n\ \ ', inputs.rstrip('\n'))
        if len(input) < 1:
            continue
        output,source = input[0].split(': ')
        file_deps = shlex_split(source) + input[1:]
        dependencies.update(file_deps)
        if verbose:
            print("\nObject: " + output)
            print("Dependencies:")
            print('\n'.join(map(lambda x: f'\t{x}',file_deps))) 
    if verbose:
        print()
    # Create Bloom Filter
    with NamedTemporaryFile(suffix='.o') as bf_obj_file:
        with NamedTemporaryFile() as bf_file:
            with BloomFilter(max_elements=100000, error_rate=1e-7, filename=(bf_file.name,-1)) as bf:
                for dep in dependencies:
                    with open(dep, 'rb') as f:
                        hash = file_digest(f, "sha3_256")
                    bf.add(hash.hexdigest())
                if ld:
                    with NamedTemporaryFile() as ln_gz:
                        for option in last[1:]:
                            if option != out and isfile(option):
                                objcopy = run(f'llvm-objcopy --dump-section=__ABOM,__abom={ln_gz.name} {option}', shell=True, capture_output=True)
                                if objcopy.returncode == 0:
                                    if verbose:
                                        print(f"Merging Linked Object ABOM: {option}")
                                    with NamedTemporaryFile() as ln:
                                        if ln_gz.read(6) != b"ABOM\x01\x01":
                                            exit("Invalid ABOM Header.")
                                        bf_file.write(decompress(ln.read()))
                                        bf_file.flush()
                                        hash = file_digest(ln, "sha3_256")
                                    bf.add(hash.hexdigest())
                                else:
                                    warnings.warn(f"Linked object lacks ABOM: {option}", category=RuntimeWarning)
            with NamedTemporaryFile() as bf_gz:
                # Write ABOM Header ('ABOM',version,num_filters)
                bf_gz.write(b"ABOM\x01\x01")
                with open(bf_file.name, 'rb') as bf_f:
                    # Compress Bloom Filter
                    bf_gz.write(compress(bf_f.read()))
                bf_gz.flush()
                # Create Bloom Filter Object File
                obj = run(f'echo ".section __ABOM,__abom\n.incbin \\"{bf_gz.name}\\"" | clang -c -x assembler -o {bf_obj_file.name} -', shell=True)
                if obj.returncode != 0:
                    exit("Could not create object file.")
        if ld:
            # Add Bloom Filter Object File to Linker
            compile = cmds[4:-1] + [join(last + [bf_obj_file.name])]
        else:
            # Add relocatable linker command to merge object files
            compile = cmds[4:] + [f'ld -r -o {out} {out} {bf_obj_file.name}']
        # Run Compilation
        for cmd in compile:
            out = run(cmd, shell=True, capture_output=True, text=True)
            print(out.stderr, end='')

if __name__ == '__main__':
    main()