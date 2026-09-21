"""Data location for HF.

Everything lives under one data directory so a backup = one folder:
``$HF_DATA_DIR`` when set, otherwise ``~/.hf_workshop``. The database file
and the generated reports subfolder both resolve from here, so the app
never scatters files into the project source tree.
"""

from __future__ import annotations

import os
from pathlib import Path

PRIMARY_DB_NAME = "hf.db"


def data_dir() -> Path:
    raw = (os.environ.get("HF_DATA_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hf_workshop"


def database_path() -> Path:
    return data_dir() / PRIMARY_DB_NAME


def reports_dir() -> Path:
    return data_dir() / "reports"


def ensure_dirs() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    reports_dir().mkdir(parents=True, exist_ok=True)


__all__ = ["PRIMARY_DB_NAME", "data_dir", "database_path", "reports_dir", "ensure_dirs"]
