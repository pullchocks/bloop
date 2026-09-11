from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bloop.core.controller import Controller
from bloop.core.library import UNCATEGORIZED
from bloop.core.player import format_duration
from bloop.ui.theme import C

COL_PLAY, COL_NAME, COL_DURATION, COL_HOTKEY = range(4)


class CategoryPane(QWidget):
    category_changed = Signal(str)

    def __init__(self, controller: Controller, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._emit)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.setSpacing(4)
        add = QPushButton("Add")
        add.setObjectName("flat")
        add.clicked.connect(self._add)
        rename = QPushButton("Rename")
        rename.setObjectName("flat")
        rename.clicked.connect(self._rename)
        remove = QPushButton("Delete")
        remove.setObjectName("flat")
        remove.clicked.connect(self._remove)
        for btn in (add, rename, remove):
            btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            btn.setMinimumWidth(btn.fontMetrics().horizontalAdvance(btn.text()) + 16)
        row.addWidget(add)
        row.addWidget(rename)
        row.addWidget(remove)
        layout.addLayout(row)
        self.rebuild()

    def current_id(self) -> str:
        item = self.list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "all") if item else "all"

    def rebuild(self) -> None:
        current = self.current_id()
        self.list.blockSignals(True)
        self.list.clear()
        rows = [("all", "All"), (UNCATEGORIZED, "Uncategorized")]
        rows.extend((cat.id, cat.name) for cat in self.controller.library.categories)
        chosen = None
        for ident, name in rows:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, ident)
            self.list.addItem(item)
            if ident == current:
                chosen = item
        self.list.setCurrentItem(chosen or self.list.item(0))
        self.list.blockSignals(False)

    def _emit(self) -> None:
        self.category_changed.emit(self.current_id())

    def _add(self) -> None:
        name, ok = QInputDialog.getText(self, "Category", "Name")
        if ok and name.strip():
            self.controller.add_category(name.strip())

    def _rename(self) -> None:
        ident = self.current_id()
        if ident in {"all", UNCATEGORIZED}:
            return
        cat = self.controller.library.find_category(ident)
        if cat is None:
            return
        name, ok = QInputDialog.getText(self, "Rename", "Name", text=cat.name)
        if ok and name.strip():
            self.controller.rename_category(ident, name.strip())

    def _remove(self) -> None:
        ident = self.current_id()
        if ident in {"all", UNCATEGORIZED}:
            return
        if QMessageBox.question(self, "Delete category", "Sounds stay in Uncategorized.") != QMessageBox.StandardButton.Yes:
            return
        self.controller.remove_category(ident)


class SoundTable(QTableWidget):
    play_requested = Signal(str, bool)
    selected = Signal(str)

    def __init__(self, controller: Controller, parent=None) -> None:
        super().__init__(0, 4, parent)
        self.controller = controller
        self.category_id = "all"
        self.query = ""
        self.setObjectName("panel")
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.setHorizontalHeaderLabels(["", "SOUND", "TIME", "HOTKEY"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(COL_PLAY, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_HOTKEY, QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().setDefaultSectionSize(36)
        self.setAcceptDrops(True)
        self.itemSelectionChanged.connect(self._emit_selected)
        self.cellDoubleClicked.connect(lambda *_: self._play(False))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def current_id(self) -> str:
        row = self.currentRow()
        if row < 0:
            return ""
        item = self.item(row, COL_NAME)
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def rebuild(self) -> None:
        current = self.current_id()
        sounds = self.controller.library.sounds_in(self.category_id)
        query = self.query.strip().lower()
        if query:
            sounds = [s for s in sounds if query in s.name.lower() or query in s.hotkey.lower()]
        playing = {item["id"] for item in self.controller.player.playing()}
        self.blockSignals(True)
        self.setRowCount(len(sounds))
        chosen = -1
        for row, sound in enumerate(sounds):
            mark = QTableWidgetItem("▶" if sound.id in playing else "")
            mark.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name = QTableWidgetItem(sound.name)
            name.setData(Qt.ItemDataRole.UserRole, sound.id)
            if not sound.exists():
                name.setForeground(C.danger)
                name.setToolTip("File missing: " + sound.path)
            duration = QTableWidgetItem(format_duration(sound.duration_ms))
            hotkey = QTableWidgetItem(sound.hotkey)
            for col, item in enumerate((mark, name, duration, hotkey)):
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.setItem(row, col, item)
            if sound.id == current:
                chosen = row
        self.blockSignals(False)
        if chosen >= 0:
            self.selectRow(chosen)
        elif sounds:
            self.selectRow(0)

    def _emit_selected(self) -> None:
        self.selected.emit(self.current_id())

    def _play(self, preview: bool) -> None:
        ident = self.current_id()
        if ident:
            self.play_requested.emit(ident, preview)

    def _menu(self, pos) -> None:
        ident = self.current_id()
        if not ident:
            return
        menu = QMenu(self)
        play = QAction("Play", self)
        play.triggered.connect(lambda: self.play_requested.emit(ident, False))
        preview = QAction("Preview (speakers)", self)
        preview.triggered.connect(lambda: self.play_requested.emit(ident, True))
        stop = QAction("Stop this", self)
        stop.triggered.connect(lambda: self.controller.player.stop_sound(ident))
        delete = QAction("Delete", self)
        delete.triggered.connect(lambda: self.controller.remove_sound(ident))
        menu.addAction(play)
        menu.addAction(preview)
        menu.addAction(stop)
        menu.addSeparator()
        menu.addAction(delete)
        menu.exec(self.viewport().mapToGlobal(pos))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            from pathlib import Path

            cat = self.category_id if self.category_id not in {"all"} else UNCATEGORIZED
            self.controller.import_files([Path(p) for p in paths], category_id=cat)
        event.acceptProposedAction()

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self._play(False)
            return
        if event.key() == Qt.Key.Key_Space:
            self.controller.stop_all()
            return
        if event.matches(QKeySequence.StandardKey.Delete):
            ident = self.current_id()
            if ident:
                self.controller.remove_sound(ident)
            return
        super().keyPressEvent(event)
