# Bloop

A Linux Soundpad: a soundboard that plays clips on your headphones **and** into voice chat through a native virtual cable (PipeWire / PulseAudio). PopStream talks to it the way a Stream Deck talks to Soundpad.

## Supported platforms

Bloop is a **Linux** app (not Windows or macOS). It needs:

- Python 3.10+ and PySide6
- PipeWire (with the Pulse compatibility layer) or PulseAudio, including `pactl` and `paplay`

The virtual cable uses Pulse/PipeWire modules (`module-null-sink`, `module-loopback`, `module-remap-source`). The `.desktop` launcher and tray icon follow the freedesktop StatusNotifier / app-menu specs (GNOME, COSMIC, KDE, Hyprland, and similar).

## Requirements

Install these on the host first. `setup.py` installs PySide6 into `.venv`; it does **not** install Python for you.

- Linux (see above)
- **Python 3.10+** (`python3 --version`), from your distro packages
- [PySide6](https://pypi.org/project/PySide6/) 6.5+ (pulled into `.venv` by setup)
- `pactl` and `paplay` (PipeWire-pulse or PulseAudio)

Optional:

- [`ffmpeg`](https://ffmpeg.org/) or [`mpv`](https://mpv.io/): MP3, M4A, AAC, Opus, and other compressed formats (WAV / FLAC / OGG play through `paplay` alone)
- **PopStream**: Stream Deck keys for the board

## Install

From this directory:

```bash
python3 setup.py
```

That is the first-run installer (not setuptools; package metadata is in `pyproject.toml`). It:

- installs PySide6 into `.venv`
- writes the app-menu launcher and icons for **this checkout**
- writes a login autostart entry so Bloop starts in the tray

Then:

```bash
python3 run.py
```

Or open **Bloop** from the app menu. After login it starts hidden in the tray. Look for the tray icon, or launch again to raise the window (or to play / stop / toggle the cable if you pass those flags). Closing the window hides to the tray so the board and cable keep working. Quit from the tray menu.

Skip the login entry if you prefer:

```bash
python3 setup.py --no-autostart
```

`run.py` also uses a sibling `../popstream/.venv` if this folder has no local install yet.

## Use

- **Import** / **Folder**: add clips (`mp3`, `wav`, `ogg`, `flac`, `m4a`, `aac`, `opus`, `wma`). Drag-and-drop onto the table also works.
- **Categories** on the left group the library. Sounds stay in Uncategorized if you delete a category.
- **Double-click** a row (or Enter) to play. Space or **Stop** / Escape stops everything. Delete removes the selected clip.
- Right-click a row for Play, Preview (speakers only), Stop this, Delete.
- Select a sound to set its name, category, volume, and in-app hotkey in the inspector.
- The top-bar slider is master volume. **Cable** toggles the virtual mic mix.

Settings:

- Play on headphones / speakers
- Send to Bloop Cable (voice chat)
- Overlap, replace, or toggle when a new clip starts
- Copy imported files into the Bloop library (otherwise paths are referenced in place)
- Enable cable on launch, leave it running after quit, optionally set Bloop Mic as the system default input
- **Voice + sounds** or **Sounds only** for what Discord hears from Bloop Mic

## AV Cable

**Cable** in the top bar (on by default at launch) builds a VB-Cable-style graph:

| Device | Role |
| --- | --- |
| **Bloop Cable** | Virtual playback sink. Board sounds are played here. |
| **Bloop Mix** | Mix of board sounds, plus your real mic if Voice + sounds is on. |
| **Bloop Mic** | Virtual capture source for Discord / voice apps. |

In Discord (or any chat app), set the **input device** to **Bloop Mic**.

Settings → AV Cable has two modes:

- **Voice + sounds** — your real mic is mixed with board clips. People hear you talking and the board.
- **Sounds only** — board clips only. Your real mic is not sent through Bloop Mic.

Pick the talk mic under Settings → AV Cable when mixing. Bloop will not loop its own virtual devices back into the mix.

## PopStream

PopStream ships a builtin **Bloop** plugin (same pattern as Clock / Audio). Start Bloop first. Drag actions from the **Bloop** group onto keys:

| Action | What it does |
| --- | --- |
| Play Sound | Play a clip from the Bloop library |
| Play / Stop | Start that clip; press again to stop it |
| Stop All | Stop every playing sound |
| Play Random | Random clip from a category |
| Volume | Live master volume; press to mute / unmute |
| Volume Up / Down | Step the master volume |
| Cable | Toggle the virtual cable / Bloop Mic |
| Now Playing | Live clip name; press to stop |

The plugin reads `~/.local/share/Bloop/ipc.json`, or `BLOOP_URL`.

## Autostart

`setup.py` writes `~/.config/autostart/bloop.desktop` (Exec: `packaging/bloop --tray`). Remove that file, or pass `--no-autostart` on setup, to stop launching at login.

## CLI

```bash
python3 run.py --play bruh
python3 run.py --stop
python3 run.py --cable on
python3 run.py --cable off
python3 run.py --cable toggle
python3 run.py --tray
```

`--play` accepts a sound id or name.

## HTTP API

Local JSON on `127.0.0.1:17380` (port is written to `ipc.json` if that bind is taken).

| Method | Path | Body |
| --- | --- | --- |
| GET | `/v1/health`, `/v1/status` | (none) |
| GET | `/v1/library`, `/v1/sounds` | (none) |
| POST | `/v1/play` | `{"id": "..."}` or `{"name": "..."}`; optional `preview`, `random`, `category_id` |
| POST | `/v1/stop` | `{}` or `{"id": "..."}` |
| POST | `/v1/cable` | `{}` to toggle, or `{"enabled": true}` |
| POST | `/v1/volume` | `{"level": 80}` or `{"step": 5}` |
| POST | `/v1/raise` | (none) |

## Data

Library, settings, and IPC live under `~/.local/share/Bloop/` (`library.json`, `settings.json`, `ipc.json`). Imported copies go in `sounds/` when that option is on.
