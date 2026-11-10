import json
import time
from datetime import date

import pytest

from agentwrapped import cli
from agentwrapped.agentlogs import Event
from agentwrapped.stats import NO, THANKS, compute, longest_run, persona, programs

Y = 2026


def ts(month, day, hour=12, minute=0):
    return time.mktime((Y, month, day, hour, minute, 0, 0, 0, -1))


def ev(kind, t, agent="claude", session="s1", **kw):
    return Event(agent, session, t, kw.pop("cwd", "/Users/me/shop"), kind, **kw)


def test_patterns():
    assert NO.search("no, undo that") and NO.search("Nope") and NO.search("that's not what I meant")
    assert not NO.search("now add tests") and not NO.search("note: use pnpm")
    assert THANKS.search("perfect, thank you!") and not THANKS.search("pretty good")


def test_programs():
    assert programs("cd app && npm test | tee log") == ["npm", "tee"]
    assert programs("python3 - <<'EOF'\nprint(1)\nEOF\nls") == ["python3", "ls"]


def test_longest_run():
    d = [date(Y, 1, 1), date(Y, 1, 2), date(Y, 1, 3), date(Y, 1, 5), date(Y, 1, 5)]
    assert longest_run(d) == (3, date(Y, 1, 1), date(Y, 1, 3))
    assert longest_run([]) == (0, None, None)


def test_compute():
    events = [
        ev("prompt", ts(3, 1, 23), text="add a login page please"),
        ev("command", ts(3, 1, 23, 1), command="npm test", tokens=1000, model="claude-x"),
        ev("write", ts(3, 1, 23, 2), path="/Users/me/shop/a.ts", added=["a", "b", "c"]),
        ev("prompt", ts(3, 1, 23, 10), text="no, undo that"),
        ev("prompt", ts(3, 2, 10), text="thanks!", session="s2"),
        ev("edit", ts(3, 2, 10, 1), path="/Users/me/shop/a.ts", added=["d"], session="s2"),
        ev("command", ts(3, 3, 10), agent="codex", session="c1", command="cd x && pytest -q && git status"),
        ev("prompt", ts(1, 1, 10), text="last year", session="old") ,
    ]
    events[-1].ts = time.mktime((Y - 1, 12, 31, 10, 0, 0, 0, 0, -1))
    w = compute(events, Y)
    assert (w.prompts, w.commands, w.edits, w.lines_written, w.files) == (3, 2, 2, 4, 1)
    assert w.sessions == 3 and w.active_days == 3 and w.longest_streak == 3
    assert w.nos == 1 and w.thanks == 1 and w.pleases == 1
    assert w.agents == [("Claude Code", 3), ("Codex", 1)]
    assert dict(w.top_commands) == {"npm": 1, "pytest": 1, "git": 1}
    assert w.tokens == 1000 and w.models == [("claude-x", 1)]
    assert w.peak_hour == 23 and w.busiest_day == date(Y, 3, 1) and w.busiest_day_prompts == 2
    assert w.longest_session_min == 10


@pytest.mark.parametrize("attrs,title", [
    ({"night_share": 0.5}, "The Night Shift"),
    ({"thanks": 30}, "The Polite One"),
    ({"nos": 40}, "The Micromanager"),
    ({"commands": 2000}, "The Delegator"),
    ({"longest_prompt_words": 900}, "The Architect"),
    ({"weekend_share": 0.4}, "The Weekend Hacker"),
    ({}, "The Pair Programmer"),
])
def test_personas(attrs, title):
    from agentwrapped.stats import Wrapped
    w = Wrapped(Y, prompts=100)
    for k, v in attrs.items():
        setattr(w, k, v)
    assert persona(w).title == title


def test_cli_and_card(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    d = home / ".claude" / "projects" / "-x"
    d.mkdir(parents=True)
    now = time.time()
    rows = [{"type": "user", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now - 3600 * i)),
             "cwd": "/x", "sessionId": "s", "message": {"content": f"prompt {i}"}} for i in range(1, 4)]
    rows.append({"type": "assistant", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now - 60)),
                 "cwd": "/x", "sessionId": "s", "message": {"content": [{"type": "tool_use", "name": "Bash",
                                                                          "input": {"command": "pytest"}}]}})
    (d / "s.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    out = tmp_path / "card.png"
    assert cli.main(["--no-anim", "--card", str(out), "--year", str(time.localtime(now - 3600).tm_year)]) == 0
    assert out.exists() and out.stat().st_size > 10_000
    from PIL import Image
    assert Image.open(out).size == (1200, 675)
    assert "agentwrapped" in capsys.readouterr().out
    assert cli.main(["--no-anim", "--no-card", "--year", "1999"]) == 1


def test_human():
    assert [cli.human(x) for x in (999, 12_345, 235_038, 1_500_000, 264_700_000)] == ["999", "12.3k", "235k", "1.5M", "265M"]
