;========================================================================
;  vars.asm - proměnné BIOSu v konvenční paměti RAM
;
;  BIOS ROM je v QEMU mapovaná jako paměť POUZE PRO ČTENÍ, takže proměnné
;  musí žít v zapisovatelné RAM. Používáme segment 0x0060 (adresa 0x600),
;  která je mimo oblast přerušení i BIOS Data Area. Přístup: [es:offset].
;========================================================================

VAR_SEG: equ 0x0060

%define current_screen  0x00   ; 0=hlavní, 1=zařízení, 2=spouštění, 3=vypnutí
%define selected_index  0x01
%define boot_device     0x02   ; 0=disk, 1=cdrom, 2=síť
%define lang            0x03   ; 0=čeština, 1=angličtina
%define screen_dirty    0x04
%define await_boot      0x05
%define event_buf       0x10   ; vyrovnávací paměť události (24 bajtů)