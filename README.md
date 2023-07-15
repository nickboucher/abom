# ABOM

This repository implements ABOM as a clang wrapper.

## Installation

```bash
pip install -e .
```
Note that clang and llvm-objcopy must both be avilable in the PATH.

## Usage

To compile a program with ABOM, run the following command:
```bash
abom CLANG_CMD
```

To check whether a certain dependency is present in the ABOM-compiled program, run the following command:
```bash
abom-check <binary> <dependency>
```

To enable verbose logging, set the environment variable `ABOM_VERBOSE` to `1`, e.g.:
```bash
export ABOM_VERBOSE=1
```

## Tests

To run unit tests, run the following command from the root directory:
```bash
python -m unittest
```