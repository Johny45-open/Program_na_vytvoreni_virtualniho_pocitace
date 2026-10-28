"""Hlavní okno správce virtuálních počítačů."""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..config import VMS_DIR
from ..i18n.tr import lang_manager, tr
from ..vm import qemu as qemu_launcher
from ..vm.manager import VMManager
from .console_window import ConsoleWindow
from .vm_dialog import VMDialog


class _BootWorker(QThread):
    """Worker pro přechod Fáze 1 -> Fáze 2 bez blokování GUI.

    Signály běží na GUI vlákně, samotné QMP/ QEMU volání běží v tomto threadu.
    """
    progress = Signal(str)
    succeeded = Signal(object, int)  # proc, qmp_port
    failed = Signal(str)

    def __init__(self, vm, device, old_proc, old_qmp_port, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.device = device
        self.old_proc = old_proc
        self.old_qmp_port = old_qmp_port

    def run(self):
        try:
            self.progress.emit(tr("console.stopping_phase1"))
            # Fáze 1 je BIOS-only, stačí 1,5 s (původně 4,0 s blokovalo GUI 4 s)
            qemu_launcher.stop_process(self.old_proc, self.old_qmp_port, wait=1.5)
            self.progress.emit(tr("console.starting_phase2"))
            proc2, qmp2 = qemu_launcher.start_phase2(self.vm, self.device)
            # rychlý poll místo fix 0,3 s — qemu.py už polluje 0,35 s, zde jen 0,15 s navíc
            import time
            deadline = time.monotonic() + 0.3
            while time.monotonic() < deadline:
                if proc2.poll() is not None:
                    break
                time.sleep(0.05)
            if proc2.poll() is not None:
                raise RuntimeError(f"QEMU Fáze 2 se neočekávaně ukončil (kód {proc2.returncode}) – zkontroluj display/audio nastavení")
            self.succeeded.emit(proc2, qmp2)
        except Exception as ex:
            self.failed.emit(str(ex))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manager = VMManager(VMS_DIR)
        self.processes = {}
        self.consoles = {}
        self._current_theme = "dark"
        self._boot_worker = None
        self._booting_vm = None

        self.setWindowTitle(tr("app.title"))
        self.resize(720, 460)

        from ..a11y.speaker import Speaker

        self.speaker = Speaker(self)

        self._build_actions()
        self._build_ui()
        self.refresh()

        lang_manager.changed.connect(self._on_language_changed)

    # --- Konstrukce UI ---
    def _build_actions(self):
        self.act_new = QAction(tr("vm.new"), self)
        self.act_new.triggered.connect(self._on_new)
        self.act_edit = QAction(tr("vm.edit"), self)
        self.act_edit.triggered.connect(self._on_edit)
        self.act_delete = QAction(tr("vm.delete"), self)
        self.act_delete.triggered.connect(self._on_delete)
        self.act_start = QAction(tr("vm.start"), self)
        self.act_start.triggered.connect(self._on_start)
        self.act_stop = QAction(tr("vm.stop"), self)
        self.act_stop.triggered.connect(self._on_stop)
        self.act_theme = QAction(tr("settings.dark"), self)
        self.act_theme.triggered.connect(self._on_theme)
        self.act_lang = QAction(tr("settings.english"), self)
        self.act_lang.triggered.connect(self._on_language)

        bar = self.addToolBar(tr("vm.list"))
        bar.setMovable(False)
        for act in (
            self.act_new,
            self.act_edit,
            self.act_delete,
            self.act_start,
            self.act_stop,
            self.act_theme,
            self.act_lang,
        ):
            bar.addAction(act)

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(lambda *_: self._show_details())
        layout.addWidget(self.list)

        self.details = QLabel(tr("vm.none"))
        self.details.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.details)

        self.setCentralWidget(central)
        self.statusBar().showMessage(tr("status.ready"))

    # --- Seznam VM ---
    def refresh(self):
        self.list.clear()
        for vm in self.manager.list_vms():
            item = QListWidgetItem(vm.name)
            item.setData(Qt.UserRole, vm.name)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._show_details()

    def _selected_name(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _show_details(self):
        name = self._selected_name()
        if not name:
            self.details.setText(tr("vm.none"))
            return
        vm = self.manager.get(name)
        if not vm:
            return
        state = self.manager.state(name)
        state_text = {
            "stopped": tr("state.stopped"),
            "running": tr("state.running"),
            "error": tr("state.error"),
        }.get(state, state)
        sound_enabled = getattr(vm, "sound_enabled", True)
        sound_card = getattr(vm, "sound_card", "intel-hda")
        sound_text = tr(f"sound.{sound_card}") if sound_enabled else tr("sound.disabled")
        # pokročilé A/V info
        audio_driver = getattr(vm, "audio_driver", "auto")
        latency = getattr(vm, "audio_latency_ms", 20)
        timer = getattr(vm, "audio_timer_period", 5000)
        disp = getattr(vm, "display_driver", "auto")
        gl_txt = "GL:on" if getattr(vm, "display_gl", True) else "GL:off"
        vsync_txt = "VSync:on" if getattr(vm, "display_vsync", False) else "VSync:off"
        if sound_enabled and (audio_driver != "auto" or latency != 20 or timer != 5000):
            av_text = f"{audio_driver}, {latency}ms/{timer}µs"
        else:
            av_text = audio_driver if sound_enabled else "-"
        # boot status (prázdný disk / ISO)
        import os
        try:
            from ..config import VMS_DIR as _VMS_DIR
            disk_path = os.path.join(_VMS_DIR, vm.disk_file)
            disk_ok = qemu_launcher.is_disk_bootable(disk_path)
            iso_ok = qemu_launcher.is_iso_available(vm)
        except Exception:
            disk_ok = False
            iso_ok = False
        if disk_ok:
            disk_status = tr("msg.disk_bootable")
        else:
            disk_status = tr("msg.disk_empty_hint")
        if vm.iso:
            iso_status = tr("msg.iso_ok") if iso_ok else tr("msg.iso_missing_short")
            iso_line = f"{vm.iso} ({iso_status})"
        else:
            iso_line = f"- ({tr('msg.iso_missing_short')})"
        self.details.setText(
            f"{vm.name}\n"
            f"{tr('field.memory')}: {vm.memory_mb}\n"
            f"{tr('field.cpus')}: {vm.cpus}\n"
            f"{tr('field.disk')}: {vm.disk_size_gb} [{disk_status}]\n"
            f"{tr('field.iso')}: {iso_line}\n"
            f"{tr('field.sound_card')}: {sound_text} ({av_text})\n"
            f"{tr('field.display')}: {disp} {gl_txt} {vsync_txt}\n"
            f"{tr('vm.list')}: {state_text}"
        )

    # --- Akce ---
    def _on_new(self):
        dlg = VMDialog(self)
        if dlg.exec():
            vm = dlg.result_vm()
            if self.manager.get(vm.name):
                QMessageBox.warning(
                    self, tr("app.title"), tr("err.name_required")
                )
                return
            self.manager.save(vm)
            self.refresh()

    def _on_edit(self):
        name = self._selected_name()
        vm = self.manager.get(name)
        if not vm:
            return
        dlg = VMDialog(self, vm)
        if dlg.exec():
            self.manager.delete(name)
            self.manager.save(dlg.result_vm())
            self.refresh()

    def _on_delete(self):
        name = self._selected_name()
        if not name:
            return
        if self.manager.state(name) == "running":
            QMessageBox.warning(self, tr("app.title"), tr("vm.stop"))
            return
        if QMessageBox.question(
            self, tr("app.title"), tr("err.delete_confirm").format(name)
        ) != QMessageBox.Yes:
            return
        self.manager.delete(name)
        self.refresh()

    def _on_start(self):
        vm = self.manager.get(self._selected_name())
        if not vm:
            return
        self.statusBar().showMessage(tr("msg.starting").format(vm.name))
        try:
            qemu_launcher.ensure_disk(vm)
        except Exception as ex:
            QMessageBox.critical(
                self, tr("app.title"), tr("err.ensure_disk").format(ex)
            )
            return
        try:
            proc, serial_port, qmp_port = qemu_launcher.start_phase1(vm)
        except Exception as ex:
            QMessageBox.critical(
                self, tr("app.title"), tr("err.start_failed").format(ex)
            )
            return
        self.manager.set_state(vm.name, "running")
        self.processes[vm.name] = (proc, qmp_port)

        console = ConsoleWindow(vm, "127.0.0.1", serial_port, self.speaker)
        console.boot_requested.connect(
            lambda dev, vm=vm, c=console: self._boot_phase2(vm, dev, c)
        )
        console.close_requested.connect(self._on_console_closed)
        self.consoles[vm.name] = console
        console.show()
        self.refresh()

    def _boot_phase2(self, vm, device, console):
        # guard proti dvojímu F10 / šumu
        if self._boot_worker is not None and self._boot_worker.isRunning():
            return
        if vm.name not in self.processes:
            return
        # --- Validace + fallback pro prázdný disk / chybějící ISO (oboji) ---
        orig_device = device
        iso_ok = qemu_launcher.is_iso_available(vm)
        import os as _os
        from ..config import VMS_DIR as _VMS_DIR2
        disk_path = _os.path.join(_VMS_DIR2, vm.disk_file)
        try:
            disk_ok = qemu_launcher.is_disk_bootable(disk_path)
        except Exception:
            disk_ok = False

        # a) boot z CDROM ale ISO chybí -> varování, nepřepínat automaticky na disk pokud je také prázdný
        if device == qemu_launcher.BOOT_CDROM and not iso_ok:
            msg = tr("warn.iso_missing_body").format(vm.iso or "-")
            console.show_message(msg)
            self.speaker.say(msg)
            if not disk_ok:
                msg2 = tr("err.no_bootable")
                QMessageBox.warning(self, tr("warn.empty_disk_title"), msg2)
                console.show_message(msg2)
                return
            ret = QMessageBox.question(
                self, tr("warn.empty_disk_title"), msg + "\n\n" + tr("err.disk_empty") + " " + tr("device.disk") + " je k dispozici. Bootovat z disku?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if ret == QMessageBox.Yes:
                device = qemu_launcher.BOOT_DISK
            else:
                return

        # b) boot z disku ale disk prázdný -> varování + auto-fallback na ISO pokud existuje
        if device == qemu_launcher.BOOT_DISK and not disk_ok:
            if iso_ok:
                msg = tr("warn.empty_disk_body").format(vm.name, vm.iso)
                ret = QMessageBox.question(
                    self, tr("warn.empty_disk_title"), msg,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
                )
                if ret == QMessageBox.Yes:
                    device = qemu_launcher.BOOT_CDROM
                    fallback_msg = tr("warn.fallback_to_cdrom")
                    console.show_message(fallback_msg)
                    self.speaker.say(fallback_msg)
            else:
                msg = tr("err.no_bootable")
                QMessageBox.warning(self, tr("warn.empty_disk_title"), msg)
                console.show_message(msg)
                self.speaker.say(msg)
                return

        # c) obecný fallback helper
        resolved, did_fallback = qemu_launcher.resolve_boot_device(vm, device)
        if did_fallback and resolved == qemu_launcher.BOOT_CDROM and orig_device == qemu_launcher.BOOT_DISK:
            device = resolved

        device_name = {
            qemu_launcher.BOOT_DISK: tr("device.disk"),
            qemu_launcher.BOOT_CDROM: tr("device.cdrom"),
            qemu_launcher.BOOT_NETWORK: tr("device.network"),
        }.get(device, tr("device.disk"))
        console.disable_input()
        console.show_message(tr("console.boot_started").format(device_name))
        self.statusBar().showMessage(tr("console.boot_started").format(device_name))
        self.speaker.say(tr("console.boot_started").format(device_name))

        proc, qmp_port = self.processes.get(vm.name, (None, None))
        # async bez blokování GUI – progress hlášky místo 0,5-5 s „nic"
        self._booting_vm = vm
        worker = _BootWorker(vm, device, proc, qmp_port, self)
        self._boot_worker = worker

        def _on_progress(text):
            # ponech konzoli živou během čekání (původně GUI zamrzlo na sleep)
            if vm.name in self.consoles:
                self.consoles[vm.name].show_message(text)
            self.statusBar().showMessage(text)
            self.speaker.say(text)

        def _on_success(p2, q2):
            self.processes[vm.name] = (p2, q2)
            if vm.name in self.consoles:
                self.consoles[vm.name].show_message(tr("console.boot_phase2"))
            self.statusBar().showMessage(tr("console.boot_phase2"))
            self.speaker.say(tr("console.boot_phase2"))
            self.manager.set_state(vm.name, "running")
            self.refresh()
            self._boot_worker = None
            self._booting_vm = None

        def _on_failed(err):
            if vm.name in self.consoles:
                self.consoles[vm.name].show_message(tr("err.start_failed").format(err))
                # po neúspěchu fáze 2 umožni znovu vybrat zařízení (Fáze 1 už je ukončena)
                try:
                    self.consoles[vm.name]._input_enabled = True
                except Exception:
                    pass
            QMessageBox.critical(self, tr("app.title"), tr("err.start_failed").format(err))
            self.processes.pop(vm.name, None)
            self.manager.set_state(vm.name, "error")
            self.refresh()
            self._boot_worker = None
            self._booting_vm = None

        worker.progress.connect(_on_progress)
        worker.succeeded.connect(_on_success)
        worker.failed.connect(_on_failed)
        worker.start()

    def _on_console_closed(self, name):
        # pokud ještě běží boot worker pro tuto VM, počkej na dokončení nebo ho ukonči
        if self._boot_worker is not None and self._booting_vm is not None and self._booting_vm.name == name:
            try:
                self._boot_worker.wait(500)
            except Exception:
                pass
            self._boot_worker = None
            self._booting_vm = None
        if name in self.consoles:
            self.consoles.pop(name, None)
        self._stop_vm(name)
        self.refresh()

    def _on_stop(self):
        name = self._selected_name()
        if name:
            if name in self.consoles:
                self.consoles[name].close()
            else:
                self._stop_vm(name)
            self.refresh()

    def _stop_vm(self, name):
        proc, qmp_port = self.processes.pop(name, (None, None))
        if proc is not None:
            # pro Fázi 2 (OS) je bezpečnější delší flush, proto explicitně 4 s
            try:
                import os as _os
                from ..config import VMS_DIR as _VMS
                # heuristika: pokud je VM známá a disk bootovatelný, jde o OS -> delší wait
                wait = 4.0
            except Exception:
                wait = 1.5
            qemu_launcher.stop_process(proc, qmp_port, wait=wait)
        self.manager.set_state(name, "stopped")
        self.statusBar().showMessage(tr("msg.stopped").format(name))

    # --- Motiv a jazyk ---
    def _on_theme(self):
        from .styles import THEMES

        self._current_theme = "light" if self._current_theme == "dark" else "dark"
        self.act_theme.setText(
            tr("settings.dark")
            if self._current_theme == "light"
            else tr("settings.light")
        )
        self.window().setStyleSheet(THEMES[self._current_theme])

    def _on_language(self):
        target = "cs" if lang_manager.lang == "en" else "en"
        lang_manager.set_language(target)

    def _on_language_changed(self, lang):
        self.speaker.set_language(lang)
        self.act_lang.setText(
            tr("settings.czech") if lang == "en" else tr("settings.english")
        )
        self.act_theme.setText(
            tr("settings.dark")
            if self._current_theme == "light"
            else tr("settings.light")
        )
        self.act_new.setText(tr("vm.new"))
        self.act_edit.setText(tr("vm.edit"))
        self.act_delete.setText(tr("vm.delete"))
        self.act_start.setText(tr("vm.start"))
        self.act_stop.setText(tr("vm.stop"))
        self.setWindowTitle(tr("app.title"))
        self._show_details()

    def closeEvent(self, event):
        for name in list(self.processes):
            self._stop_vm(name)
        super().closeEvent(event)
