#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marshal module stability and correctness test suite

Test objectives:
  1. Byte-level determinism  : does the same input always produce the
     same marshal byte stream within one environment / across OSes?
  2. Round-trip correctness  : does dump -> load always recover a value
     that is logically equal (and, for reference structures, identity-
     preserving) to the original object?
  3. Cross-version stability : does the marshal byte stream (and the
     ability to load it) stay consistent across different Python
     interpreter versions / different marshal format versions?
"""

import argparse
import json
import marshal
import os
import platform
import sys
from datetime import datetime


# ============================================================
# Colored output (only works if terminal supports it)
# ============================================================
try:
    from colorama import init, Fore, Style
    init()
    GREEN = Fore.GREEN
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    RESET = Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = RESET = ""


def cprint(color, text):
    """Print with color"""
    print(f"{color}{text}{RESET}")


# ============================================================
# Test Framework
# ============================================================
class MarshalStabilityTest:
    """marshal stability test class"""

    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.results = []

    # ------------------------------------------------------------------
    # Stability: does the same input produce the same bytes, repeatedly
    # and (via persisted .bin artifacts) across separate runs / OSes?
    # ------------------------------------------------------------------
    def assert_stable(self, name, obj, compare_twice=True):
        self.total += 1
        safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c in " _-"]).rstrip()
        artifact_file = f"os_artifact_{safe_name}.bin"

        try:
            # NOTE (Fix 1a): both b1 and b2 are produced by the *same*
            # real call pattern marshal users would make. No artificial
            # construction of a different NaN bit pattern here -- we are
            # testing whether marshal.dumps is deterministic for the
            # given obj, not comparing two different objects.
            if name == "NaN":
                b1 = marshal.dumps(float('nan'))
                b2 = marshal.dumps(float('nan'))
            else:
                b1 = marshal.dumps(obj)
                b2 = marshal.dumps(obj)

            if compare_twice and b1 != b2:
                raise AssertionError(
                    f"Non-deterministic byte stream detected within the same process!\n"
                    f"  First:  {b1[:20]}...\n"
                    f"  Second: {b2[:20]}..."
                )

            if os.path.exists(artifact_file):
                with open(artifact_file, "rb") as f:
                    b_other_os = f.read()
                if b1 != b_other_os:
                    raise AssertionError(
                        f"Cross-OS Non-determinism detected!\n"
                        f"  Current OS Byte Stream: {b1.hex()[:20]}...\n"
                        f"  Other OS Byte Stream:   {b_other_os.hex()[:20]}..."
                    )
            else:
                with open(artifact_file, "wb") as f:
                    f.write(b1)

            self.passed += 1
            self.results.append((name, True, None))
            cprint(GREEN, f"  \u2705 PASS: {name}")
            return True

        except Exception as e:
            self.failed += 1
            self.results.append((name, False, str(e)))
            cprint(RED, f"  \u274c FAIL: {name}")
            print(f"      Error: {e}")
            return False

    def assert_roundtrip(self, name, obj, identity_check=None):
        self.total += 1
        try:
            dumped = marshal.dumps(obj)
            loaded = marshal.loads(dumped)

            if identity_check is not None:
                # Used for cyclic / self-referential structures.
                if identity_check(loaded):
                    self.passed += 1
                    cprint(GREEN, f"  \u2705 PASS (roundtrip): {name} (reference identity preserved)")
                    return True
                else:
                    raise AssertionError("Round-trip did not preserve self-reference identity")

            if isinstance(obj, float) and obj != obj:
                if loaded != loaded:
                    self.passed += 1
                    cprint(GREEN, f"  \u2705 PASS (roundtrip): {name} (NaN handled)")
                    return True
                else:
                    raise AssertionError("NaN roundtrip failed")
            else:
                if loaded == obj:
                    self.passed += 1
                    cprint(GREEN, f"  \u2705 PASS (roundtrip): {name}")
                    return True
                else:
                    raise AssertionError(f"Roundtrip mismatch: {obj} -> {loaded}")
        except Exception as e:
            self.failed += 1
            self.results.append((name, False, str(e)))
            cprint(RED, f"  \u274c FAIL (roundtrip): {name}")
            print(f"      Error: {e}")
            return False

    # ------------------------------------------------------------------
    # Explicit format-version matrix (in-process, no second interpreter
    # required). Exercises marshal's `version` parameter directly, since
    # two interpreter versions may share the same default format version
    # (e.g. 3.12 and 3.13 both default to format version 4) and therefore
    # would never actually exercise a format difference if we only ever
    # used the default version.
    # ------------------------------------------------------------------
    def assert_format_version_roundtrip(self, name, obj, fmt_version):
        self.total += 1
        try:
            # NOTE: `version` is a positional-only parameter on
            # marshal.dumps (signature: dumps(value, version, /)), so it
            # must be passed positionally rather than as version=....
            dumped = marshal.dumps(obj, fmt_version)
            loaded = marshal.loads(dumped)
            ok = (loaded != loaded) if (isinstance(obj, float) and obj != obj) else (loaded == obj)
            if ok:
                self.passed += 1
                cprint(GREEN, f"  \u2705 PASS: {name} [format version {fmt_version}]")
                return True
            raise AssertionError(f"Roundtrip mismatch at format version {fmt_version}: {obj} -> {loaded}")
        except Exception as e:
            self.failed += 1
            self.results.append((name, False, str(e)))
            cprint(RED, f"  \u274c FAIL: {name} [format version {fmt_version}]")
            print(f"      Error: {e}")
            return False

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        print(f"Total tests: {self.total}")
        print(f"Passed: {GREEN}{self.passed}{RESET}")
        print(f"Failed: {RED}{self.failed}{RESET}")
        if self.total:
            print(f"Pass rate: {self.passed / self.total * 100:.1f}%")

        failed_tests = [name for name, passed, _ in self.results if not passed]
        if failed_tests:
            print(f"\n{RED}Failed tests:{RESET}")
            for name in failed_tests:
                print(f"  - {name}")

    def print_environment(self):
        """Print test environment information"""
        print("=" * 70)
        print("Test Environment")
        print("=" * 70)
        print(f"Operating System: {platform.system()} {platform.release()}")
        print(f"Python version: {sys.version}")
        print(f"Marshal format version (default): {marshal.version}")
        print(f"Architecture: {platform.machine()}")
        print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)


# ============================================================
# Shared object battery used by both the local stability suite
# and the cross-version dump/verify workflow, so that "the same
# input" really does mean the same input in both contexts.
# ============================================================
def get_cross_version_battery():
    """A fixed set of (name, object) pairs used for cross-version testing.
    Code objects are deliberately NOT included here: the marshal docs
    state the format of code objects is version-dependent and undefined
    across interpreter versions, so comparing code-object bytes across
    versions is expected to differ/fail and is tested separately by
    test_code_object_cross_version_warning().
    """
    return [
        ("None", None),
        ("Bool True", True),
        ("Bool False", False),
        ("Int small", 42),
        ("Int negative", -1),
        ("Int large 2**100", 2**100),
        ("Int very large 2**100000", 2**100000),
        ("Float pi", 3.14159),
        ("Float negative zero", -0.0),
        ("Float inf", float('inf')),
        ("Float -inf", float('-inf')),
        ("String hello", "hello"),
        ("String empty", ""),
        ("String long", "a" * 10000),
        ("Bytes hello", b"hello"),
        ("Bytes empty", b""),
        ("List nested", [1, [2, 3]]),
        ("List large", list(range(1000))),
        ("Tuple basic", (1, 2, 3)),
        ("Dict basic", {"a": 1, "b": [1, 2]}),
        ("Set basic", {1, 2, 3}),
        ("Frozenset basic", frozenset({1, 2})),
    ]


# ============================================================
# Cross-version stability workflow 
# ============================================================
def cross_version_dump(baseline_path):
    """Phase A: run this under interpreter/version A.
    Serializes the shared object battery and writes a JSON baseline file
    containing interpreter metadata plus each object's marshal bytes
    (hex-encoded, since raw bytes aren't JSON-safe).
    """
    battery = get_cross_version_battery()
    entries = []
    for name, obj in battery:
        try:
            data = marshal.dumps(obj)
            entries.append({"name": name, "bytes_hex": data.hex(), "error": None})
        except Exception as e:
            entries.append({"name": name, "bytes_hex": None, "error": str(e)})

    baseline = {
        "python_version": sys.version,
        "python_version_info": list(sys.version_info),
        "marshal_format_version": marshal.version,
        "platform": platform.platform(),
        "created_at": datetime.now().isoformat(),
        "entries": entries,
    }

    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)

    print("=" * 70)
    print("Cross-version DUMP phase complete")
    print("=" * 70)
    print(f"Interpreter : {sys.version.splitlines()[0]}")
    print(f"Marshal fmt : {marshal.version}")
    print(f"Wrote       : {baseline_path}  ({len(entries)} objects)")
    print("\nNext step: run this script with --mode verify --baseline "
          f"{baseline_path} under a DIFFERENT Python interpreter/version.")


def cross_version_verify(baseline_path):
    """Phase B: run this under interpreter/version B, pointing at a
    baseline file produced by Phase A under interpreter/version A.

    For every object in the shared battery this:
      1. Re-serializes the object under the CURRENT interpreter.
      2. Compares the new bytes to the baseline bytes byte-for-byte.
      3. Attempts marshal.loads() on the BASELINE bytes under the current
         interpreter, to check whether data written by version A can
         still be correctly read by version B (this is the scenario the
         marshal docs warn about: "de-serializing ... in the incorrect
         Python version has undefined behavior" for code objects, and
         more generally format changes are only guaranteed compatible
         within the same format version number).
    """
    if not os.path.exists(baseline_path):
        cprint(RED, f"Baseline file not found: {baseline_path}")
        cprint(YELLOW, "Run with --mode dump first, under the OTHER interpreter version.")
        return None

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    print("=" * 70)
    print("Cross-version VERIFY phase")
    print("=" * 70)
    print(f"Baseline interpreter : {baseline['python_version'].splitlines()[0]}")
    print(f"Baseline marshal fmt : {baseline['marshal_format_version']}")
    print(f"Current interpreter  : {sys.version.splitlines()[0]}")
    print(f"Current marshal fmt  : {marshal.version}")
    print("=" * 70)

    battery = dict(get_cross_version_battery())
    tester = MarshalStabilityTest()

    for entry in baseline["entries"]:
        name = entry["name"]
        tester.total += 1
        if name not in battery:
            cprint(YELLOW, f"  \u26a0 SKIP: {name} (not present in current battery)")
            continue
        obj = battery[name]

        if entry["error"] is not None:
            cprint(YELLOW, f"  \u26a0 SKIP: {name} (baseline could not serialize it: {entry['error']})")
            continue

        baseline_bytes = bytes.fromhex(entry["bytes_hex"])

        try:
            current_bytes = marshal.dumps(obj)
            bytes_match = (current_bytes == baseline_bytes)

            try:
                loaded_from_baseline = marshal.loads(baseline_bytes)
                if isinstance(obj, float) and obj != obj:
                    load_ok = (loaded_from_baseline != loaded_from_baseline)
                else:
                    load_ok = (loaded_from_baseline == obj)
            except Exception as load_err:
                load_ok = False
                cprint(YELLOW, f"      Could not load baseline bytes: {load_err}")

            if bytes_match and load_ok:
                tester.passed += 1
                cprint(GREEN, f"  \u2705 PASS: {name} (bytes identical, baseline loads correctly)")
            elif load_ok and not bytes_match:
                tester.passed += 1
                cprint(YELLOW, f"  \u26a0 PASS-WITH-NOTE: {name} (bytes differ across versions, "
                                f"but baseline data still loads correctly -- format is "
                                f"version-tolerant for this object)")
            else:
                tester.failed += 1
                tester.results.append((name, False, "baseline bytes failed to load correctly"))
                cprint(RED, f"  \u274c FAIL: {name} (baseline bytes could not be correctly "
                            f"loaded under the current interpreter)")
        except Exception as e:
            tester.failed += 1
            tester.results.append((name, False, str(e)))
            cprint(RED, f"  \u274c FAIL: {name}")
            print(f"      Error: {e}")

    tester.print_summary()
    return tester


# ============================================================
# In-process explicit format-version matrix
# ============================================================
def run_format_version_matrix(tester):
    """Exercise marshal.dumps(obj, version=N) explicitly for every
    documented format version up to and including the version this
    interpreter understands, since two interpreter versions chosen for
    the cross_version_dump/verify workflow might not actually straddle
    a format-version boundary (3.12 and 3.13 both default to format
    version 4, for example).
    """
    print("\n" + "=" * 70)
    print("Explicit Format-Version Matrix (marshal.version parameter)")
    print("=" * 70)

    max_version = marshal.version
    sample_objects = [
        ("Int 42", 42),
        ("Float 3.14", 3.14),
        ("String short", "hi"),
        ("List nested", [1, [2, 3]]),
        ("Dict basic", {"a": 1}),
        ("Set basic", {1, 2, 3}),
    ]
    # slice was only added in format version 5 / Python 3.14; only test
    # it if the running interpreter actually understands that version.
    if max_version >= 5:
        sample_objects.append(("Slice object", slice(1, 10, 2)))

    for fmt_version in range(0, max_version + 1):
        print(f"\n--- Format version {fmt_version} ---")
        for name, obj in sample_objects:
            if fmt_version < 5 and isinstance(obj, slice):
                continue
            tester.assert_format_version_roundtrip(f"{name}", obj, fmt_version)


def test_code_object_cross_version_warning():
    """Not a pass/fail test -- a deliberate demonstration / documentation
    case. The marshal docs explicitly state that code-object format is
    NOT guaranteed across Python versions, even when the format version
    number is the same, and that loading a code object under the wrong
    version is undefined behavior. We dump a code object here and report
    its format so the README / report can point at concrete evidence
    rather than just quoting the documentation.
    """
    print("\n" + "=" * 70)
    print("Code Object Note (not scored - documentation purposes only)")
    print("=" * 70)
    code_obj = compile("x = 1 + 1", "<string>", "exec")
    data = marshal.dumps(code_obj)
    print(f"Compiled under Python {sys.version.splitlines()[0]}")
    print(f"marshal.dumps(code_object) length: {len(data)} bytes")
    print("Per the marshal documentation: code-object byte layout is "
          "version-specific and is NOT expected to match across "
          "interpreter versions, even when marshal.version is the same. "
          "This is excluded from the pass/fail battery for that reason; "
          "compare this length/hex manually against another interpreter "
          "version's output if you want to see the difference directly.")
    print(f"First 16 bytes (hex): {data[:16].hex()}")


# ============================================================
# Local (single-interpreter) Test Case Definitions
# ============================================================
def run_all_tests():
    """Run all in-process test cases (stability + roundtrip + format-version matrix)."""
    tester = MarshalStabilityTest()
    tester.print_environment()

    print("\n" + "=" * 70)
    print("Stability Tests (are two serializations of the same input identical?)")
    print("=" * 70)

    # ----- 1. Basic Types -----
    print("\n--- 1. Basic Types ---")
    tester.assert_stable("None", None)
    tester.assert_stable("True", True)
    tester.assert_stable("False", False)
    tester.assert_stable("Integer 0", 0)
    tester.assert_stable("Integer 42", 42)
    tester.assert_stable("Integer -1", -1)
    tester.assert_stable("Large integer 2**100", 2**100)
    tester.assert_stable("String 'hello'", "hello")
    tester.assert_stable("Empty string ''", "")
    tester.assert_stable("Bytes b'hello'", b"hello")
    tester.assert_stable("Empty bytes b''", b"")

    # ----- 2. Floating Point Numbers -----
    print("\n--- 2. Floating Point Numbers ---")
    tester.assert_stable("Float 0.0", 0.0)
    tester.assert_stable("Float 3.14159", 3.14159)
    tester.assert_stable("Float -2.5", -2.5)
    tester.assert_stable("Negative zero -0.0", -0.0)

    # ----- 3. Special Floating Point Values (Critical!) -----
    print("\n--- 3. Special Floating Point Values (Critical Tests) ---")
    tester.assert_stable("NaN", float('nan'))
    tester.assert_stable("Positive Infinity Inf", float('inf'))
    tester.assert_stable("Negative Infinity -Inf", float('-inf'))

    # ----- 4. Container Types -----
    print("\n--- 4. Container Types ---")
    tester.assert_stable("Empty list []", [])
    tester.assert_stable("Single-element list [1]", [1])
    tester.assert_stable("Nested list [1, [2, 3]]", [1, [2, 3]])
    tester.assert_stable("Empty tuple ()", ())
    tester.assert_stable("Single-element tuple (1,)", (1,))
    tester.assert_stable("Tuple (1,2,3)", (1, 2, 3))
    tester.assert_stable("Empty dict {}", {})
    tester.assert_stable("Dict {'a': 1}", {"a": 1})
    tester.assert_stable("Empty set set()", set())
    tester.assert_stable("Set {1,2,3}", {1, 2, 3})
    tester.assert_stable("Empty frozenset frozenset()", frozenset())
    tester.assert_stable("Frozenset frozenset({1,2})", frozenset({1, 2}))

    # ----- 5. Boundary Values -----
    print("\n--- 5. Boundary Values ---")
    tester.assert_stable("Very large integer 2**100000", 2**100000)
    tester.assert_stable("Very small integer -2**100000", -2**100000)
    tester.assert_stable("Long string 'a' * 10000", "a" * 10000)
    tester.assert_stable("Large list list(range(1000))", list(range(1000)))

    # ----- 6. Recursive/Cyclic Structures -----
    # FIX 1b: these now genuinely call marshal.dumps()/loads() instead of
    # being hard-coded to fail. marshal has supported recursive
    # containers since format version 3 (Python 3.4), so the expectation
    # going in is PASS, and assert_stable measures whether that is
    # actually true for two independent dumps in this process.
    print("\n--- 6. Recursive/Cyclic Structures ---")
    recursive_list = []
    recursive_list.append(recursive_list)
    tester.assert_stable("Self-referential list", recursive_list)

    recursive_dict = {}
    recursive_dict["self"] = recursive_dict
    tester.assert_stable("Self-referential dictionary", recursive_dict)

    a = [1]
    b = [2]
    a.append(b)
    b.append(a)
    tester.assert_stable("Mutually referential lists", a)

    # ----- 7. Composite Types -----
    print("\n--- 7. Composite Types ---")
    complex_obj = {
        "int": 42,
        "float": 3.14,
        "nan": float('nan'),
        "list": [1, 2, [3, 4]],
        "tuple": (5, 6),
        "nested_dict": {"key": "value"}
    }
    tester.assert_stable("Composite dictionary object", complex_obj)

    # ----- 8. Fuzz Testing -----
    print("\n--- 8. Fuzz Testing ---")
    import random
    random.seed(42)  # Fixed seed for reproducibility
    for i in range(20):
        rand_val = random.random()
        tester.assert_stable(f"Random float #{i+1}", rand_val)

    # ============================================================
    # Round-trip Correctness Tests
    # ============================================================
    print("\n" + "=" * 70)
    print("Round-trip Correctness Tests (dump -> load == original?)")
    print("=" * 70)

    tester.assert_roundtrip("None", None)
    tester.assert_roundtrip("Integer 42", 42)
    tester.assert_roundtrip("Large integer", 2**100)
    tester.assert_roundtrip("Float 3.14", 3.14)
    tester.assert_roundtrip("NaN", float('nan'))
    tester.assert_roundtrip("String 'hello'", "hello")
    tester.assert_roundtrip("List [1,2,3]", [1, 2, 3])
    tester.assert_roundtrip("Dict {'a':1}", {"a": 1})
    tester.assert_roundtrip("Empty list", [])
    tester.assert_roundtrip("Empty dict", {})

    # FIX 1b (continued): roundtrip coverage for cyclic structures too,
    # using an identity check rather than == , since what we actually
    # care about is whether the reference cycle itself was reconstructed.
    rl = []
    rl.append(rl)
    tester.assert_roundtrip(
        "Self-referential list (roundtrip)", rl,
        identity_check=lambda loaded: loaded[0] is loaded
    )

    rd = {}
    rd["self"] = rd
    tester.assert_roundtrip(
        "Self-referential dictionary (roundtrip)", rd,
        identity_check=lambda loaded: loaded["self"] is loaded
    )

    ma, mb = [1], [2]
    ma.append(mb)
    mb.append(ma)
    tester.assert_roundtrip(
        "Mutually referential lists (roundtrip)", ma,
        identity_check=lambda loaded: loaded[1][1] is loaded
    )

    # ============================================================
    # Explicit format-version matrix (Fix 2, in-process half)
    # ============================================================
    run_format_version_matrix(tester)

    # Documentation-only note about code objects (not scored)
    test_code_object_cross_version_warning()

    # ============================================================
    # Print Summary
    # ============================================================
    tester.print_summary()

    return tester


# ============================================================
# Main Entry Point
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="marshal module stability, correctness, and "
                     "cross-version test suite"
    )
    parser.add_argument(
        "--mode",
        choices=["local", "dump", "verify"],
        default="local",
        help=(
            "local  : run the full in-process stability/roundtrip/"
            "format-version suite under the current interpreter only "
            "(default). "
            "dump   : (cross-version phase A) serialize the shared "
            "object battery under the CURRENT interpreter and write a "
            "baseline file. "
            "verify : (cross-version phase B) compare the CURRENT "
            "interpreter's serialization against a baseline file "
            "produced by `--mode dump` under a DIFFERENT interpreter."
        ),
    )
    parser.add_argument(
        "--baseline",
        default="cross_version_baseline.json",
        help="Path to the baseline JSON file used by --mode dump/verify "
             "(default: cross_version_baseline.json)",
    )
    args = parser.parse_args()

    if args.mode == "local":
        run_all_tests()
    elif args.mode == "dump":
        cross_version_dump(args.baseline)
    elif args.mode == "verify":
        cross_version_verify(args.baseline)


if __name__ == "__main__":
    main()
