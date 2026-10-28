;========================================================================
;  boot.asm - hlavní vstupní bod vlastního BIOSu
;
;  Sestavení: nasm -f bin boot.asm -o bios.bin
;  QEMU:      qemu-system-x86_64 -bios bios.bin ...
;
;  Vznikne 64 KB binárka mapovaná na 0xF0000, reset vektor na 0xFFFF0.
;========================================================================

BITS 16
CPU 386

BIOS_SEG:  equ 0xF000
STACK_SEG: equ 0x9000

section .text

%include "vars.asm"
%include "serial.asm"
%include "vga.asm"
%include "keyboard.asm"
%include "strings.asm"
%include "screen.asm"
%include "menu.asm"

;--- Krátké zpoždění (omezení vytížení CPU při čekání) ---
delay_short:
    push cx
    mov cx, 0xFFFF
.loop:
    loop .loop
    pop cx
    ret

;--- Vstupní bod (volá se z reset vektoru) ---
bios_entry:
    cli
    cld
    mov ax, BIOS_SEG
    mov ds, ax
    mov ax, VAR_SEG
    mov es, ax
    mov ax, STACK_SEG
    mov ss, ax
    mov sp, 0x0000
    sti

    call serial_init
    call vga_init
    call vga_clear
    call keyboard_init
    call menu_init
    call screen_render

.main_loop:
    call key_poll
    test al, al
    jz .idle
    call menu_handle_key
    call screen_render
.idle:
    call delay_short
    jmp .main_loop

;--- Vycpávka k reset vektoru (0xFFF0) ---
times 0xFFF0-($-$$) db 0

;--- Reset vektor (0xFFFF0) ---
reset_vector:
    jmp 0xF000:bios_entry

;--- Doplní na plných 64 KB ---
times 0x10000-($-$$) db 0
