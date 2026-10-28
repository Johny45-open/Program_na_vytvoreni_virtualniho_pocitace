"""Základní konfigurace a cesty aplikace."""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE_DIR = os.path.join(PROJECT_ROOT, "firmware")
BIOS_PATH = os.path.join(FIRMWARE_DIR, "bios.bin")
VMS_DIR = os.path.join(PROJECT_ROOT, "vms")

QEMU_EXE = os.environ.get("QEMU", r"C:\Program Files\qemu\qemu-system-x86_64.exe")
QEMU_IMG = os.environ.get("QEMU_IMG", r"C:\Program Files\qemu\qemu-img.exe")

DEFAULT_MEMORY_MB = 1024
DEFAULT_CPUS = 2
DEFAULT_DISK_GB = 20

DEFAULT_AUDIO_DRIVER = "auto"
DEFAULT_AUDIO_TIMER_PERIOD = 5000
DEFAULT_AUDIO_LATENCY_MS = 20
DEFAULT_DISPLAY_DRIVER = "auto"

APP_NAME = "Vlastní BIOS"
