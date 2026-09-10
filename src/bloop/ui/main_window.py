from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from bloop.core.controller import Controller
from bloop.core.icons import application_icon, tray_icon
from bloop.core.library import UNCATEGORIZED
from bloop.ui.inspector import SoundInspector
from bloop.ui.settings_dialog import SettingsDialog
from bloop.ui.sound_list import CategoryPane, SoundTable
from bloop.ui.theme import C, apply_app_theme


class MainWindow(QMainWindow):
    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Bloop")
        self.resize(1180, 760)
        self.setMinimumSize(800, 520)
        self._force_quit = False
        self._settings_dialog: SettingsDialog | None = None
        self.setWindowIcon(application_icon())
        self._setup_tray()

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(10)
        layout.addWidget(self._build_topbar())

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.hide()
        layout.addWidget(self.banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.categories = CategoryPane(controller)
        self.categories.setMinimumWidth(160)
        self.categories.setMaximumWidth(240)
        self.categories.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.table = SoundTable(controller)
        self.table.setMinimumWidth(280)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.inspector = SoundInspector(controller)
        inspector_scroll = QScrollArea()
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inspector_scroll.setWidget(self.inspector)
        inspector_scroll.setMinimumWidth(260)
        inspector_scroll.setMaximumWidth(360)
        inspector_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self.categories)
        splitter.addWidget(self.table)
        splitter.addWidget(inspector_scroll)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([180, 680, 280])
        layout.addWidget(splitter, 1)

        status = QStatusBar()
        status.setSizeGripEnabled(False)
        self._status = QLabel("")
        status.addWidget(self._status, 1)
        self.setStatusBar(status)

        self.categories.category_changed.connect(self._category_changed)
        self.table.play_requested.connect(lambda sid, preview: controller.play(sid, preview=preview))
        self.table.selected.connect(self.inspector.show_sound)
        controller.library_changed.connect(self._refresh_library)
        controller.playback_changed.connect(self._refresh_playback)
        controller.cable_changed.connect(self._refresh_cable)
        controller.settings_changed.connect(self._on_theme)
        controller.log_message.connect(self._status.setText)

        self._bind_shortcuts()
        controller.bind_hotkeys(self)
        self._refresh_library()
        self._refresh_cable()
        self._refresh_playback()

    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 10, 14, 10)
        logo = QLabel("BLO")
        logo.setObjectName("logo")
        accent = QLabel("OP")
        accent.setObjectName("logoAccent")
        row.addWidget(logo)
        row.addWidget(accent)
        row.addSpacing(16)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search sounds")
        self.search.setMinimumWidth(160)
        self.search.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.search.textChanged.connect(self._search)
        row.addWidget(self.search, 1)
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._import)
        folder_btn = QPushButton("Folder")
        folder_btn.clicked.connect(self._import_folder)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self.controller.stop_all)
        self.cable_btn = QPushButton("Cable")
        self.cable_btn.setCheckable(True)
        self.cable_btn.clicked.connect(lambda: self.controller.set_cable(self.cable_btn.isChecked()))
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 150)
        self.vol.setFixedWidth(120)
        self.vol.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.vol.valueChanged.connect(lambda v: self.controller.update_settings(master_volume=v))
        self.vol_label = QLabel("100%")
        self.vol_label.setObjectName("muted")
        self.vol_label.setFixedWidth(40)
        settings = QPushButton("Settings")
        settings.clicked.connect(self._open_settings)
        row.addWidget(import_btn)
        row.addWidget(folder_btn)
        row.addWidget(self.stop_btn)
        row.addWidget(self.cable_btn)
        row.addWidget(self.vol)
        row.addWidget(self.vol_label)
        row.addWidget(settings)
        return bar

    def _bind_shortcuts(self) -> None:
        stop = QAction("Stop", self)
        stop.setShortcut(QKeySequence("Escape"))
        stop.triggered.connect(self.controller.stop_all)
        self.addAction(stop)
        import_act = QAction("Import", self)
        import_act.setShortcut(QKeySequence.StandardKey.Open)
        import_act.triggered.connect(self._import)
        self.addAction(import_act)

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(tray_icon(), self)
        self.tray.setToolTip("Bloop")
        menu = QMenu()
        show = QAction("Show Bloop", self)
        show.triggered.connect(self._show_from_tray)
        stop = QAction("Stop all", self)
        stop.triggered.connect(self.controller.stop_all)
        cable = QAction("Toggle cable", self)
        cable.triggered.connect(self.controller.toggle_cable)
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(show)
        menu.addAction(stop)
        menu.addAction(cable)
        menu.addSeparator()
        menu.addAction(quit_act)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._show_from_tray()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        self.tray.show()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self) -> None:
        self._force_quit = True
        self.controller.shutdown()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self._force_quit or not self.tray.isVisible():
            self.controller.shutdown()
            event.accept()
            return
        event.ignore()
        self.hide()

    def _search(self, text: str) -> None:
        self.table.query = text
        self.table.rebuild()

    def _category_changed(self, category_id: str) -> None:
        self.table.category_id = category_id
        self.table.rebuild()

    def _import(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import sounds",
            str(Path.home()),
            "Audio (*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.opus *.oga *.wma);;All files (*)",
        )
        if files:
            self._add_paths([Path(p) for p in files])

    def _import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Import folder", str(Path.home()))
        if folder:
            self._add_paths([Path(folder)])

    def _add_paths(self, paths: list[Path]) -> None:
        cat = self.categories.current_id()
        if cat == "all":
            cat = UNCATEGORIZED
        copy = bool(self.controller.settings().get("copy_imports"))
        count = self.controller.import_files(paths, category_id=cat, copy=copy)
        self._status.setText(f"Imported {count} sound{'s' if count != 1 else ''}")

    def _open_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self.controller, self)
        dialog = self._settings_dialog
        if dialog.width() < dialog.minimumWidth() or dialog.height() < dialog.minimumHeight():
            dialog.resize(max(dialog.width(), dialog.minimumWidth()), max(dialog.height(), dialog.minimumHeight()))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _on_theme(self) -> None:
        apply_app_theme()
        self.vol.blockSignals(True)
        self.vol.setValue(int(self.controller.settings().get("master_volume", 100)))
        self.vol.blockSignals(False)
        self.vol_label.setText(f"{self.vol.value()}%")

    def _refresh_library(self) -> None:
        current = self.table.current_id()
        self.categories.rebuild()
        self.table.rebuild()
        self.inspector.show_sound(current or self.table.current_id())

    def _refresh_playback(self) -> None:
        self.table.rebuild()
        playing = self.controller.player.playing()
        if playing:
            names = ", ".join(item["name"] for item in playing[:3])
            extra = "" if len(playing) <= 3 else f" +{len(playing) - 3}"
            self._status.setText(f"Playing {names}{extra}")
        self.vol.blockSignals(True)
        self.vol.setValue(self.controller.player.master_volume)
        self.vol.blockSignals(False)
        self.vol_label.setText(f"{self.controller.player.master_volume}%")

    def _refresh_cable(self) -> None:
        status = self.controller.cable_status()
        self.cable_btn.blockSignals(True)
        self.cable_btn.setChecked(status.enabled)
        self.cable_btn.blockSignals(False)
        if status.enabled and status.healthy:
            self.cable_btn.setText("Cable on")
            self.banner.hide()
        elif status.enabled:
            self.cable_btn.setText("Cable")
            self.banner.setText(status.error or "Cable is up but not healthy.")
            self.banner.setStyleSheet(
                f"background: #2a1a1a; color: {C.danger}; border: 1px solid #5a2a2a; "
                f"border-radius: 10px; padding: 8px 12px;"
            )
            self.banner.show()
        else:
            self.cable_btn.setText("Cable")
            if status.error:
                self.banner.setText(status.error)
                self.banner.setStyleSheet(
                    f"background: #2a1a1a; color: {C.danger}; border: 1px solid #5a2a2a; "
                    f"border-radius: 10px; padding: 8px 12px;"
                )
                self.banner.show()
            else:
                self.banner.hide()

    def handle_ipc_raise(self) -> None:
        self._show_from_tray()
