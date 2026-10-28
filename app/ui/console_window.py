"""Přístupná konzole BIOSu: sériové zrcadlení obrazovky + hlasové čtení."""
import socket
import threading
import time

from PySide6.QtCore import QThread, Qt, Signal, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..bios.protocol import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESC,
    KEY_F10,
    KEY_UP,
    parse_frame,
)
from ..i18n.tr import tr


class SerialReader(QThread):
    frame_ready = Signal(bytes)

    def __init__(self, host, port, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self._stop = False
        self._sock = None
        self._lock = threading.Lock()

    def run(self):
        for _ in range(40):
            try:
                self._sock = socket.create_connection(
                    (self.host, self.port), timeout=2
                )
                break
            except OSError:
                time.sleep(0.05)
        if not self._sock:
            return
        try:
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self._sock.settimeout(0.02)
        buf = bytearray()
        try:
            while not self._stop:
                try:
                    chunk = self._sock.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buf.extend(chunk)
                # zpracuj všechny kompletní framy v bufferu (oddělené 0x03)
                while True:
                    try:
                        idx = buf.index(0x03)
                    except ValueError:
                        break
                    frame = bytes(buf[: idx + 1])
                    del buf[: idx + 1]
                    self.frame_ready.emit(frame)
                # ochrana proti neomezenému růstu při poškozeném streamu
                if len(buf) > 8192:
                    buf.clear()
        finally:
            try:
                self._sock.close()
            except OSError:
                pass

    def send_key(self, key):
        with self._lock:
            try:
                if self._sock:
                    self._sock.sendall(bytes([key]))
            except OSError:
                pass

    def stop(self):
        self._stop = True
        with self._lock:
            try:
                if self._sock:
                    self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.wait(500)


class ConsoleWindow(QWidget):
    boot_requested = Signal(int)
    close_requested = Signal(str)

    def __init__(self, vm, host, port, speaker, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.speaker = speaker
        self.reader = SerialReader(host, port, self)
        self._input_enabled = True
        self._last_announced = ""

        self.setWindowTitle(f"{tr('console.title')} - {vm.name}")
        self.setMinimumSize(520, 360)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlainText(tr("console.waiting_bios"))

        self.speech_check = QCheckBox(tr("console.read_aloud"))
        self.speech_check.setChecked(speaker.enabled)
        self.speech_check.toggled.connect(self._toggle_speech)

        hint = QLabel(tr("hint.keys"))

        top = QHBoxLayout()
        top.addWidget(self.speech_check)
        top.addStretch()
        top.addWidget(QLabel(tr("console.speaking")))

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.output)
        layout.addWidget(hint)

        self.reader.frame_ready.connect(self._on_frame)
        self.reader.start()
        
        # instalace filtru pro zachycení šipek dříve než je zkonzumuje QPlainTextEdit
        self.output.installEventFilter(self)

    def _toggle_speech(self, enabled):
        self.speaker.enabled = enabled
        if not enabled:
            self.speaker.stop()

    def eventFilter(self, watched, event):
        if watched == self.output and event.type() == QEvent.KeyPress:
            if self._handle_key(event.key()):
                return True
        return super().eventFilter(watched, event)

    def _handle_key(self, key):
        mapping = {
            Qt.Key_Up: KEY_UP,
            Qt.Key_Down: KEY_DOWN,
            Qt.Key_Return: KEY_ENTER,
            Qt.Key_Enter: KEY_ENTER,
            Qt.Key_Escape: KEY_ESC,
            Qt.Key_F10: KEY_F10,
        }
        if key in mapping and self._input_enabled:
            self.reader.send_key(mapping[key])
            return True
        return False

    def _on_frame(self, data):
        frame = parse_frame(data)
        lines = [frame.title, ""]
        for item in frame.items:
            sel = "*" if item.selected else " "
            foc = ">" if item.focused else " "
            lines.append(f"{foc} {sel} {item.label}")
        if frame.status:
            lines += ["", frame.status]
        self.output.setPlainText("\n".join(lines))

        ann = frame.announcement()
        # dedup + okamžité přerušení předchozí řeči pro nižší latenci B
        if ann and ann != self._last_announced:
            # drobné zrychlení: pokud je nový text delší, nech preempt proběhnout hned
            self.speaker.say(ann)
        self._last_announced = ann

        if frame.is_event:
            if frame.event.startswith("boot:"):
                device = int(frame.event[5:]) if frame.event[5:].isdigit() else 0
                self.boot_requested.emit(device)
            elif frame.event == "poweroff":
                self.speaker.say(tr("msg.stopped").format(self.vm.name))

    def keyPressEvent(self, event):
        if self._handle_key(event.key()):
            event.accept()
            return
        super().keyPressEvent(event)

    def show_message(self, text):
        self.output.setPlainText(text)
        self.speaker.say(text)

    def disable_input(self):
        self._input_enabled = False

    def enable_input(self):
        self._input_enabled = True

    def closeEvent(self, event):
        self.reader.stop()
        self.close_requested.emit(self.vm.name)
        super().closeEvent(event)