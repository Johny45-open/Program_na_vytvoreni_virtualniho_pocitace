;========================================================================
;  keyboard.asm - klávesnice PS/2 (8042) a interní kódy kláves
;
;  Interní kódy kláves (používají se i přes sériový port):
;    KEY_UP=0x01  KEY_DOWN=0x02  KEY_ENTER=0x0D  KEY_ESC=0x1B
;    KEY_F1=0x80  KEY_F2=0x81  KEY_F5=0x82  KEY_F10=0x83  KEY_TAB=0x09
;========================================================================

KEY_UP:    equ 0x01
KEY_DOWN:  equ 0x02
KEY_ENTER: equ 0x0D
KEY_ESC:   equ 0x1B
KEY_F1:    equ 0x80
KEY_F2:    equ 0x81
KEY_F5:    equ 0x82
KEY_F10:   equ 0x83
KEY_TAB:   equ 0x09

;--- Inicializace klávesnice ---
keyboard_init:
    call kbd_wait_ibuf
    mov al, 0xAE           ; povolit klávesnici
    out 0x64, al
    call kbd_wait_ibuf
    mov al, 0xF4           ; povolit skenování
    out 0x60, al
    ret

;--- Počkat, dokud není vstupní buffer prázdný ---
kbd_wait_ibuf:
    push ax
    push dx
.loop:
    mov dx, 0x64
    in al, dx
    test al, 0x02
    jnz .loop
    pop dx
    pop ax
    ret

;--- Přečíst sken-kód bez čekání ---
;    Výstup: CF=0 -> sken-kód v AL; CF=1 -> nic
ps2_getc:
    push dx
    mov dx, 0x64
    in al, dx
    test al, 0x01
    jz .none
    mov dx, 0x60
    in al, dx
    clc
    pop dx
    ret
.none:
    stc
    pop dx
    ret

;--- Přečíst klávesu z libovolného zdroje ---
;    Přednost má sériový port (aplikace), pak PS/2.
;    Výstup: AL = interní kód klávesy, nebo 0 = žádná
key_poll:
    call serial_getc
    jnc .got              ; CF=0 -> bajt z aplikace
    call ps2_getc
    jc .none
    call scancode_to_key
    ret
.got:
    ret
.none:
    xor al, al
    ret

;--- Převést sken-kód (sada 1) na interní kód ---
;    Vstup: AL = sken-kód
;    Výstup: AL = interní kód, nebo 0
scancode_to_key:
    test al, 0x80
    jnz .unknown          ; break kód - ignorovat
    push bx
    push cx
    mov bl, al
    mov si, scancode_table
.loop:
    lodsb
    test al, al
    jz .unknown2
    cmp al, bl
    je .match
    lodsb                 ; přeskočit interní kód
    jmp .loop
.match:
    lodsb
    jmp .done
.unknown2:
    xor al, al
.done:
    pop cx
    pop bx
    ret
.unknown:
    xor al, al
    ret

scancode_table:
    db 0x01, KEY_ESC       ; Esc
    db 0x1C, KEY_ENTER     ; Enter
    db 0x48, KEY_UP        ; Šipka nahoru
    db 0x50, KEY_DOWN      ; Šipka dolů
    db 0x4B, KEY_UP        ; Šipka vlevo
    db 0x4D, KEY_DOWN      ; Šipka vpravo
    db 0x44, KEY_F10       ; F10
    db 0x3B, KEY_F1        ; F1
    db 0x3C, KEY_F2        ; F2
    db 0x0F, KEY_TAB       ; Tab
    db 0x00, 0x00
