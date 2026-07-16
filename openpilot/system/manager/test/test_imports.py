#!/usr/bin/env python3
"""fork: smoke-test that every managed Python process module imports.

openpilot disables ty's unresolved-import check (Cython/.pyx and capnp modules
can't be statically resolved), so a genuinely wrong import in a process module
isn't caught by lint -- it only blows up when the manager spawns the process
on-device. This test *executes* each import, so it catches that class of bug
(e.g. `import cereal` vs `import openpilot.cereal`) in the fast CI lane.

Each import runs in its own subprocess so a native crash in one module (e.g. a
raylib/GLFW init) can't take down the whole test session.
"""
import subprocess
import sys

import pytest

from openpilot.system.manager.process_config import procs
from openpilot.system.manager.process import PythonProcess

# Skipped for reasons unrelated to a bad import:
#  - ui: initializes raylib/GLFW at import, needs a display (headless -> segfault)
#  - webcamerad: needs the optional opencv (cv2) extra
SKIP = {"ui", "webcamerad"}

PYTHON_PROCS = [p for p in procs if isinstance(p, PythonProcess) and p.name not in SKIP]


@pytest.mark.parametrize("proc", PYTHON_PROCS, ids=lambda p: p.name)
def test_process_module_imports(proc):
  r = subprocess.run([sys.executable, "-c", f"import {proc.module}"],
                     capture_output=True, text=True, timeout=120)
  assert r.returncode == 0, f"{proc.module} failed to import:\n{r.stderr}"
