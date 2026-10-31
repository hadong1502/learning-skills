"""Safety-net log of every subagent's brief and final report.

Runs as a SubagentStop hook (JSON on stdin) or by hand to backfill:

    python log_subagent_report.py                      # hook mode, reads stdin
    python log_subagent_report.py --transcript X.jsonl [--cwd DIR]

Writes <cwd>/.claude/agent-reports/_raw/<stamp>_<agent-type>_<id8>.md holding the
task brief (first user message) and the final report (the SubagentHandback
message, else the last assistant text), and appends one line to
<cwd>/.claude/agent-reports/INDEX.md. Curated reports written under the
subagent-reports skill (../SKILL.md) live one level up; this file only
guarantees nothing is lost. Registered as a SubagentStop hook in ~/.claude/settings.json.

Stdlib only. Never fails the hook: errors go to stderr and exit 0.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys


def load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for b in content or []:
        if b.get("type") == "text":
            parts.append(b.get("text", ""))
    return "\n".join(parts)


def extract(entries):
    brief, report, report_kind, first_ts, last_ts = "", "", "", None, None
    for e in entries:
        ts = e.get("timestamp")
        first_ts = first_ts or ts
        last_ts = ts or last_ts
    for e in entries:
        if e.get("type") == "user":
            brief = text_of((e.get("message") or {}).get("content"))
            if brief:
                break
    for e in reversed(entries):
        if e.get("type") != "assistant":
            continue
        content = (e.get("message") or {}).get("content") or []
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for b in content:
            if b.get("type") == "tool_use" and "handback" in (b.get("name") or "").lower():
                msg = (b.get("input") or {}).get("message")
                if isinstance(msg, str) and msg.strip():
                    return brief, msg, "SubagentHandback", first_ts, last_ts
        t = text_of(content)
        if t.strip() and not report:
            report, report_kind = t, "last assistant text"
            break
    return brief, report, report_kind, first_ts, last_ts


def slug(s, n=40):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s or "").strip("-").lower()
    return s[:n].strip("-") or "agent"


def write_log(transcript, cwd, agent_type="", description="", agent_id=""):
    entries = load_jsonl(transcript)
    if not entries:
        return None
    meta_path = transcript[: -len(".jsonl")] + ".meta.json"
    if os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path, encoding="utf-8"))
            agent_type = agent_type or meta.get("agentType", "")
            description = description or meta.get("description", "")
        except Exception:
            pass
    agent_id = agent_id or entries[0].get("agentId") or os.path.basename(transcript)
    brief, report, kind, first_ts, last_ts = extract(entries)

    root = os.path.join(cwd, ".claude", "agent-reports")
    raw = os.path.join(root, "_raw")
    os.makedirs(raw, exist_ok=True)
    # Same agent can stop more than once (resumed); one file per agent, overwritten.
    try:  # transcript timestamps are UTC; name files in local time
        started = dt.datetime.fromisoformat(first_ts.replace("Z", "+00:00")).astimezone()
    except Exception:
        started = dt.datetime.now()
    stamp = started.strftime("%Y-%m-%d_%H%M")
    name = f"{stamp}_{slug(agent_type, 20)}_{str(agent_id).replace('agent-', '')[:8]}.md"
    path = os.path.join(raw, name)
    existed = os.path.exists(path)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {description or 'Subagent run'}\n\n")
        f.write(f"- agent type: {agent_type or 'unknown'}\n")
        f.write(f"- agent id: {agent_id}\n")
        f.write(f"- started: {first_ts}\n- finished: {last_ts}\n")
        f.write(f"- report source: {kind or 'none found'}\n")
        f.write(f"- transcript: {transcript}\n\n")
        f.write("## Brief\n\n" + (brief.strip() or "_(not found)_") + "\n\n")
        f.write("## Final report\n\n" + (report.strip() or "_(no report found)_") + "\n")

    if not existed:
        with open(os.path.join(root, "INDEX.md"), "a", encoding="utf-8") as f:
            f.write(f"- {stamp} · raw · [{description or agent_id}](_raw/{name}) · {agent_type}\n")
    return path


def project_root(cwd):
    """The hook's cwd is the shell's current directory, which drifts into subfolders.
    Walk up to the nearest folder marked by .learn, .git or its own .claude (never ~/.claude)."""
    home = os.path.normcase(os.path.abspath(os.path.expanduser("~")))
    d = os.path.abspath(cwd)
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:  # inside the session's project: keep every report with the project, not a nested repo
        pa = os.path.normcase(os.path.abspath(proj))
        if os.path.normcase(d) == pa or os.path.normcase(d).startswith(pa + os.sep):
            return os.path.abspath(proj)
    while True:
        if os.path.normcase(d) != home and any(
                os.path.isdir(os.path.join(d, m)) for m in (".learn", ".git", ".claude")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.environ.get("CLAUDE_PROJECT_DIR") or cwd
        d = parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript")
    ap.add_argument("--cwd")
    a = ap.parse_args()
    try:
        if a.transcript:
            p = write_log(a.transcript, a.cwd or os.getcwd())
            print(p)
            return
        data = json.load(sys.stdin)
        cwd = project_root(data.get("cwd") or os.getcwd())
        transcript = data.get("agent_transcript_path")
        agent_id = data.get("agent_id", "")
        if not transcript and data.get("transcript_path") and agent_id:
            base = data["transcript_path"][: -len(".jsonl")]
            transcript = os.path.join(base, "subagents", f"agent-{agent_id}.jsonl")
        if transcript and os.path.exists(transcript):
            write_log(transcript, cwd, data.get("agent_type", ""), "", agent_id)
    except Exception as e:  # never break the session over logging
        print(f"log_subagent_report: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
