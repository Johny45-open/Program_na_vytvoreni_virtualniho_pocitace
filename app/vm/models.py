"""Datové modely virtuálních počítačů."""
from dataclasses import asdict, dataclass


def _safe_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in "._- ")
    safe = safe.strip().replace(" ", "_")
    return safe or "vm"


@dataclass
class VMSpec:
    name: str
    memory_mb: int = 1024
    cpus: int = 2
    disk_size_gb: int = 20
    iso: str = ""
    sound_enabled: bool = True
    sound_card: str = "intel-hda"
    # --- Audio/video latence (per-VM, konfigurovatelné v UI) ---
    audio_driver: str = "auto"  # auto|wasapi|dsound
    audio_timer_period: int = 5000  # µs (2000-10000)
    audio_latency_ms: int = 20  # ms (10-50)
    display_driver: str = "auto"  # auto|sdl|gtk|cocoa|none
    display_gl: bool = True
    display_vsync: bool = False

    @property
    def disk_file(self) -> str:
        return f"{_safe_filename(self.name)}.qcow2"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data):
        # zpětná kompatibilita: chybějící klíče -> default
        def _int(key, default):
            try:
                return int(data.get(key, default))
            except (ValueError, TypeError):
                return default

        def _str(key, default):
            v = data.get(key, default)
            return str(v) if v is not None else default

        def _bool(key, default):
            v = data.get(key, default)
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.lower() in ("1", "true", "yes", "on")
            return bool(v)

        return VMSpec(
            name=str(data.get("name", "")),
            memory_mb=_int("memory_mb", 1024),
            cpus=_int("cpus", 2),
            disk_size_gb=_int("disk_size_gb", 20),
            iso=_str("iso", ""),
            sound_enabled=_bool("sound_enabled", True),
            sound_card=_str("sound_card", "intel-hda"),
            audio_driver=_str("audio_driver", "auto"),
            audio_timer_period=_int("audio_timer_period", 5000),
            audio_latency_ms=_int("audio_latency_ms", 20),
            display_driver=_str("display_driver", "auto"),
            display_gl=_bool("display_gl", True),
            display_vsync=_bool("display_vsync", False),
        )