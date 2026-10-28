"""Claude Code hooks for the learn / quiz skills. Stdlib only; never breaks a session.

    learn_hooks.py session-start   # SessionStart: one-line course status when cwd is in a .learn course
    learn_hooks.py guard           # PreToolUse(Write|Edit): block hand edits of .learn/*.json state

Registered in ~/.claude/settings.json. The guard leaves .learn/tmp/*.json alone (batches for
`concept import` / `quiz add` are written there on purpose).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

LEARNCTL = Path(__file__).resolve().with_name("learnctl.py")


def find_root(start):
    p = Path(start).resolve()
    for q in [p, *p.parents]:
        if (q / ".learn" / "course.json").is_file():
            return q
    return None


def session_start(data):
    root = find_root(data.get("cwd") or os.getcwd())
    if not root:
        return
    r = subprocess.run([sys.executable, "-I", str(LEARNCTL), "--root", str(root), "status"],
                       capture_output=True, text=True, encoding="utf-8", timeout=20)
    if r.returncode:
        return
    out = r.stdout
    field = lambda pat: (m.group(1).strip() if (m := re.search(pat, out, re.M)) else None)
    title = field(r"^course: (.+?)\s+\(") or root.name
    pos = field(r"^position: (.+)$")
    due = field(r"^quiz: \d+ items, (\d+) due now") or "0"
    open_m = field(r"(\d+) open misconceptions") or "0"
    pending = field(r"\(pending (\d+), removed") or "0"
    active = re.findall(r"^ACTIVE ASSIGNMENT (\S+)", out, re.M)
    bits = [f"position {pos}", f"{due} quiz items due", f"{open_m} open misconceptions"]
    if pending != "0":
        bits.append(f"{pending} new/changed sources (run /learn sync)")
    if active:
        bits.append("active: " + ", ".join(active))
    line = f"{title}: " + " · ".join(bits)
    print(json.dumps({
        "systemMessage": line,
        "hookSpecificOutput": {"hookEventName": "SessionStart",
                               "additionalContext": f"Course folder with learn state ({root}). {line}. "
                                                    "Use the learn / quiz / visualize skills; full status: learnctl status."},
    }))


def guard(data):
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    p = Path(fp)
    if p.suffix.lower() == ".json" and p.parent.name == ".learn":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{p.name} is learn-skill state; change it only through learnctl.py "
                "(schema validation + history). Write batches to .learn/tmp/ and import them, "
                "e.g. `learnctl.py concept import`, `quiz add`, `unit update`, `evidence add`."),
        }}))


def main():
    try:
        data = json.load(sys.stdin)
        {"session-start": session_start, "guard": guard}[sys.argv[1]](data)
    except Exception as e:  # a hook must never take the session down
        print(f"learn_hooks: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
