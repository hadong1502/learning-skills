# learning-skills

[Claude Code](https://claude.com/claude-code) skills for studying a math-heavy course from its own materials (slides, LaTeX notes, papers, problem sets).

| Skill | What it does |
|---|---|
| `learn` | The first call in a course folder indexes it into `.learn/`: PDF → LaTeX-markdown with Marker, course order, and a concept index where each concept is listed under the unit that first introduces it. Later calls sync changed files, then answer at the depth the question's phrasing shows, scoped to where you are in the curriculum. |
| `quiz` | Mixes spaced-repetition reviews (FSRS), re-tests of recorded misconceptions, and new items on weak concepts. Each item gets a rubric before it is shown, a confidence rating before feedback, and strict per-criterion grading. |
| `visualize` | Quick visuals without video encoding: a step-through viewer of a ManimGL derivation, a slider over a ManimGL parameter sweep, or a live JSXGraph widget. Each is one self-contained HTML page. |
| `subagent-reports` | Makes a written report part of every subagent's deliverable and logs it under `<project>/.claude/agent-reports/`. `learn` uses it when it extracts concepts in parallel. |

`PLAN.md` holds the design decisions. `research/` holds the prior-art and pedagogy surveys behind them.

## Requirements

Developed and tested on Windows 11 with an 8 GB RTX 4070. Most of it is plain Python, but a few parts assume Windows (see the notes).

- **Python 3.12** with [uv](https://docs.astral.sh/uv/). Running `uv sync` in this folder creates `.venv` with Marker 1.10 (pinned below 2.0, which needs a vLLM or llama.cpp server), CUDA 12.8 torch, PyMuPDF, SymPy and py-fsrs.
- **The state script** `learn/scripts/learnctl.py` uses only the standard library, so any `python` on PATH works.
- **Optional:**
  - **Microsoft PowerPoint**, to convert `.pptx` decks.
  - **For `visualize`:** a ManimGL 1.7.2 workspace. It needs its own `.venv` with `manimgl` and Pillow, a `common.py` providing `txt()` and `tex()`, and `.claude/skills/manimgl/` from [manimgl-skill](https://github.com/do-gongil/manimgl-skill), whose `core/assets/snapshot.py` drives the beats mode.

## Install

1. Link each skill folder into `~/.claude/skills/`. On Windows:

   ```bash
   for s in learn quiz visualize subagent-reports; do cmd //c mklink /J "%USERPROFILE%\\.claude\\skills\\$s" "$(cygpath -w "$PWD/$s")"; done
   ```

   On macOS or Linux, symlink them instead: `ln -s "$PWD/$s" ~/.claude/skills/$s`.

2. Tell the skills where the interpreters are, in `~/.claude/settings.json`:

   ```json
   "env": {
     "LEARN_PY": "<this repo>/.venv/Scripts/python.exe",
     "MANIM_WORKSPACE": "<path to the ManimGL workspace>"
   }
   ```

3. Add the optional hooks to the same file:
   - `SessionStart` prints a one-line course status.
   - `PreToolUse` on `Write|Edit` blocks hand edits to `.learn/*.json`.
   - `SubagentStop` keeps a raw copy of every subagent's output.

   ```json
   "hooks": {
     "SessionStart": [{"hooks": [{"type": "command", "command": "python",
       "args": ["-I", "<home>/.claude/skills/learn/scripts/learn_hooks.py", "session-start"], "timeout": 20}]}],
     "PreToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "python",
       "args": ["-I", "<home>/.claude/skills/learn/scripts/learn_hooks.py", "guard"], "timeout": 10}]}],
     "SubagentStop": [{"hooks": [{"type": "command", "command": "python",
       "args": ["-I", "<home>/.claude/skills/subagent-reports/scripts/log_subagent_report.py"], "timeout": 30}]}]
   }
   ```

4. Write your learner profile: copy `learn/profile-template.md` to `~/.claude/learning/profile.md` and fill it in, or let `/learn profile` interview you.

## Use

In a course folder:

```
/learn                         first run: scan, convert, order units, extract concepts
/learn where L05               set your position in the course
/learn why is x1=x2 the stable manifold in the WTA network?
/quiz                          5 items: due reviews, misconception re-tests, new items
/quiz midterm
/visualize the pitchfork as w crosses 1
```

## Notes

- **Marker drops minus signs** in inline math, both between symbols and inside small matrices. `learnctl audit` compares the converted math with the PDF's text layer and flags pages, and the skills check the page image before using a flagged formula.
- **Conversion is slow:** about 7 s per page with OCR on, and 30–55 s per page for figure-heavy slides. Run long conversions in the background. Interrupted batches resume.
- **Windows-only parts:**
  - `.pptx` export (PowerPoint COM)
  - the junction-based eval sandboxes in `evals/make_sandboxes.py`
  - the `.venv/Scripts/python.exe` paths

  Everything else should port.
- **Evals:** `evals/` holds phrasing-pair cases and the harness for checking that answers adapt to how a question is asked. The replies themselves aren't in this repo, because they quote course material.

## License

MIT; see `LICENSE`. The vendored ManimGL skill this depends on carries its own licenses.
