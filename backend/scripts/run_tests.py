#!/usr/bin/env python
"""One-shot test runner.

Skeleton entry — full fixtures and suites land in Phase 6.
Usage:
    python scripts/run_tests.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    backend_dir = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-m", "pytest", "tests", "-q"]
    print(f"> {' '.join(cmd)}  (cwd={backend_dir})")
    result = subprocess.run(cmd, cwd=backend_dir)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())