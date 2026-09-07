from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from bloop.core.controller import Controller
from bloop.core.desktop import DESKTOP_ID, install_launcher
from bloop.core.icons import application_icon
from bloop.core.ipc import IpcServer
from bloop.core.store import ipc_path, load_json
from bloop.ui.main_window import MainWindow
from bloop.ui.theme import apply_app_theme

_INSTANCE = "bloop-session"
DEFAULT_PORT = 17380


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _existing_url() -> str:
    data = load_json(ipc_path())
    url = str(data.get("url") or "")
    if url:
        return url
    port = int(data.get("port") or DEFAULT_PORT)
    return f"http://127.0.0.1:{port}"


def _http(method: str, path: str, payload: dict | None = None, timeout: float = 0.4) -> dict | None:
    url = _existing_url().rstrip("/") + path
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode() or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _handoff(argv: list[str]) -> bool:
    health = _http("GET", "/v1/health")
    if not health:
        socket = QLocalSocket()
        socket.connectToServer(_INSTANCE)
        if not socket.waitForConnected(150):
            return False
        socket.write(b"raise")
        socket.waitForBytesWritten(150)
        socket.flush()
        socket.disconnectFromServer()
        return True
    args = list(argv)
    if "--play" in args:
        index = args.index("--play")
        key = args[index + 1] if index + 1 < len(args) else ""
        _http("POST", "/v1/play", {"id": key}, timeout=2)
        return True
    if "--stop" in args:
        _http("POST", "/v1/stop", {}, timeout=2)
        return True
    if "--cable" in args:
        index = args.index("--cable")
        value = (args[index + 1] if index + 1 < len(args) else "toggle").lower()
        payload = {} if value == "toggle" else {"enabled": value in {"on", "1", "true"}}
        _http("POST", "/v1/cable", payload, timeout=2)
        return True
    _http("POST", "/v1/raise", {}, timeout=1)
    socket = QLocalSocket()
    socket.connectToServer(_INSTANCE)
    if socket.waitForConnected(150):
        socket.write(b"raise")
        socket.waitForBytesWritten(150)
        socket.flush()
        socket.disconnectFromServer()
    return True


def _listen(app: QApplication) -> QLocalServer:
    QLocalServer.removeServer(_INSTANCE)
    server = QLocalServer(app)
    server.listen(_INSTANCE)
    return server


def _parse_cli(argv: list[str]) -> tuple[list[str], dict]:
    start_in_tray = "--tray" in argv
    play = ""
    stop = False
    cable = None
    args = []
    skip = False
    for i, item in enumerate(argv):
        if skip:
            skip = False
            continue
        if item == "--tray":
            start_in_tray = True
        elif item == "--play" and i + 1 < len(argv):
            play = argv[i + 1]
            skip = True
        elif item == "--stop":
            stop = True
        elif item == "--cable" and i + 1 < len(argv):
            cable = argv[i + 1]
            skip = True
        else:
            args.append(item)
    return args, {"tray": start_in_tray, "play": play, "stop": stop, "cable": cable}


def main(argv: list[str] | None = None) -> int:
    raw = list(argv if argv is not None else sys.argv)
    argv, flags = _parse_cli(raw)
    argv = list(argv)
    argv[0] = DESKTOP_ID
    QGuiApplication.setDesktopFileName(DESKTOP_ID)
    app = QApplication(argv)
    app.setApplicationName(DESKTOP_ID)
    app.setOrganizationName("Bloop")
    app.setApplicationDisplayName("Bloop")
    app.setDesktopFileName(DESKTOP_ID)
    app.setQuitOnLastWindowClosed(False)
    if _handoff(raw[1:]):
        return 0
    install_launcher(_project_root())
    icon = application_icon()
    app.setWindowIcon(icon)
    server = _listen(app)

    controller = Controller()
    ipc = IpcServer(controller.handle_ipc, app)
    ipc.start(int(controller.settings().get("ipc_port") or DEFAULT_PORT))

    apply_app_theme(app)
    window = MainWindow(controller)
    server.newConnection.connect(window.handle_ipc_raise)

    original = controller.handle_ipc

    def wrapped(method: str, path: str, payload: dict) -> dict:
        result = original(method, path, payload)
        if path == "/v1/raise":
            window.handle_ipc_raise()
        return result

    ipc._handler = wrapped  # noqa: SLF001

    if flags["tray"]:
        window.hide()
        window.tray.show()
    else:
        window.show()

    if flags["play"]:
        controller.play(flags["play"])
    if flags["stop"]:
        controller.stop_all()
    if flags["cable"] is not None:
        value = str(flags["cable"]).lower()
        if value == "toggle":
            controller.toggle_cable()
        else:
            controller.set_cable(value in {"on", "1", "true"})

    code = app.exec()
    ipc.stop()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
