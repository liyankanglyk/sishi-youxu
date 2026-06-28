#!/usr/bin/env python
"""一次性测试运行脚本。

骨架入口 —— 完整的 fixture 与测试套件将在 Phase 6 落地。
用法：
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