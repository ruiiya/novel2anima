"""Compatibility wrapper for src/novel2anima/story/logic.py.

Deprecated compatibility shim. Import the package module instead:
    novel2anima.story.logic
"""
from __future__ import annotations

import importlib
import importlib.util
import pathlib
import runpy
import sys
import types

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_TARGET = "novel2anima.story.logic"
_TARGET_FILE = ''

if __name__ == "__main__":
    if _TARGET_FILE:
        runpy.run_path(_TARGET_FILE, run_name="__main__")
    else:
        runpy.run_module(_TARGET, run_name="__main__", alter_sys=True)
else:
    if _TARGET_FILE:
        _spec = importlib.util.spec_from_file_location("_n2a_compat_" + pathlib.Path(_TARGET_FILE).stem, _TARGET_FILE)
        _module = importlib.util.module_from_spec(_spec)
        assert _spec.loader is not None
        _spec.loader.exec_module(_module)
    else:
        _module = importlib.import_module(_TARGET)
    for _name, _value in vars(_module).items():
        if not _name.startswith("_") and not isinstance(_value, types.ModuleType):
            globals()[_name] = _value
    sys.modules[__name__] = _module
