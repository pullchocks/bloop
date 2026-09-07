from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
)

from bloop.core.controller import Controller
from bloop.ui.theme import ColorSwatch, DEFAULT_ACCENT, DEFAULT_TEXT


class SettingsDialog(QDialog):
    def __init__(self, controller: Controller, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Settings")
        self.setModal(False)
        self.setMinimumWidth(480)
        self.setMinimumHeight(420)
        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._playback_page(), "Playback")
        tabs.addTab(self._cable_page(), "AV Cable")
        tabs.addTab(self._appearance_page(), "Appearance")
        outer.addWidget(tabs, 1)
        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(close)
        outer.addLayout(row)
        self._sync()
        controller.settings_changed.connect(self._sync)
        controller.cable_changed.connect(self._sync_cable)

    def _playback_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        self.hear = QCheckBox("Play on headphones / speakers")
        self.hear.toggled.connect(lambda v: self.controller.update_settings(hear_locally=v))
        self.voice = QCheckBox("Send to Bloop Cable (voice chat)")
        self.voice.toggled.connect(lambda v: self.controller.update_settings(send_to_voice=v))
        self.overlap = QComboBox()
        self.overlap.addItem("Overlap (stack sounds)", "overlap")
        self.overlap.addItem("Replace (stop others first)", "replace")
        self.overlap.addItem("Toggle (press again to stop)", "toggle")
        self.overlap.currentIndexChanged.connect(
            lambda: self.controller.update_settings(overlap=self.overlap.currentData())
        )
        self.copy_files = QCheckBox("Copy imported files into the Bloop library")
        self.copy_files.toggled.connect(lambda v: self.controller.update_settings(copy_imports=v))
        self.headphones = QComboBox()
        self.headphones.currentIndexChanged.connect(self._save_headphones)
        refresh = QPushButton("Refresh devices")
        refresh.clicked.connect(self._fill_devices)
        layout.addRow(self.hear)
        layout.addRow(self.voice)
        layout.addRow("When playing", self.overlap)
        layout.addRow("Headphones", self.headphones)
        layout.addRow("", refresh)
        layout.addRow(self.copy_files)
        return page

    def _cable_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        hint = QLabel(
            "Bloop creates a virtual cable and a mixed microphone. In Discord / "
            "voice chat, set the input device to Bloop Mic. Your real mic still "
            "talks; board sounds are mixed in."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        self.cable_on_start = QCheckBox("Enable cable when Bloop starts")
        self.cable_on_start.toggled.connect(lambda v: self.controller.update_settings(cable_on_start=v))
        self.keep_cable = QCheckBox("Leave cable running after quit")
        self.keep_cable.toggled.connect(lambda v: self.controller.update_settings(keep_cable=v))
        self.default_mic = QCheckBox("Set Bloop Mic as the system default input")
        self.default_mic.toggled.connect(lambda v: self.controller.update_settings(set_default_mic=v))
        self.mic = QComboBox()
        self.mic.currentIndexChanged.connect(self._save_mic)
        enable = QPushButton("Enable cable")
        enable.setObjectName("accent")
        enable.clicked.connect(self.controller.enable_cable)
        disable = QPushButton("Disable cable")
        disable.clicked.connect(self.controller.disable_cable)
        row = QHBoxLayout()
        row.addWidget(enable)
        row.addWidget(disable)
        wrap = QWidget()
        wrap.setLayout(row)
        self.cable_status = QLabel("")
        self.cable_status.setObjectName("hint")
        self.cable_status.setWordWrap(True)
        layout.addRow(hint)
        layout.addRow(self.cable_on_start)
        layout.addRow(self.keep_cable)
        layout.addRow(self.default_mic)
        layout.addRow("Talk mic", self.mic)
        layout.addRow(wrap)
        layout.addRow(self.cable_status)
        return page

    def _appearance_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        scheme_row = QHBoxLayout()
        self.theme_color = ColorSwatch(allow_reset=True, fallback="accent")
        self.theme_color.color_changed.connect(
            lambda color: self.controller.update_settings(accent=color or DEFAULT_ACCENT)
        )
        scheme_row.addWidget(self.theme_color)
        scheme_row.addStretch()
        scheme_wrap = QWidget()
        scheme_wrap.setLayout(scheme_row)
        text_row = QHBoxLayout()
        self.theme_text = ColorSwatch(allow_reset=True, fallback="text")
        self.theme_text.color_changed.connect(
            lambda color: self.controller.update_settings(text=color or DEFAULT_TEXT)
        )
        text_row.addWidget(self.theme_text)
        text_row.addStretch()
        text_wrap = QWidget()
        text_wrap.setLayout(text_row)
        layout.addRow("Scheme", scheme_wrap)
        layout.addRow("Text", text_wrap)
        return page

    def _fill_devices(self) -> None:
        settings = self.controller.settings()
        self.headphones.blockSignals(True)
        self.headphones.clear()
        self.headphones.addItem("System default", "")
        for name, desc in self.controller.cable.real_sinks():
            self.headphones.addItem(desc, name)
        index = self.headphones.findData(settings.get("headphones") or "")
        self.headphones.setCurrentIndex(index if index >= 0 else 0)
        self.headphones.blockSignals(False)

        self.mic.blockSignals(True)
        self.mic.clear()
        self.mic.addItem("System default mic", "")
        for name, desc in self.controller.cable.real_sources():
            self.mic.addItem(desc, name)
        index = self.mic.findData(settings.get("mic_source") or "")
        self.mic.setCurrentIndex(index if index >= 0 else 0)
        self.mic.blockSignals(False)

    def _save_headphones(self) -> None:
        self.controller.update_settings(headphones=self.headphones.currentData() or "")

    def _save_mic(self) -> None:
        self.controller.update_settings(mic_source=self.mic.currentData() or "")

    def _sync_cable(self) -> None:
        status = self.controller.cable_status()
        if status.enabled and status.healthy:
            text = "Cable is on. Voice apps should use input “Bloop Mic”."
        elif status.enabled:
            text = status.error or "Cable is on, but something looks off."
        else:
            text = status.error or "Cable is off. Enable it to inject sounds into voice chat."
        self.cable_status.setText(text)

    def _sync(self) -> None:
        settings = self.controller.settings()
        for box, key, default in (
            (self.hear, "hear_locally", True),
            (self.voice, "send_to_voice", True),
            (self.copy_files, "copy_imports", False),
            (self.cable_on_start, "cable_on_start", True),
            (self.keep_cable, "keep_cable", True),
            (self.default_mic, "set_default_mic", False),
        ):
            box.blockSignals(True)
            box.setChecked(bool(settings.get(key, default)))
            box.blockSignals(False)
        self.overlap.blockSignals(True)
        index = self.overlap.findData(settings.get("overlap") or "overlap")
        self.overlap.setCurrentIndex(index if index >= 0 else 0)
        self.overlap.blockSignals(False)
        self.theme_color.set_color(str(settings.get("accent") or ""))
        self.theme_text.set_color(str(settings.get("text") or ""))
        self._fill_devices()
        self._sync_cable()
