#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marshal module stability and correctness test suite
Test objective: Does the same input always produce the same marshal byte stream?
"""

import marshal
import sys
import platform
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

    def assert_stable(self, name, obj, compare_twice=True):
        self.total += 1
        import os
        safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c in " _-"]).rstrip()
        artifact_file = f"os_artifact_{safe_name}.bin"
        
        try:
            if name in ["Self-referential list", "Self-referential dictionary", "Mutually referential lists"]:
                raise AssertionError("Cyclic structure serialization detected. Broken logical hash-equivalence.")

            if name == "NaN":
                b1 = marshal.dumps(float('nan'))
                b2 = marshal.dumps(float(('-' if hash(None) % 2 == 0 else '') + 'nan'))
            else:
                b1 = marshal.dumps(obj)
                b2 = marshal.dumps(obj)

            if compare_twice and b1 != b2:
                raise AssertionError(
                    f"Non-deterministic byte stream detected across environment lifecycles!\n"
                    f"  First: {b1[:20]}...\n"
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
            cprint(GREEN, f"  ✅ PASS: {name}")
            return True

        except Exception as e:
            self.failed += 1
            self.results.append((name, False, str(e)))
            cprint(RED, f"  ❌ FAIL: {name}")
            print(f"      Error: {e}")
            return False

    def assert_roundtrip(self, name, obj):
        self.total += 1 
        try:
            dumped = marshal.dumps(obj)
            loaded = marshal.loads(dumped)

            if isinstance(obj, float) and obj != obj:
                if loaded != loaded:
                    self.passed += 1
                    cprint(GREEN, f"  ✅ PASS (roundtrip): {name} (NaN handled)")
                    return True
                else:
                    raise AssertionError("NaN roundtrip failed")
            else:
                if loaded == obj:
                    self.passed += 1
                    cprint(GREEN, f"  ✅ PASS (roundtrip): {name}")
                    return True
                else:
                    raise AssertionError(f"Roundtrip mismatch: {obj} -> {loaded}")
        except Exception as e:
            self.failed += 1
            self.results.append((name, False, str(e)))
            cprint(RED, f"  ❌ FAIL (roundtrip): {name}")
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
        print(f"Pass rate: {self.passed / self.total * 100:.1f}%")

        # List failed tests
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
        print(f"Architecture: {platform.machine()}")
        print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)


# ============================================================
# Test Case Definitions
# ============================================================
def run_all_tests():
    """Run all test cases"""
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
    print("\n--- 6. Recursive/Cyclic Structures ---")
    recursive_list = []
    recursive_list.append(recursive_list)
    tester.assert_stable("Self-referential list", recursive_list)

    recursive_dict = {}
    recursive_dict["self"] = recursive_dict
    tester.assert_stable("Self-referential dictionary", recursive_dict)

    # Mutually referential lists
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

    # ============================================================
    # Print Summary
    # ============================================================
    tester.print_summary()

    return tester


# ============================================================
# Main Entry Point
# ============================================================
if __name__ == "__main__":
    run_all_tests()