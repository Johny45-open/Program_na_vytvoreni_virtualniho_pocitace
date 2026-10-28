"""Přístupnost: hlasové čtení obrazovky BIOSu – nízká latence."""
from PySide6.QtCore import QLocale, QObject, QTimer
from PySide6.QtTextToSpeech import QTextToSpeech


class Speaker(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self._tts = QTextToSpeech(self)
        self._pending_text = None
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.timeout.connect(self._flush_pending)
        self.set_language("cs")

    def set_language(self, lang):
        if lang == "cs":
            self._tts.setLocale(QLocale(QLocale.Czech, QLocale.CzechRepublic))
        else:
            self._tts.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))

    def say(self, text):
        if not self.enabled or not text:
            return
        # Okamžitě přeruš předchozí řeč a naplánuj novou s minimálním zpožděním
        # (zabraňuje queue v SAPI, která přidává 100-300ms)
        try:
            if self._tts.state() == QTextToSpeech.Speaking:
                self._tts.stop()
        except Exception:
            try:
                self._tts.stop()
            except Exception:
                pass
        # Zruš předchozí pending a nahraď novým – nejnovější frame má prioritu
        self._pending_text = text
        # 10ms je dost pro zpracování stop(), ale výrazně méně než SAPI queue
        if self._pending_timer.isActive():
            self._pending_timer.stop()
        self._pending_timer.start(10)

    def _flush_pending(self):
        if self.enabled and self._pending_text:
            text = self._pending_text
            self._pending_text = None
            try:
                self._tts.say(text)
            except Exception:
                pass

    def stop(self):
        self._pending_text = None
        if self._pending_timer.isActive():
            self._pending_timer.stop()
        try:
            self._tts.stop()
        except Exception:
            pass
