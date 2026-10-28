;========================================================================
;  vga.asm - textový režim VGA 80x25
;  České znaky (UTF-8 ve zdrojovém kódu) se pro VGA převádějí na
;  ASCII bez diakritiky, protože standardní font VGA nemá českou
;  abecedu. Sériový port dostává plné UTF-8.
;========================================================================

VGA_MEM_SEG: equ 0xB800

;--- Nastavení textového režimu 80x25 (režim 3) ---
vga_init:
    push ax
    push bx
    push cx
    push dx
    ; Sekvencer - vypnout displej
    mov dx, 0x3C4
    mov al, 0x01
    out dx, al
    inc dx
    mov al, 0x00
    out dx, al
    ; Sekvencer - režimy
    mov dx, 0x3C4
    mov al, 0x00
    out dx, al
    inc dx
    mov al, 0x03
    out dx, al
    mov dx, 0x3C4
    mov al, 0x02
    out dx, al
    inc dx
    mov al, 0x03
    out dx, al
    mov dx, 0x3C4
    mov al, 0x04
    out dx, al
    inc dx
    mov al, 0x03
    out dx, al
    ; CRT řadič - 80x25
    mov bx, crtc_table
    mov cl, crtc_table_len
.crtc:
    mov dx, 0x3D4
    mov al, [bx]
    out dx, al
    inc dx
    inc bx
    mov al, [bx]
    out dx, al
    inc bx
    dec cl
    jnz .crtc
    ; Sekvencer - povolit displej
    mov dx, 0x3C4
    mov al, 0x01
    out dx, al
    inc dx
    mov al, 0x20
    out dx, al
    pop dx
    pop cx
    pop bx
    pop ax
    ret

crtc_table:
    db 0x00,0x50, 0x01,0x4F, 0x02,0x50, 0x03,0x82, 0x04,0x50, 0x05,0x1E
    db 0x06,0x0B, 0x07,0x3E, 0x08,0x00, 0x09,0x40, 0x0A,0x00, 0x0B,0x00
    db 0x0C,0x00, 0x0D,0x00, 0x0E,0x00, 0x0F,0x00, 0x10,0xEA, 0x11,0x8C
    db 0x12,0xDF, 0x13,0x28, 0x14,0x00, 0x15,0xE7, 0x16,0x06, 0x17,0xE3
crtc_table_len: equ ($-crtc_table)/2

;--- Vymazat obrazovku ---
vga_clear:
    push ax
    push cx
    push di
    push es
    mov ax, VGA_MEM_SEG
    mov es, ax
    mov cx, 80*25
    xor di, di
    mov ax, 0x0720         ; mezera + atribut 0x07
.clear:
    mov [es:di], ax
    add di, 2
    loop .clear
    pop es
    pop di
    pop cx
    pop ax
    ret

;--- Vymazat řádek (AL = řádek) ---
vga_clear_row:
    push ax
    push cx
    push di
    push es
    mov dl, 80
    mul dl
    shl ax, 1
    mov di, ax
    mov ax, VGA_MEM_SEG
    mov es, ax
    mov cx, 80
    mov ax, 0x0720
.clear:
    mov [es:di], ax
    add di, 2
    loop .clear
    pop es
    pop di
    pop cx
    pop ax
    ret

;--- Zapsat řetězec na obrazovku ---
;    Vstup: AL = řádek, DL = sloupec, BH = atribut, DS:SI = řetězec
vga_write_string:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    ; pozice = (řádek*80 + sloupec) * 2
    push dx
    mov dl, 80
    mul dl
    pop dx
    xor bx, bx
    mov bl, dl
    add ax, bx
    shl ax, 1
    mov di, ax
    mov ax, VGA_MEM_SEG
    mov es, ax
.loop:
    call utf8_to_ascii
    test al, al
    jz .done
    mov [es:di], al
    mov byte [es:di+1], bh
    add di, 2
    jmp .loop
.done:
    pop es
    pop di
    pop si
    pop cx
    pop dx
    pop bx
    pop ax
    ret

;--- Přečte jeden znak z UTF-8 řetězce (DS:SI) a vrátí ASCII ---
;    Výstup: AL = znak, SI posunutý o 1-2 bajty
utf8_to_ascii:
    lodsb
    cmp al, 0x80
    jb .done               ; běžný ASCII
    cmp al, 0xE0
    jae .skip2             ; 3bajtový - přeskakujeme
    mov ah, al
    lodsb
    and ah, 0x1F
    mov cl, ah
    shl cl, 6
    and al, 0x3F
    or al, cl              ; AL = kódový bod (nízký bajt)
    mov di, utf8_ascii_table
.search:
    mov cl, [di]
    test cl, cl
    jz .unknown
    cmp cl, al
    je .found
    add di, 2
    jmp .search
.found:
    inc di
    mov al, [di]
    ret
.skip2:
    inc si
    mov al, '?'
    ret
.unknown:
    mov al, '?'
.done:
    ret

;--- Tabulka kódových bodů UTF-8 -> ASCII (české znaky) ---
utf8_ascii_table:
    db 0xE1,'a'    ; á
    db 0xE9,'e'    ; é
    db 0xED,'i'    ; í
    db 0xF3,'o'    ; ó
    db 0xFA,'u'    ; ú
    db 0xFD,'y'    ; ý
    db 0xC1,'A'    ; Á
    db 0xC9,'E'    ; É
    db 0xCD,'I'    ; Í
    db 0xD3,'O'    ; Ó
    db 0xDA,'U'    ; Ú
    db 0xDD,'Y'    ; Ý
    db 0x0D,'c'    ; č
    db 0x0F,'d'    ; ď
    db 0x1B,'e'    ; ě
    db 0x48,'n'    ; ň
    db 0x59,'r'    ; ř
    db 0x61,'s'    ; š
    db 0x65,'t'    ; ť
    db 0x7E,'z'    ; ž
    db 0x6F,'u'    ; ů
    db 0x0C,'C'    ; Č
    db 0x0E,'D'    ; Ď
    db 0x1A,'E'    ; Ě
    db 0x47,'N'    ; Ň
    db 0x58,'R'    ; Ř
    db 0x60,'S'    ; Š
    db 0x64,'T'    ; Ť
    db 0x7D,'Z'    ; Ž
    db 0x6E,'U'    ; Ů
    db 0x00,0x00
