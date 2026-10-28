"""Sestaví firmware BIOSu ze zdrojového kódu NASM do bios.bin."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(ROOT)
OUT = os.path.join(ROOT, "bios.bin")
SRC = os.path.join(ROOT, "boot.asm")


def find_nasm():
    override = os.environ.get("NASM")
    if override:
        return override
    candidate = os.path.join(PROJECT, "tools", "nasm", "nasm-3.02", "nasm.exe")
    if os.path.exists(candidate):
        return candidate
    return "nasm"


def main():
    nasm = find_nasm()
    print(f"NASM: {nasm}")
    result = subprocess.run([nasm, "-f", "bin", "-i", ROOT, "-o", OUT, SRC])
    if result.returncode != 0:
        sys.exit(result.returncode)
    size = os.path.getsize(OUT)
    print(f"Sestaveno: {OUT} ({size} bajtů)")
    if size != 0x10000:
        print(f"Varování: očekávaná velikost je 65536 bajtů, je {size}")


if __name__ == "__main__":
    main()
