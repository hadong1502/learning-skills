# Research survey: prior art for a Claude Code "learn a math-heavy course" skill

Research subagent report, 2026-10-27.

## 1. Existing learning/tutoring skills and plugins

- **Anthropic `learning-output-style` plugin** ([repo](https://github.com/anthropics/claude-code/tree/main/plugins/learning-output-style); [docs](https://code.claude.com/docs/en/output-styles)). It uses a SessionStart hook to inject instructions into every session. Claude asks the user to write 5-10 lines at real decision points (marked `TODO(human)`) and does the boilerplate itself. It adds fixed-format "★ Insight" blocks with 2-3 points each. It keeps no learner state. The output style is now chosen via `/config`; `/output-style` has been removed.
- **Claude for Education "Learning mode"** ([Anthropic, Apr 2025](https://www.anthropic.com/news/introducing-claude-for-education)). It works inside Projects and uses Socratic prompts like "How would you approach this?" instead of giving answers. It was later rolled out to all users; the date could not be confirmed.
- **kirilxd/claude-tutor** ([repo](https://github.com/kirilxd/claude-tutor)). This is the best example of persistent learner state:
  - Skills: learn, quiz, review, resources, and a dashboard (Express server).
  - State lives in `~/.claude/learning/`: `index.json`, `profile.json`, `plans/<topic>-<date>.json`, and `progress/<topic>.json`, which holds SM-2 review schedules.
  - A SessionStart hook shows overdue reviews. PreToolUse hooks enforce the JSON schemas because Claude sometimes invents field names. That is a pitfall worth borrowing the fix for.
  - Plans come from web research, not from the user's own documents.
- **roundtable02/tutor-skills** ([repo](https://github.com/roundtable02/tutor-skills)). This is the closest to what we want:
  - `/tutor-setup` (Document Mode) scans PDF/MD/TXT/EPUB files with source mapping and builds an Obsidian "StudyVault": a `00-Dashboard/` (map of contents, quick reference, exam traps), numbered topic folders, concept notes, 8+ practice questions per topic with answers hidden in fold callouts, and `[[wikilinks]]`.
  - `/tutor` runs 4-question rounds and records attempts, correct count, last-tested date and error notes per concept, plus mastery badges per area.
  - It has no mechanism for adding new sources incrementally.
- **coding-tutor** (EveryInc compound-engineering plugin). It interviews the learner up front, builds tutorials from the user's own code, and quizzes with spaced repetition. Its SKILL.md could not be fetched (404), so this is unverified.

**Implications for design.** The pattern that works is a small set of skills (ingest/setup, teach, quiz/review) plus a learner-state folder made of plain JSON or markdown. Use hooks to validate the schema and to bring up due reviews at session start. None of these tools is aware of math or of where the learner is in the course. That gap is the opportunity.

## 2. Caching a folder of course materials

- **Karpathy's "LLM wiki" idea file** ([gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), Apr 2026; read directly).
  - It has three layers: immutable `raw/` sources, an LLM-maintained markdown wiki, and a schema file (CLAUDE.md or AGENTS.md).
  - Two special files: `index.md` (a catalog with one line per page, read first on every query) and `log.md` (append-only, with greppable `## [date] ingest | Title` entries).
  - Operations are **ingest** (one source at a time, which touches 10-15 pages), **query** (useful answers get filed back into the wiki), and **lint** (checks for contradictions, orphan pages, missing concept pages).
  - It says the index alone works "surprisingly well" up to about 100 sources and hundreds of pages, and recommends a search tool beyond that.
- **Claude Code itself dropped vector RAG.** Boris Cherny said early Claude Code used a local vector DB and that agentic grep/read worked better, citing index staleness and the liability of keeping a second copy of the data ([AI Engineer talk](https://www.ai.engineer/talks/UM6sFg_jdlE-rag-is-dead-right-kuba-rogut); [summary](https://smartscope.blog/ai-development/practices/rag-debate-agentic-search-code-exploration/)). The counterpoint is that embeddings are "cached compute" that can save tokens at scale.
- **qmd by Tobi Lütke** ([repo](https://github.com/tobi/qmd)). This is the hybrid option that the gist recommends.
  - One SQLite file holds an FTS5 BM25 index plus sqlite-vec vectors.
  - Local GGUF models: about 300MB for embeddings, about 640MB for the reranker, about 1.1GB for query expansion.
  - It has an MCP server and a `qmd update` command that hashes content and reports new, updated, unchanged and removed files.
  - Windows support is not stated. The docs mention only a Windows CUDA parallelism caveat, and it needs Node 22+.
- **NotebookLM-style source grounding** (answers cite the uploaded sources). Not researched in depth. The same goal can be met with page or slide citations in the markdown.

**Implications for design.** For one course of roughly 10-40 lectures, the simplest robust setup is: convert to markdown once, keep one `.md` file per lecture with page or slide anchors, write a compiled `index.md` / concept wiki, and let Claude grep. SQLite FTS5 (Python stdlib `sqlite3`, works on Windows) is a cheap optional step up for keyword search. Embeddings add install weight and staleness risk for little gain at this scale.

For incremental updates, keep a `manifest.json` that maps each source path to its sha256, mtime and the converter version used. Re-convert only files whose entry changed, then run a wiki "ingest" for the new lecture only. The gist's index/log/lint pattern carries over directly.

## 3. Math-preserving PDF and slide extraction

- **Benchmarks (olmOCR-bench, mixed versions).** Overall scores: Chandra 83.1, olmOCR v0.4 82.4, Marker 1.10 76.1, MinerU 2.5.4 75.2, Docling about 50 ([Codesota](https://www.codesota.com/ocr/benchmark/olmocr-bench); [dots.ocr paper](https://arxiv.org/pdf/2512.02498)). On the arXiv-math category, Marker scored 76.0 and MinerU 75.4. Several of these figures are self-reported by Datalab, the company behind Marker.
- **Marker** (`pip install marker-pdf`, PyTorch; runs on CPU, much faster on GPU). It outputs LaTeX math. A `--use_llm` mode (Gemini or Ollama) improves inline math and tables. The code is GPL and the weights are restricted to non-commercial use or small organizations; the exact thresholds were not checked. It is fine for personal research use.
- **MinerU 2.5.** Its `pipeline` backend runs on CPU. The VLM and hybrid backends need a GPU: one user reported the default hybrid backend running out of memory on 8GB, while VLM mode used about 4-5GB ([blog](https://www.nite07.com/en/posts/mineru-low-vram/)). Strong on formulas. Official Windows support not verified.
- **Docling.** Formula-to-LaTeX is off by default; turn it on with `--enrich-formula` / `do_formula_enrichment` (CodeFormula model) ([docs](https://docling-project.github.io/docling/usage/enrichments/)). It is pip-installable and works on Windows. It also handles PPTX and DOCX natively, which helps with slides.
- **pymupdf4llm.** It is fast and light but has **no LaTeX output**. A user bug report says layout mode silently drops formula blocks ([forum](https://forum.mupdf.com/t/layout-mode-silently-drops-the-text-of-blocks-classified-as-formula-to-markdown-to-text/361)). Avoid it for math.
- **Other tools.**
  - olmOCR needs a 12-20GB NVIDIA GPU on Linux (sources conflict) and has no CPU mode; on Windows realistically only via Docker.
  - Chandra (Datalab, 9B) runs in about 6GB at 4-bit.
  - Nougat is 2023-era, hallucinates on long documents and has effectively been superseded.
  - Mathpix is the best-known paid cloud option; not benchmarked here.

**Reading PDFs directly with Claude.** Claude processes each page as extracted text plus an image, at about 1,500-3,000 text tokens per page plus image tokens ([docs](https://platform.claude.com/docs/en/build-with-claude/pdf-support)). In Claude Code, the Read tool requires a `pages` range for PDFs over 10 pages and allows at most 20 pages per call. No head-to-head study was found comparing page images with converted markdown for math accuracy.

**Implications for design.** Use a hybrid:
- If LaTeX or `.tex` sources exist, use them directly (they are the best source).
- Otherwise run a one-time local conversion: Marker or MinerU for PDFs; Docling or python-pptx for slides; `jupyter nbconvert --to markdown` for notebooks.
- Keep page anchors and the original PDF, and have Claude Read the actual page image when a formula looks garbled or a figure matters. Direct reading on every query costs too many tokens to rely on.
- Make the converter pluggable and record which one was used in the manifest.

## 4. Curriculum and prerequisite structure

- **LLMs can recover concept graphs reasonably well.** Zero-shot LLM concept-graph recovery is competitive with supervised methods (about +3% F1) on NLP-education data, and the same paper introduces the TutorQA benchmark ([arXiv 2402.14293](https://arxiv.org/abs/2402.14293)). Zero-shot prerequisite-skill prediction has also been evaluated against expert taxonomies ([arXiv 2507.18479](https://arxiv.org/html/2507.18479v1)).
- **Lecture-specific systems.**
  - ConceptThread ([arXiv 2401.11132](https://arxiv.org/pdf/2401.11132)) extracts concepts with GPT-3.5, but derives "sequence" edges from timestamps rather than from LLM prediction. That is a useful trick: course order gives "seen-before" for free.
  - TSConnect ([arXiv 2503.09062](https://arxiv.org/pdf/2503.09062)) builds an LLM-extracted dependency graph and uses Wikipedia to disambiguate concepts.
  - LECDPR ([IJCAI 2026](https://www.ijcai.org/proceedings/2026/0567.pdf)) uses two-stage prompting (concept description, then contextual evidence) before predicting prerequisites. Full text not read.
  - LectureBank ([arXiv 1811.12181](https://arxiv.org/pdf/1811.12181)) is the standard dataset.
- **Math-specific models.** Lean blueprints and KnowTeX ([arXiv 2601.15294](https://arxiv.org/pdf/2601.15294v1)) model definitions and lemmas as nodes with explicit `\uses{}` edges. The Mathlib network study found that 74% of dependencies are implicit, which warns that extracted graphs will be incomplete.

**Implications for design.** Don't aim for a full prerequisite graph. Build a **first-introduced index** instead. During ingest, extract per lecture: the definitions, theorems and notation introduced (with page anchors), plus the earlier concepts each one uses. Store this as `concepts.json` or a markdown table: concept → lecture/page introduced → depends-on.

"Already seen at lecture N" then becomes a simple filter on lecture order and needs no inference. Use the LLM only for the depends-on edges, and treat those as soft hints. For LaTeX sources, `\begin{definition}` and `\label` give high-precision extraction.

## Unverified items
- The exact Marker license thresholds.
- olmOCR VRAM requirements (sources conflict).
- Official Windows support for MinerU and qmd.
- The contents of coding-tutor's SKILL.md.
- The date Claude Learning mode became available to everyone.
- Benchmark numbers that mix tool versions or are self-reported by vendors.
