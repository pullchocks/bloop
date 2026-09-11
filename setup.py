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


def _run(command: list[str], **kwargs) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True, **kwargs)


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
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="Write a login autostart entry (same as Settings → Start Bloop when I log in).",
    )
    parser.add_argument(
        "--no-autostart",
        action="store_true",
        help="Remove the login autostart entry if it exists.",
    )
    args = parser.parse_args(argv)

    if args.autostart and args.no_autostart:
        print("Use only one of --autostart or --no-autostart.", file=sys.stderr)
        return 2

    if os.geteuid() == 0:
        print("Do not run setup.py as root.", file=sys.stderr)
        return 1

    print(f"Installing Bloop from {ROOT}")
    install_deps()
    write_launcher()
    from bloop.core.desktop import set_autostart

    if args.autostart:
        path = set_autostart(True, ROOT)
        if path:
            print(f"wrote {path}")
        else:
            print("Could not write the login autostart entry.", file=sys.stderr)
    elif args.no_autostart:
        set_autostart(False, ROOT)
        print("Removed autostart.")
    else:
        print("Skipped autostart. Enable it later in Settings if you want Bloop at login.")
    check_audio()

    print()
    print("Done. Launch with:")
    print("  python3 run.py")
    print("Or open Bloop from the app menu.")
    print("Start at login is off unless you enable it in Settings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
