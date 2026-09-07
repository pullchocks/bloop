from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


def run_bin(name: str, *args: str, timeout: float = 4.0) -> tuple[int, str, str]:
    binary = shutil.which(name)
    if not binary:
        return 1, "", ""
    try:
        result = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, "", ""


def pactl(*args: str, timeout: float = 4.0) -> tuple[int, str]:
    code, out, _err = run_bin("pactl", *args, timeout=timeout)
    return code, out


def json_list(kind: str) -> list[dict[str, Any]]:
    code, out = pactl("--format=json", "list", kind)
    if code != 0 or not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def list_sinks() -> list[tuple[str, str]]:
    items = []
    for sink in json_list("sinks"):
        name = str(sink.get("name") or "")
        desc = str(sink.get("description") or name)
        if name:
            items.append((name, desc))
    return items


def list_sources(*, include_monitors: bool = False) -> list[tuple[str, str]]:
    items = []
    for source in json_list("sources"):
        name = str(source.get("name") or "")
        if not name:
            continue
        if not include_monitors and name.endswith(".monitor"):
            continue
        desc = str(source.get("description") or name)
        items.append((name, desc))
    return items


def default_sink() -> str:
    return pactl("get-default-sink")[1]


def default_source() -> str:
    return pactl("get-default-source")[1]


def sink_exists(name: str) -> bool:
    return any(ident == name for ident, _desc in list_sinks())


def source_exists(name: str) -> bool:
    return any(ident == name for ident, _desc in list_sources(include_monitors=True))


def load_module(name: str, *args: str) -> int | None:
    code, out = pactl("load-module", name, *args)
    if code != 0 or not out:
        return None
    try:
        return int(out.strip().split()[0])
    except ValueError:
        return None


def unload_module(module_id: int) -> bool:
    code, _ = pactl("unload-module", str(module_id))
    return code == 0


def modules() -> list[dict[str, Any]]:
    code, out = pactl("list", "short", "modules")
    if code == 0 and out:
        items: list[dict[str, Any]] = []
        for line in out.splitlines():
            parts = line.split("\t", 2)
            if len(parts) < 2:
                continue
            try:
                index = int(parts[0])
            except ValueError:
                continue
            items.append(
                {
                    "index": index,
                    "name": parts[1],
                    "argument": parts[2] if len(parts) > 2 else "",
                }
            )
        if items:
            return items
    rows = json_list("modules")
    items = []
    for module in rows:
        index = module.get("index", module.get("n"))
        try:
            index = int(index) if index is not None else None
        except (TypeError, ValueError):
            index = None
        items.append(
            {
                "index": index,
                "name": str(module.get("name") or ""),
                "argument": str(module.get("argument") or ""),
                "properties": module.get("properties") or {},
            }
        )
    if items:
        return items
    code, out = pactl("list", "modules")
    if code != 0 or not out:
        return []
    parsed: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("Module #"):
            if current:
                parsed.append(current)
            try:
                current = {"index": int(stripped.split("#", 1)[1]), "argument": "", "name": ""}
            except ValueError:
                current = {"argument": "", "name": ""}
        elif stripped.lower().startswith("argument:") and current:
            current["argument"] = stripped.split(":", 1)[1].strip()
        elif stripped.lower().startswith("name:") and current:
            current["name"] = stripped.split(":", 1)[1].strip()
    if current:
        parsed.append(current)
    return parsed


def unload_matching(*needles: str) -> None:
    for module in modules():
        blob = " ".join(
            str(module.get(key) or "")
            for key in ("name", "argument", "n", "properties")
        )
        if any(needle in blob for needle in needles):
            index = module.get("index")
            if index is None and isinstance(module.get("n"), int):
                index = module.get("n")
            try:
                unload_module(int(index))
            except (TypeError, ValueError):
                continue
