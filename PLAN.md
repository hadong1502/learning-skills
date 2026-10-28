# Learning-support skills: research summary and plan

Status: design draft, nothing built yet (2026-10-27).

## Goals

- Help me reach real understanding of a new concept or course, which is often math-heavy. Tips and tricks are not the goal.
- Run from whichever project folder holds the course materials. The first run indexes those materials into a cache I can query and update.
- For a course, know where I am in the curriculum. Treat earlier lectures as prior knowledge, and flag anything that needs material from later lectures.
- Read how I phrase a question for what I already know, and set the depth of the answer accordingly. Ask a clarifying question only when that helps.
- Include a quiz mode and a visualization mode. Visuals use Manim, and are cheap to render because they are frames I scrub through, not full videos.

---

## 1. What the research says

### Prior art

**[kirilxd/claude-tutor](https://github.com/kirilxd/claude-tutor)**
- Has learn, quiz and review skills.
- Stores learner state as JSON in `~/.claude/learning/`, with SM-2 review scheduling.
- A SessionStart hook shows which reviews are due.
- **Lesson:** Claude invents JSON field names. They had to add PreToolUse hooks that validate the schema. Writes to state should go through a script.

**[roundtable02/tutor-skills](https://github.com/roundtable02/tutor-skills)**
- `/tutor-setup` scans your own PDFs and markdown into an Obsidian vault of concept notes and practice questions.
- `/tutor` quizzes in rounds of 4 questions and tracks mastery per concept.
- **Gap:** you can't add new sources incrementally, and it has no idea of course order.

**Anthropic `learning-output-style` / Learning mode**
- Uses Socratic prompting and `TODO(human)` handoffs.
- Keeps no state.

**Karpathy's "LLM wiki" ([gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f))**
- Raw sources are never edited. An LLM-maintained markdown wiki sits on top.
- `index.md` is a catalog that gets read first. `log.md` is append-only.
- Three operations: ingest, query, lint.
- Works without search tooling up to roughly 100 sources.

**No existing tool handles math or knows where the learner is in a course.** That is the niche this project fills.

### Caching course materials

- Claude Code itself dropped its vector database in favour of grep and read; the stated reasons were stale indexes and keeping a second copy of the data. At the scale of one course (10–40 lectures), the best fit is:
  - markdown converted once, with page anchors
  - a compiled index and concept table
  - grep for lookup
- SQLite FTS5 (Python stdlib) is an optional step up. Embeddings aren't worth adding.
- For incremental updates, keep a `manifest.json` that maps each source to its sha256, the converter used, and the output. Re-convert only the files that changed, and re-run ingest only for those.
- For math extraction:
  - `.tex` sources are best when they exist.
  - Otherwise Marker or MinerU (good at LaTeX math; PyTorch, GPU preferred).
  - Docling has formula enrichment and handles PPTX.
  - **Avoid pymupdf4llm**: it has no LaTeX output and silently drops formula blocks.
  - Claude can also read PDF pages directly: max 20 pages per Read call, roughly 1.5–3k tokens per page plus the image. That's too costly for every query, but it's the right fallback when a converted formula looks garbled.

### Curriculum structure

- LLMs recover concept and prerequisite graphs reasonably well, but extracted graphs miss a lot of edges. In Mathlib, 74% of dependencies are implicit.
- **Design choice:** don't build a full prerequisite graph. Build a **first-introduced index** instead: concept → lecture/page where it's introduced → concepts it uses (soft hints).
  - "Already seen by lecture N" then becomes a filter on course order rather than an inference.
  - This is the same trick ConceptThread uses with timestamps.

### Pedagogy for an expert learner

**Question phrasing is evidence.**
- Signals:
  - correct vocabulary and notation
  - naming a specific step or assumption, rather than "I don't get X"
  - saying what you already tried
  - structural versus surface framing
  - false presuppositions inside the question
- Miyake & Norman: "to ask a question, one must know enough to know what is not known."

**Cheap diagnosis.**
- Kalyuga's *first-step method*: ask only for the first step of a task.
- Or ask "what's your current mental model?". One probe is enough; a long quiz isn't needed.

**Expertise reversal.**
- Worked examples help novices but are redundant or harmful for experts.
- Experts learn better from problem-first work, faded guidance and leaving gaps for them to fill.
- Productive failure (try first, then instruction) beats instruction-first for conceptual STEM learning.

**Learner model.**
- A per-concept mastery estimate with evidence and a forgetting term matches deep knowledge tracing (Khajah et al. 2016).
- "Annotate then trace": an LLM tags each turn with the concepts involved and whether I was right, then updates the model (Scarlatos et al. 2025).
- Mark a misconception resolved **only after a later item tests it again**.

**Quiz evidence.**

| Effect | Size |
|---|---|
| Retrieval practice | g ≈ 0.61 (transfer 0.53) |
| Self-explanation | g = 0.55 |
| Interleaved math | d = 0.83 on a delayed test |

- Asking for confidence before revealing the answer gives calibration data, and high-confidence errors get corrected more often (hypercorrection).
- `pip install fsrs` gives FSRS-6 scheduling for free.

**Grading.**
- LLM judges are lenient on proofs, with up to 75% false positives (QEDBench).
- What works:
  - write a reference solution and rubric *before* seeing the answer
  - grade step by step, naming the missing step
  - use SymPy for symbolic or numeric answers
  - fall back to the LLM only when SymPy can't decide

**Known LLM-tutor failures.**

| Failure | Evidence | Mitigation |
|---|---|---|
| Giving answers away | MathDial; unguarded GPT-4 cut exam scores 17% in Bastani et al. (PNAS 2025) | Hint-only tutoring removed the harm |
| Sycophancy | Accuracy drops ~15 points when the student states a wrong answer | Re-check before conceding |
| Hallucinated math | 32% of hints failed quality checks | Self-consistency and code tools |
| Structure carried only by prompt tone | The Harvard RCT (Kestin 2025) needed a **structured sequence**, not just a system prompt | Put sequencing in the skill's structure |

**Gap:** every RCT studied K-12 or intro-undergrad learners. Nothing tests PhD-level learners, so the expert-learner choices are extrapolation.

### Visualization (measured on this machine's ManimGL 1.7.2 workspace)

**Render costs.**

| Output | Time |
|---|---|
| Fixed startup | ~3.5–5 s |
| Each extra frame | ~15–20 ms |
| 3-frame snapshot | ~5.5 s |
| Full 10 s video, 480p | 9.0 s |
| Full 10 s video, 1080p | 10.9 s |

- Startup dominates. Frames are almost free once the scene is loaded.

**ValueTracker sweep prototype.**
- 60 frames at 480p in 7.5 s wall time.
- As WebP: ~270 KB total (~4–5 KB per frame), so a single self-contained HTML slider stays under 1 MB.
- A sprite sheet saved only 6%, so use separate frames.

**SVG export.**
- A ~30-line walker over VMobject Bézier paths gives crisp vector frames, ~9 KB gzipped each.
- Not verified for 3D, gradients or images.

**Other tools.**
- `manim-slides` supports ManimGL, but it still renders video per slide. Good for decks, not for fast iteration.
- `manim-web` (a TypeScript port) is young and targets the Manim CE API.
- JSXGraph or Plotly HTML suit free exploration with two or more parameters, dragging, or 3D rotation.

**Footgun.** `manimgl -s` without `-w` opens a window and hangs when headless.

---

## 2. Architecture

### Packaging

A small suite of user-level skills, developed in this repo (`learning-skills/`) and installed into `~/.claude/skills/` (by junction, or as a local plugin). That way they work from any course folder.

| Skill | Invoked as | Job |
|---|---|---|
| `learn` | `/learn <question or command>` | Main tutor. On first use in a folder it runs ingest. On later uses it syncs changed sources, then answers. Subcommands: `status`, `where <lecture>`, `sync`. |
| `quiz` | `/quiz [topic \| due \| lecture N]` | Quiz session: due reviews plus new items, graded, then logged to the learner model. |
| `visualize` | `/visualize <concept>` | Builds a stepper, slider, live widget or video for a concept, using the course's notation. |

All three share one Python helper, `learnctl.py` (stdlib-first). **Every state write goes through it**: record evidence, add a misconception, set the course position, review a quiz item, sync the manifest. This validates the schema, which is the claude-tutor lesson. Claude reads state by reading and grepping the rendered markdown and JSON.

### Per-course state: `<course folder>/.learn/`

```
.learn/
  manifest.json      source path → sha256, mtime, converter, output file
  sources/           one .md per source, with <!-- p.12 --> / <!-- slide 7 --> anchors
  course.md          ordered units (L1…Ln) with titles; confirmed by me on first ingest
  concepts.json      id, name, introduced_in (unit, page), uses[], notation, aliases
  index.md           one-line catalog per unit and per key concept (read first)
  position.json      current unit pointer + "known background" overrides
  learner.json       per-concept evidence list, mastery 0–1, last_seen;
                     misconceptions with status observed → addressed → verified;
                     calibration log (confidence vs. correct)
  quiz/items.jsonl   item, type, concept ids, reference solution, rubric, FSRS card state
  log.md             append-only session log (## [date] ingest | question | quiz)
  viz/<slug>/        scene.py, frames, viewer.html
```

A **global profile** lives at `~/.claude/learning/profile.md`. It holds my background (fields I know deeply, notation habits) and my preferences (formal-first or intuition-first, length). It's shared across courses, so "I'm fluent in linear algebra and dynamical systems" doesn't need re-learning in each folder.

### Ingest pipeline (first call, and `sync`)

1. **Discover files.** Find PDF, PPTX, TEX, MD and IPYNB files. Hash them and diff against the manifest.
2. **Convert** with the best source available:
   - `.tex` → use it directly
   - `.ipynb` → nbconvert
   - `.pptx` → python-pptx or Docling
   - `.pdf` → pluggable backend (see open question 1)
   
   Keep page anchors throughout.
3. **Order the course.** Propose an order from the syllabus, filenames and dates, then ask me to confirm it once.
4. **Extract concepts, per unit, in course order.** For each unit: the definitions, theorems and notation it introduces, and the earlier concepts it uses. Because this runs in order, "introduced in" is reliable. Where LaTeX environments exist (`\begin{definition}`, `\label`), use them first.
5. **Compile `index.md`** and append to `log.md`.
6. **Sync only what changed.** On later calls, re-run steps 2 and 4 for changed or new files only.

A large course might need a subagent per unit so the main context stays clean.

### The `learn` turn: answering a question

1. **Locate.** Work out the course position from an explicit `where` setting, or from the question itself ("in lecture 5…"), or from the last position used. Load `index.md`, the relevant `concepts.json` entries, and my learner record for those concepts.
2. **Read the question.** Extract the concepts mentioned, my vocabulary and precision, what I said I tried, and any presuppositions. Classify into one of four routes:

   | Signal | Response |
   |---|---|
   | Precise and technical, names the stuck step | Answer directly at that level and keep it short. Skip what I clearly know. |
   | Broad ("I don't get X") or level unclear | One probe (first step, or "what's your current model of X?"), **or** a short layered answer that ends with the probe. Never more than one question. |
   | A false presupposition | Address the misconception first, citing the course source. Log it. |
   | "Just show me" | Give the full derivation. Expert override, no withholding. |

3. **Scope to the curriculum.** Explain using only concepts introduced up to the current position, plus my known background. When the honest answer needs later material, say so explicitly ("this is L9's spectral theorem; here's the minimum you need now"). Use the course's notation, and cite unit and page.
4. **Ground every claim.**
   - Check derivations and numbers with SymPy or Python before stating them.
   - When I push back, re-check before conceding. Confidence isn't evidence.
   - When a formula in a converted source looks garbled, read that PDF page directly.
5. **Teach for understanding, not recipes.** Where they help:
   - why this definition, and what breaks without each assumption
   - limiting and special cases
   - more than one representation (algebraic, geometric, computational)
   - links to things I already know from my profile
   
   For derivations, go problem-first and leave gaps: I do the next step.
6. **Record.** Tag the turn: concepts touched, evidence (asked / explained correctly / misconception). Write it through `learnctl.py`. Offer a visualization when the concept is geometric or parametric.

### The `quiz` session

- **Picking items.** Draw due FSRS items plus new items for the concepts I'm weakest on. Interleave across units I've already reached, and never quiz on units past my position.
- **Item types, weighted toward understanding:**
  - derive or explain why
  - predict, then check
  - find the error in a proof
  - construct a counterexample
  - limiting or special case
  - drop assumption X and say what breaks
  - transfer to a new setting
  - which method applies (interleaved)
- **Generating an item.** Write the reference solution and step rubric first, and verify any computable part with SymPy. Save the item before showing it.
- **Running an item.** Ask for my confidence (1–5) **before** I answer. Grade step by step and name the missing or wrong step. Lean strict: LLM graders are known to be lenient.
- **After the session.**
  - Update the FSRS card and `learner.json`.
  - Re-test any open misconception later; mark it verified-resolved only when I then get it right.
  - Report calibration (confidence vs. accuracy) at the end.

### The `visualize` modes (built on the existing manim-workspace)

| Mode | When | How |
|---|---|---|
| **Beat stepper** (default) | Discrete logical steps, derivations | One `snapshot.py` pass over all indices. Pack the frames into one HTML file with prev/next, a slider and captions. ~5–15 s. |
| **Parameter slider** | One continuous knob on a Manim-styled picture | New `sweep.py`, a sibling of `snapshot.py`: the scene exposes `tracker`, a range and N (30–120). Output is WebP frames plus an HTML value label. Optional SVG frames when crispness matters. ~5–10 s. |
| **Live widget** | Two or more knobs, dragging, 3D rotation, open-ended exploration | JSXGraph or Plotly HTML, with no Manim involved. |
| **Video** | Only on request (the motion is the point, or it's for presenting) | The existing render ladder: `-w -l`, then `--hd`. |

**Where things run.**
- Scene code and outputs live in `<course>/.learn/viz/<slug>/`.
- Rendering uses `manim-workspace/.venv` with the working directory set to `manim-workspace`, so `custom_config.yml` (the 3b1b look) and `common.py` still apply. `snapshot.py` will need an `--out` option.
- The `visualize` skill delegates scene authoring to the existing `manimgl` skill's conventions (ManimGL, not Manim CE).
- Viewers are single self-contained HTML files with base64 WebP. They open in a browser, or in the app's browser pane.

### Hooks (later)

- **SessionStart:** when `.learn/` exists, print a one-line course status plus the number of due quiz items.
- **PreToolUse:** reject direct `Write`/`Edit` to `.learn/*.json`, so all state writes must go through `learnctl.py`.

---

## 3. Build phases

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | Answers to the open questions below; one real course folder to test on | — |
| 1 | `learnctl.py` (manifest, schemas, state writes) + `learn` skill with ingest/sync + tutor turn | Ingesting the test course gives a sensible `course.md` and `concepts.json`; questions from different positions get answers scoped to the curriculum; adding a lecture file re-ingests only that file |
| 2 | `quiz` skill + FSRS + strict grading | One quiz session runs end to end; items persist; a misconception moves observed → verified |
| 3 | `visualize`: stepper, `sweep.py`, HTML viewer template; then the live-widget path | A stepper and a slider for a test concept each render in under 20 s with no video encode |
| 4 | Hooks, the global profile, evals (skill-creator) on fixed test questions at different "expertise phrasings" | Evals show the response depth changes with how the question is phrased |

## 4. Decisions (2026-10-27)

- **PDF conversion: Marker on the GPU.** The machine has an RTX 4070 Laptop GPU with 8 GB. Marker goes into a dedicated uv env at `learning-skills/.venv` with CUDA PyTorch. When a formula looks garbled, Claude re-reads that page of the original PDF.
- **Materials:** PDF lecture slides, LaTeX sources, and textbooks/papers as PDF. PPTX, notebooks and transcripts are not a priority.
- **Visualization:** chosen per concept. Manim stepper or slider for derivations and one-knob pictures; a live JS widget for free exploration.
- **Test course:** one of the user's real courses. Path still to come.
- **Global profile:** seeded by a short interview on the first `/learn` run (the default; not asked).
- **Marker version:** pinned to `marker-pdf` 1.10.x.
  - Marker 2.0 (surya 0.22) moved its models into a separate vLLM (Docker) or llama.cpp server.
  - 1.10 runs on PyTorch in-process. With `force_ocr`, inline math comes out as LaTeX at about 7 s/page on the RTX 4070.
- **Layout:**
  - Skills are developed in `learning-skills/{learn,quiz,visualize}/` and junctioned into `~/.claude/skills/`.
  - `learnctl.py` is stdlib-only, so system Python can run it. Only `convert` shells out to the venv's Marker.

## 5. Phase 2 (built 2026-10-27)

**`quiz` skill** (`learning-skills/quiz/SKILL.md`, junctioned into `~/.claude/skills/quiz`):
- Items are written with a reference solution and rubric before they are shown.
- The learner gives a confidence of 1–5 with the answer, before feedback.
- Grading is strict, criterion by criterion, with SymPy checks.
- FSRS scheduling uses py-fsrs 6.3.2, loaded from the venv by the stdlib `learnctl`. There is one 10-minute learning step, so a missed item recurs in the same session.

**`learnctl quiz plan | add | show | record | list | stats`:**
- `plan` returns due reviews, then "addressed" misconceptions to re-test, then new items on the weakest concepts.
  - On a cold start, ties break by importance: number of dependents plus a bonus for theorem/result/method.
  - Picks interleave across units.
- `record` maps score and confidence to an FSRS rating:

  | Score | Rating |
  |---|---|
  | below 0.5 | Again |
  | 0.5 to below 0.8 | Hard |
  | 0.8 and above | Good |
  | 0.95 and above, with confidence ≥ 4 | Easy |

  It also adds per-concept evidence and a calibration entry, and flags when a targeted misconception can be marked verified.
- `stats` reports calibration by confidence level and the over/underconfidence bias.

**Also added during the first real ingest (neural_circuit):**
- `audit` checks for dropped minus signs.
- `concept move` reassigns concepts when the real teaching order differs from the syllabus.
- `unit remove`.
- `course set --policy` records the course AI policy.
- Units take a kind and an active-assignment status.
- PPTX and notebook conversion.

## 6. Phase 3 (built 2026-10-27)

**`visualize` skill** (`learning-skills/visualize/`, junctioned into `~/.claude/skills/visualize`).

**`scripts/viz.py`** runs with the manim-workspace venv:
- `beats` uses the workspace's `snapshot.py`. It saves one frame after every `play()` and takes captions from trailing `#` comments.
- `sweep` hooks `Scene.tear_down` to step a `SWEEP` ValueTracker.
- `viewer` builds a single HTML page with base64 WebP frames. It has a slider, prev/next/play, arrow keys, KaTeX captions, and light/dark themes.

**`templates/live_linear2d.html`** is a JSXGraph widget: a 2-D linear network with a unit-arrow vector field, a draggable initial condition, ‖x(t)‖, eigenvalues and a normality check.

**Measured on neural_circuit:**

| Visual | Output | Time | Size |
|---|---|---|---|
| Sweep (`autapse-pitchfork`) | 56 frames, 720p | 17 s | 1.3 MB |
| Beats (`wta-nullclines`) | 8 frames, 1080p | 33 s | 257 KB |
| Live (`linear2d-explorer`) | checked against $8/e$ peak amplification for practice-exam $W_2$ | — | — |

**Lessons:**
- Never name a scene `scene.py`.
- Align axis ranges to the tick step and set decimal places on the labels.
- WebP `method=6` is too slow; use 4.
- The browser pane only shows local HTML as a static snapshot; serve it over HTTP to test.

## 7. Phase 4 (done 2026-10-27)

**Profile** (`~/.claude/learning/profile.md`):
- Neuroscience PhD student, strongest in neuroscience. Dynamical systems, linear algebra and probability/information theory are college-level but rusty.
- Math: intuition AND formal. Biology: formal first. Length: judged per question.
- The skills no longer assume an "expert researcher"; they defer to the profile.

**Hooks** (in `~/.claude/settings.json`, script `learn/scripts/learn_hooks.py`):
- SessionStart prints a one-line course status when the working directory is in a course.
- PreToolUse(Write|Edit) denies hand edits of `.learn/*.json`; `.learn/tmp/` is allowed. Verified live.

**Cleanups:**
- forward and duplicate `uses` references fixed
- git repo created
- the subagent-report hook now keeps paths inside `CLAUDE_PROJECT_DIR` with the project, not a nested repo

**Evals** (`evals/learn_cases.json`, `make_sandboxes.py`, `results/`):
- Six cases, three phrasing pairs, in sandboxes.
- Round 1: everything held except length, which ran 551–687 words for every route.
- Fix: word budgets per route, "offer, don't deliver", course material first, previews limited to 2–3 sentences.
- Round 2: A2 went from 654 to 245 words and B2 from 587 to 294, with quality intact.
- A1, B1, C1 and C2 are still to re-run after the next skill change.

## 8. Open questions (original)

1. **PDF conversion backend.** Choose one:
   - **(a)** Marker or MinerU run locally: best math, but a heavy PyTorch install, and much faster with an NVIDIA GPU. Do you have one?
   - **(b)** Claude transcribes each page during ingest: no install and high fidelity, but it costs tokens once per course.
   - **(c)** Plain text extraction for search, with Claude reading page images on demand.
   
   Leaning: (a) when a GPU is present, otherwise (b) for slides and (c) for long textbooks.
2. **Typical materials.** PDF slides? LaTeX notes? Textbook chapters? Lecture video transcripts? This sets which converters ship first.
3. **Global background profile.** Should I seed `~/.claude/learning/profile.md` now from a short interview (fields you're expert in, formal-first vs. intuition-first)?
4. **Visualization default.** Is Manim always the default, or should the skill pick a live JS widget when the concept is better explored than narrated?
5. **A test course.** Which folder should Phase 1 be developed against?
