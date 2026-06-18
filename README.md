# marshal-stability-test

A black-box and white-box test suite for Python's built-in `marshal` 
module, investigating byte-stream stability across operating systems, 
Python versions, and edge-case inputs.

## Requirements

- Python 3.10+
- `colorama` (optional, for colored terminal output)

## Installation

cd marshal-stability-test

pip install colorama

## Usage

python MarshalTest.py

Results are printed to stdout. Cross-OS artifact files (*.bin) 
are written to the working directory for byte-stream comparison 
across environments.

## What Is Tested

| Category              | Technique Used                  | Cases |
|-----------------------|---------------------------------|-------|
| Basic types           | Equivalence partitioning        | 11    |
| Floating point        | Boundary value analysis         | 4     |
| Special floats        | Boundary value analysis         | 3     |
| Container types       | Equivalence partitioning        | 12    |
| Boundary values       | Boundary value analysis         | 4     |
| Cyclic structures     | White-box / structural testing  | 3     |
| Composite types       | Equivalence partitioning        | 1     |
| Fuzz testing          | Random fuzzing (seed=42)        | 20    |
| Round-trip correctness| Black-box correctness           | 10    |
| **Total**             |                                 | **68**|

## Key Findings

- **NaN is non-deterministic**: `marshal.dumps(float('nan'))` produces 
  different byte streams across process lifecycles due to floating-point 
  sign-bit ambiguity.
- **Cyclic structures are unsupported**: Self-referential lists and 
  dicts cause assertion errors — `marshal` cannot handle graph topologies.
- All other types pass with 100% stability across Windows and Linux.

<!-- See [REPORT.md](REPORT.md) for full analysis and traceability matrix. -->

## License

MIT
