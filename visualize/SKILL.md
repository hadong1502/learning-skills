---
name: visualize
description: >-
  Build a quick, interactive visual of a math concept for a learner
  studying a course (usually in a folder indexed by the `learn` skill). The
  default is a step-through viewer of a ManimGL derivation; alternatives are a
  parameter slider over a ManimGL sweep, or a live JSXGraph widget for free
  exploration. Each is one self-contained HTML page, with no video encode unless
  asked. Use for /visualize, "show me", "can I see how X changes with w",
  "draw the phase plane", or when a concept is geometric or parametric.
argument-hint: "<concept or question> [beats | slider | live | video]"
---

# Visualize

A picture is worth building when it shows the mechanism: how the geometry
changes, or why a step follows. Use the course's notation and its parameter
values. Keep each visual to one idea.

```bash
L="python -I $HOME/.claude/skills/learn/scripts/learnctl.py"
PYM="$MANIM_WORKSPACE/.venv/Scripts/python.exe"   # ManimGL 1.7.2 + Pillow (see README)
VIZ="$HOME/.claude/skills/visualize/scripts/viz.py"
```

Output goes to `<course>/.learn/viz/<slug>/`, or `./viz/<slug>/` outside a course folder.

## 1. Choose the mode

| The concept is… | Mode | Cost |
|---|---|---|
| A sequence of logical steps: a derivation, a construction, "first the nullclines, then the fixed points" | **beats**: a ManimGL scene, one frame after each `play()`, stepped through in a viewer | ~35–45 s, ~250 KB |
| One parameter whose effect on a picture matters (a bifurcation, a gain, a coupling strength) | **slider**: a ManimGL scene with a `ValueTracker` swept over a range | ~20 s for 56 frames at 720p, ~1.3 MB |
| Two or more knobs, dragging an initial condition, or open-ended exploration | **live**: a JSXGraph page computing in the browser | seconds to write; no render |
| The motion itself is the point, or it's for presenting | **video**: only on request | from the workspace root: `$PYM -m manimlib <dir>/<slug>.py <Scene> -w -l --video_dir <dir>` (`--hd` for final) |

When unsure, ask in one line. Say which mode you picked and why in one line.

## 2. Ground it in the course

- Run `$L context --query "<terms>"` and read the cited passage, so equations, parameter values and names match the lecture.
- If `context` says `CHECK PAGE IMAGE`, check the page before copying a formula.
- Before drawing any computed quantity (fixed points, eigenvalues, trajectories), check it with NumPy/SymPy. The picture must be right.

## 3a. ManimGL scenes (beats, slider)

The engine is **ManimGL** (`from manimlib import *`), **never Manim CE**.
- Read `$MANIM_WORKSPACE/.claude/skills/manimgl/SKILL.md` for the API before writing a scene.
- `from common import *` gives `txt()` (Pango text) and `tex()` (LaTeX with amsmath).

**Conventions** (each one cost a re-render):
- **Name the file `<slug>.py`, never `scene.py`.** Caption lookup matches by file basename, and manimlib's own `scene/scene.py` would match first.
- **Captions are trailing comments** on the `self.play(...)` line: `self.play(FadeIn(m))  # Mixed state is a saddle: eigenvalues $-1\pm w$`. Use `$...$` for math; the viewer renders it with KaTeX. An uncommented `self.wait()` is skipped.
- **Axes:** use ranges aligned to the tick step (ticks start at the range minimum) and `add_coordinate_labels(num_decimal_places=1)` when ticks aren't integers. Otherwise labels round to "0, 0, 1".
- **Known ManimGL 1.7.2 footguns:**
  - `Dot(fill_color=…)`, not `color=`.
  - Pass one string to `tex()`; split strings lose relation spacing.
- **Slider scenes** declare
  `SWEEP = {"tracker": "w", "range": [a, b], "n": 56, "label": "$w$", "fmt": ".2f"}`.
  - Store the tracker as `self.w`.
  - Build the picture in `construct()` with `always_redraw` / updaters, and add no animations.
  - Keep per-frame work cheap: `always_redraw` reruns every frame.
- **Trajectories:** integrate them in NumPy and draw them with `VMobject().set_points_smoothly([...])`.

**Render:**
```bash
$PYM "$VIZ" beats  <dir>/<slug>.py <Scene> --out <dir> --hd --title "…" --description "…"
$PYM "$VIZ" sweep  <dir>/<slug>.py <Scene> --out <dir> --title "…" --description "…"   # 720p; --quality l | --hd
```

**Before handing it over, look at 2–3 frames** (Read the PNGs in `<dir>/frames/`). Check for:
- overlapping text
- labels cut off at the frame edge
- tick labels
- the computed objects in the right places

Re-render after fixing. `viz.py viewer <dir> --title …` rebuilds only the HTML.

## 3b. Live widgets

- Copy `templates/live_linear2d.html` (next to this file) to `<dir>/index.html` and adapt the model function, sliders, presets and readouts.
  - The template is a 2-D linear network with a vector field, a draggable initial condition, ‖x(t)‖, eigenvalues and a normality check.
- Keep it one file. Load libraries only from cdnjs, pinned: JSXGraph 1.11.1, KaTeX 0.16.9.
- Draw vector fields as **unit-length directions**. Raw vectors swamp the plot when coupling is strong.
- **Test it.** The browser pane only shows local files as static snapshots, so serve the folder with `python -I -m http.server 8765 --bind 127.0.0.1` in the background. Open it in a pane tab, and check the readouts with `javascript_tool` against a value you computed independently. Then stop the server.

## 4. Hand over and record

- **Show it running, not as a file link.** The app's browser pane renders local HTML as a static snapshot with no JavaScript, so the controls look dead. Instead:
  - Serve the viz folder in the background: `cd <course>/.learn/viz && python -I -m http.server 8765 --bind 127.0.0.1`. Reuse the server if it's already up.
  - Open it with `preview_start` (url `http://127.0.0.1:8765/<slug>/viewer.html`) and confirm it loaded with `javascript_tool`.
  - Also tell the learner that double-clicking the file opens it in their own browser, where everything works.
- Give the path to `viewer.html` / `index.html` as a link, in a few lines:
  - what to look at
  - which control to move
  - what should surprise them
- Link it to the course: "this is L08 p.9's saddle".
- The pages work offline except for the KaTeX/JSXGraph CDN.
- Append one line to `<course>/.learn/viz/INDEX.md`: `- <date> · <mode> · [<title>](<slug>/viewer.html) · <concepts / unit>`.
- Then run `$L log --kind viz --text "<slug>: <mode>, <concepts>"`.
