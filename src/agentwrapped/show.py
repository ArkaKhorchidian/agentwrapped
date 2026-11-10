"""Animated terminal story: one stat per screen, numbers counting up in block digits."""
from __future__ import annotations

import time

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

GLYPHS = {
    "0": ["▄▀▀▄", "█  █", "▀▄▄▀"], "1": [" ▄█ ", "  █ ", " ▄█▄"], "2": ["▄▀▀▄", "  ▄▀", "▄█▄▄"],
    "3": ["▀▀▀█", " ▀▀▄", "▄▄▄▀"], "4": ["█  █", "▀▀▀█", "   █"], "5": ["█▀▀▀", "▀▀▀▄", "▄▄▄▀"],
    "6": ["▄▀▀ ", "█▄▄ ", "▀▄▄▀"], "7": ["▀▀▀█", "  █ ", " █  "], "8": ["▄▀▀▄", "▄▀▀▄", "▀▄▄▀"],
    "9": ["▄▀▀▄", "▀▄▄█", " ▄▄▀"], ",": ["  ", "  ", "▄▀"], ".": [" ", " ", "▄"], ":": [" ", "▀", "▀"],
    "%": ["▀ ▄▀", " ▄▀ ", "▄▀ ▄"], " ": ["  ", "  ", "  "], "-": ["   ", "▀▀▀", "   "],
}


def big(text: str, style: str) -> Text:
    rows = ["", "", ""]
    for ch in text:
        g = GLYPHS.get(ch)
        if g is None:
            continue
        for i in range(3):
            rows[i] += g[i] + " "
    return Text("\n".join(r.rstrip() for r in rows), style=style, justify="center")


def headline_text(text: str, style: str, max_width: int) -> Text:
    """Large FIGlet lettering when it fits, plain bold text otherwise. Times/numbers use block digits."""
    import re

    m = re.fullmatch(r"([\d:,.%]+)\s*(am|pm)?", text.strip())
    if m:
        out = big(m.group(1), style)
        if m.group(2):
            out.append("\n" + m.group(2), style=style)
        return out
    try:
        import pyfiglet

        art = pyfiglet.figlet_format(text, font="future", width=1000).rstrip("\n")
        if art.strip() and max(len(l) for l in art.splitlines()) <= max_width:
            return Text(art, style=style, justify="center")
    except Exception:  # missing glyphs, missing font: fall back to plain text
        pass
    return Text(text, style=style, justify="center")


class Story:
    def __init__(self, console: Console, accent: str = "#ff6b57", speed: float = 1.0, animate: bool = True):
        self.c, self.accent, self.speed, self.animate = console, accent, speed, animate

    def _panel(self, label: str, body, caption: str = "") -> Panel:
        parts = [Text(label.upper(), style="bold #a09cbe", justify="center"), Text(""), body]
        if caption:
            parts += [Text(""), Text(caption, style="#d8d4f0", justify="center")]
        height = max(13, self.c.size.height - 2)
        return Panel(Align.center(Group(*parts), vertical="middle"), border_style=self.accent, height=height)

    def number(self, label: str, value: int, caption: str = "", fmt: str = "{:,}", hold: float = 2.2) -> None:
        if not self.animate:
            return
        steps = 28
        with Live(self._panel(label, big(fmt.format(0), f"bold {self.accent}")), console=self.c,
                  refresh_per_second=40, transient=True, screen=True) as live:
            for i in range(1, steps + 1):
                v = round(value * (1 - (1 - i / steps) ** 3))  # ease-out
                live.update(self._panel(label, big(fmt.format(v), f"bold {self.accent}"),
                                        caption if i == steps else ""))
                time.sleep(0.9 / steps / self.speed)
            time.sleep(hold / self.speed)

    def words(self, label: str, headline: str, caption: str = "", hold: float = 2.4) -> None:
        if not self.animate:
            return
        with Live(self._panel(label, Text("")), console=self.c, refresh_per_second=40, transient=True,
                  screen=True) as live:
            shown = ""
            for ch in headline:
                shown += ch
                live.update(self._panel(label, Text(shown, style=f"bold {self.accent}", justify="center")))
                time.sleep(0.035 / self.speed)
            live.update(self._panel(label, headline_text(headline, f"bold {self.accent}", self.c.size.width - 8),
                                    caption))
            time.sleep(hold / self.speed)

    def bars(self, label: str, rows: list[tuple[str, int]], caption: str = "", hold: float = 2.6) -> None:
        if not self.animate or not rows:
            return
        mx = max(v for _, v in rows) or 1
        w = max(10, min(46, self.c.size.width - 40))
        nw = max(len(n) for n, _ in rows)
        with Live(self._panel(label, Text("")), console=self.c, refresh_per_second=40, transient=True,
                  screen=True) as live:
            for step in range(1, 21):
                t = Text(justify="left")
                for name, v in rows:
                    n = round(w * v / mx * step / 20)
                    t.append(f"{name:>{nw}}  ", style="bold #f5f3ff")
                    t.append("█" * n, style=self.accent)
                    t.append(f" {round(v * step / 20):,}\n", style="#a09cbe")
                live.update(self._panel(label, Align.center(t), caption if step == 20 else ""))
                time.sleep(0.025 / self.speed)
            time.sleep(hold / self.speed)
