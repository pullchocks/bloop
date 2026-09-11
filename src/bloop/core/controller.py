from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

from bloop import __version__
from bloop.core.cable import CableManager, CableStatus
from bloop.core.library import UNCATEGORIZED, Library, Sound
from bloop.core.player import Player, format_duration, probe_duration_ms
from bloop.core.desktop import autostart_installed, project_root, set_autostart
from bloop.core.store import load_settings, save_settings
from bloop.ui.theme import DEFAULT_ACCENT, DEFAULT_TEXT, apply_accent, apply_text


class Controller(QObject):
    library_changed = Signal()
    playback_changed = Signal()
    cable_changed = Signal()
    settings_changed = Signal()
    log_message = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.library = Library.load()
        self.player = Player(self)
        self.cable = CableManager()
        self._settings = load_settings()
        self._sync_autostart_setting()
        self._apply_settings()
        self._hotkeys: list[QShortcut] = []
        self._hotkey_host: QWidget | None = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._flush)
        self.player.changed.connect(self.playback_changed.emit)
        if self._settings.get("cable_on_start", True):
            QTimer.singleShot(250, self.enable_cable)
        QTimer.singleShot(400, self._prefetch_loudness)

    def log(self, message: str) -> None:
        self.log_message.emit(message)

    def _sync_autostart_setting(self) -> None:
        if "start_on_login" not in self._settings:
            self._settings["start_on_login"] = autostart_installed()
            save_settings(self._settings)
            return
        set_autostart(bool(self._settings.get("start_on_login")), project_root())

    def _apply_settings(self) -> None:
        apply_accent(str(self._settings.get("accent") or DEFAULT_ACCENT))
        apply_text(str(self._settings.get("text") or DEFAULT_TEXT))
        self.player.master_volume = int(self._settings.get("master_volume", 100))
        self.player.hear_locally = bool(self._settings.get("hear_locally", True))
        self.player.send_to_voice = bool(self._settings.get("send_to_voice", True))
        self.player.local_sink = str(self._settings.get("headphones") or "")
        self.player.overlap = str(self._settings.get("overlap") or "overlap")
        self.player.normalize_loudness = bool(self._settings.get("normalize_loudness", True))
        try:
            self.player.loudness_target = float(self._settings.get("loudness_target", -18))
        except (TypeError, ValueError):
            self.player.loudness_target = -18.0

    def settings(self) -> dict[str, Any]:
        return dict(self._settings)

    def update_settings(self, **values: Any) -> None:
        rebuild_keys = {"mix_mic", "mic_source", "set_default_mic"}
        rebuild = self.cable.is_up() and any(key in values for key in rebuild_keys)
        self._settings.update(values)
        save_settings(self._settings)
        self._apply_settings()
        if "start_on_login" in values:
            set_autostart(bool(self._settings.get("start_on_login")), project_root())
        if rebuild:
            self.enable_cable(rebuild=True)
        self.settings_changed.emit()
        self.cable_changed.emit()
        self.playback_changed.emit()

    def schedule_save(self) -> None:
        self._save_timer.start(250)

    def _flush(self) -> None:
        self.library.save()

    def bind_hotkeys(self, host: QWidget) -> None:
        self._hotkey_host = host
        self.rebuild_hotkeys()

    def rebuild_hotkeys(self) -> None:
        host = self._hotkey_host
        for shortcut in self._hotkeys:
            shortcut.setParent(None)
        self._hotkeys.clear()
        if host is None:
            return
        for sound in self.library.sounds:
            if not sound.hotkey:
                continue
            shortcut = QShortcut(QKeySequence(sound.hotkey), host)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sound_id = sound.id
            shortcut.activated.connect(lambda sid=sound_id: self.play(sid))
            self._hotkeys.append(shortcut)

    def _prefetch_loudness(self) -> None:
        if not self.player.normalize_loudness:
            return
        for sound in self.library.sounds:
            self.player.enqueue_probe(sound.path)

    def import_files(self, paths: list[Path], category_id: str = UNCATEGORIZED, copy: bool = False) -> int:
        added = self.library.import_paths(paths, category_id=category_id, copy=copy)
        for sound in added:
            if sound.duration_ms <= 0:
                sound.duration_ms = probe_duration_ms(sound.path)
            self.player.enqueue_probe(sound.path)
        self.schedule_save()
        self.rebuild_hotkeys()
        self.library_changed.emit()
        return len(added)

    def remove_sound(self, sound_id: str) -> None:
        self.player.stop_sound(sound_id)
        self.library.remove_sound(sound_id)
        self.schedule_save()
        self.rebuild_hotkeys()
        self.library_changed.emit()

    def update_sound(self, sound_id: str, **values: Any) -> Sound | None:
        sound = self.library.find_sound(sound_id)
        if sound is None:
            return None
        for key, value in values.items():
            if hasattr(sound, key):
                setattr(sound, key, value)
        self.schedule_save()
        self.rebuild_hotkeys()
        self.library_changed.emit()
        return sound

    def add_category(self, name: str) -> None:
        self.library.add_category(name)
        self.schedule_save()
        self.library_changed.emit()

    def rename_category(self, category_id: str, name: str) -> None:
        self.library.rename_category(category_id, name)
        self.schedule_save()
        self.library_changed.emit()

    def remove_category(self, category_id: str) -> None:
        self.library.remove_category(category_id)
        self.schedule_save()
        self.library_changed.emit()

    def play(self, key: str, preview: bool = False) -> bool:
        sound = self.library.find_sound(key)
        if sound is None:
            self.log(f"Unknown sound {key}")
            return False
        if sound.duration_ms <= 0:
            sound.duration_ms = probe_duration_ms(sound.path)
            self.schedule_save()
        ok = self.player.play(sound, preview=preview, cable_up=self.cable.is_up())
        if not ok:
            self.log(f"Could not play {sound.name}")
        return ok

    def stop_all(self) -> None:
        self.player.stop_all()

    def enable_cable(self, rebuild: bool = False) -> CableStatus:
        status = self.cable.enable(
            mic_source=str(self._settings.get("mic_source") or ""),
            set_default_mic=bool(self._settings.get("set_default_mic", False)),
            mix_mic=bool(self._settings.get("mix_mic", True)),
            rebuild=rebuild,
        )
        self.cable_changed.emit()
        if status.error:
            self.log(status.error)
        return status

    def disable_cable(self) -> CableStatus:
        status = self.cable.disable()
        self.cable_changed.emit()
        return status

    def set_cable(self, enabled: bool) -> CableStatus:
        return self.enable_cable() if enabled else self.disable_cable()

    def toggle_cable(self) -> CableStatus:
        return self.set_cable(not self.cable.is_up())

    def cable_status(self) -> CableStatus:
        return self.cable.status(
            str(self._settings.get("mic_source") or ""),
            mix_mic=bool(self._settings.get("mix_mic", True)),
        )

    def public_status(self) -> dict[str, Any]:
        cable = self.cable_status()
        playing = self.player.playing()
        return {
            "ok": True,
            "app": "bloop",
            "version": __version__,
            "playing": playing,
            "now_playing": playing[0]["name"] if playing else "",
            "volume": self.player.master_volume,
            "hear_locally": self.player.hear_locally,
            "send_to_voice": self.player.send_to_voice,
            "overlap": self.player.overlap,
            "cable": {
                "enabled": cable.enabled,
                "healthy": cable.healthy,
                "sink": cable.sink,
                "mic": cable.mic,
                "error": cable.error,
                "mix_mic": bool(self._settings.get("mix_mic", True)),
            },
        }

    def handle_ipc(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if path in {"/", "/v1/health", "/v1/status"} and method == "GET":
            return self.public_status()
        if path == "/v1/library" and method == "GET":
            data = self.library.public_payload()
            data["ok"] = True
            return data
        if path == "/v1/sounds" and method == "GET":
            return {"ok": True, "sounds": self.library.public_payload()["sounds"]}
        if path == "/v1/play" and method == "POST":
            if payload.get("random"):
                category = str(payload.get("category_id") or "all")
                pool = self.library.sounds_in(category)
                if not pool:
                    return {"ok": False, "error": "no sounds", **self.public_status()}
                sound = random.choice(pool)
                ok = self.play(sound.id, preview=bool(payload.get("preview")))
                data = self.public_status()
                data["ok"] = ok
                data["error"] = "" if ok else "play failed"
                return data
            key = str(payload.get("id") or payload.get("name") or "")
            preview = bool(payload.get("preview"))
            ok = self.play(key, preview=preview)
            data = self.public_status()
            data["ok"] = ok
            data["error"] = "" if ok else "play failed"
            return data
        if path == "/v1/stop" and method == "POST":
            sound_id = str(payload.get("id") or "")
            if sound_id:
                self.player.stop_sound(sound_id)
            else:
                self.stop_all()
            return self.public_status()
        if path == "/v1/cable" and method == "POST":
            if "enabled" in payload:
                self.set_cable(bool(payload.get("enabled")))
            else:
                self.toggle_cable()
            return self.public_status()
        if path == "/v1/volume" and method == "POST":
            current = self.player.master_volume
            if "step" in payload:
                level = current + int(payload.get("step") or 0)
            else:
                level = int(payload.get("level", current))
            self.update_settings(master_volume=max(0, min(150, level)))
            return self.public_status()
        if path == "/v1/raise" and method == "POST":
            return {"ok": True, "raise": True, **self.public_status()}
        return {"ok": False, "error": f"unknown {method} {path}"}

    def shutdown(self) -> None:
        self.player.stop_all()
        self.library.save()
        if not self._settings.get("keep_cable", True):
            self.cable.disable()
