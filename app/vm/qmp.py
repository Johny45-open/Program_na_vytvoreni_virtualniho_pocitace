"""Minimální klient protokolu QEMU Monitor Protocol (QMP)."""
import json
import socket


class QMPError(Exception):
    pass


class QMPClient:
    def __init__(self, host="127.0.0.1", port=0, timeout=5):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._file = self._sock.makefile("rb")
        self._recv()  # uvítací zpráva
        self.cmd("qmp_capabilities")

    def _recv(self):
        while True:
            line = self._file.readline()
            if not line:
                raise QMPError("QMP spojení ukončeno")
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    def cmd(self, name, **kwargs):
        msg = {"execute": name}
        if kwargs:
            msg["arguments"] = kwargs
        self._sock.sendall(json.dumps(msg).encode() + b"\n")
        while True:
            reply = self._recv()
            if "error" in reply:
                raise QMPError(reply["error"].get("desc", str(reply["error"])))
            if "return" in reply:
                return reply["return"]

    def system_powerdown(self):
        self.cmd("system_powerdown")

    def close(self):
        try:
            self._file.close()
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass