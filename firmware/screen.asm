;========================================================================
;  screen.asm - stav obrazovky a vykreslování (VGA + sériové zrcadlení)
;
;  Sériový protokol:
;    0x0C ... začátek snímku (form feed)
;    "T:"   titulek
;    "M:index|popisek|vybrané|zaměřené" ... položky menu
;    "S:"   stavový řádek
;    0x03 ... konec snímku (ETX)
;========================================================================

;--- Stav (proměnné v RAM, segment VAR_SEG, přístup přes [es:...]) ---
;    Offsety jsou definované v vars.asm.

;--- Vybrat popisek podle jazyka ---
;    Vstup: DS:SI = ukazatel na dvojici (cs, en)
;    Výstup: DS:SI = vybraný popisek
lang_pick:
    push bx
    mov bx, [si]
    cmp byte [es:lang], 0
    je .cs
    mov bx, [si+2]
.cs:
    mov si, bx
    pop bx
    ret

;--- Počet položek aktuální obrazovky (výstup: CL) ---
screen_count:
    cmp byte [es:current_screen], 0
    jne .check1
    mov cl, main_items_count
    ret
.check1:
    cmp byte [es:current_screen], 1
    jne .none
    mov cl, device_items_count
    ret
.none:
    xor cl, cl
    ret

;--- Popisek položky ---
;    Vstup: AL = index položky
;    Výstup: DS:SI = popisek dle jazyka; CF=1 pokud neplatný index
item_label:
    push bx
    cmp byte [es:current_screen], 1
    ja .err
    cmp byte [es:current_screen], 0
    jne .device
    mov bx, main_items
    mov cl, main_items_count
    jmp .check
.device:
    mov bx, device_items
    mov cl, device_items_count
.check:
    cmp al, cl
    jae .err
    xor ah, ah
    shl ax, 1
    shl ax, 1
    add bx, ax
    mov si, bx
    call lang_pick
    clc
    pop bx
    ret
.err:
    stc
    pop bx
    ret

;--- Hodnota položky (Vstup: AL = index, Výstup: AL = hodnota) ---
item_value:
    cmp byte [es:current_screen], 1
    jne .main
    push bx
    mov bl, al
    xor bh, bh
    mov si, device_values
    add si, bx
    mov al, [si]
    pop bx
    ret
.main:
    xor al, al
    ret

;--- Titulek aktuální obrazovky (Výstup: DS:SI) ---
screen_title:
    cmp byte [es:current_screen], 0
    je .main
    cmp byte [es:current_screen], 1
    je .device
    cmp byte [es:current_screen], 2
    je .boot
    mov si, title_power_pair
    jmp .pick
.main:
    mov si, title_main_pair
    jmp .pick
.device:
    mov si, title_device_pair
    jmp .pick
.boot:
    mov si, title_boot_pair
.pick:
    call lang_pick
    ret

;--- Stavový řádek aktuální obrazovky (Výstup: DS:SI) ---
screen_status:
    cmp byte [es:current_screen], 0
    je .main
    cmp byte [es:current_screen], 1
    je .device
    mov si, status_boot_pair
    jmp .pick
.main:
    mov si, status_main_pair
    jmp .pick
.device:
    mov si, status_device_pair
.pick:
    call lang_pick
    ret

;--- Vykreslit aktuální obrazovku na VGA ---
vga_render:
    push ax
    push bx
    push cx
    push dx
    push si
    call vga_clear
    ; titulek
    mov al, 0
    mov dl, 0
    mov bh, 0x0F
    call screen_title
    call vga_write_string
    ; položky
    call screen_count
    xor ch, ch
.item_loop:
    cmp ch, cl
    jae .items_done
    mov al, ch
    call item_label
    jc .items_done
    push ax
    push bx
    push cx
    mov al, ch
    add al, 2
    mov dl, 1
    mov bh, 0x07
    cmp ch, [es:selected_index]
    jne .not_focused
    mov bh, 0x0F
    ; marker zaměření
    mov al, ch
    add al, 2
    mov dl, 0
    mov bh, 0x0B
    mov si, marker_focus
    call vga_write_string
.not_focused:
    ; marker vybraného zařízení
    cmp byte [es:current_screen], 1
    jne .no_sel_marker
    mov al, ch
    call item_value
    cmp al, [es:boot_device]
    jne .not_selected
    mov al, ch
    add al, 2
    mov dl, 0
    mov bh, 0x0B
    mov si, marker_selected
    call vga_write_string
.not_selected:
.no_sel_marker:
    pop cx
    pop bx
    pop ax
    mov al, ch
    add al, 2
    mov dl, 1
    mov bh, 0x07
    cmp ch, [es:selected_index]
    jne .write
    mov bh, 0x0F
.write:
    call vga_write_string
    inc ch
    jmp .item_loop
.items_done:
    ; stavový řádek
    mov al, 24
    mov dl, 0
    mov bh, 0x07
    call screen_status
    call vga_write_string
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

marker_focus:    db ">",0
marker_selected: db "*",0

;--- Odeslat snímek přes sériový port ---
serial_frame:
    push ax
    push bx
    push cx
    push si
    mov al, 0x0C
    call serial_putc
    ; titulek
    mov si, tag_t
    call serial_puts
    call screen_title
    call serial_puts
    call serial_crlf
    ; položky
    call screen_count
    xor bh, bh
.item_loop:
    cmp bh, cl
    jae .items_done
    mov al, bh
    call item_label
    jc .items_done
    push si
    mov si, tag_m
    call serial_puts
    mov al, bh
    call serial_put_decimal
    mov al, '|'
    call serial_putc
    pop si
    call serial_puts
    mov al, '|'
    call serial_putc
    ; vybrané? (jen u obrazovky výběru zařízení)
    cmp byte [es:current_screen], 1
    jne .sel0
    mov al, bh
    call item_value
    cmp al, [es:boot_device]
    jne .sel0
    mov al, '1'
    jmp .sel_out
.sel0:
    mov al, '0'
.sel_out:
    call serial_putc
    mov al, '|'
    call serial_putc
    ; zaměřené?
    cmp bh, [es:selected_index]
    jne .foc0
    mov al, '1'
    jmp .foc_out
.foc0:
    mov al, '0'
.foc_out:
    call serial_putc
    call serial_crlf
    inc bh
    jmp .item_loop
.items_done:
    ; stavový řádek
    mov si, tag_s
    call serial_puts
    call screen_status
    call serial_puts
    call serial_crlf
    mov al, 0x03
    call serial_putc
    pop si
    pop cx
    pop bx
    pop ax
    ret

tag_t: db "T:",0
tag_m: db "M:",0
tag_s: db "S:",0

;--- Vykreslit, pokud se obrazovka změnila ---
screen_render:
    push ax
    cmp byte [es:screen_dirty], 0
    je .skip
    call vga_render
    call serial_frame
    mov byte [es:screen_dirty], 0
.skip:
    pop ax
    ret

;--- Vykreslit vždy ---
screen_render_force:
    push ax
    call vga_render
    call serial_frame
    mov byte [es:screen_dirty], 0
    pop ax
    ret

;--- Odeslat událost (E:...), Vstup: DS:SI = řádek události ---
serial_event:
    push ds
    push si
    mov al, 0x0C
    call serial_putc
    mov si, tag_t
    call serial_puts
    call screen_title
    call serial_puts
    call serial_crlf
    pop si
    ; event_buf je v RAM (segment VAR_SEG), proto dočasně přepneme DS
    mov ax, VAR_SEG
    mov ds, ax
    call serial_puts
    mov ax, BIOS_SEG
    mov ds, ax
    call serial_crlf
    mov al, 0x03
    call serial_putc
    pop ds
    ret

;--- Sestavit řetězec události "E:boot:<cifra>" do event_buf ---
build_boot_event:
    push ax
    push di
    push si
    mov di, event_buf
    mov si, event_boot_prefix
.copy:
    lodsb
    test al, al
    jz .done
    stosb
    jmp .copy
.done:
    mov al, [es:boot_device]
    add al, '0'
    stosb
    mov al, 0
    stosb
    pop si
    pop di
    pop ax
    ret

event_boot_prefix: db "E:boot:",0
event_poweroff:    db "E:poweroff",0
