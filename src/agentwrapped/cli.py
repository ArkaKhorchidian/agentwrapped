"""agentwrapped: Spotify Wrapped for your AI coding agents, from the logs on your machine."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__, agentlogs, card
from .show import Story
from .stats import Wrapped, clock12, compute

ACCENT = "#ff8a3d"
DIM = "#a09cbe"


def human(n: int) -> str:
    for size, unit in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if n >= size * (10 if unit == "k" else 1):
            v = n / size
            return f"{v:.0f}{unit}" if v >= 100 else f"{v:.1f}{unit}"
    return f"{n:,}"


def story(w: Wrapped, s: Story) -> None:
    s.words("agentwrapped", f"Your {w.year} with AI", "Reading your agents' logs. Nothing leaves this machine.", hold=1.8)
    s.number("prompts sent", w.prompts, f"across {w.sessions:,} sessions on {w.active_days} days")
    s.number("commands your agents ran", w.commands, f"{w.commands / max(w.prompts, 1):.1f} for every prompt you wrote")
    if w.lines_written:
        s.number("lines of code they wrote", w.lines_written, f"in {w.files:,} files")
    if len(w.agents) > 1:
        s.bars("your agents", w.agents, f"{w.agents[0][0]} did the most work")
    if w.tokens:
        s.words("tokens burned", human(w.tokens), "input, output and cache, where the logs say")
    if w.longest_session_min >= 30:
        h, m = divmod(w.longest_session_min, 60)
        s.words("your longest session", f"{h}h {m:02d}m" if h else f"{m} min",
                f"in {w.longest_session_project}" if w.longest_session_project else "")
    if w.longest_streak > 1:
        s.number("day streak", w.longest_streak,
                 f"{w.streak_start:%b} {w.streak_start.day} to {w.streak_end:%b} {w.streak_end.day}, AI every single day")
    if w.prompts:
        s.words("you prompt hardest at", f"{clock12(w.peak_hour)} on {w.peak_weekday}s",
                f"Busiest day: {w.busiest_day:%B} {w.busiest_day.day}, {w.busiest_day_prompts} prompts")
    if w.nos:
        s.number("times you told it no", w.nos, "undo, revert, stop, \"that's not what I meant\"")
    if w.thanks:
        s.number("times you said thanks", w.thanks, "and please " + f"{w.pleases:,} times" if w.pleases else "")
    if w.top_commands:
        s.bars("what it ran most", w.top_commands[:5])
    if w.persona:
        s.words("your AI personality", w.persona.title, w.persona.line, hold=3.0)


def summary(w: Wrapped) -> Panel:
    t = Table.grid(padding=(0, 3))
    t.add_column(style=DIM, justify="right")
    t.add_column(style="bold #f5f3ff")
    t.add_row("prompts", f"{w.prompts:,}  [{DIM}]{w.sessions:,} sessions · {w.active_days} active days[/]")
    t.add_row("agents ran", f"{w.commands:,} commands  [{DIM}]{w.edits:,} edits · {w.lines_written:,} lines written[/]")
    if w.agents:
        t.add_row("agents", "  ".join(f"{a} [{DIM}]{human(n)}[/]" for a, n in w.agents))
    if w.models:
        t.add_row("models", "  ".join(f"{m} [{DIM}]{human(n)}[/]" for m, n in w.models[:3]))
    if w.tokens:
        t.add_row("tokens", human(w.tokens))
    if w.longest_streak:
        t.add_row("longest streak", f"{w.longest_streak} days")
    if w.prompts:
        t.add_row("rhythm", f"{clock12(w.peak_hour)} · {w.peak_weekday}s  "
                            f"[{DIM}]{w.night_share:.0%} at night · {w.weekend_share:.0%} weekends[/]")
        t.add_row("manners", f"{w.thanks:,} thanks · {w.pleases:,} please · {w.nos:,} no's")
    if w.top_commands:
        t.add_row("it ran most", "  ".join(f"{c} [{DIM}]{n}[/]" for c, n in w.top_commands[:5]))
    if w.persona:
        t.add_row("personality", f"[{ACCENT}]{w.persona.title}[/]  [{DIM}]{w.persona.line}[/]")
    return Panel(t, title=f"[bold {ACCENT}]agentwrapped[/] [{DIM}]{w.year}[/]", title_align="left",
                 border_style=ACCENT, padding=(1, 2))


def make_card(w: Wrapped, path: Path) -> Path:
    stats = [("prompts", f"{w.prompts:,}"), ("commands run", human(w.commands)),
             ("lines written", human(w.lines_written)), ("day streak", f"{w.longest_streak}")]
    # project names can be private work, so the card only shows which agents did the work
    return card.render(path, brand="agentwrapped", year_label=str(w.year), persona=w.persona.title,
                       tagline=w.persona.line, stats=stats, bars=w.agents, bars_title="agents",
                       footer="uvx agentwrapped", accent=(255, 138, 61), top=(36, 18, 30), bottom=(10, 8, 16))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="agentwrapped", description="Spotify Wrapped for your AI coding agents: your "
                                "year with Claude Code, Codex and Gemini CLI, from the logs on your machine.")
    p.add_argument("--year", type=int, default=date.today().year)
    p.add_argument("--no-anim", action="store_true", help="skip the animated story")
    p.add_argument("--speed", type=float, default=1.0, help="animation speed multiplier")
    p.add_argument("--card", type=Path, help="share card path (default ./agentwrapped-<year>.png)")
    p.add_argument("--no-card", action="store_true")
    p.add_argument("-V", "--version", action="version", version=f"agentwrapped {__version__}")
    a = p.parse_args(argv)
    console = Console()
    since = time.mktime((a.year, 1, 1, 0, 0, 0, 0, 0, -1))
    with console.status(f"[{DIM}]reading agent logs…[/]", spinner="dots"):
        events = list(agentlogs.all_events(since=since))
    w = compute(events, a.year)
    if not w.prompts and not w.commands:
        console.print(f"No Claude Code, Codex or Gemini CLI activity found for {a.year}. agentwrapped reads "
                      "~/.claude, ~/.codex and ~/.gemini on this machine.")
        return 1
    if not a.no_anim and console.is_terminal:
        try:
            story(w, Story(console, ACCENT, a.speed))
        except KeyboardInterrupt:
            pass
    console.print(summary(w))
    if not a.no_card:
        out = a.card or Path(f"agentwrapped-{a.year}.png")
        try:
            make_card(w, out)
            console.print(f"\n[bold {ACCENT}]Share card saved:[/] {out}  [{DIM}](no project names, prompts or code "
                          f"on it, just your numbers)[/]")
        except OSError as e:
            console.print(f"[{DIM}]Couldn't save the share card: {e}[/]")
    return 0


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
