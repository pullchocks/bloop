#!/usr/bin/env python3
"""First-run installer for Bloop.

This is not a setuptools script. From the project root:

    python3 setup.py

Installs PySide6 into .venv, writes the app-menu launcher and icons for this
checkout, and optionally a login autostart entry.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
LAUNCHER = ROOT / "packaging" / "bloop"
APP_DESKTOP = Path.home() / ".local/share/applications/bloop.desktop"
AUTOSTART_DESKTOP = Path.home() / ".config/autostart/bloop.desktop"


def _run(command: list[str], **kwargs) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True, **kwargs)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path}")


def install_deps() -> None:
    VENV.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(VENV),
            "-r",
            str(ROOT / "requirements.txt"),
        ]
    )


def write_launcher() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(VENV))
    sys.path.insert(0, str(ROOT / "src"))
    from PySide6.QtGui import QGuiApplication

    from bloop.core.desktop import install_launcher

    _app = QGuiApplication.instance() or QGuiApplication(["bloop-setup"])
    LAUNCHER.chmod(LAUNCHER.stat().st_mode | 0o111)
    desktop = install_launcher(ROOT)
    if desktop is None:
        raise SystemExit("could not write the Bloop desktop launcher")
    print(f"wrote {desktop}")
    update = shutil.which("update-desktop-database")
    if update:
        subprocess.run([update, str(APP_DESKTOP.parent)], check=False)


def write_autostart() -> None:
    text = (ROOT / "packaging" / "bloop-autostart.desktop").read_text(encoding="utf-8")
    text = text.replace("@ROOT@", str(ROOT.resolve()))
    _write(AUTOSTART_DESKTOP, text)


def check_audio() -> None:
    missing = [name for name in ("pactl", "paplay") if not shutil.which(name)]
    if missing:
        print(
            "Missing audio tools: "
            + ", ".join(missing)
            + ". Install PipeWire (pipewire-pulse) or PulseAudio.",
            file=sys.stderr,
        )
    if not shutil.which("ffmpeg") and not shutil.which("mpv"):
        print(
            "Note: ffmpeg or mpv is needed for MP3 and other compressed formats.",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    leftover = {
        "build",
        "egg_info",
        "sdist",
        "bdist_wheel",
        "develop",
        "editable_wheel",
    }
    if argv and argv[0] in leftover:
        print(
            "setup.py is the Bloop first-run installer, not setuptools.\n"
            "Run: python3 setup.py\n"
            "The package metadata lives in pyproject.toml.",
            file=sys.stderr,
        )
        return 2

    parser = argparse.ArgumentParser(description="Install Bloop on this Linux machine.")
    parser.add_argument("--no-autostart", action="store_true", help="Skip the login autostart entry.")
    args = parser.parse_args(argv)

    if os.geteuid() == 0:
        print("Do not run setup.py as root.", file=sys.stderr)
        return 1

    print(f"Installing Bloop from {ROOT}")
    install_deps()
    write_launcher()
    if args.no_autostart:
        print("Skipped autostart.")
    else:
        write_autostart()
    check_audio()

    print()
    print("Done. Launch with:")
    print("  python3 run.py")
    print("Or open Bloop from the app menu. After login it starts in the tray.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
