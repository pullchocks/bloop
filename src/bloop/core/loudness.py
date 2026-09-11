from __future__ import annotations

import threading
from pathlib import Path

from bloop.core.pulse import run_bin
from bloop.core.store import load_json, loudness_path, save_json

# Mean RMS target in dBFS. Clips are gained toward this, then limited so
# peaks stay under PEAK_CEILING_DB (so a hot meme cannot clip the output).
DEFAULT_TARGET_DB = -18.0
PEAK_CEILING_DB = -1.0
MAX_BOOST_DB = 18.0
MAX_CUT_DB = 24.0
ANALYZE_SECONDS = 30.0


def gain_db(
    mean_db: float,
    max_db: float,
    target_mean: float = DEFAULT_TARGET_DB,
) -> float:
    """Return the dB offset that brings a clip near target without clipping."""
    if mean_db <= -90:
        return 0.0
    gain = float(target_mean) - mean_db
    headroom = PEAK_CEILING_DB - max_db
    gain = min(gain, headroom)
    return max(-MAX_CUT_DB, min(MAX_BOOST_DB, gain))


def probe_levels(path: str) -> tuple[float, float] | None:
    file = Path(path)
    if not file.is_file():
        return None
    _code, _out, err = run_bin(
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-i",
        str(file),
        "-t",
        str(ANALYZE_SECONDS),
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
        timeout=12,
    )
    if not err:
        return None
    mean_db: float | None = None
    max_db: float | None = None
    for line in err.splitlines():
        stripped = line.strip()
        if "mean_volume:" in stripped:
            mean_db = _parse_db(stripped, "mean_volume:")
        elif "max_volume:" in stripped:
            max_db = _parse_db(stripped, "max_volume:")
    if mean_db is None or max_db is None:
        return None
    return mean_db, max_db


def _parse_db(line: str, key: str) -> float | None:
    try:
        token = line.split(key, 1)[1].strip().split()[0]
        return float(token)
    except (IndexError, ValueError):
        return None


class LoudnessCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data = load_json(loudness_path())

    def gain_for(self, path: str, target_mean: float = DEFAULT_TARGET_DB) -> float:
        levels = self.levels_for(path)
        if levels is None:
            return 0.0
        return gain_db(levels[0], levels[1], target_mean)

    def levels_for(self, path: str) -> tuple[float, float] | None:
        with self._lock:
            cached = self._cached(path)
        if cached is not None:
            return cached
        probed = probe_levels(path)
        if probed is None:
            return None
        with self._lock:
            self._store(path, probed)
        return probed

    def _cached(self, path: str) -> tuple[float, float] | None:
        file = Path(path)
        try:
            stat = file.stat()
        except OSError:
            return None
        entry = self._data.get(str(file))
        if not isinstance(entry, dict):
            return None
        if int(entry.get("mtime") or 0) != int(stat.st_mtime):
            return None
        if int(entry.get("size") or 0) != int(stat.st_size):
            return None
        try:
            return float(entry["mean_db"]), float(entry["max_db"])
        except (KeyError, TypeError, ValueError):
            return None

    def _store(self, path: str, levels: tuple[float, float]) -> None:
        file = Path(path)
        try:
            stat = file.stat()
        except OSError:
            return
        self._data[str(file)] = {
            "mean_db": levels[0],
            "max_db": levels[1],
            "mtime": int(stat.st_mtime),
            "size": int(stat.st_size),
        }
        try:
            save_json(loudness_path(), self._data)
        except OSError:
            pass
