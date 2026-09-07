"""Native virtual audio cable via PulseAudio / PipeWire-pulse.

Creates a VB-Cable style graph:

* ``bloop_cable`` — virtual playback sink (sounds are played here)
* ``bloop_mix`` — mix of the real microphone + the cable monitor
* ``bloop_mic`` — virtual capture source for Discord / voice chat

Voice apps pick **Bloop Mic** as their input. The user still talks on their
real mic; Bloop injects board sounds into the same stream.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from bloop.core import pulse
from bloop.core.store import cable_state_path, load_json, save_json

CABLE_SINK = "bloop_cable"
MIX_SINK = "bloop_mix"
MIC_SOURCE = "bloop_mic"
VIRTUAL_NAMES = {CABLE_SINK, MIX_SINK, MIC_SOURCE, f"{CABLE_SINK}.monitor", f"{MIX_SINK}.monitor"}


@dataclass
class CableStatus:
    enabled: bool = False
    healthy: bool = False
    sink: str = CABLE_SINK
    mic: str = MIC_SOURCE
    mix: str = MIX_SINK
    error: str = ""
    mic_source: str = ""


@dataclass
class CableManager:
    module_ids: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        raw = load_json(cable_state_path())
        self.module_ids = [int(item) for item in raw.get("modules") or [] if str(item).isdigit()]

    def _persist(self) -> None:
        save_json(cable_state_path(), {"modules": self.module_ids})

    def is_up(self) -> bool:
        return pulse.sink_exists(CABLE_SINK) and pulse.source_exists(MIC_SOURCE)

    def status(self, mic_source: str = "") -> CableStatus:
        enabled = self.is_up()
        error = ""
        if enabled and mic_source and not pulse.source_exists(mic_source):
            error = "Configured microphone is missing"
        elif not pulse.pactl("info")[1] and not enabled:
            error = "PulseAudio / PipeWire is not available"
        return CableStatus(
            enabled=enabled,
            healthy=enabled and not error,
            error=error,
            mic_source=mic_source,
        )

    def real_sources(self) -> list[tuple[str, str]]:
        items = []
        for name, desc in pulse.list_sources():
            if name in VIRTUAL_NAMES or name.startswith("bloop_"):
                continue
            items.append((name, desc))
        return items

    def real_sinks(self) -> list[tuple[str, str]]:
        items = []
        for name, desc in pulse.list_sinks():
            if name in VIRTUAL_NAMES or name.startswith("bloop_"):
                continue
            items.append((name, desc))
        return items

    def resolve_mic(self, preferred: str = "") -> str:
        if preferred and preferred not in VIRTUAL_NAMES and pulse.source_exists(preferred):
            return preferred
        current = pulse.default_source()
        if current and current not in VIRTUAL_NAMES:
            return current
        sources = self.real_sources()
        return sources[0][0] if sources else ""

    def enable(self, mic_source: str = "", set_default_mic: bool = False) -> CableStatus:
        if self.is_up():
            status = self.status(mic_source)
            if set_default_mic:
                pulse.pactl("set-default-source", MIC_SOURCE)
            return status

        mic = self.resolve_mic(mic_source)
        loaded: list[int] = []

        cable = pulse.load_module(
            "module-null-sink",
            "sink_name=" + CABLE_SINK,
            "sink_properties=device.description=BloopCable",
            "rate=48000",
            "channels=2",
        )
        mix = pulse.load_module(
            "module-null-sink",
            "sink_name=" + MIX_SINK,
            "sink_properties=device.description=BloopMix",
            "rate=48000",
            "channels=2",
        )
        if cable:
            loaded.append(cable)
        if mix:
            loaded.append(mix)

        time.sleep(0.2)

        voice = pulse.load_module(
            "module-loopback",
            f"source={CABLE_SINK}.monitor",
            f"sink={MIX_SINK}",
            "latency_msec=1",
            "source_dont_move=true",
            "sink_dont_move=true",
            'sink_input_properties=media.name="Bloop Cable"',
        )
        if voice:
            loaded.append(voice)

        if mic:
            talk = pulse.load_module(
                "module-loopback",
                f"source={mic}",
                f"sink={MIX_SINK}",
                "latency_msec=20",
                "source_dont_move=true",
                "sink_dont_move=true",
                'sink_input_properties=media.name="Bloop Talk"',
            )
            if talk:
                loaded.append(talk)

        remap = pulse.load_module(
            "module-remap-source",
            f"master={MIX_SINK}.monitor",
            f"source_name={MIC_SOURCE}",
            "source_properties=device.description=BloopMic",
        )
        if remap is None:
            remap = pulse.load_module(
                "module-remap-source",
                f"master={MIX_SINK}.monitor",
                f"source_name={MIC_SOURCE}",
            )
        if remap:
            loaded.append(remap)

        self.module_ids = loaded
        self._persist()
        time.sleep(0.15)

        if not pulse.sink_exists(CABLE_SINK):
            return CableStatus(enabled=False, healthy=False, error="Could not create Bloop Cable sink", mic_source=mic)
        if not pulse.source_exists(MIC_SOURCE):
            return CableStatus(enabled=False, healthy=False, error="Could not create Bloop Mic source", mic_source=mic)

        if set_default_mic:
            pulse.pactl("set-default-source", MIC_SOURCE)

        return CableStatus(enabled=True, healthy=True, mic_source=mic)

    def disable(self) -> CableStatus:
        for module_id in list(self.module_ids):
            pulse.unload_module(module_id)
        self.module_ids = []
        self._persist()
        pulse.unload_matching(CABLE_SINK, MIX_SINK, MIC_SOURCE, "BloopCable", "BloopMix", "BloopMic")
        time.sleep(0.1)
        return self.status()

    def set_enabled(self, enabled: bool, mic_source: str = "", set_default_mic: bool = False) -> CableStatus:
        if enabled:
            return self.enable(mic_source=mic_source, set_default_mic=set_default_mic)
        return self.disable()
