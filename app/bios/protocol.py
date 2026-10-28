"""Protokol vlastního BIOSu: kódy kláves, snímky a události."""
from dataclasses import dataclass, field

KEY_UP = 0x01
KEY_DOWN = 0x02
KEY_ENTER = 0x0D
KEY_ESC = 0x1B
KEY_TAB = 0x09
KEY_F1 = 0x80
KEY_F2 = 0x81
KEY_F5 = 0x82
KEY_F10 = 0x83

FRAME_START = 0x0C
FRAME_END = 0x03

BOOT_DISK = 0
BOOT_CDROM = 1
BOOT_NETWORK = 2


@dataclass
class MenuItem:
    index: int
    label: str
    selected: bool = False
    focused: bool = False


@dataclass
class ScreenFrame:
    title: str = ""
    items: list = field(default_factory=list)
    status: str = ""
    event: str = ""

    @property
    def is_event(self):
        return bool(self.event)

    def focused_label(self):
        for item in self.items:
            if item.focused:
                return item.label
        return self.title

    def announcement(self):
        parts = [self.title]
        if self.event:
            parts.append(self.event)
        else:
            for item in self.items:
                if item.focused:
                    parts.append(item.label)
                    break
            if not self.items and self.status:
                parts.append(self.status)
        return " ".join(p for p in parts if p)


def parse_frame(data: bytes) -> ScreenFrame:
    text = data.decode("utf-8", errors="replace")
    frame = ScreenFrame()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("T:"):
            frame.title = line[2:].strip()
        elif line.startswith("S:"):
            frame.status = line[2:].strip()
        elif line.startswith("M:"):
            parts = line[2:].split("|")
            if len(parts) >= 4:
                frame.items.append(
                    MenuItem(
                        index=int(parts[0]) if parts[0].isdigit() else -1,
                        label=parts[1],
                        selected=parts[2] == "1",
                        focused=parts[3] == "1",
                    )
                )
        elif line.startswith("E:"):
            frame.event = line[2:].strip()
    return frame