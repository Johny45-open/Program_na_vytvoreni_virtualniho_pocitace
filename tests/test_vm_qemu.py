"""Integrační test VM vrstvy: fáze 1, sériové zrcadlení, událost boot, fáze 2."""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.bios.protocol import KEY_DOWN, KEY_F10, parse_frame
from app.vm import qemu as q
from app.vm.manager import VMManager


def _read_frame(sock, timeout=8.0):
    sock.settimeout(timeout)
    data = bytearray()
    while True:
        b = sock.recv(1)
        if not b:
            return bytes(data)
        data.append(b[0])
        if b[0] == 0x03:
            return bytes(data)


def _connect(port, attempts=40):
    for _ in range(attempts):
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=2)
        except OSError:
            time.sleep(0.25)
    raise AssertionError("nelze se připojit")


def _wait_for(text, needle, attempts=60):
    for _ in range(attempts):
        if needle in text:
            return text
        time.sleep(0.15)
    raise AssertionError(f"nenalezeno {needle!r} v:\n{text}")


def test_two_phase_boot(tmp_path):
    vm_name = "testvm"
    vms_dir = tmp_path / "vms"
    vms_dir.mkdir()
    os.environ["VMS_DIR"] = str(vms_dir)

    # dočasně přesměrujeme VMS_DIR pro test
    import app.vm.qemu as qemu_module
    old = qemu_module.VMS_DIR
    qemu_module.VMS_DIR = str(vms_dir)
    manager = VMManager(str(vms_dir))

    from app.vm.models import VMSpec

    vm = VMSpec(name=vm_name, memory_mb=256, cpus=1, disk_size_gb=1)
    manager.save(vm)

    try:
        # vytvoření disku
        disk = q.ensure_disk(vm)
        assert os.path.exists(disk), "disk nebyl vytvořen"
        assert disk.endswith(".qcow2")

        # fáze 1
        proc, serial_port, qmp_port = q.start_phase1(vm)
        assert proc.poll() is None, "QEMU fáze 1 spadlo"

        sock = _connect(serial_port)
        try:
            sock.sendall(bytes([KEY_DOWN]))
            frame = None
            for _ in range(60):
                f = _read_frame(sock, timeout=2)
                if not f:
                    continue
                frame = f
                break
            assert frame is not None, "nepřišel žádný snímek"
            decoded = parse_frame(frame)
            assert "Vlastní BIOS" in decoded.title

            # F10 -> událost boot
            sock.sendall(bytes([KEY_F10]))
            boot = None
            for _ in range(60):
                f = _read_frame(sock, timeout=2)
                if not f:
                    continue
                parsed = parse_frame(f)
                if parsed.is_event:
                    boot = parsed
                    break
            assert boot is not None, "nedošla událost boot"
            assert boot.event.startswith("boot:"), boot.event
            device = int(boot.event.split(":")[1])
        finally:
            sock.close()

        # zastavení fáze 1
        q.stop_process(proc, qmp_port)
        assert proc.poll() is not None, "fáze 1 se nezastavila"

        # fáze 2
        proc2, qmp2 = q.start_phase2(vm, device)
        assert proc2.poll() is None, "QEMU fáze 2 spadlo"
        q.stop_process(proc2, qmp2)
        assert proc2.poll() is not None, "fáze 2 se nezastavila"

        # úklid
        manager.delete(vm_name)
    finally:
        qemu_module.VMS_DIR = old


def test_vmspec_sound():
    from app.vm.models import VMSpec

    vm = VMSpec(name="sndvm", sound_enabled=True, sound_card="sb16")
    d = vm.to_dict()
    assert d["sound_enabled"] is True
    assert d["sound_card"] == "sb16"

    restored = VMSpec.from_dict(d)
    assert restored.sound_enabled is True
    assert restored.sound_card == "sb16"


def test_qemu_audio_args():
    from app.vm.models import VMSpec
    from app.vm.qemu import build_audio_args

    vm_on = VMSpec(name="on", sound_enabled=True, sound_card="intel-hda")
    args_on = build_audio_args(vm_on)
    assert "-audiodev" in args_on
    # auto na Win11 může být wasapi nebo dsound podle help – ošetři obojí
    assert any(x in args_on[args_on.index("-audiodev") + 1] for x in ["dsound", "wasapi"])
    assert "intel-hda" in args_on
    # low-latency parametry musí být přítomny
    audiodev_val = args_on[args_on.index("-audiodev") + 1]
    assert "timer-period=" in audiodev_val
    assert "latency=" in audiodev_val

    vm_off = VMSpec(name="off", sound_enabled=False)
    args_off = build_audio_args(vm_off)
    assert args_off == []


def test_qemu_audio_args_wasapi_explicit():
    from app.vm.models import VMSpec
    from app.vm.qemu import build_audio_args, _AUDIO_HELP_CACHE
    import app.vm.qemu as qm
    # vynutit wasapi bez ohledu na help (mock)
    old = qm._AUDIO_HELP_CACHE
    qm._AUDIO_HELP_CACHE = "wasapi dsound"
    try:
        vm = VMSpec(name="w", sound_enabled=True, sound_card="intel-hda", audio_driver="wasapi", audio_latency_ms=15, audio_timer_period=3000)
        args = build_audio_args(vm)
        val = args[args.index("-audiodev") + 1]
        assert val.startswith("wasapi,")
        assert "timer-period=3000" in val
        assert "out.latency=15" in val
    finally:
        qm._AUDIO_HELP_CACHE = old


def test_qemu_audio_args_dsound_explicit():
    from app.vm.models import VMSpec
    from app.vm.qemu import build_audio_args
    import app.vm.qemu as qm
    old = qm._AUDIO_HELP_CACHE
    qm._AUDIO_HELP_CACHE = "wasapi dsound"
    try:
        vm = VMSpec(name="d", sound_enabled=True, sound_card="sb16", audio_driver="dsound", audio_latency_ms=25, audio_timer_period=7000)
        args = build_audio_args(vm)
        val = args[args.index("-audiodev") + 1]
        assert val.startswith("dsound,")
        assert "timer-period=7000" in val
        assert "latency=25" in val
        assert any("sb16" in a for a in args)
    finally:
        qm._AUDIO_HELP_CACHE = old


def test_qemu_audio_args_clamp():
    from app.vm.models import VMSpec
    from app.vm.qemu import build_audio_args
    import app.vm.qemu as qm
    old = qm._AUDIO_HELP_CACHE
    qm._AUDIO_HELP_CACHE = "dsound"
    try:
        vm = VMSpec(name="c", sound_enabled=True, audio_driver="dsound", audio_latency_ms=999, audio_timer_period=1)
        args = build_audio_args(vm)
        val = args[args.index("-audiodev") + 1]
        # clamp: latency max 50, timer min 2000
        assert "latency=50" in val
        assert "timer-period=2000" in val
    finally:
        qm._AUDIO_HELP_CACHE = old


def test_qemu_display_args():
    from app.vm.models import VMSpec
    from app.vm.qemu import build_display_args
    import app.vm.qemu as qm
    old = qm._DISPLAY_HELP_CACHE
    qm._DISPLAY_HELP_CACHE = "sdl gtk none"
    try:
        vm_auto = VMSpec(name="a", display_driver="auto", display_gl=True)
        args = build_display_args(vm_auto)
        assert "-display" in args
        # auto preferuje sdl pokud je v help
        assert "sdl" in args[1]
        assert "gl=on" in args[1]

        vm_none = VMSpec(name="n", display_driver="none")
        assert build_display_args(vm_none) == ["-display", "none"]

        vm_gtk = VMSpec(name="g", display_driver="gtk", display_gl=False)
        args2 = build_display_args(vm_gtk)
        assert args2 == ["-display", "gtk,gl=off"]
    finally:
        qm._DISPLAY_HELP_CACHE = old


def test_vmspec_latency_fields():
    from app.vm.models import VMSpec
    vm = VMSpec(name="lat", audio_driver="wasapi", audio_latency_ms=15, audio_timer_period=3000, display_driver="sdl", display_gl=False, display_vsync=True)
    d = vm.to_dict()
    assert d["audio_driver"] == "wasapi"
    assert d["audio_latency_ms"] == 15
    assert d["display_driver"] == "sdl"
    restored = VMSpec.from_dict(d)
    assert restored.audio_driver == "wasapi"
    assert restored.audio_latency_ms == 15
    assert restored.display_gl is False
    # zpětná kompatibilita – chybějící klíče
    old_dict = {"name": "old", "sound_enabled": True, "sound_card": "intel-hda"}
    restored2 = VMSpec.from_dict(old_dict)
    assert restored2.audio_driver == "auto"
    assert restored2.audio_latency_ms == 20
    assert restored2.display_driver == "auto"