from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths

APP_DIR_NAMES = {"bloop", ".bloop-data"}


def data_dir() -> Path:
    candidates = []
    qt_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if qt_path:
        candidates.append(Path(qt_path))
    candidates.append(Path.home() / ".local" / "share" / "Bloop")
    candidates.append(Path.cwd() / ".bloop-data")
    for path in candidates:
        if path.name.lower() not in APP_DIR_NAMES:
            path = path / "Bloop"
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            continue
    raise RuntimeError("Unable to create Bloop data directory")


def sounds_dir() -> Path:
    path = data_dir() / "sounds"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_dir() / "settings.json"


def library_path() -> Path:
    return data_dir() / "library.json"


def ipc_path() -> Path:
    return data_dir() / "ipc.json"


def cable_state_path() -> Path:
    return data_dir() / "cable-state.json"


def load_json(path: Path, fallback: dict | None = None) -> dict:
    if not path.is_file():
        return dict(fallback or {})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else dict(fallback or {})
    except Exception:
        return dict(fallback or {})


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_settings() -> dict:
    return load_json(settings_path())


def save_settings(data: dict) -> None:
    save_json(settings_path(), data)
