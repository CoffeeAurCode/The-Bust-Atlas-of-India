r"""Local entrypoint for the Bust Atlas API.

    .venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000

The app itself lives in `frontend/api/index.py` because that is the file Vercel
deploys as a Python function, and only the `frontend` folder is deployed there.
Rather than keep two copies, this module loads that file by path and re-exports
`app`. Set BUST_ATLAS_DATA to serve a different data directory.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "frontend" / "api" / "index.py"


def _load(path: Path, name: str = "bust_atlas_api") -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


api = _load(APP_FILE)
app = api.app
data_dir = api.data_dir

__all__ = ["api", "app", "data_dir"]
