from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bloop.core.controller import Controller
from bloop.core.library import UNCATEGORIZED
from bloop.ui.theme import C


class SoundInspector(QWidget):
    def __init__(self, controller: Controller, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._sound_id = ""
        self._syncing = False
        self.setObjectName("panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        self.header = QLabel("Sound")
        self.header.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.empty = QLabel("Select a sound, or drop files onto the board.")
        self.empty.setObjectName("hint")
        self.empty.setWordWrap(True)
        self.form = QWidget()
        layout = QFormLayout(self.form)
        layout.setContentsMargins(0, 8, 0, 0)
        self.name = QLineEdit()
        self.name.editingFinished.connect(self._save)
        self.category = QComboBox()
        self.category.currentIndexChanged.connect(self._save)
        self.volume = QSpinBox()
        self.volume.setRange(0, 150)
        self.volume.setSuffix(" %")
        self.volume.valueChanged.connect(self._save)
        self.hotkey = QKeySequenceEdit()
        self.hotkey.editingFinished.connect(self._save)
        self.path = QLabel("")
        self.path.setObjectName("hint")
        self.path.setWordWrap(True)
        reveal = QPushButton("Show file")
        reveal.clicked.connect(self._reveal)
        play = QPushButton("Play")
        play.setObjectName("accent")
        play.clicked.connect(lambda: self.controller.play(self._sound_id))
        preview = QPushButton("Preview")
        preview.clicked.connect(lambda: self.controller.play(self._sound_id, preview=True))
        buttons = QHBoxLayout()
        buttons.addWidget(play)
        buttons.addWidget(preview)
        layout.addRow("Name", self.name)
        layout.addRow("Category", self.category)
        layout.addRow("Volume", self.volume)
        layout.addRow("Hotkey", self.hotkey)
        layout.addRow("File", self.path)
        layout.addRow("", reveal)
        layout.addRow(buttons)
        outer.addWidget(self.header)
        outer.addWidget(self.empty)
        outer.addWidget(self.form)
        outer.addStretch()
        self.show_sound("")

    def show_sound(self, sound_id: str) -> None:
        self._sound_id = sound_id
        sound = self.controller.library.find_sound(sound_id)
        self.empty.setVisible(sound is None)
        self.form.setVisible(sound is not None)
        if sound is None:
            self.header.setText("Sound")
            return
        self._syncing = True
        self.header.setText(sound.name)
        self.name.setText(sound.name)
        self._fill_categories(sound.category_id)
        self.volume.setValue(sound.volume)
        self.hotkey.setKeySequence(sound.hotkey)
        self.path.setText(sound.path)
        self.path.setStyleSheet(f"color: {C.danger};" if not sound.exists() else f"color: {C.muted};")
        self._syncing = False

    def _fill_categories(self, current: str) -> None:
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("Uncategorized", UNCATEGORIZED)
        for cat in self.controller.library.categories:
            self.category.addItem(cat.name, cat.id)
        index = self.category.findData(current)
        self.category.setCurrentIndex(index if index >= 0 else 0)
        self.category.blockSignals(False)

    def _save(self) -> None:
        if self._syncing or not self._sound_id:
            return
        self.controller.update_sound(
            self._sound_id,
            name=self.name.text().strip() or "Sound",
            category_id=self.category.currentData() or UNCATEGORIZED,
            volume=self.volume.value(),
            hotkey=self.hotkey.keySequence().toString(),
        )

    def _reveal(self) -> None:
        sound = self.controller.library.find_sound(self._sound_id)
        if sound is None:
            return
        path = Path(sound.path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent if path.exists() else path)))
