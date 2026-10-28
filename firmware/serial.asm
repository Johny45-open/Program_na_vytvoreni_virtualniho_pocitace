;========================================================================
;  serial.asm - sériový port COM1 (16550 UART)
;  Připraveno na 115200 baudů, 8 datových bitů, bez parity, 1 stop bit.
;========================================================================

COM1:     equ 0x3F8
COM1_IER: equ 0x3F9
COM1_FCR: equ 0x3FA
COM1_LCR: equ 0x3FB
COM1_MCR: equ 0x3FC
COM1_LSR: equ 0x3FD

;--- Inicializace COM1 ---
serial_init:
    push ax
    push dx
    mov dx, COM1_IER       ; vypnout přerušení
    mov al, 0
    out dx, al
    mov dx, COM1_LCR       ; DLAB zapnout
    mov al, 0x80
    out dx, al
    mov dx, COM1           ; dělitel = 1 (115200 baudů)
    mov al, 1
    out dx, al
    mov dx, COM1_IER       ; vyšší bajt dělitele = 0
    mov al, 0
    out dx, al
    mov dx, COM1_LCR       ; 8N1, DLAB vypnout
    mov al, 0x03
    out dx, al
    mov dx, COM1_FCR       ; povolit FIFO
    mov al, 0xC7
    out dx, al
    mov dx, COM1_MCR       ; DTR + RTS
    mov al, 0x03
    out dx, al
    pop dx
    pop ax
    ret

;--- Odeslat jeden bajt (AL) ---
serial_putc:
    push dx
    push ax
    mov dx, COM1_LSR
.wait:
    in al, dx
    test al, 0x20          ; THR prázdné?
    jz .wait
    pop ax
    mov dx, COM1
    out dx, al
    pop dx
    ret

;--- Odeslat řetězec (DS:SI, ukončený nulou) ---
serial_puts:
    push ax
.loop:
    lodsb
    test al, al
    jz .done
    call serial_putc
    jmp .loop
.done:
    pop ax
    ret

;--- Odeslat CR LF ---
serial_crlf:
    push ax
    mov al, 13
    call serial_putc
    mov al, 10
    call serial_putc
    pop ax
    ret

;--- Přečíst bajt bez čekání ---
;    Výstup: CF=0 -> bajt v AL; CF=1 -> nic nepřišlo
serial_getc:
    push dx
    mov dx, COM1_LSR
    in al, dx
    test al, 0x01          ; data ready?
    jz .none
    mov dx, COM1
    in al, dx
    clc
    pop dx
    ret
.none:
    stc
    pop dx
    ret

;--- Vypíše číslo 0-99 v AL desítkově ---
serial_put_decimal:
    push ax
    push bx
    xor ah, ah
    mov bl, 10
    div bl                 ; AL = desítky, AH = jednotky
    test al, al
    jz .units
    push ax
    add al, '0'
    call serial_putc
    pop ax
.units:
    mov al, ah
    add al, '0'
    call serial_putc
    pop bx
    pop ax
    ret
