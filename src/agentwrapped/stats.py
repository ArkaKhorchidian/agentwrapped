"""Your year with AI coding agents, in numbers."""
from __future__ import annotations

import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from .agentlogs import Event

NAMES = {"claude": "Claude Code", "codex": "Codex", "gemini": "Gemini CLI"}
NO = re.compile(r"^\s*(no+\b|nope\b|undo\b|revert\b|stop\b|wait\b|that'?s (wrong|not)|not what i|why did you|"
                r"don'?t\b|wrong\b|ugh\b|wtf\b|that broke|you broke|still (broken|failing|wrong)|it'?s still)", re.I)
THANKS = re.compile(r"\b(thanks|thank you|thx|ty|great job|nice work|perfect|awesome|amazing|you'?re the best)\b", re.I)
PLEASE = re.compile(r"\bplease\b|\bpls\b|\bplz\b", re.I)
SKIP = {"cd", "export", "set", "source", ".", "for", "do", "done", "if", "then", "fi", "else", "while", "echo",
        "true", "false", "sleep", "time", "env", "exec", "local"}


HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(\n|$)", re.S)


def programs(cmd: str) -> list[str]:
    """The programs a command line runs (heredoc bodies aren't commands)."""
    cmd = HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0] + "\n", cmd)
    out = []
    for seg in re.split(r"&&|\|\||[;|\n]", cmd):
        words = [w for w in seg.strip().split() if not re.match(r"^\w+=", w)]
        if words and words[0] not in SKIP and re.match(r"^[\w./-]+$", words[0]):
            out.append(os.path.basename(words[0]))
    return out


def clock12(hour: int) -> str:
    return f"{hour % 12 or 12}{'am' if hour < 12 else 'pm'}"


@dataclass
class Persona:
    title: str
    line: str


@dataclass
class Wrapped:
    year: int
    prompts: int = 0
    sessions: int = 0
    commands: int = 0
    edits: int = 0  # file writes and edits
    lines_written: int = 0
    files: int = 0
    tokens: int = 0
    active_days: int = 0
    longest_streak: int = 0
    streak_start: date | None = None
    streak_end: date | None = None
    agents: list[tuple[str, int]] = field(default_factory=list)  # (name, actions)
    models: list[tuple[str, int]] = field(default_factory=list)
    projects: list[tuple[str, int]] = field(default_factory=list)
    top_commands: list[tuple[str, int]] = field(default_factory=list)
    peak_hour: int = 0
    peak_weekday: str = ""
    busiest_day: date | None = None
    busiest_day_prompts: int = 0
    night_share: float = 0.0
    weekend_share: float = 0.0
    longest_session_min: int = 0
    longest_session_project: str = ""
    nos: int = 0
    thanks: int = 0
    pleases: int = 0
    longest_prompt_words: int = 0
    shortest_prompts: Counter = field(default_factory=Counter)  # one-word prompts: "continue", "yes"...
    persona: Persona | None = None


def longest_run(days: list[date]) -> tuple[int, date | None, date | None]:
    if not days:
        return 0, None, None
    days = sorted(set(days))
    best, start, cur_start, cur = 1, days[0], days[0], 1
    best_start, best_end = days[0], days[0]
    for a, b in zip(days, days[1:]):
        if (b - a).days == 1:
            cur += 1
        else:
            cur, cur_start = 1, b
        if cur > best:
            best, best_start, best_end = cur, cur_start, b
    return best, best_start, best_end


def compute(events: list[Event], year: int) -> Wrapped:
    w = Wrapped(year)
    sessions: dict[tuple, list[float]] = defaultdict(list)
    session_proj: dict[tuple, str] = {}
    agents, models, projects, cmds, files = Counter(), Counter(), Counter(), Counter(), set()
    prompt_times: list[datetime] = []
    days: list[date] = []
    per_day = Counter()
    for ev in events:
        if not ev.ts:
            continue
        dt = datetime.fromtimestamp(ev.ts)
        if dt.year != year:
            continue
        key = (ev.agent, ev.session)
        sessions[key].append(ev.ts)
        if ev.cwd:
            session_proj.setdefault(key, os.path.basename(ev.cwd.rstrip("/\\")))
        days.append(dt.date())
        w.tokens += ev.tokens
        if ev.model:
            models[ev.model] += 1
        if ev.kind == "prompt":
            w.prompts += 1
            prompt_times.append(dt)
            per_day[dt.date()] += 1
            text = ev.text.strip()
            words = len(text.split())
            w.longest_prompt_words = max(w.longest_prompt_words, words)
            if NO.search(text):
                w.nos += 1
            if THANKS.search(text):
                w.thanks += 1
            if PLEASE.search(text):
                w.pleases += 1
            if words == 1:
                w.shortest_prompts[text.lower().strip(".!?")] += 1
            continue
        if ev.kind in ("command", "read", "write", "edit", "fetch", "tool"):
            agents[ev.agent] += 1
            if ev.cwd:
                projects[session_proj.get(key) or os.path.basename(ev.cwd.rstrip("/\\"))] += 1
        if ev.kind == "command":
            w.commands += 1
            cmds.update(programs(ev.command))
        elif ev.kind in ("write", "edit"):
            w.edits += 1
            w.lines_written += len(ev.added)
            if ev.path:
                files.add(ev.path)
    w.sessions = len(sessions)
    w.files = len(files)
    w.agents = [(NAMES.get(a, a), n) for a, n in agents.most_common()]
    w.models = models.most_common(4)
    w.projects = projects.most_common(5)
    w.top_commands = cmds.most_common(6)
    w.active_days = len(set(days))
    w.longest_streak, w.streak_start, w.streak_end = longest_run(days)
    if prompt_times:
        hours = Counter(t.hour for t in prompt_times)
        w.peak_hour = hours.most_common(1)[0][0]
        wd = Counter(t.strftime("%A") for t in prompt_times)
        w.peak_weekday = wd.most_common(1)[0][0]
        w.night_share = sum(1 for t in prompt_times if t.hour >= 22 or t.hour < 5) / len(prompt_times)
        w.weekend_share = sum(1 for t in prompt_times if t.weekday() >= 5) / len(prompt_times)
        w.busiest_day, w.busiest_day_prompts = per_day.most_common(1)[0]
    for key, ts in sessions.items():
        # a session's working time: sum of gaps under 30 minutes (a resumed session days later isn't one sitting)
        ts.sort()
        active = sum(b - a for a, b in zip(ts, ts[1:]) if b - a < 1800)
        if active / 60 > w.longest_session_min:
            w.longest_session_min = int(active / 60)
            w.longest_session_project = session_proj.get(key, "")
    w.persona = persona(w)
    return w


def persona(w: Wrapped) -> Persona:
    p = max(w.prompts, 1)
    if w.night_share >= 0.35:
        return Persona("The Night Shift", f"{w.night_share:.0%} of your prompts were sent between 10pm and 5am.")
    if w.thanks / p >= 0.12:
        return Persona("The Polite One", f"You thanked your agent {w.thanks:,} times. It will remember.")
    if w.nos / p >= 0.2:
        return Persona("The Micromanager", f"{w.nos:,} prompts started with some version of \"no\".")
    if w.commands / p >= 12:
        return Persona("The Delegator", f"Your agents ran {w.commands / p:.0f} commands for every prompt you wrote.")
    if w.longest_prompt_words >= 600:
        return Persona("The Architect", f"Your longest prompt was {w.longest_prompt_words:,} words. That's a spec.")
    if w.weekend_share >= 0.3:
        return Persona("The Weekend Hacker", f"{w.weekend_share:.0%} of your prompts were on weekends.")
    return Persona("The Pair Programmer", f"{w.sessions:,} sessions, {w.active_days} days, one very patient partner.")


def year_events(events, year: int):
    start = time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1))
    return [e for e in events if e.ts and e.ts >= start]
