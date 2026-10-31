---
name: subagent-reports
description: >-
  Makes a written report part of every subagent's deliverable and logs it in the
  project. Use EVERY time before delegating work to a subagent — the Agent tool
  (general-purpose, Explore, Plan, claude-code-guide, forks, custom agents),
  Workflow scripts, or parallel research/review agents — and again when the
  agent's result comes back. Also use when the user asks where a subagent's
  findings were saved, or to backfill a report for an agent that already ran.
---

# Subagent reports

The user wants every subagent's work kept as a file, not just relayed in chat.
Reports live in the project the session works in:

```
<project>/.claude/agent-reports/
  INDEX.md                         one line per report (curated and raw)
  <YYYY-MM-DD>_<slug>.md           curated report (this skill)
  _raw/<stamp>_<type>_<id8>.md     automatic safety net (SubagentStop hook)
```

`<project>` is the session's working directory. `<slug>` is 3–6 kebab-case
words naming the task (`course-ingestion-prior-art`). If the name exists, add
`-2`, `-3`.

## Before spawning: add the deliverable to the brief

Append the block below to every agent prompt, with the path filled in. In a
Workflow script, append it to each `agent()` prompt, with one path per agent.

**Agents that can write files** (general-purpose, claude, fork, and most custom
agents) write the report themselves:

```
## Report deliverable (required)
Write your full report to: <absolute path to .claude/agent-reports/<date>_<slug>.md>
Use the structure in ~/.claude/skills/subagent-reports/template.md. The file
is the record: put every finding, source link, number and caveat in it, not
just a summary. Then hand back the path plus a 3-6 bullet summary.
```

**Read-only agents** (Explore, Plan, claude-code-guide, anything without
Write) can't save files. Instead, ask them to return the full report in the
template's structure, and write it yourself afterwards. Never ask a read-only
agent to write a file.

## When the result comes back

1. Open the report file and check that it is the full report, not just the summary. If it is missing or thin, write it yourself from the hand-back. Copy the hand-back word for word and add the frontmatter.
2. Add a line to `INDEX.md`:
   `- <date> · <status> · [<title>](<file>) · <agent type>`
3. Name the report path in your reply to the user, as a link.
4. Treat the report as the agent's claims. Check it before you rely on it, and record what you verified or corrected under `## Parent notes` in the report.

Files the agent made outside the reports folder (prototypes, scripts, outputs)
go under the report's "Files" section. If they're in the scratchpad or another
temporary place, copy them next to the report into `<date>_<slug>/`, so the
report doesn't point at files that will disappear.

## Safety net

A `SubagentStop` hook in `~/.claude/settings.json` runs
`scripts/log_subagent_report.py` every time a subagent finishes. It writes the
brief and the final hand-back to `_raw/` and indexes it. That copy is
automatic and unedited, and it doesn't replace the curated report.

To backfill an agent that ran before the hook existed:

```bash
python -I ~/.claude/skills/subagent-reports/scripts/log_subagent_report.py --transcript ~/.claude/projects/<project-key>/<session-id>/subagents/agent-<id>.jsonl --cwd <project>
```

The task `.output` files in the temp folder can be empty on Windows. The
transcripts under `~/.claude/projects/.../subagents/` are the real record.
