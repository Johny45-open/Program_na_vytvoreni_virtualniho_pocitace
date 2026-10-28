;========================================================================
;  strings.asm - řetězce rozhraní (čeština / angličtina)
;  Text je v UTF-8; sériový port odesílá UTF-8, VGA převádí na ASCII.
;========================================================================

;--- Titulky ---
title_main_cs:    db "Vlastní BIOS - Nastavení",0
title_main_en:    db "Custom BIOS - Setup",0
title_device_cs:  db "Výběr spouštěcího zařízení",0
title_device_en:  db "Select boot device",0
title_boot_cs:    db "Spouštím systém...",0
title_boot_en:    db "Booting system...",0
title_power_cs:   db "Vypínám počítač...",0
title_power_en:   db "Powering off...",0

;--- Stavové řádky ---
status_main_cs:   db "Šipky: výběr   Enter: potvrzení   F10: spustit systém",0
status_main_en:   db "Arrows: select   Enter: confirm   F10: boot",0
status_device_cs: db "Vyberte zařízení, ze kterého se systém spustí",0
status_device_en: db "Choose the device to boot from",0
status_boot_cs:   db "Čekám na řízení aplikací...",0
status_boot_en:   db "Waiting for application control...",0

;--- Položky hlavního menu ---
item_boot_cs:     db "Pokračovat ve spuštění systému",0
item_boot_en:     db "Continue booting the system",0
item_device_cs:   db "Vybrat spouštěcí zařízení",0
item_device_en:   db "Select boot device",0
item_lang_cs:     db "Jazyk: čeština",0
item_lang_en:     db "Language: English",0
item_power_cs:    db "Vypnout počítač",0
item_power_en:    db "Power off computer",0

;--- Položky výběru zařízení ---
item_disk_cs:     db "Pevný disk",0
item_disk_en:     db "Hard disk",0
item_cdrom_cs:    db "CD/DVD (ISO)",0
item_cdrom_en:    db "CD/DVD (ISO)",0
item_net_cs:      db "Síť (PXE)",0
item_net_en:      db "Network (PXE)",0

;--- Dvojice (čeština, angličtina) ---
title_main_pair:   dw title_main_cs,   title_main_en
title_device_pair: dw title_device_cs, title_device_en
title_boot_pair:   dw title_boot_cs,   title_boot_en
title_power_pair:  dw title_power_cs,  title_power_en

status_main_pair:   dw status_main_cs,   status_main_en
status_device_pair: dw status_device_cs, status_device_en
status_boot_pair:   dw status_boot_cs,   status_boot_en

;--- Tabulky položek menu (4 bajty na položku: cs, en) ---
main_items:
    dw item_boot_cs,   item_boot_en
    dw item_device_cs, item_device_en
    dw item_lang_cs,   item_lang_en
    dw item_power_cs,  item_power_en
main_items_count: equ 4

device_items:
    dw item_disk_cs,  item_disk_en
    dw item_cdrom_cs, item_cdrom_en
    dw item_net_cs,   item_net_en
device_items_count: equ 3

;--- Hodnoty položek výběru zařízení ---
device_values: db 0,1,2
