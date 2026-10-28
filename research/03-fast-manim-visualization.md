# Report: cheap interactive output for a ManimGL learning-visualization skill

Research subagent report, 2026-10-27. The prototype scripts it mentions are copied into `prototypes/` next to this file.

## Local setup (read only; timings run with all output sent to scratchpad)
- `snapshot.py` already does the expensive part well. It runs `construct()` once with animations skipped, hooks `Scene.pre_play`, and saves end-of-beat PNGs. Every `SNAP` line also prints the source line, which could serve as a free caption for each beat.
- **Measured on the template `FiringRateCurve` scene** (10 s, 300 frames at 30 fps; Tex cache was already warm):
  - `import manimlib` alone: about 3.4 s.
  - Snapshot of 3 frames: 5.5 s at 480p, 5.1 s at 1080p.
  - Full video: 9.0 s at 480p (`-w -l`), 10.9 s at 1080p (`--hd`).
  - Startup dominates. Each extra frame costs roughly 15–20 ms on the GPU.
- **ValueTracker sweep prototype** (`prototypes/sweep_scene.py`). A loop of `set_value` → `update_mobjects(0)` → `update_frame(force_draw=True)` → `get_image().save` produced 60 frames at 480p in 2.6 s (7.5 s wall). The curve used `always_redraw` and the Tex label used `make_number_changeable`. Frames look correct.
- **Footgun:** `manimgl ... -s` without `-w` opens a preview window and hangs headless. Always pass `-s -w`, as snapshot.py does.
- **Size of 60 frames at 854×480:**
  - PNG: 1.0 MB
  - WebP q80: 269 KB
  - Lossless WebP: 336 KB
  - JPEG q85: 841 KB
  - Single WebP sprite sheet: 253 KB, at 8540×2880 px
- **SVG export is feasible in ManimGL 1.7.2 (not built in)** (`prototypes/svg_scene.py`). A 30-line walker over `scene.get_mobject_family_members()`: for each VMobject it takes `get_subpaths()`, writes the quadratic Béziers as SVG `Q` commands, and uses `get_fill_color/opacity` and `get_stroke_color/opacity/width`. Headless Edge rendered it essentially identical to the ManimGL PNG, including Tex glyphs, axis numbers and the curve. Stroke-width scale needs tuning.
  - Size: 37 KB raw / 8.6 KB gzipped, versus a 22 KB PNG.
  - Unverified: gradients, 3D surfaces, `ImageMobject`, per-point opacity and shader effects. Assume these won't export.

## 1. Cheap scrubbable output from Manim
- **[manim-slides](https://github.com/jeertmans/manim-slides)** (v5.7.0). It supports ManimGL; its extra is `manimgl>=1.7.2`, compatible with this workspace. `manim-slides convert --to html|pdf|pptx|zip` with `--one-file` and `--offline` gives a self-contained reveal.js deck ([CLI docs](https://manim-slides.eertmans.be/latest/reference/cli.html)). It still renders a video per slide, so it doesn't save render time. It fits final narrated decks, not fast iteration.
- **ManimGL interactive.** Already used: `-e LINE` / `checkpoint_paste` through Manim Notebook. Also available: presenter mode `-p`, `-n a,b` to render a range of animations, and `--subdivide` for one file per animation. ManimGL has no partial-movie cache, only a Tex/Text SVG cache (`--clear-cache`). Its "caching" is effectively the notebook checkpoints.
- **Manim CE** ([config docs](https://docs.manim.community/en/stable/guides/configuration.html)):
  - `-s` / `--format png` gives the last frame only; `--format png-sequence` writes every frame.
  - `--save_sections` writes section videos.
  - `-ql` is 854×480 at 15 fps.
  - It caches partial movies by hashing each play/wait call ([PR #166](https://github.com/ManimCommunity/manim/pull/166)).
  - There is no flag to save an arbitrary mid-scene frame ([#2589](https://github.com/ManimCommunity/manim/issues/2589)); snapshot.py already solves that for ManimGL.
  - Current status of CE's OpenGL renderer not verified; older sources call it under development. Not relevant, since the workspace forbids CE.
- **Manim in the browser:**
  - [manim-web](https://github.com/maloyan/manim-web): MIT, about 500 stars, self-described as "young". A TypeScript port with KaTeX for Tex (an incomplete LaTeX subset), draggable/clickable mobjects, a scrubbing player, and a `py2ts` converter. It added scene-to-SVG export ([PR #629](https://github.com/maloyan/manim-web/pull/629)) and animated SMIL SVG export ([PR #699](https://github.com/maloyan/manim-web/pull/699)). It targets the CE API, not ManimGL, so expect friction with 3b1b-style code.
  - Academa Studio ([HN](https://hn.svelte.dev/item/49091703)): closed-source Rust/WebGPU/Pyodide. Not usable here.
  - No working Pyodide port of real Manim was found.
  - ManimML is an ML-diagram library on top of CE, not a browser runtime.

## 2. Self-contained HTML slider viewer
- **Structure:** one `.html` file holding a JS array of base64 WebP data URIs (base64 adds about 33%). Decode them all up front into `Image` objects. On `<input type=range>` `input`, swap `img.src`, which feels instant.
- **Controls:** arrow keys plus a play button. Show the parameter value in an HTML label instead of baking it into the frames, so one frame set serves several readouts.
- **Individual frames vs sprite sheet:** use individual frames. A sprite sheet saved only 6% with WebP, and an 8540×2880 image is heavy to decode on mobile. Sprites only pay off with PNG (505 KB vs 1.0 MB) or for HTTP-request count, which a single file doesn't have.
- **Budget:** about 4–5 KB per 480p WebP frame for line-art scenes, so 60–120 frames come to 0.3–0.6 MB. Use 1080p only for dense Tex: about 3× the bytes.
- **SVG frames** are crisp at any zoom, but 60 raw frames would be about 2 MB (they gzip about 4×). Reduce this by:
  - emitting static mobjects (axes, Tex) once as a base layer and only the changing paths per frame;
  - rounding coordinates to 2 decimals.

  An alternative for crisp math: raster frames with a KaTeX/HTML overlay for labels.
- **Beat stepper:** reuse `snapshot.py --list` output. Every index becomes a frame and its `SNAP` source line becomes the caption.

## 3. Live JS alternatives (no pre-render)
| Tool | Best for | Notes |
|---|---|---|
| [JSXGraph](https://jsxgraph.org) | Geometry and function plots with sliders and draggable points | Single script, no build step. License/size not verified |
| [Mafs](https://mafs.dev) (v0.21) | Clean 2D interactive plots in React | Needs React; can't do a no-build CDN page easily (not verified) |
| [Desmos API](https://www.desmos.com/api/v1.11/docs/index.html) | Fastest "drag a slider over a formula" | **Requires an API key**; terms not checked |
| GeoGebra embed | Geometry and CAS | Heavy runtime; online |
| [Plotly](https://plotly.com/python/sliders/) | Sliders over precomputed traces, heatmaps, 3D surfaces from Python | `write_html`; the inline plotly.js bundle is several MB (use `include_plotlyjs="cdn"`). Size figure not re-verified |
| matplotlib + ipywidgets | Quick exploration inside Jupyter | Needs a live kernel; not shareable as static HTML |
| D3 | Custom data-driven graphics | Most code per visual |
| Three.js | Real-time 3D (rotate, drag) | ManimGL 3D stills can't offer orbiting |
| [Motion Canvas](https://motioncanvas.io/docs) | TypeScript-authored animations with an editor timeline | Its LaTeX support was still maturing as of [v3.11](https://motioncanvas.io/blog/version-3.11.0); a parallel toolchain |

Manim wins for narrated, step-by-step derivations with 3b1b typesetting and transforms. JS wins for continuous exploration of more than one parameter, dragging points, rotating 3D, or anything the learner should poke at freely.

## 4. Render-time takeaways
- In ManimGL, cost is about 3.5–5 s of fixed startup, plus cold LaTeX compiles, plus about 15–20 ms per frame. Encoding at 480p vs 1080p barely matters (9.0 vs 10.9 s).
- A 60-frame sweep costs about the same as one 10 s low-res video, and both are seconds.
- Cold Tex compile time was not measured (the user's cache was not cleared). Typically about 0.5–2 s per unique string through latex + dvisvgm, cached afterwards. Varying Tex text per frame (rather than `make_number_changeable`) would multiply this cost.
- Not measured: Manim CE's Cairo renderer, which is CPU-bound and widely reported to be much slower per frame.

## Recommended architecture
Output modes, in order of default preference:
1. **Beat stepper (default for derivations and explanations).** One snapshot.py pass at all indices, packed into a single HTML with step buttons and a slider, using source-line or author captions. Cost: one skipped pass, about 5–15 s.
2. **Parameter slider (one continuous ValueTracker).** Generalize the sweep loop as a sibling of snapshot.py: the scene exposes `tracker`, a range and N (30–120). Output is WebP frames with an HTML value label; optionally SVG with a static base layer when crispness matters. A 2D grid (N×M) is acceptable only up to about 400 frames (about 20 s and 2 MB).
3. **Live JS widget.** Choose JSXGraph (no build step) or Plotly HTML from Python when there are two or more free parameters, the learner needs to drag objects or rotate in 3D, or the parameter space is open-ended.
4. **Animation scrub (optional).** Render the frames of one beat (`-n K,K+1` with a per-frame save hook) when the motion itself is the insight.
5. **Full video only on request:** `-w -l` to check timing, then `--hd`. Use manim-slides HTML only for a presentation deck.

**Decision rule:**
- Discrete logical steps → stepper.
- One knob whose effect on a Manim-styled picture matters → slider.
- Free exploration, two or more knobs, or direct manipulation → live JS.
- Motion itself is the point, or the output is for presenting → video.

**Not verified:**
- JSXGraph, Mafs and Desmos license and size details.
- Plotly bundle size.
- Current status of CE's OpenGL renderer.
- Cold Tex compile timings.
- SVG export of 3D, gradient or image mobjects.
