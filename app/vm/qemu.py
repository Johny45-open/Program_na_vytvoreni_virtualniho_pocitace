"""Spouštění QEMU: fáze 1 (vlastní BIOS), fáze 2 (SeaBIOS) a nástroje."""
import os
import socket
import subprocess
import time

from ..config import BIOS_PATH, QEMU_EXE, QEMU_IMG, VMS_DIR
from .qmp import QMPClient

BOOT_DISK = 0
BOOT_CDROM = 1
BOOT_NETWORK = 2

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# Cache pro detekci QEMU schopností (aby se nespouštěl help při každém startu)
_AUDIO_HELP_CACHE = None
_DISPLAY_HELP_CACHE = None
_ACCEL_HELP_CACHE = None


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ensure_disk(vm):
    """Vytvoří disk qcow2, pokud ještě neexistuje. Vrací cestu."""
    path = os.path.join(VMS_DIR, vm.disk_file)
    if os.path.exists(path):
        return path
    cmd = [QEMU_IMG, "create", "-f", "qcow2", path, f"{vm.disk_size_gb}G"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, creationflags=_NO_WINDOW
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return path


def _clamp(value, lo, hi, default):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _run_qemu_help(args):
    """Spustí QEMU s help argumenty, vrátí stdout+stderr jako text nebo '' při chybě."""
    try:
        if not os.path.exists(QEMU_EXE):
            return ""
        result = subprocess.run(
            [QEMU_EXE] + args,
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=_NO_WINDOW,
        )
        return (result.stdout or "") + (result.stderr or "")
    except Exception:
        return ""


def _get_audio_help():
    global _AUDIO_HELP_CACHE
    if _AUDIO_HELP_CACHE is None:
        _AUDIO_HELP_CACHE = _run_qemu_help(["-audiodev", "help"]).lower()
    return _AUDIO_HELP_CACHE


def _get_display_help():
    global _DISPLAY_HELP_CACHE
    if _DISPLAY_HELP_CACHE is None:
        _DISPLAY_HELP_CACHE = _run_qemu_help(["-display", "help"]).lower()
    return _DISPLAY_HELP_CACHE


def _get_accel_help():
    global _ACCEL_HELP_CACHE
    if _ACCEL_HELP_CACHE is None:
        _ACCEL_HELP_CACHE = _run_qemu_help(["-accel", "help"]).lower()
    return _ACCEL_HELP_CACHE


def detect_audio_driver():
    """Detekuje preferovaný audio driver na tomto hostu (wasapi pokud dostupný)."""
    help_text = _get_audio_help()
    if "wasapi" in help_text:
        return "wasapi"
    if "dsound" in help_text:
        return "dsound"
    # pokud help selhalo (prázdné), preferuj kompatibilní dsound
    if help_text == "":
        return "dsound"
    # fallback podle OS – Win11 má wasapi, ale pokud help selže, odhadneme
    if os.name == "nt":
        return "wasapi"
    return "dsound"


def resolve_audio_driver(vm):
    """Vyřeší driver pro VM: auto -> detekce, jinak explicitní hodnota."""
    requested = getattr(vm, "audio_driver", "auto") or "auto"
    requested = str(requested).lower().strip()
    if requested == "auto":
        return detect_audio_driver()
    if requested in ("wasapi", "dsound"):
        # ověř dostupnost, fallback pokud QEMU neumí wasapi
        if requested == "wasapi" and "wasapi" not in _get_audio_help() and _get_audio_help() != "":
            return "dsound"
        return requested
    return "dsound"


def build_audio_args(vm):
    """Sestaví QEMU argumenty pro zvukový subsystém podle specifikace VM.

    Low-latency ladění:
    - wasapi: timer-period (µs) + out.latency (ms), default 5000 / 20
    - dsound: timer-period + latency (ms)
    Hodnoty jsou clampovány pro stabilitu (praskání při příliš nízkých).
    """
    if not getattr(vm, "sound_enabled", True):
        return []

    card = getattr(vm, "sound_card", "intel-hda")
    audio_dev = "snd0"

    driver = resolve_audio_driver(vm)
    timer_period = _clamp(getattr(vm, "audio_timer_period", 5000), 2000, 10000, 5000)
    latency_ms = _clamp(getattr(vm, "audio_latency_ms", 20), 10, 50, 20)

    # nízko-latenční audiodev string
    if driver == "wasapi":
        # wasapi podporuje out.latency (ms), exclusive=off pro kompatibilitu
        audiodev_spec = f"wasapi,id={audio_dev},timer-period={timer_period},out.latency={latency_ms}"
    else:
        # dsound: společný latency parametr
        audiodev_spec = f"dsound,id={audio_dev},timer-period={timer_period},latency={latency_ms}"

    args = ["-audiodev", audiodev_spec]

    if card == "intel-hda":
        args += ["-device", "intel-hda", "-device", f"hda-duplex,audiodev={audio_dev}"]
    elif card == "sb16":
        args += ["-device", f"sb16,audiodev={audio_dev}"]
    elif card == "ac97":
        args += ["-device", f"ac97,audiodev={audio_dev}"]
    elif card == "pcspk":
        args += ["-device", f"pcspk,audiodev={audio_dev}"]
    return args


def build_display_args(vm):
    """Sestaví display argumenty pro fázi 2 s ohledem na latenci.

    - auto: preferuje sdl,gl=on na Win (nejnižší latence), fallback gtk,gl=on
    - respektuje vm.display_gl / vm.display_vsync
    - fáze 1 používá vždy -display none (voláno separátně)
    """
    driver = str(getattr(vm, "display_driver", "auto") or "auto").lower().strip()
    gl_on = bool(getattr(vm, "display_gl", True))
    vsync = bool(getattr(vm, "display_vsync", False))
    help_text = _get_display_help()

    if driver == "none":
        return ["-display", "none"]

    # auto detekce preferovaného driveru
    if driver == "auto":
        # Win11: sdl má nejnižší latenci, gtk jako fallback
        if "sdl" in help_text:
            driver = "sdl"
        elif "gtk" in help_text:
            driver = "gtk"
        elif help_text == "":
            # help selhalo – předpokládej sdl (nejčastější na Win), jinak gtk bude fallback níže
            driver = "sdl"
        else:
            # QEMU nehlásí sdl/gtk – explicitně zkus sdl
            driver = "sdl"

    # validace že QEMU daný driver zná; pokud help neobsahuje, zkus alternativu
    if help_text:
        if driver not in help_text:
            # zkus druhý preferovaný driver místo návratu []
            if driver == "sdl" and "gtk" in help_text:
                driver = "gtk"
            elif driver == "gtk" and "sdl" in help_text:
                driver = "sdl"
            else:
                # driver není podporován – nech QEMU default, ale logicky vrátí []
                # pro robustnost vrať explicitní fallback místo ticha
                if "sdl" in help_text:
                    driver = "sdl"
                elif "gtk" in help_text:
                    driver = "gtk"
                else:
                    return []

    opts = []
    if driver in ("sdl", "gtk"):
        if gl_on:
            opts.append("gl=on")
        else:
            opts.append("gl=off")
        # vsync off snižuje latenci o 1 frame (~16ms) – pouze pokud QEMU podporuje
        if not vsync and driver == "sdl":
            # sdl podporuje show-cursor, vsync není všude – přidáme jen gl
            pass
        # gtk má implicitní vsync, nelze vypnout přes QEMU arg

    if opts:
        return ["-display", f"{driver}," + ",".join(opts)]
    return ["-display", driver]


def build_accel_args():
    """Vrátí accel argumenty pro Win11 (whpx) s fallbackem.

    QEMU 10+ neakceptuje '-accel whpx:tcg' (to je syntaxe pro '-machine accel=...'),
    takže vracíme pouze jeden '-accel' (whpx preferenčně, tcg jako fallback).
    """
    help_text = _get_accel_help()
    if "whpx" in help_text:
        return ["-accel", "whpx"]
    if "tcg" in help_text:
        return ["-accel", "tcg"]
    return []


def is_iso_available(vm) -> bool:
    """Ověří, zda má VM platné ISO (cesta existuje a soubor není prázdný)."""
    iso = getattr(vm, "iso", "") or ""
    iso = os.path.normpath(str(iso).strip())
    if not iso:
        return False
    if not os.path.exists(iso):
        return False
    try:
        # soubor menší než 1 MB je podezřelý (poškozené/prázdné ISO)
        if os.path.getsize(iso) < 1024 * 1024:
            return False
    except OSError:
        return False
    return True


def is_disk_bootable(disk_path: str) -> bool:
    """Rychlá detekce, zda disk obsahuje bootloader (MBR 0x55AA nebo data).

    Prázdný qcow2 z `qemu-img create` má minimální alokaci a žádný MBR.
    Kontroluje:
    1) soubor neexistuje -> False
    2) velmi malý soubor (< 1 MB) -> False
    3) pokus přes `qemu-img info --output=json` (allocated_size == 0 -> prázdný)
    4) fallback: hledá MBR signaturu 0x55AA na offsetu 510-511
       (u qcow2 čte přes qemu-img convert do stdout nebo brute-force scan)
    """
    try:
        norm = os.path.normpath(disk_path)
        if not os.path.exists(norm):
            return False
        try:
            size = os.path.getsize(norm)
            if size < 1024 * 1024:
                # čerstvý qcow2 má ~200 KB, ale už označuje prázdný
                # rozlišíme podle allocated
                pass
            else:
                # velký soubor, ale může být sparse prázdný
                pass
        except OSError:
            return False

        # 1) qemu-img info JSON - nejspolehlivější pro qcow2
        _fmt = None
        _allocated = None
        try:
            if os.path.exists(QEMU_IMG):
                result = subprocess.run(
                    [QEMU_IMG, "info", "--output=json", norm],
                    capture_output=True, text=True, timeout=3,
                    creationflags=_NO_WINDOW,
                )
                if result.returncode == 0 and result.stdout:
                    import json
                    info = json.loads(result.stdout)
                    _fmt = info.get("format")
                    # virtual-size vs disk-size/actual-size
                    _allocated = info.get("actual-size", info.get("disk-size", None))
                    # pokud má backing file, považuj za bootovatelný
                    if info.get("backing-filename"):
                        return True
        except Exception:
            pass

        # 2) pokus přes qemu-img dd do temp souboru (spolehlivé pro qcow2, jen první sektory)
        try:
            if os.path.exists(QEMU_IMG):
                import tempfile
                tmp_raw = tempfile.mktemp(suffix=".raw")
                try:
                    # dd umí číst qcow2 logický obsah, stačí první 2 sektory pro MBR/GPT
                    dres = subprocess.run(
                        [QEMU_IMG, "dd", f"if={norm}", f"of={tmp_raw}", "bs=512", "count=4"],
                        capture_output=True, timeout=5, creationflags=_NO_WINDOW,
                    )
                    if dres.returncode == 0 and os.path.exists(tmp_raw):
                        with open(tmp_raw, "rb") as fr:
                            sector = fr.read(2048)
                            if len(sector) >= 512:
                                if sector[510] == 0x55 and sector[511] == 0xAA:
                                    return True
                                if any(b != 0 for b in sector[:440]):
                                    return True
                                if len(sector) >= 1024 and sector[512:520] == b"EFI PART":
                                    return True
                                if all(b == 0 for b in sector):
                                    # prázdný logický disk
                                    if _fmt == "qcow2" and _allocated is not None:
                                        try:
                                            if int(_allocated) < 500 * 1024:
                                                return False
                                        except (ValueError, TypeError):
                                            pass
                                    return False
                                # má data ale bez MBR -> považuj za bootovatelný (např. GPT)
                                return True
                finally:
                    try:
                        os.unlink(tmp_raw)
                    except OSError:
                        pass
        except Exception:
            pass

        # 3) raw fallback - scan prvních 64KB na MBR signaturu
        try:
            with open(norm, "rb") as f:
                head = f.read(64 * 1024)
                if len(head) >= 512:
                    # hledej 0x55AA na offsetu 510
                    if head[510] == 0x55 and head[511] == 0xAA:
                        return True
                    # qcow2: hlavička ~1KB, pak data; scan po 512B blocích (pro raw s posunem)
                    for off in range(0, min(len(head) - 512, 8192), 512):
                        if head[off + 510] == 0x55 and head[off + 511] == 0xAA:
                            return True
                    # prázdný qcow2 má ~138 nenulových bajtů v hlavičce, bootovatelný má víc
                    if _fmt == "qcow2" and _allocated is not None:
                        try:
                            if int(_allocated) < 500 * 1024:
                                # allocated malé = prázdný, ale už jsme zkontrolovali MBR výše
                                return False
                        except (ValueError, TypeError):
                            pass
                    if len(head) >= 4096 and any(b != 0 for b in head[2048:]):
                        non_zero = sum(1 for b in head if b != 0)
                        if non_zero > 200:  # qcow2 hlavička má ~138, bootovatelný má víc
                            return True
                    # raw s MBR mimo 0 offset už jsme pokryli scanem
                    # pokud je to qcow2 a nenulových je málo, je prázdný
                    if _fmt == "qcow2":
                        return False
                    # pro raw bez MBR a bez dat -> neprázdný?
                    if any(b != 0 for b in head[:440]):
                        return True
                    return False
        except OSError:
            return False
        # poslední fallback: rozhodni podle allocated (jen pro qcow2)
        if _fmt == "qcow2" and _allocated is not None:
            try:
                return int(_allocated) >= 500 * 1024
            except (ValueError, TypeError):
                pass
        return False
    except Exception:
        return False


def resolve_boot_device(vm, requested: int):
    """Vyřeší skutečné boot zařízení s fallbackem pro prázdný disk.

    - Pokud je požadován disk a disk je prázdný/nebootovatelný a ISO je k dispozici,
      vrátí BOOT_CDROM (fallback) a volající má zobrazit varování.
    - Pokud je požadován CDROM a ISO chybí, vrátí BOOT_DISK pokud je disk bootovatelný,
      jinak ponechá CDROM (SeaBIOS pak zahlásí chybu, ale UI už varovalo).
    Vrací (resolved_device, did_fallback: bool)
    """
    try:
        req = int(requested)
    except (TypeError, ValueError):
        req = BOOT_DISK
    if req not in (BOOT_DISK, BOOT_CDROM, BOOT_NETWORK):
        req = BOOT_DISK

    disk = os.path.join(VMS_DIR, getattr(vm, "disk_file", ""))
    iso_ok = is_iso_available(vm)
    try:
        disk_ok = is_disk_bootable(disk)
    except Exception:
        disk_ok = False

    if req == BOOT_DISK and not disk_ok and iso_ok:
        return BOOT_CDROM, True
    return req, False


def start_phase1(vm):
    """Spustí vlastní BIOS (přístupné nastavení). Vrací (proces, serial_port, qmp_port)."""
    serial_port = find_free_port()
    qmp_port = find_free_port()
    args = [
        QEMU_EXE,
        "-name", vm.name,
        "-m", str(vm.memory_mb),
        "-smp", str(vm.cpus),
        "-bios", BIOS_PATH,
        "-display", "none",
        "-serial", f"tcp:127.0.0.1:{serial_port},server=on,nowait",
        "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,nowait",
        "-monitor", "none",
        "-no-reboot",
    ] + build_audio_args(vm)
    proc = subprocess.Popen(args, creationflags=_NO_WINDOW)
    return proc, serial_port, qmp_port


def _build_phase2_args(vm, boot_device, qmp_port):
    """Interní helper – sestaví kompletní argv pro fázi 2."""
    args = [
        QEMU_EXE,
        "-name", vm.name,
        "-m", str(vm.memory_mb),
        "-smp", str(vm.cpus),
    ]
    args += build_accel_args()
    args += ["-rtc", "base=localtime,driftfix=slew"]
    args += build_display_args(vm)
    disk = os.path.join(VMS_DIR, vm.disk_file)
    args += ["-drive", f"file={disk},format=qcow2,if=ide"]
    if vm.iso and os.path.exists(vm.iso):
        args += ["-cdrom", vm.iso]
    args += ["-netdev", "user,id=net0", "-device", "e1000,netdev=net0"]
    args += build_audio_args(vm)
    order = {BOOT_DISK: "c", BOOT_CDROM: "d", BOOT_NETWORK: "n"}.get(boot_device, "c")
    args += [
        "-boot", f"order={order}",
        "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,nowait",
        "-monitor", "none",
        "-no-reboot",
    ]
    return args


def _poll_process(proc, timeout: float, interval: float = 0.05) -> bool:
    """Polling čekání bez blokování GUI – vrací True pokud proces skončil."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return True
        time.sleep(interval)
    return proc.poll() is not None


def start_phase2(vm, boot_device):
    """Spustí skutečné zavádění systému přes SeaBIOS. Vrací (proces, qmp_port)."""
    qmp_port = find_free_port()

    def _launch(argv):
        try:
            return subprocess.Popen(argv, creationflags=_NO_WINDOW)
        except FileNotFoundError as ex:
            raise RuntimeError(f"QEMU nenalezen: {QEMU_EXE} ({ex})") from ex

    args = _build_phase2_args(vm, boot_device, qmp_port)
    proc = _launch(args)

    # Rychlá detekce pádu: poll každých 50 ms, max 0,35 s (místo fix 0,5 s) – snižuje „nic" z 0,5 na ~0,2 s
    _poll_process(proc, 0.35, 0.05)
    if proc.poll() is not None:
        # zkus fallback – vždy s dsound a gl=off, protože to je nejkompatibilnější
        try:
            import copy

            fb = copy.copy(vm)
            # vynutit nejkompatibilnější nastavení
            fb.audio_driver = "dsound"
            fb.display_gl = False
            # pokud původní driver byl wasapi, už je dsound; jinak také fallback
            args_fb = _build_phase2_args(fb, boot_device, qmp_port)
            # pokud i tak selže kvůli display, zkus ještě bez explicitního display
            proc = _launch(args_fb)
            _poll_process(proc, 0.35, 0.05)
            if proc.poll() is not None:
                # poslední pokus – bez display arg (nech QEMU default)
                # sestav args bez display
                args_min = [
                    QEMU_EXE, "-name", vm.name, "-m", str(vm.memory_mb), "-smp", str(vm.cpus),
                ] + build_accel_args() + ["-rtc", "base=localtime,driftfix=slew"]
                disk = os.path.join(VMS_DIR, vm.disk_file)
                args_min += ["-drive", f"file={disk},format=qcow2,if=ide"]
                if vm.iso and os.path.exists(vm.iso):
                    args_min += ["-cdrom", vm.iso]
                args_min += ["-netdev", "user,id=net0", "-device", "e1000,netdev=net0"]
                args_min += build_audio_args(fb)
                order = {BOOT_DISK: "c", BOOT_CDROM: "d", BOOT_NETWORK: "n"}.get(boot_device, "c")
                args_min += ["-boot", f"order={order}", "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,nowait", "-monitor", "none", "-no-reboot"]
                proc = _launch(args_min)
                _poll_process(proc, 0.25, 0.05)
                if proc.poll() is not None:
                    raise RuntimeError("QEMU fáze 2 stále padá i po fallbacích (zkontroluj log)")
        except RuntimeError:
            raise
        except Exception:
            pass
    return proc, qmp_port


def stop_process(proc, qmp_port=None, wait=1.5):
    """Zastaví QEMU: pokus o měkké vypnutí přes QMP, jinak ukončí proces.

    Pro Fázi 1 (vlastní BIOS bez diskového I/O) stačí 1,5 s (původně 4,0 s blokovalo GUI 4 s).
    Pro Fázi 2 lze předat wait=4.0 explicitně pokud je potřeba flush.
    """
    if proc is None or proc.poll() is not None:
        return
    if qmp_port is not None:
        try:
            qmp = QMPClient("127.0.0.1", qmp_port, timeout=2)
            qmp.system_powerdown()
            qmp.close()
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    return
                time.sleep(0.1)
        except Exception:
            pass
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
