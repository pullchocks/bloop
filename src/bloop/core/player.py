from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from bloop.core.cable import CABLE_SINK
from bloop.core.library import Sound
from bloop.core.pulse import default_sink, run_bin

NATIVE = {".wav", ".flac", ".ogg", ".oga"}


def _pulse_volume(percent: int) -> int:
    return max(0, min(98304, int(65536 * max(0, percent) / 100)))


def _spawn(command: list[str], stdin: int | None = None) -> subprocess.Popen | None:
    try:
        return subprocess.Popen(
            command,
            stdin=stdin,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None


def _kill(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        try:
            proc.terminate()
        except OSError:
            return
    try:
        proc.wait(timeout=0.4)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass


def probe_duration_ms(path: str) -> int:
    file = Path(path)
    if not file.is_file():
        return 0
    for tool, args in (
        ("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(file)]),
        ("mediainfo", ["--Inform=General;%Duration%", str(file)]),
    ):
        if not shutil.which(tool):
            continue
        code, out, _err = run_bin(tool, *args, timeout=6)
        if code != 0 or not out:
            continue
        try:
            value = float(out.splitlines()[0].strip())
            if tool == "mediainfo":
                return int(value)
            return int(value * 1000)
        except ValueError:
            continue
    if shutil.which("ffmpeg"):
        code, _out, err = run_bin("ffmpeg", "-i", str(file), timeout=6)
        for line in (err or "").splitlines():
            if "Duration:" not in line:
                continue
            stamp = line.split("Duration:", 1)[1].split(",", 1)[0].strip()
            parts = stamp.split(":")
            if len(parts) != 3:
                continue
            try:
                hours, minutes, seconds = float(parts[0]), float(parts[1]), float(parts[2])
                return int((hours * 3600 + minutes * 60 + seconds) * 1000)
            except ValueError:
                return 0
    return 0


def format_duration(ms: int) -> str:
    if ms <= 0:
        return "—"
    total = max(0, ms // 1000)
    return f"{total // 60}:{total % 60:02d}"


@dataclass
class Voice:
    sound_id: str
    name: str
    procs: list[subprocess.Popen]
    preview: bool = False


class Player(QObject):
    changed = Signal()
    finished = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.voices: list[Voice] = []
        self.master_volume = 100
        self.hear_locally = True
        self.send_to_voice = True
        self.local_sink = ""
        self.overlap = "overlap"
        self._poll = QTimer(self)
        self._poll.setInterval(250)
        self._poll.timeout.connect(self._reap)
        self._poll.start()

    def playing(self) -> list[dict]:
        return [{"id": voice.sound_id, "name": voice.name, "preview": voice.preview} for voice in self.voices]

    def is_playing(self, sound_id: str) -> bool:
        return any(voice.sound_id == sound_id for voice in self.voices)

    def stop_all(self) -> None:
        for voice in list(self.voices):
            self._stop_voice(voice)
        self.voices.clear()
        self.changed.emit()

    def stop_sound(self, sound_id: str) -> None:
        remaining = []
        for voice in self.voices:
            if voice.sound_id == sound_id:
                self._stop_voice(voice)
            else:
                remaining.append(voice)
        self.voices = remaining
        self.changed.emit()

    def play(self, sound: Sound, *, preview: bool = False, cable_up: bool = False) -> bool:
        if not sound.exists():
            return False
        if self.overlap == "toggle" and self.is_playing(sound.id) and not preview:
            self.stop_sound(sound.id)
            return True
        if self.overlap == "replace" and not preview:
            self.stop_all()

        volume = int(self.master_volume * max(0, min(150, sound.volume)) / 100)
        sinks: list[str] = []
        if preview or self.hear_locally:
            sinks.append(self.local_sink or "@DEFAULT_SINK@")
        if not preview and self.send_to_voice and cable_up:
            sinks.append(CABLE_SINK)
        sinks = list(dict.fromkeys(sinks))
        if not sinks:
            sinks.append(self.local_sink or "@DEFAULT_SINK@")

        procs: list[subprocess.Popen] = []
        for sink in sinks:
            proc = self._play_to(sound.path, sink, volume)
            if proc is not None:
                procs.append(proc)
        if not procs:
            return False
        self.voices.append(Voice(sound_id=sound.id, name=sound.name, procs=procs, preview=preview))
        self.changed.emit()
        return True

    def _play_to(self, path: str, sink: str, volume: int) -> subprocess.Popen | None:
        target = default_sink() if sink in {"", "@DEFAULT_SINK@"} else sink
        if not target:
            target = sink or "@DEFAULT_SINK@"
        vol = str(_pulse_volume(volume))
        suffix = Path(path).suffix.lower()
        if suffix in NATIVE and shutil.which("paplay"):
            return _spawn(["paplay", f"--device={target}", f"--volume={vol}", path])
        if shutil.which("ffmpeg") and shutil.which("paplay"):
            command = (
                "ffmpeg -hide_banner -loglevel error -nostdin "
                f"-i {shlex.quote(path)} -ac 2 -ar 48000 -f wav - | "
                f"paplay --device={shlex.quote(target)} --volume={vol}"
            )
            return _spawn(["bash", "-lc", command])
        if shutil.which("mpv"):
            return _spawn(
                [
                    "mpv",
                    "--no-video",
                    "--really-quiet",
                    f"--volume={min(150, volume)}",
                    f"--audio-device=pulse/{target}",
                    path,
                ]
            )
        if shutil.which("pw-play"):
            return _spawn(["pw-play", f"--target={target}", path])
        return None

    def _stop_voice(self, voice: Voice) -> None:
        for proc in voice.procs:
            _kill(proc)

    def _reap(self) -> None:
        alive: list[Voice] = []
        finished: list[str] = []
        for voice in self.voices:
            running = False
            for proc in voice.procs:
                if proc.poll() is None:
                    running = True
                    break
            if running:
                alive.append(voice)
            else:
                finished.append(voice.sound_id)
        if len(alive) != len(self.voices):
            self.voices = alive
            self.changed.emit()
            for sound_id in finished:
                self.finished.emit(sound_id)
