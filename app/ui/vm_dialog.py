"""Dialog pro vytvoření a úpravu virtuálního počítače."""
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..i18n.tr import tr
from ..vm.models import VMSpec


class VMDialog(QDialog):
    SOUND_CARDS = [
        ("intel-hda", "sound.intel-hda"),
        ("sb16", "sound.sb16"),
        ("ac97", "sound.ac97"),
        ("pcspk", "sound.pcspk"),
    ]
    AUDIO_DRIVERS = [
        ("auto", "audio.auto"),
        ("wasapi", "audio.wasapi"),
        ("dsound", "audio.dsound"),
    ]
    DISPLAY_DRIVERS = [
        ("auto", "display.auto"),
        ("sdl", "display.sdl"),
        ("gtk", "display.gtk"),
        ("none", "display.none"),
    ]

    def __init__(self, parent=None, vm=None):
        super().__init__(parent)
        self.vm = vm
        title = tr("dlg.edit_title") if vm else tr("dlg.new_title")
        self.setWindowTitle(title)
        self.setMinimumWidth(480)

        self.name_edit = QLineEdit()
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(256, 65536)
        self.memory_spin.setSingleStep(256)
        self.cpus_spin = QSpinBox()
        self.cpus_spin.setRange(1, 16)
        self.disk_spin = QSpinBox()
        self.disk_spin.setRange(1, 1024)
        self.iso_edit = QLineEdit()
        browse = QPushButton(tr("action.browse"))
        browse.clicked.connect(self._browse)

        self.sound_check = QCheckBox(tr("field.sound"))
        self.sound_check.setChecked(True)
        self.sound_combo = QComboBox()
        for code, key in self.SOUND_CARDS:
            self.sound_combo.addItem(tr(key), code)

        # --- Pokročilé A/V: konfigurovatelná latence ---
        self.audio_driver_combo = QComboBox()
        for code, key in self.AUDIO_DRIVERS:
            self.audio_driver_combo.addItem(tr(key), code)

        self.audio_latency_spin = QSpinBox()
        self.audio_latency_spin.setRange(10, 50)
        self.audio_latency_spin.setSingleStep(5)
        self.audio_latency_spin.setSuffix(" ms")
        self.audio_latency_spin.setValue(20)

        self.audio_timer_spin = QSpinBox()
        self.audio_timer_spin.setRange(2000, 10000)
        self.audio_timer_spin.setSingleStep(500)
        self.audio_timer_spin.setSuffix(" µs")
        self.audio_timer_spin.setValue(5000)

        self.display_combo = QComboBox()
        for code, key in self.DISPLAY_DRIVERS:
            self.display_combo.addItem(tr(key), code)

        self.gl_check = QCheckBox(tr("field.display_gl"))
        self.gl_check.setChecked(True)
        self.vsync_check = QCheckBox(tr("field.display_vsync"))
        self.vsync_check.setChecked(False)

        # propojení povolení
        self.sound_check.toggled.connect(self.sound_combo.setEnabled)
        self.sound_check.toggled.connect(self.audio_driver_combo.setEnabled)
        self.sound_check.toggled.connect(self.audio_latency_spin.setEnabled)
        self.sound_check.toggled.connect(self.audio_timer_spin.setEnabled)

        form = QFormLayout()
        form.addRow(tr("field.name"), self.name_edit)
        form.addRow(tr("field.memory"), self.memory_spin)
        form.addRow(tr("field.cpus"), self.cpus_spin)
        form.addRow(tr("field.disk"), self.disk_spin)
        form.addRow(tr("field.iso"), self.iso_edit)
        form.addRow(browse)
        form.addRow(self.sound_check)
        form.addRow(tr("field.sound_card"), self.sound_combo)

        # skupina pokročilé
        adv_group = QGroupBox(tr("group.advanced_av"))
        adv_group.setCheckable(True)
        adv_group.setChecked(False)
        adv_form = QFormLayout(adv_group)
        adv_form.addRow(tr("field.audio_driver"), self.audio_driver_combo)
        adv_form.addRow(tr("field.audio_latency"), self.audio_latency_spin)
        adv_form.addRow(tr("field.audio_timer"), self.audio_timer_spin)
        adv_form.addRow(tr("field.display"), self.display_combo)
        adv_form.addRow(self.gl_check)
        adv_form.addRow(self.vsync_check)
        # tooltip pro latenci
        self.audio_latency_spin.setToolTip("Nižší = menší zpoždění obrazu↔zvuk, ale riziko praskání. Doporučeno 15-25 ms.")
        self.audio_timer_spin.setToolTip("Periody QEMU audiodev (µs). Nižší = menší latence, vyšší CPU.")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        ok = buttons.button(QDialogButtonBox.Ok)
        ok.setText(tr("action.save") if vm else tr("action.create"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("action.cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(adv_group)
        layout.addWidget(buttons)

        if vm:
            self.name_edit.setText(vm.name)
            self.memory_spin.setValue(vm.memory_mb)
            self.cpus_spin.setValue(vm.cpus)
            self.disk_spin.setValue(vm.disk_size_gb)
            self.iso_edit.setText(vm.iso)
            sound_enabled = getattr(vm, "sound_enabled", True)
            sound_card = getattr(vm, "sound_card", "intel-hda")
            self.sound_check.setChecked(sound_enabled)
            self.sound_combo.setEnabled(sound_enabled)
            self.audio_driver_combo.setEnabled(sound_enabled)
            self.audio_latency_spin.setEnabled(sound_enabled)
            self.audio_timer_spin.setEnabled(sound_enabled)
            idx = self.sound_combo.findData(sound_card)
            if idx >= 0:
                self.sound_combo.setCurrentIndex(idx)
            # pokročilé hodnoty
            driver = getattr(vm, "audio_driver", "auto")
            idx2 = self.audio_driver_combo.findData(driver)
            if idx2 >= 0:
                self.audio_driver_combo.setCurrentIndex(idx2)
            self.audio_latency_spin.setValue(int(getattr(vm, "audio_latency_ms", 20)))
            self.audio_timer_spin.setValue(int(getattr(vm, "audio_timer_period", 5000)))
            disp = getattr(vm, "display_driver", "auto")
            idx3 = self.display_combo.findData(disp)
            if idx3 >= 0:
                self.display_combo.setCurrentIndex(idx3)
            self.gl_check.setChecked(bool(getattr(vm, "display_gl", True)))
            self.vsync_check.setChecked(bool(getattr(vm, "display_vsync", False)))
            # otevři pokročilé pokud není default
            if driver != "auto" or disp != "auto" or getattr(vm, "audio_latency_ms", 20) != 20:
                adv_group.setChecked(True)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("field.iso"), "", "ISO obrazy (*.iso);;Všechny soubory (*)"
        )
        if path:
            self.iso_edit.setText(path)

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, tr("app.title"), tr("err.name_required"))
            return
        # varování: velký nový disk bez ISO bude prázdný -> vyžaduje instalaci
        iso_text = self.iso_edit.text().strip()
        import os
        iso_ok = bool(iso_text and os.path.exists(iso_text) and os.path.getsize(iso_text) >= 1024 * 1024) if iso_text else False
        if not iso_ok and self.disk_spin.value() >= 10:
            # jen informační hint, neblokuje vytvoření
            ret = QMessageBox.question(
                self, tr("warn.empty_disk_title"),
                tr("err.disk_empty") + "\n" + tr("err.no_bootable") + "\n\nPokračovat bez ISO?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if ret != QMessageBox.Yes:
                return
        self.accept()

    def result_vm(self):
        return VMSpec(
            name=self.name_edit.text().strip(),
            memory_mb=self.memory_spin.value(),
            cpus=self.cpus_spin.value(),
            disk_size_gb=self.disk_spin.value(),
            iso=self.iso_edit.text().strip(),
            sound_enabled=self.sound_check.isChecked(),
            sound_card=self.sound_combo.currentData(),
            audio_driver=self.audio_driver_combo.currentData(),
            audio_timer_period=self.audio_timer_spin.value(),
            audio_latency_ms=self.audio_latency_spin.value(),
            display_driver=self.display_combo.currentData(),
            display_gl=self.gl_check.isChecked(),
            display_vsync=self.vsync_check.isChecked(),
        )
