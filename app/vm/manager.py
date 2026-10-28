"""Správa uložených virtuálních počítačů (JSON v adresáři vms/)."""
import json
import os

from .models import VMSpec


class VMManager:
    def __init__(self, directory):
        self.dir = directory
        os.makedirs(self.dir, exist_ok=True)
        self._state = {}

    def _path(self, name):
        safe = "".join(c for c in name if c.isalnum() or c in "._- ")
        return os.path.join(self.dir, f"{safe.strip().replace(' ', '_')}.json")

    def list_vms(self):
        vms = []
        for fn in sorted(os.listdir(self.dir)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.dir, fn), encoding="utf-8") as f:
                    vms.append(VMSpec.from_dict(json.load(f)))
            except (OSError, ValueError):
                continue
        return vms

    def get(self, name):
        for vm in self.list_vms():
            if vm.name == name:
                return vm
        return None

    def save(self, vm):
        with open(self._path(vm.name), "w", encoding="utf-8") as f:
            json.dump(vm.to_dict(), f, ensure_ascii=False, indent=2)

    def delete(self, name):
        try:
            os.remove(self._path(name))
        except OSError:
            pass

    def state(self, name):
        return self._state.get(name, "stopped")

    def set_state(self, name, state):
        self._state[name] = state