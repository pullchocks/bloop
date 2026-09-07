from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Qt, Signal, Slot

from bloop.core.store import ipc_path, save_json

Handler = Callable[[str, str, dict[str, Any]], dict[str, Any]]


class IpcServer(QObject):
    _requested = Signal(object)

    def __init__(self, handler: Handler, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._handler = handler
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 17380
        self.url = f"http://127.0.0.1:{self.port}"
        self._requested.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    def start(self, preferred: int = 17380) -> str:
        last_error = ""
        for port in [preferred, *range(17381, 17390)]:
            try:
                httpd = ThreadingHTTPServer(("127.0.0.1", port), self._make_handler())
            except OSError as exc:
                last_error = str(exc)
                continue
            self._httpd = httpd
            self.port = port
            self.url = f"http://127.0.0.1:{port}"
            self._thread = threading.Thread(target=httpd.serve_forever, name="bloop-ipc", daemon=True)
            self._thread.start()
            save_json(ipc_path(), {"port": port, "url": self.url})
            return self.url
        raise RuntimeError(f"Could not bind Bloop IPC server ({last_error})")

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def invoke(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        box: dict[str, Any] = {"event": threading.Event(), "data": None}
        self._requested.emit((method, path, payload, box))
        if not box["event"].wait(8):
            return {"ok": False, "error": "timeout"}
        return box.get("data") or {"ok": False, "error": "empty"}

    @Slot(object)
    def _dispatch(self, job: object) -> None:
        method, path, payload, box = job  # type: ignore[misc]
        try:
            box["data"] = self._handler(method, path, payload)
        except Exception as exc:
            box["data"] = {"ok": False, "error": str(exc)}
        box["event"].set()

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class HandlerImpl(BaseHTTPRequestHandler):
            def log_message(self, _fmt: str, *_args: Any) -> None:
                return

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw.decode() or "{}")
                except json.JSONDecodeError:
                    return {}
                return data if isinstance(data, dict) else {}

            def _send(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                result = server.invoke("GET", path, {})
                self._send(200 if result.get("ok", True) else 400, result)

            def do_POST(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                result = server.invoke("POST", path, self._read_json())
                self._send(200 if result.get("ok", True) else 400, result)

        return HandlerImpl
