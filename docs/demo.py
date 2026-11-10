"""Write a made-up year of Claude Code, Codex and Gemini CLI logs to a temp home folder and run agentwrapped on it.
Used to record the README GIF and card; nothing here is real activity."""
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

random.seed(9)
HOME = Path(tempfile.mkdtemp(prefix="agentwrapped-demo-"))
YEAR = time.localtime().tm_year
PROJECTS = ["/Users/sam/code/storefront", "/Users/sam/code/pricing-api", "/Users/sam/code/ml-pipeline"]
PROMPTS = ["add pagination to the orders endpoint", "why is this test flaky", "refactor cart.ts into smaller functions",
           "write tests for the pricing rules", "fix the type errors", "continue", "yes", "no, undo that",
           "no that's not what I meant", "thanks!", "perfect, thank you", "please add logging around the retries",
           "the build is still failing", "explain this stack trace", "make it faster", "ship it", "revert that",
           "can you clean up the imports please", "wtf why did you delete the migration", "great job"]
CMDS = ["npm test", "npm run build", "pytest -q", "git status", "git diff", "rg -n TODO", "tsc --noEmit",
        "python -m mypy src", "docker compose up -d", "make test", "cargo check", "go test ./...", "eslint . --fix"]


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))


day0 = time.mktime((YEAR, 1, 6, 0, 0, 0, 0, 0, -1))
today = time.time()
n = 0
d = day0
while d < today - 86400:
    usage = 0.35 + 0.6 * (d - day0) / (today - day0)  # more AI every month
    if random.random() < usage:
        for _ in range(random.randint(1, 3)):
            n += 1
            agent = random.choices(["claude", "codex", "gemini"], [0.6, 0.3, 0.1])[0]
            proj = random.choice(PROJECTS)
            hour = random.choice([10, 11, 14, 15, 16, 21, 22, 23, 23, 0, 1])
            t = d + hour * 3600 + random.randint(0, 3000)
            sid = f"s{n}"
            rows = []
            for k in range(random.randint(3, 14)):
                t += random.randint(30, 400)
                rows.append(("prompt", random.choice(PROMPTS), t))
                for _ in range(random.randint(2, 9)):
                    t += random.randint(5, 60)
                    if random.random() < 0.6:
                        rows.append(("command", random.choice(CMDS), t))
                    else:
                        lines = "\n".join(f"const v{random.randint(0, 999)} = compute({j});"
                                          for j in range(random.randint(5, 60)))
                        rows.append(("write", (f"{proj}/src/f{random.randint(1, 80)}.ts", lines), t))
            if agent == "claude":
                p = HOME / ".claude" / "projects" / proj.replace("/", "-")
                p.mkdir(parents=True, exist_ok=True)
                with (p / f"{sid}.jsonl").open("w") as fh:
                    for kind, what, ts in rows:
                        if kind == "prompt":
                            rec = {"type": "user", "timestamp": iso(ts), "cwd": proj, "sessionId": sid,
                                   "message": {"role": "user", "content": what}}
                        else:
                            tool = {"type": "tool_use", "name": "Bash", "input": {"command": what}} if kind == "command" \
                                else {"type": "tool_use", "name": "Write", "input": {"file_path": what[0], "content": what[1]}}
                            rec = {"type": "assistant", "timestamp": iso(ts), "cwd": proj, "sessionId": sid,
                                   "message": {"model": random.choice(["claude-opus-4-5", "claude-sonnet-4-5"]),
                                               "usage": {"input_tokens": random.randint(2000, 40000),
                                                         "output_tokens": random.randint(200, 3000)},
                                               "content": [tool]}}
                        fh.write(json.dumps(rec) + "\n")
            elif agent == "codex":
                p = HOME / ".codex" / "sessions" / str(YEAR) / "01" / "01"
                p.mkdir(parents=True, exist_ok=True)
                out = [{"timestamp": iso(rows[0][2]), "type": "session_meta", "payload": {"id": sid, "cwd": proj}}]
                for kind, what, ts in rows:
                    if kind == "prompt":
                        out.append({"timestamp": iso(ts), "type": "event_msg",
                                    "payload": {"type": "user_message", "message": what}})
                    elif kind == "command":
                        out.append({"timestamp": iso(ts), "type": "response_item", "payload": {
                            "type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": what})}})
                    else:
                        patch = f"*** Begin Patch\n*** Add File: {what[0]}\n" + \
                            "".join("+" + l + "\n" for l in what[1].splitlines()) + "*** End Patch\n"
                        out.append({"timestamp": iso(ts), "type": "response_item", "payload": {
                            "type": "custom_tool_call", "name": "apply_patch", "input": patch}})
                (p / f"rollout-{sid}.jsonl").write_text("\n".join(json.dumps(x) for x in out) + "\n")
            else:
                p = HOME / ".gemini" / "tmp" / proj.rsplit("/", 1)[1] / "chats"
                p.mkdir(parents=True, exist_ok=True)
                msgs = [{"sessionId": sid, "projectHash": "h"}]
                for i, (kind, what, ts) in enumerate(rows):
                    if kind == "prompt":
                        msgs.append({"id": f"u{i}", "type": "user", "timestamp": iso(ts), "content": [{"text": what}]})
                    else:
                        call = {"id": "c", "name": "run_shell_command", "args": {"command": what}} if kind == "command" \
                            else {"id": "c", "name": "write_file", "args": {"file_path": what[0], "content": what[1]}}
                        msgs.append({"id": f"g{i}", "type": "gemini", "timestamp": iso(ts), "content": "",
                                     "model": "gemini-2.5-pro", "tokens": {"total": random.randint(3000, 30000)},
                                     "toolCalls": [call]})
                (p / f"session-{sid}.jsonl").write_text("\n".join(json.dumps(m) for m in msgs) + "\n")
    d += 86400
(HOME / ".gemini" / "projects.json").write_text(json.dumps({"projects": {p: p.rsplit("/", 1)[1] for p in PROJECTS}}))
env = dict(os.environ, HOME=str(HOME), USERPROFILE=str(HOME))
env.pop("CLAUDE_CONFIG_DIR", None)
env.pop("CODEX_HOME", None)
os.chdir(HOME)
code = subprocess.call(["agentwrapped", *sys.argv[1:]], env=env)
for f in HOME.glob("agentwrapped-*.png"):
    f.replace(Path(__file__).parent / "card.png")
sys.exit(code)
