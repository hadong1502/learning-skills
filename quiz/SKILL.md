---
name: quiz
description: >-
  Quiz the learner on a course indexed by the `learn` skill (the
  current folder has .learn/). It mixes spaced-repetition reviews (FSRS), re-tests
  of known misconceptions and new items on the weakest concepts, interleaved
  across lectures. Items test understanding: derive, explain why, predict,
  find the error, counterexample, limiting case, drop an assumption, transfer.
  Each item gets a reference solution and rubric before it is shown, a
  confidence rating before feedback, and strict step-by-step grading. Use for
  /quiz, "quiz me", "test me on L08", exam prep, or "what's due".
argument-hint: "[midterm | due | L08,L09 | stats]"
---

# Quiz

The point is retrieval and diagnosis, not reassurance. Items should make the
learner think for 3–10 minutes, not recall trivia. Pitch difficulty from
`~/.claude/learning/profile.md` and their mastery record: where a math tool is
rusty, test the tool on its own before stacking it into a multi-step derivation.
Course state is shared with the `learn` skill.

```bash
L="python -I $HOME/.claude/skills/learn/scripts/learnctl.py"
PY="S:/coding_support/claude_skills/learning-skills/.venv/Scripts/python.exe"   # SymPy / NumPy
```

All state writes go through `$L`; never edit `.learn/*.json` by hand.

## 0. Start

1. Run `$L status`. If there is no `.learn/`, tell the learner to run `/learn` in the course folder first, and stop.
2. Note the course AI policy and any `ACTIVE ASSIGNMENT` lines from the status output.
3. Pick a mode from the argument:

   | Argument | Session |
   |---|---|
   | (none) | `$L quiz plan --n 5`: due reviews first, then misconception re-tests, then new items on weak concepts |
   | `due` | due reviews only |
   | `L08,L09` | `$L quiz plan --n 5 --units L08,L09` |
   | `midterm` / `exam` | `$L quiz plan --n 6` over everything in scope, plus the exam unit's summary (topics, practice-problem style). Mix short conceptual answers with one multi-part derivation, like the practice exam |
   | `stats` | `$L quiz stats` and `$L misc list`, then stop |

Tell the learner the plan in one line ("5 items: 2 reviews, 1 re-test of M2, 2 new on L09/L10").

## 1. Write new items, before showing any

For each concept the plan asks for, and for each misconception to re-test:

1. **Read the material.**
   - Run `$L context --concepts <id>` and read the cited source passage.
   - If `context` prints `CHECK PAGE IMAGE`, look at the page (`$L page …`) before trusting a formula.
2. **Choose a type that forces understanding.**

   | Type | What it asks |
   |---|---|
   | `derive` | Produce a result from the model. |
   | `explain-why` | Mechanism or reason, not definition. |
   | `predict` | What happens if we change X? Commit before computing. |
   | `find-error` | A plausible but wrong argument; find the flaw. Course errata and the dropped-minus examples make good seeds. |
   | `counterexample` | Show a claim is false in general. |
   | `limiting-case` | Check a result at an extreme. |
   | `drop-assumption` | Remove an assumption (symmetry, normality, w = 1) and say what breaks. |
   | `transfer` | Same tool, new setting. |
   | `which-method` | Interleaved: which analysis applies, and why? |
   | `compute`, `interpret-figure` | When the skill itself is the point. |
   | `recall` | Only for a definition the rest depends on. |

3. **Write the reference solution and rubric first.**
   - The rubric is 2–5 criteria with points. The crucial step gets its own criterion.
   - Verify every computable part with `$PY`, and put the check in `check` (e.g. `"sympy: simplify(J - Matrix(...)) == 0"`).
   - If you can't solve it cleanly, don't ask it.
4. **Respect the course.**
   - Use its notation, and cite the source in `source` (e.g. `"L10 NN p.17"`).
   - Never reuse or lightly paraphrase a problem from an `ACTIVE` assignment. Items on the same concepts are fine.
   - Practice exams and psets with released solutions can inspire `transfer` variants; rewrite them, don't copy them.
5. **For a misconception re-test**, set `"targets_misconception": "M3"`. Make the item one where the misconception leads to a wrong answer.
6. **Save before asking.** Write the batch to `.learn/tmp/quiz_<date>.json` (fields: `prompt`, `type`, `concepts`, `reference_solution`, `rubric`, optional `check`, `source`, `targets_misconception`), then run `$L quiz add <file>`.

## 2. Ask, one item at a time

- Show the prompt with `$L quiz show Q007`, without the solution, and no hints.
- Ask for the answer **and a confidence of 1–5 in the same reply**: "how sure are you this is right?". Collect the confidence before any feedback; it powers calibration and hypercorrection.
- Answers can be LaTeX, plain text, or a photo or scan of handwritten work (Read the image).
- If the learner says "skip" or "don't know", record score 0 and confidence 1, then teach the item briefly.

## 3. Grade strictly

LLM graders are known to over-credit proofs. Counter that:

- **Go criterion by criterion.** Award points only for what is actually on the page; an unstated step earns nothing. "Clearly" or "it follows" does not stand in for an argument.
- **Check symbolic and numeric answers with SymPy or NumPy, not by eye.** Equivalent forms get full credit.
- **Name the gap precisely.** Quote the line that is wrong or the step that is missing. Don't give a holistic "mostly right".
- **When unsure, mark down and say why.** The learner can contest.
- **If they contest, re-derive independently.** Change the grade only on evidence; confidence and authority aren't evidence.
- **Feedback stays short.**
  - Give the score with per-criterion marks, the gap, and a targeted explanation. The full reference solution comes only if the gap is large or they ask.
  - After a **high-confidence miss**, say so plainly. That surprise is when correction sticks.
  - Sometimes ask for a one-line self-explanation of the corrected step.

## 4. Record

- After each item, run `$L quiz record Q007 --score <fraction of rubric points> --confidence <1-5> --notes "<the gap, in a few words>"`.
- If the learner disputes the automatic FSRS rating (1 Again, 2 Hard, 3 Good, 4 Easy), override it with `--rating`.
- A new misconception surfaced: `$L misc add --concept <id> --desc "…"`. Once feedback has addressed it: `$L misc set --id M4 --status addressed --note "…"`.
- If `record` says a targeted misconception was answered correctly and it was `addressed`, run `$L misc set --id M3 --status verified --note "Q007 correct"`. Only a later, separate item can verify a misconception.

## 5. Close

- Run `$L quiz stats`. Report in a few lines:
  - the per-item scores
  - calibration (overconfident, underconfident or well calibrated)
  - the weakest concepts
  - what's due next, and when
- Add `$L log --kind quiz --text "<items, scores, misconceptions>"`.
- Offer one next step, e.g. `/learn` on the weakest concept, or another round on a unit.
