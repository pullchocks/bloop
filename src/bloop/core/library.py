from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from bloop.core.store import library_path, load_json, save_json, sounds_dir

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac", ".opus", ".wma"}
UNCATEGORIZED = "uncategorized"


def _uid() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Category:
    id: str
    name: str

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "Category":
        return cls(id=str(data.get("id") or _uid()), name=str(data.get("name") or "Category"))


@dataclass
class Sound:
    id: str
    name: str
    path: str
    category_id: str = UNCATEGORIZED
    volume: int = 100
    hotkey: str = ""
    duration_ms: int = 0

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "Sound":
        volume = int(data.get("volume") or 100)
        volume = max(0, min(150, volume))
        return cls(
            id=str(data.get("id") or _uid()),
            name=str(data.get("name") or "Sound"),
            path=str(data.get("path") or ""),
            category_id=str(data.get("category_id") or UNCATEGORIZED),
            volume=volume,
            hotkey=str(data.get("hotkey") or ""),
            duration_ms=int(data.get("duration_ms") or 0),
        )

    def exists(self) -> bool:
        return bool(self.path) and Path(self.path).is_file()


@dataclass
class Library:
    categories: list[Category] = field(default_factory=list)
    sounds: list[Sound] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "categories": [item.to_json() for item in self.categories],
            "sounds": [item.to_json() for item in self.sounds],
        }

    @classmethod
    def from_json(cls, data: dict) -> "Library":
        cats = [Category.from_json(row) for row in data.get("categories") or [] if isinstance(row, dict)]
        sounds = [Sound.from_json(row) for row in data.get("sounds") or [] if isinstance(row, dict)]
        return cls(categories=cats, sounds=sounds)

    @classmethod
    def load(cls) -> "Library":
        return cls.from_json(load_json(library_path()))

    def save(self) -> None:
        save_json(library_path(), self.to_json())

    def find_sound(self, key: str) -> Sound | None:
        key = (key or "").strip()
        if not key:
            return None
        lowered = key.lower()
        for sound in self.sounds:
            if sound.id == key:
                return sound
        for sound in self.sounds:
            if sound.name.lower() == lowered:
                return sound
        return None

    def find_category(self, category_id: str) -> Category | None:
        for category in self.categories:
            if category.id == category_id:
                return category
        return None

    def add_category(self, name: str) -> Category:
        category = Category(id=_uid(), name=name.strip() or "Category")
        self.categories.append(category)
        return category

    def rename_category(self, category_id: str, name: str) -> None:
        category = self.find_category(category_id)
        if category is None:
            return
        category.name = name.strip() or category.name

    def remove_category(self, category_id: str) -> None:
        self.categories = [item for item in self.categories if item.id != category_id]
        for sound in self.sounds:
            if sound.category_id == category_id:
                sound.category_id = UNCATEGORIZED

    def add_sound(self, path: str | Path, category_id: str = UNCATEGORIZED, copy: bool = False) -> Sound | None:
        source = Path(path).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in AUDIO_EXTS:
            return None
        dest = source
        if copy:
            dest = sounds_dir() / source.name
            stem, suffix = dest.stem, dest.suffix
            n = 2
            while dest.exists():
                dest = sounds_dir() / f"{stem}-{n}{suffix}"
                n += 1
            dest.write_bytes(source.read_bytes())
        sound = Sound(
            id=_uid(),
            name=source.stem,
            path=str(dest),
            category_id=category_id if self.find_category(category_id) or category_id == UNCATEGORIZED else UNCATEGORIZED,
        )
        self.sounds.append(sound)
        return sound

    def import_paths(self, paths: list[Path], category_id: str = UNCATEGORIZED, copy: bool = False) -> list[Sound]:
        added: list[Sound] = []
        for path in paths:
            if path.is_dir():
                files = sorted(
                    child
                    for child in path.rglob("*")
                    if child.is_file() and child.suffix.lower() in AUDIO_EXTS
                )
            else:
                files = [path]
            for file in files:
                sound = self.add_sound(file, category_id=category_id, copy=copy)
                if sound:
                    added.append(sound)
        return added

    def remove_sound(self, sound_id: str) -> None:
        self.sounds = [item for item in self.sounds if item.id != sound_id]

    def sounds_in(self, category_id: str | None) -> list[Sound]:
        if not category_id or category_id == "all":
            return list(self.sounds)
        return [item for item in self.sounds if item.category_id == category_id]

    def public_payload(self) -> dict:
        return {
            "categories": [
                {"id": "all", "name": "All"},
                {"id": UNCATEGORIZED, "name": "Uncategorized"},
                *[item.to_json() for item in self.categories],
            ],
            "sounds": [item.to_json() for item in self.sounds],
        }
