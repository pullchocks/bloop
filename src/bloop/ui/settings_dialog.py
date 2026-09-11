from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
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
        self.setMinimumSize(520, 460)
        self.resize(560, 520)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)
        tabs = QTabWidget()
        tabs.addTab(self._general_page(), "General")
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

    def _general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.close_to_tray = QCheckBox("Keep Bloop in the tray when the window is closed")
        self.close_to_tray.setToolTip("The board and cable keep running. Quit from the tray menu to exit fully.")
        self.close_to_tray.toggled.connect(lambda v: self.controller.update_settings(close_to_tray=v))
        close_hint = QLabel("On by default. Turn this off if closing the window should quit Bloop.")
        close_hint.setObjectName("hint")
        close_hint.setWordWrap(True)
        self.start_on_login = QCheckBox("Start Bloop when I log in")
        self.start_on_login.setToolTip("Launch in the tray after login. Off by default.")
        self.start_on_login.toggled.connect(lambda v: self.controller.update_settings(start_on_login=v))
        start_hint = QLabel("Off by default. When on, Bloop starts hidden in the tray after you log in.")
        start_hint.setObjectName("hint")
        start_hint.setWordWrap(True)
        layout.addWidget(self.close_to_tray)
        layout.addWidget(close_hint)
        layout.addWidget(self.start_on_login)
        layout.addWidget(start_hint)
        layout.addStretch(1)
        return page

    def _playback_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setVerticalSpacing(10)
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
        self.normalize = QCheckBox("Even out clip loudness")
        self.normalize.setToolTip(
            "Boost quiet clips and turn down hot ones so they play at a similar level."
        )
        self.normalize.toggled.connect(self._save_normalize)
        self.loudness_target = QComboBox()
        self.loudness_target.addItem("Quieter", -22)
        self.loudness_target.addItem("Balanced", -18)
        self.loudness_target.addItem("Louder", -14)
        self.loudness_target.currentIndexChanged.connect(self._save_loudness_target)
        self.headphones = QComboBox()
        self.headphones.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.headphones.currentIndexChanged.connect(self._save_headphones)
        refresh = QPushButton("Refresh devices")
        refresh.clicked.connect(self._fill_devices)
        layout.addRow(self.hear)
        layout.addRow(self.voice)
        layout.addRow("When playing", self.overlap)
        layout.addRow(self.normalize)
        layout.addRow("Loudness target", self.loudness_target)
        layout.addRow("Headphones", self.headphones)
        layout.addRow("", refresh)
        layout.addRow(self.copy_files)
        return page

    def _cable_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        intro = QLabel(
            "Bloop Mic is the input Discord (and other voice apps) should use. "
            "Pick whether that input is just board sounds, or your real mic mixed with them."
        )
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        mode_box = QFrame()
        mode_box.setObjectName("panel")
        mode_l = QVBoxLayout(mode_box)
        mode_l.setContentsMargins(12, 10, 12, 10)
        mode_l.setSpacing(8)
        mode_title = QLabel("What Discord hears from Bloop Mic")
        mode_title.setStyleSheet("font-weight: 600;")
        self.mode_mix = QRadioButton("Voice + sounds")
        self.mode_mix.setToolTip("Your real microphone is mixed with board clips")
        mix_hint = QLabel("Your mic stays in the mix. People hear you talking and the board.")
        mix_hint.setObjectName("hint")
        mix_hint.setWordWrap(True)
        mix_hint.setContentsMargins(22, 0, 0, 6)
        self.mode_sounds = QRadioButton("Sounds only")
        self.mode_sounds.setToolTip("Board clips only. Your real mic is not sent through Bloop Mic.")
        sounds_hint = QLabel("Your real mic is left alone. Discord on Bloop Mic hears clips, not your voice.")
        sounds_hint.setObjectName("hint")
        sounds_hint.setWordWrap(True)
        sounds_hint.setContentsMargins(22, 0, 0, 0)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_mix)
        self.mode_group.addButton(self.mode_sounds)
        self.mode_mix.toggled.connect(self._save_mix_mode)
        mode_l.addWidget(mode_title)
        mode_l.addWidget(self.mode_mix)
        mode_l.addWidget(mix_hint)
        mode_l.addWidget(self.mode_sounds)
        mode_l.addWidget(sounds_hint)
        layout.addWidget(mode_box)

        self.mic_label = QLabel("Your microphone (mixed in)")
        self.mic = QComboBox()
        self.mic.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mic.currentIndexChanged.connect(self._save_mic)
        layout.addWidget(self.mic_label)
        layout.addWidget(self.mic)

        self.cable_on_start = QCheckBox("Turn the cable on when Bloop starts")
        self.cable_on_start.toggled.connect(lambda v: self.controller.update_settings(cable_on_start=v))
        self.keep_cable = QCheckBox("Leave the cable running after quit")
        self.keep_cable.toggled.connect(lambda v: self.controller.update_settings(keep_cable=v))
        self.default_mic = QCheckBox("Set Bloop Mic as the system default input")
        self.default_mic.toggled.connect(lambda v: self.controller.update_settings(set_default_mic=v))
        layout.addWidget(self.cable_on_start)
        layout.addWidget(self.keep_cable)
        layout.addWidget(self.default_mic)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        enable = QPushButton("Enable cable")
        enable.setObjectName("accent")
        enable.clicked.connect(self.controller.enable_cable)
        disable = QPushButton("Disable cable")
        disable.clicked.connect(self.controller.disable_cable)
        buttons.addWidget(enable, 1)
        buttons.addWidget(disable, 1)
        layout.addLayout(buttons)

        self.cable_status = QLabel("")
        self.cable_status.setObjectName("hint")
        self.cable_status.setWordWrap(True)
        layout.addWidget(self.cable_status)
        layout.addStretch(1)
        return page

    def _appearance_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setVerticalSpacing(10)
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

    def _save_normalize(self, on: bool) -> None:
        self.loudness_target.setEnabled(on)
        self.controller.update_settings(normalize_loudness=on)

    def _save_loudness_target(self) -> None:
        value = self.loudness_target.currentData()
        try:
            target = float(value)
        except (TypeError, ValueError):
            target = -18.0
        self.controller.update_settings(loudness_target=target)

    def _save_mic(self) -> None:
        self.controller.update_settings(mic_source=self.mic.currentData() or "")

    def _save_mix_mode(self) -> None:
        mix = self.mode_mix.isChecked()
        if bool(self.controller.settings().get("mix_mic", True)) == mix:
            return
        self.controller.update_settings(mix_mic=mix)

    def _sync_cable(self) -> None:
        status = self.controller.cable_status()
        mix = bool(self.controller.settings().get("mix_mic", True))
        if status.enabled and status.healthy:
            if mix:
                text = "Cable is on. Discord input: Bloop Mic (your voice + board sounds)."
            else:
                text = "Cable is on. Discord input: Bloop Mic (board sounds only; your mic is not mixed in)."
        elif status.enabled:
            text = status.error or "Cable is on, but something looks off."
        else:
            text = status.error or "Cable is off. Enable it to send sounds into voice chat."
        self.cable_status.setText(text)
        self.mic.setEnabled(mix)
        self.mic_label.setEnabled(mix)

    def _sync(self) -> None:
        settings = self.controller.settings()
        for box, key, default in (
            (self.hear, "hear_locally", True),
            (self.voice, "send_to_voice", True),
            (self.copy_files, "copy_imports", False),
            (self.normalize, "normalize_loudness", True),
            (self.close_to_tray, "close_to_tray", True),
            (self.start_on_login, "start_on_login", False),
            (self.cable_on_start, "cable_on_start", True),
            (self.keep_cable, "keep_cable", True),
            (self.default_mic, "set_default_mic", False),
        ):
            box.blockSignals(True)
            box.setChecked(bool(settings.get(key, default)))
            box.blockSignals(False)
        mix = bool(settings.get("mix_mic", True))
        self.mode_mix.blockSignals(True)
        self.mode_sounds.blockSignals(True)
        self.mode_mix.setChecked(mix)
        self.mode_sounds.setChecked(not mix)
        self.mode_mix.blockSignals(False)
        self.mode_sounds.blockSignals(False)
        self.overlap.blockSignals(True)
        index = self.overlap.findData(settings.get("overlap") or "overlap")
        self.overlap.setCurrentIndex(index if index >= 0 else 0)
        self.overlap.blockSignals(False)
        self.loudness_target.blockSignals(True)
        try:
            target = float(settings.get("loudness_target", -18))
        except (TypeError, ValueError):
            target = -18.0
        index = self.loudness_target.findData(int(round(target)))
        if index < 0:
            closest = min(
                range(self.loudness_target.count()),
                key=lambda i: abs(float(self.loudness_target.itemData(i)) - target),
            )
            index = closest
        self.loudness_target.setCurrentIndex(index if index >= 0 else 1)
        self.loudness_target.blockSignals(False)
        self.loudness_target.setEnabled(bool(settings.get("normalize_loudness", True)))
        self.theme_color.set_color(str(settings.get("accent") or ""))
        self.theme_text.set_color(str(settings.get("text") or ""))
        self._fill_devices()
        self._sync_cable()
