# ABOM

This repository implements ABOM as a clang wrapper.

## Installation

```bash
pip install -r requirements.txt
```
Note that clang and llvm-objcopy must both be avilable in the PATH.

## Usage

To compile a program with ABOM, run the following command:
```bash
./abom CLANG_CMD
```

To check whether a certain dependency is present in the ABOM-compiled program, run the following command:
```bash
./abom-check <binary> <dependency>
```