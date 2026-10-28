"""Kouřový test vlastního BIOSu: spustí ho v QEMU a ověří sériové zrcadlení.

Použití:  python tests/smoke_bios.py
"""
import os
import socket
import subprocess
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QEMU = os.environ.get("QEMU", r"C:\Program Files\qemu\qemu-system-x86_64.exe")
BIOS = os.path.join(PROJECT, "firmware", "bios.bin")

KEY_UP = b"\x01"
KEY_DOWN = b"\x02"
KEY_ENTER = b"\x0d"
KEY_ESC = b"\x1b"
KEY_F10 = b"\x83"


def start_qemu(port):
    args = [
        QEMU,
        "-m", "64",
        "-bios", BIOS,
        "-display", "none",
        "-serial", f"tcp:127.0.0.1:{port},server=on,nowait",
        "-monitor", "none",
        "-no-reboot",
    ]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen(args, creationflags=flags)


def read_frame(sock, timeout=6.0):
    """Přečte jeden snímek ukončený 0x03."""
    sock.settimeout(timeout)
    data = bytearray()
    while True:
        try:
            b = sock.recv(1)
        except socket.timeout:
            return bytes(data)
        if not b:
            return bytes(data)
        data.append(b[0])
        if b[0] == 0x03:
            return bytes(data)


def connect(port, attempts=40):
    for _ in range(attempts):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=2)
            return s
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Nepodařilo se připojit k sériovému portu QEMU")


def wait_for_frame(sock, predicate, attempts=40):
    """Čte snímky, dokud predicate(decoded_text) nevrátí True."""
    for _ in range(attempts):
        frame = read_frame(sock)
        text = frame.decode("utf-8", errors="replace")
        if predicate(text):
            return text
        time.sleep(0.1)
    raise AssertionError("Nedošel očekávaný snímek")


def main():
    if not os.path.exists(BIOS):
        print("Nejprve sestav firmware: python firmware/build.py")
        return 1
    port = 45454
    qemu = start_qemu(port)
    try:
        sock = connect(port)
        try:
            time.sleep(0.3)  # nech BIOS naběhnout

            # šipka dolů -> index 1, zaměřená položka
            sock.sendall(KEY_DOWN)
            text = wait_for_frame(sock, lambda t: "M:1|Vybrat spouštěcí zařízení|0|1" in t)
            print("== úvodní snímek ==")
            print(text)
            assert "Vlastní BIOS" in text, "chybí titulek hlavního menu"
            assert "Pokračovat ve spuštění systému" in text
            assert "Vybrat spouštěcí zařízení" in text
            assert "Vypnout počítač" in text

            # Enter -> obrazovka výběru zařízení
            sock.sendall(KEY_ENTER)
            text = wait_for_frame(sock, lambda t: "Výběr spouštěcího zařízení" in t)
            print("== výběr zařízení ==")
            print(text)
            assert "Pevný disk" in text and "CD/DVD (ISO)" in text and "Síť (PXE)" in text

            # šipka dolů + Enter -> zvolíme CD/DVD (ISO)
            sock.sendall(KEY_DOWN)
            wait_for_frame(sock, lambda t: "M:1|CD/DVD (ISO)" in t)
            sock.sendall(KEY_ENTER)
            text = wait_for_frame(sock, lambda t: "Vlastní BIOS" in t and "M:0|Pokračovat" in t)
            print("== zpět v hlavním menu ==")
            print(text)

            # F10 -> událost boot s číslem 1 (cdrom)
            sock.sendall(KEY_F10)
            text = wait_for_frame(sock, lambda t: "E:boot:" in t)
            print("== událost boot ==")
            print(text)
            assert "E:boot:1" in text, "očekávala se událost E:boot:1"

            print("VŠE OK")
        finally:
            sock.close()
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=5)
        except subprocess.TimeoutExpired:
            qemu.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())