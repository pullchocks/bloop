"""Linux shell identity: WM class, .desktop file, and hicolor icons.

Without this, launching via ``python3 run.py`` makes GNOME / COSMIC show a
generic Python cog labeled "python3".
"""

from __future__ import annotations

from pathlib import Path

from bloop.core.icons import launcher_pixmap

DESKTOP_ID = "bloop"


def _home_applications() -> Path:
    path = Path.home() / ".local" / "share" / "applications"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _home_icon(size: int) -> Path:
    path = Path.home() / ".local" / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{DESKTOP_ID}.png"


def install_launcher(project_root: Path) -> Path | None:
    try:
        for size in (16, 22, 24, 32, 48, 64, 128, 256):
            launcher_pixmap(size).save(str(_home_icon(size)), "PNG")
        exec_path = (project_root / "packaging" / "bloop").resolve()
        desktop = _home_applications() / f"{DESKTOP_ID}.desktop"
        desktop.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    "Version=1.0",
                    "Name=Bloop",
                    "Comment=Soundboard with a native virtual audio cable",
                    f"Exec={exec_path}",
                    f"Path={project_root.resolve()}",
                    f"Icon={DESKTOP_ID}",
                    "Terminal=false",
                    "Categories=AudioVideo;Audio;",
                    "StartupNotify=true",
                    f"StartupWMClass={DESKTOP_ID}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return desktop
    except OSError:
        return None
