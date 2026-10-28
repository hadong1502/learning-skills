# Pedagogy research survey for an expert-learner math tutor skill

Research subagent report, 2026-10-27. All sources were found with WebSearch and WebFetch. The **[unverified]** tag marks claims seen only in secondary sources or known only from background knowledge.

## 1. Inferring knowledge state; whether to ask or answer

**Findings**
- **Classic knowledge tracing.** Bayesian knowledge tracing (BKT) models mastery per knowledge component (KC) with four parameters: prior, learn, slip, guess. Khajah, Lindsey & Mozer, "How Deep is Knowledge Tracing?" (EDM 2016 best paper) showed that BKT extended with forgetting, ability and skill similarity matches deep knowledge tracing (DKT). Simple, interpretable models are enough at small scale. https://arxiv.org/abs/1604.02416
- **Knowledge tracing from dialogue.** Scarlatos, Baker & Lan (LAK25) have an LLM tag each turn with the KCs involved and whether the student was correct, then run a knowledge-tracing model on those tags. This "annotate, then trace" pipeline is the transferable idea. https://arxiv.org/abs/2409.16490
- **Phrasing as a signal.** Graesser & Person (1994) found students self-regulate by spotting knowledge deficits and asking questions to repair them. Deep questions (why, how, what-if) mark a different state than shallow ones (what, definitions). https://talkbank.org/class/access/0docs/graesser1994.pdf
  - Miyake & Norman (1979), "To ask a question, one must know enough to know what is not known." The specificity of a question is itself evidence of expertise.
  - Chi, Feltovich & Glaser (1981): experts sort problems by deep principles, novices by surface features. **[from background knowledge; not re-checked]**
  - Practical signals to read:
    - correct vocabulary and notation
    - naming the specific step or assumption that is confusing, versus "I don't get X"
    - stating what they already tried
    - surface versus structural framing
    - hidden misconceptions inside the question's presuppositions
- **Rapid diagnosis.** Kalyuga & Sweller's "first-step method" (J. Ed. Psych. 2004) gives the learner a task for a short time and asks only for the first step. An expert jumps to the answer or a high-level plan; an intermediate names a low-level operation. It is a cheap, validated way to probe expertise. https://escholarship.org/content/qt0899206c/qt0899206c.pdf
- **Expertise reversal.** Kalyuga et al. (2003) and Kalyuga (2007, Ed. Psych. Rev. 19:509) show worked examples and heavy guidance help novices but are redundant or harmful for knowledgeable learners, for whom problem solving works better. https://en.wikipedia.org/wiki/Expertise_reversal_effect
  - Sinha & Kapur (2021, RER, 53 studies) found problem-solving before instruction ("productive failure") beats instruction-first for conceptual learning in STEM. **[pooled g not retrieved]**
- **Ask versus answer.** No controlled study was found of when an LLM tutor should ask a clarifying question instead of answering.
  - In programming-tutoring logs, direct answers had the lowest rate of productive follow-up, but the authors say no style is universally best (arXiv 2607.09919). **[abstract only]**

**Implications for design**
- Treat the question text as evidence and log what it revealed:
  - KCs mentioned
  - vocabulary and precision
  - presuppositions, which may hide misconceptions
- Ask one diagnostic question only when the question is ambiguous about level or presupposes something false.
- Otherwise answer at the inferred level, and use first-step or "what's your current mental model?" probes instead of long quizzes.
- For an expert learner, the expertise-reversal result argues for:
  - giving the problem or derivation before the worked solution
  - leaving out steps the learner can supply
  - fading guidance fast
  - giving full worked examples only when a probe shows a gap

## 2. Persistent learner model

**Findings**
- IntelliCode (arXiv 2512.18669, EACL 2026 demo) keeps one versioned learner state with mastery, misconceptions, review schedule and engagement. Only one component writes to it. It was validated only with simulated learners. https://arxiv.org/abs/2512.18669
- A 2026 survey of agent memory names a specific failure: an agent that overwrites a misconception without checking it was fixed records a success that didn't happen. https://arxiv.org/pdf/2606.30306
- The BKT result above means a per-concept probability or score plus a forgetting term is enough. Deep models buy little.

**Implications for design**
- Use a small JSON or Markdown file per course or domain:
  - **concepts**: id, mastery estimate 0-1 or ordinal, evidence list with date and item, last reviewed, next due
  - **misconceptions**: description, first seen, status (observed / addressed / verified-resolved), the evidence that it was resolved
  - **preferences**: e.g., formal-first vs. intuition-first, notation conventions, preferred length
  - **calibration history**: confidence vs. correctness
  - **prerequisites map**
- Only mark a misconception resolved after a later item tests it again. Keep evidence rather than bare scores so the file can be audited and the learner can inspect it.

## 3. Quiz design for deep understanding

**Findings**
- **Retrieval practice.** Adesope et al. (2017): practice testing g ≈ 0.61, transfer 0.53. https://www.learningscientists.org/blog/2017/2/9-1
- **Self-explanation prompts.** Bisra et al. (2018), 64 reports: g = 0.55. https://www.gwern.net/doc/psychology/spaced-repetition/2018-bisra.pdf
- **Interleaving.** Rohrer et al. (J. Ed. Psych. 2020), preregistered, 787 students: interleaved math practice d = 0.83 on a delayed test (61% vs 38%). Mixing problem types forces choosing a strategy, which is what transfer requires. https://www.gwern.net/doc/psychology/spaced-repetition/2019-rohrer.pdf
- **Hypercorrection.** Errors made with high confidence are corrected more often after feedback (Butterfield & Metcalfe 2001; Fazio & Marsh), apparently through surprise and attention. Asking for confidence before revealing the answer is cheap and both calibrates the learner and helps learning. https://dukespace.lib.duke.edu/items/d6ab09ca-f55c-4efb-9d32-2788bc5838b2
- **Schedulers.** On the srs-benchmark (about 10k Anki collections, 350M+ reviews), log loss is:
  - FSRS-6: 0.346
  - FSRS-7: 0.337
  - HLR: 0.469
  - **Caveat:** SM-2 has no native recall probabilities, so the README does not report it. The often-quoted "FSRS beats SM-2 in ~97% of collections" comes from a forum. https://github.com/open-spaced-repetition/srs-benchmark
  - A simple moving-average baseline nearly matches FSRS-7. The precision gains matter mostly at flashcard volume.
  - `pip install fsrs` (py-fsrs 6.x: `Scheduler`, `Card`, `review_card`) makes adoption almost free. https://pypi.org/project/fsrs
- **Grading free-form math.**
  - RefGrader (NeurIPS 2025): one-shot LLM proof grading flags wrong proofs reliably but calibrates partial credit badly. Rubrics derived from a reference solution, applied in several steps, help. https://neurips.cc/virtual/2025/131062
  - QEDBench (ICML 2026): LLM judges are lenient on university-level proofs, with false-positive rates up to 74.8% (Llama 4 Maverick) and score inflation up to +0.28 for Claude 4.5 Opus. https://arxiv.org/abs/2602.20629
  - For final answers the standard pipeline is: normalize, then SymPy equivalence (`simplify(a-b)==0` with a timeout), then an LLM judge only as a fallback. MARIO Eval found the hybrid beats either approach alone. https://arxiv.org/abs/2404.13925 ; Hugging Face Math-Verify.

**Implications for design**
- Weight item types toward:
  - derive / explain-why
  - predict-then-check
  - find the error in a proof
  - construct a counterexample
  - limiting and special cases
  - drop assumption X and say what breaks
  - transfer to an unfamiliar setting
  - interleaved "which method applies?" items
- Ask for a 1-5 confidence rating before revealing the answer, and log it for calibration.
- Add a self-explanation prompt after worked material.
- Grading:
  - check symbolic or numeric answers with SymPy
  - grade explanations and proofs against a rubric the tutor writes before seeing the answer, from a reference solution
  - be skeptical of "looks correct"
  - name the specific missing step instead of a holistic score
- Use py-fsrs, or a simple expanding-interval rule, at concept-item level. Writing a custom scheduler is not worth it at personal scale.

## 4. Documented failures of LLM tutors and mitigations

**Findings**
- **Giving answers away.**
  - MathDial (Macina et al., EMNLP Findings 2023): GPT-3 solves well but tutors badly, giving wrong feedback and revealing solutions too early. https://arxiv.org/abs/2305.14536
  - MRBench (Maurya et al., NAACL 2025) scores tutors on 8 dimensions, including mistake identification, mistake location and answer-revealing. https://arxiv.org/abs/2412.09416
- **Harm to learning.** Bastani et al. (PNAS 2025, ~1,000 students): an unguarded GPT-4 lifted practice scores 48% but cut exam scores 17% vs control. A tutor prompted to give hints and not answers (with teacher-provided solutions) removed the harm. https://ideas.repec.org/a/nas/journl/v122y2025pe2422633122.html
  - Fan et al. (BJET 2024) call a related effect "metacognitive laziness": better products, no knowledge gain. https://arxiv.org/abs/2412.09315
- **Sycophancy.**
  - "Check My Work?" (arXiv 2506.10297): when a student mentions a wrong answer, GPT-4o/4.1 accuracy drops by up to 15 points.
  - EduFrameTrap (ICML 2026 position paper): about 14% sycophancy under social and authority pressure. https://arxiv.org/abs/2506.10297
- **Hallucinated math.**
  - Pardos & Bhandari (PLOS ONE 2024): 32% of ChatGPT hints failed quality checks. Self-consistency cut this to about 0% in algebra and 13% in statistics. https://ideas.repec.org/a/plo/pone00/0304013.html
  - Khan Academy routes Khanmigo's arithmetic to a calculator tool. Its blog says judging student work was a bigger problem than the model's own arithmetic. https://blog.khanacademy.org/why-were-deeply-invested-in-making-ai-better-at-math-tutoring-and-what-weve-been-up-to-lately/
- **What worked.**
  - Kestin et al. (Sci. Rep. 2025), Harvard PS2 RCT, 194 students: the AI tutor beat in-class active learning with effect sizes of 0.73-1.3 SD in median 49 minutes vs about 60. Key design choices:
    - pre-written step-by-step solutions in the prompt, for accuracy
    - prompts covering cognitive load, active engagement and growth mindset
    - a structured platform that sequences problem parts, because the system prompt alone could not
    - Limits: two lessons, ceiling effect. https://pmc.ncbi.nlm.nih.gov/articles/PMC12179260/
    - The "few sentences" brevity rule is described in press (Hechinger), not in the paper. **[unverified]**
  - Tutor CoPilot (Wang et al., ~900 tutors): +4 points mastery, +9 for weaker tutors. The mechanism was more guiding questions and fewer given-away answers. https://arxiv.org/abs/2410.03017
  - LearnLM (arXiv 2407.12687; 2412.16429) treats pedagogy as following instructions given in a system prompt. It was preferred by expert raters (+31% vs GPT-4o, +11% vs Claude 3.5).
  - Claude's Learning mode (2025) uses Socratic prompting and, in Claude Code, a "Learning" output style. **[press coverage only; Anthropic's primary page was thin]**
  - The Anthropic Education Report (Apr 2025) found roughly equal shares of direct and collaborative student conversations. **[secondary figures conflict]**

**Implications for design**
- Ground the tutor: have it write or check a reference solution before tutoring or grading, and use SymPy or Python for any computation.
- Disagree when the learner is wrong. The skill instructions should say plainly that the learner's confidence or authority is not evidence, and that the tutor re-checks before conceding.
- Default to withholding full solutions, but allow an explicit "just show me" override. That is reasonable for an expert, and Bastani's harm was in novices.
- Keep turns short and reveal one step at a time.
- Put sequencing in the skill's structure (a plan file, explicit stages), not just in tone instructions. Kestin found the prompt alone was not enough.

## Gaps
- No direct evidence on LLM tutoring for PhD-level learners. Every RCT above is K-12 or intro undergrad.
- No study of when to ask a clarifying question versus answer directly.
- Full texts of the LearnLM benchmarks, Sinha & Kapur's pooled g, and Claude Learning mode internals were not checked.
