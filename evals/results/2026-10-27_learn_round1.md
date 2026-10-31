# learn skill evals — round 1 (2026-10-27)

**Setup.**
- Cases: `evals/learn_cases.json`, three pairs of one topic asked two ways (precise vs broad, false premise vs precise, out of scope vs intuition).
- Each case ran in its own sandbox copy of the neural_circuit `.learn`, as an independent subagent invoking `/learn`.
- The replies (`round1/`, `round2/`) and agent reports are kept locally, not in the public repo, because they quote course material.
- Grading was done by the parent session against each case's `expect` list. The numbers were spot-checked independently with SymPy and NumPy: A1 eigenpairs; B1 peak ‖δs‖ = 2.01, gain 10/3, λmax(sym) = 4.10; B2 Schur form; C1 left eigenvector and kick shift (w_E+w_I)ε; C2 peak at √2σ.

| Case | Signal | Words | Passed | Missed |
|---|---|---|---|---|
| A1 | precise ("why is x1=x2 the stable manifold") | 640 | Exact reason (piecewise linearity makes linearization exact, plus exchange symmetry); no basics; cites L08; math right | Not short; added an unasked unequal-input section and a w=1 aside |
| A2 | broad ("I don't get the WTA slide") | 654 | Flagged the ambiguity (L08 p.6 vs L02 p.4); neuroscience bridge (owl data) first; one probe at the end; cites | A full mini-lecture instead of one key idea plus a probe |
| B1 | false premise ("stable ⇒ can't amplify") | 659 | "No to both parts" in sentence 1; mechanism; checked example; misconception recorded; **avoided the active P6 (used k=1.5) with a disclosure reminder** | Long; unasked "precise condition" section |
| B2 | precise (where w_ff=w(1+k) comes from) | 587 | Correct Schur entry derived and SymPy-checked; cites L10 p.15–16, 21 | Unasked normalization and Frobenius-norm section |
| C1 | beyond position (asked at L05 about L09) | 687 | Explicit "you're at L05, the balanced state comes in L09"; anchored in P2/L05; numbers right | Preview not minimal (went into L10 and the MT data); cited an outside paper unasked |
| C2 | intuition for f'²/f | 551 | Intuition AND formal (profile); score derivation; J=0 at the peak | Long; unasked √f-view section |

**Verdict.**
- What holds: correctness, grounding, citations, scope flagging, correcting false premises first, the active-assignment rule, and the profile's intuition+formal preference.
- The *structure* adapts to the phrasing (direct answer vs layered answer with a probe vs premise first).
- The *length* does not: every reply ran 551–687 words. That fails the Phase 4 "done" criterion. The cause is bonus sections: generalizations, alternative views, literature.

**Harness bugs found.**
1. The sandboxes had no original files, so every reply carried a "22 sources removed" note.
2. The replies were saved inside the course root, so they showed up as new sources.

Both are fixed in `make_sandboxes.py`: the originals and the cache are linked in as junctions, and replies go to `OUT/<id>_response.md`.

**Skill changes made** (`learn/SKILL.md` §3b–c, e):
- word budgets for each answer route
- "offer, don't deliver" for extensions
- course material before outside papers
- housekeeping as one line at the end, recognizing an unmounted drive rather than reporting deletions
- out-of-scope previews limited to 2–3 sentences
- pick 1–2 teaching moves, not all

Round 2 re-runs A2 and B2 to check.

## Round 2 (after the budget changes; fixed sandboxes)

| Case | Round 1 words | Round 2 words | Budget | Notes |
|---|---|---|---|---|
| A2 broad | 654 | 245 | 120–250 | One key idea, $\frac{d}{dt}(x_1-x_2)=(w-1)(x_1-x_2)+(b_1-b_2)$ (hand-checked), owl data bridge, ambiguity flagged, p.9 erratum, one probe. The closing offer is phrased as a question (acceptable as an offer). No false housekeeping. |
| B2 precise | 587 | 294 | 150–300 | Same derivation (disinhibition picture, then U entry by entry, SymPy-checked). The Frobenius aside shrank to a one-line offer. Rusty-linear-algebra refresher kept to one line, per profile. |

**Verdict:**
- Length now tracks the route, and the structure still differs: direct derivation vs one idea plus a probe.
- Correctness, citations and profile-fit are unchanged.
- Phase 4 "done" criterion: met for the re-run pair.
- A1, B1, C1 and C2 haven't been re-run. Re-run the full set after the next substantive skill change: `python make_sandboxes.py learn_cases.json OUT`, then one `/learn` agent per case.
