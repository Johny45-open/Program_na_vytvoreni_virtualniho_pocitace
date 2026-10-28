;========================================================================
;  menu.asm - ovládání menu BIOSu
;========================================================================

;--- Inicializace stavu menu ---
menu_init:
    mov byte [es:current_screen], 0
    mov byte [es:selected_index], 0
    mov byte [es:boot_device], 0
    mov byte [es:lang], 0
    mov byte [es:screen_dirty], 1
    mov byte [es:await_boot], 0
    ret

;--- Zpracovat klávesu (Vstup: AL = interní kód klávesy) ---
menu_handle_key:
    cmp al, KEY_UP
    je .up
    cmp al, KEY_DOWN
    je .down
    cmp al, KEY_ENTER
    je .enter
    cmp al, KEY_ESC
    je .esc
    cmp al, KEY_F10
    je .f10
    ret

.up:
    call screen_count
    cmp byte [es:selected_index], 0
    jne .up_dec
    mov al, cl
    dec al
    mov [es:selected_index], al
    jmp .changed
.up_dec:
    dec byte [es:selected_index]
    jmp .changed

.down:
    call screen_count
    mov al, [es:selected_index]
    inc al
    cmp al, cl
    jb .down_ok
    xor al, al
.down_ok:
    mov [es:selected_index], al
    jmp .changed

.esc:
    cmp byte [es:current_screen], 1
    jne .changed
    mov byte [es:current_screen], 0
    mov byte [es:selected_index], 1
    jmp .changed

.enter:
    cmp byte [es:await_boot], 0
    jne .changed
    cmp byte [es:current_screen], 0
    jne .enter_device
    mov al, [es:selected_index]
    cmp al, 0
    je .boot
    cmp al, 1
    je .goto_device
    cmp al, 2
    je .toggle_lang
    cmp al, 3
    je .power_off
    ret

.enter_device:
    mov al, [es:selected_index]
    call item_value
    mov [es:boot_device], al
    mov byte [es:current_screen], 0
    mov byte [es:selected_index], 0
    jmp .changed

.goto_device:
    mov byte [es:current_screen], 1
    mov byte [es:selected_index], 0
    jmp .changed

.toggle_lang:
    xor byte [es:lang], 1
    jmp .changed

.boot:
    cmp byte [es:await_boot], 1
    je .changed
    mov byte [es:current_screen], 2
    mov byte [es:selected_index], 0
    mov byte [es:await_boot], 1
    call vga_render
    call build_boot_event
    mov si, event_buf
    call serial_event
    mov byte [es:screen_dirty], 0
.wait:
    call key_poll
    test al, al
    jz .wait_idle
    cmp al, KEY_ESC
    je .boot_cancel
    ; během čekání na hosta ignoruj ostatní klávesy (zůstaň v čekání)
    jmp .wait_idle
.wait_idle:
    call delay_short
    jmp .wait
.boot_cancel:
    mov byte [es:await_boot], 0
    mov byte [es:current_screen], 0
    mov byte [es:selected_index], 0
    jmp .changed

.power_off:
    mov byte [es:current_screen], 3
    mov byte [es:selected_index], 0
    call vga_render
    mov si, event_poweroff
    call serial_event
    mov byte [es:screen_dirty], 0
.halt:
    cli
    hlt
    jmp .halt

.f10:
    cmp byte [es:await_boot], 1
    je .changed
    jmp .boot

.changed:
    mov byte [es:screen_dirty], 1
    ret