# Validity audit

UFM-18, 2026-11-23. Each item of the book's checklist (13.5.1 to 13.5.6), its threats (1.3), its
evidence types (1.2) and its durable-evaluator properties (11.9.1), plus the bullets of UFM-18,
answered for this study: **Yes**, **Partly**, **No** or **N/A**, with the file and number behind
it. The book's wording comes from `docs/notes/book_validity_and_causality.md` (sections 1, 2 and
5); those notes were written before the main run and say 3 runs at temperature 0.7, while the run
has 3 runs for block-1 items and 2 for the rest (`results/full/findings.md`), so the answers below
use the results. Nothing here is recomputed except the three new checks in section 6; a few
counts are taken over existing tables, and say so. The
deviations made today are in `docs/decisions.md` (2026-11-23).

Results files are cited by short name: `analysis` = `results/analysis/findings.md`, `reliability`
= `results/reliability/findings.md`, `full` = `results/full/findings.md`, `claude` =
`results/claude/findings.md`, `layout` = `results/layout/findings.md`, `block1` =
`results/block1/findings.md`, `audit` = `results/audit/summary.md`.

## 1. UFM-18 checklist

1. **Construct and indicator (13.5.1).** Yes. The construct is completing one function or method in
   a Java or Python repository with the repository's code as context (`docs/methodology.md` 3.2);
   the indicator is the run-averaged binary pass of the target tests. Copies of the reference
   (section 1.3), the floor (item 13.5.6-20) and misreading (item 1.9) are where the two part.
2. **Item-level bias by condition (1.3.4, 13.5.2).** Partly. The item:condition SD is 0.913 [0.603,
   1.210] on CoderUJB and 1.386 [1.268, 1.509] on DevEval, and the held-out log-likelihood gains
   +4.8 (SE 5.1) and +182.2 (SE 47.3) from it (`analysis`, GLMM). No item:condition mode survives
   BH (0 of 544 and 0 of 3384; 1 and 38 with a raw interval excluding 0), so no list of the items
   with the largest shrunken penalty is reported (not computed; the modes are in
   `results/analysis/glmm_item_flags.csv`). By letter size, 14 px beats 12 px for Qwen3.5 27B on
   both benchmarks (+8.8 and +6.4 pp) and for Mistral and Qwen3.5 9B on DevEval (+4.2, +4.1), with
   intervals above 0 (`analysis`, differences between sizes). By model, equal contrasts are
   rejected: Wald chi2 40.15 and 127.34 on 4 df, p 4.0e-08 and 1.5e-26 (`analysis`). Mantel-Haenszel
   DIF is not used, for the reason in `docs/methodology.md` 3.3.
3. **Contamination (1.3.3).** Yes. Other models copy the reference token for token in 155 text
   answers on 25 CoderUJB items and 934 on 149 DevEval items; removing each model's flagged items
   (22 to 25 and 141 to 146) shrinks 39 of the 40 gaps and leaves all 40 negative, the smallest at
   -6.9 pp (`analysis`, Contamination; counts over its tables). Against matched random removal the
   shrink is above the control's 97.5% point for 3 of 5 models in each benchmark and below the
   range for Qwen3.5 27B on DevEval; some bins were short of unflagged items, so the control
   removes slightly fewer items. Contamination is flagged, not removed, and absolute rates are
   inflated.
4. **Scoring across conditions.** Partly. No answer is empty in any cell. Truncation at 2048
   tokens reaches 11.5% (CoderUJB text) and 13.2% (DevEval image14), both Qwen3.5 9B; no extractable
   code reaches 4.8% (Qwen2.5-VL 7B, CoderUJB image10); no def line of the target reaches 17.8%
   (Gemma 4 12B, DevEval image10, against 11.8% in text) (`analysis`, scoring shares). A re-score of
   70 answers gave the same verdict for all 70 (`full`, Re-score). The checks in section 6 found
   13 DevEval items (1.5%) that could not be passed because of how answers are spliced in
   (confirmed by a regrade of their references, then excluded), and an
   extraction rule that grades the first code block when a reply gives a corrected second one
   (4 of 40 hand-read failures). The hand read is on Claude Sonnet 5.5, not an open model.
5. **Content coverage (1.2.1).** Partly. 136 Java methods from 14 Defects4J projects and 846 Python
   functions from 79 repositories (`analysis`, Gaps), every item used except the 13 DevEval items
   the splice made unpassable (section 6). Not covered: debugging, code
   review, multi-file edits, screenshots of real IDEs (`docs/methodology.md` 3.2). There is no
   blueprint by sub-domain and no expert review of the items (not computed).
6. **Reliability (ch. 5).** Yes. Variance components with runs nested in cells and MCMC intervals;
   the reliability of a model's item score at 2 runs is 0.741 to 0.807 (CoderUJB) and 0.803 to
   0.862 (DevEval), and the observed run 0 vs run 1 correlation is 0.594 to 0.629 and 0.664 to
   0.759. G for ranking the five models (finite set) is 0.846 to 0.944 on CoderUJB except 12 px,
   0.606 [0.014, 0.856], and 0.920 to 0.984 on DevEval (`reliability`). 13 of 16 fits pass the
   convergence gate; the other 3 (DevEval image12 and image14) fail on s2_model only, which none of
   these numbers uses (`docs/decisions.md` 2026-11-25). No SEM per condition, by design
   (`docs/methodology.md` 3.3).
7. **Durable evaluator (11.9.1).** Partly; see section 5.
8. **Claude extension.** Yes, exploratory. The copy flag over the other 6 models marks 126 (Sonnet)
   and 106 (Opus) of 136 CoderUJB items and 673 and 492 of 846 DevEval items, so on CoderUJB the
   matched control is uninformative. 0 refusals and 0 request errors in 15,920 replies; 1 Sonnet
   max_tokens and 1 Opus over_budget, both DevEval text. No seed, temperature 1.0, 2 runs, and Opus
   thinks in 45 replies, at most 3.0% of output tokens (`claude`, Contamination and ceiling,
   Replies; addendum in `docs/methodology.md`).
9. **Reading vs coding.** **Placeholder (UFM-28).** Planned in `docs/methodology.md` 3.3 (lines 212
   to 218) with the transcription test (UFM-12); in the paper only if UFM-28 is done by 2026-11-28.
   Until then the only evidence is exploratory: in block 1, answers with a missing name rise from
   8% to 31% of DevEval answers and 17% to 40% of CoderUJB answers from text to image, and about 400
   DevEval image answers use a context name with an underscore dropped or added (`block1`, Why
   image answers fail), from grader output that is not in the repo.

## 2. Book 13.5 checklist

Numbering follows the notes (23 lines).

**13.5.1 Construct definition**

1. Explicit construct, and what it is not. Yes. `docs/methodology.md` 3.2.
2. Content domain and blueprint. Partly. Item 1.5 above.
3. Construct vs indicator. Yes. Item 1.1 above.

**13.5.2 Item development and calibration**

4. IRT calibration on diverse models. No. Five models are too few, and many items are all-pass or
   all-fail (item 20); item effects are random terms in the GLMM.
5. Item screening by item-total correlations and fit. No (not computed). Every item is used
   except the 13 DevEval items the splice made unpassable (section 6).
6. DIF across families. Partly. No Mantel-Haenszel; the GLMM's item:model SD is 1.344 (CoderUJB)
   and 1.380 (DevEval) and the model x condition Wald test rejects equal contrasts (`analysis`).
7. Audit item content for errors. Partly. Items were kept only if the reference passed our grader
   (`benchmarks/*/results/gold_results.jsonl`), but that run tests the unmodified source and never
   goes through the answer splice. 10 items no model passes were desk-checked (section 6): 6 are
   likely harness artifacts and 3 are under-specified. No full content review.

**13.5.3 Evaluation design**

8. Response format. Yes. Binary pass of the target tests, averaged over runs, which drops partial
   credit.
9. Adaptive testing. N/A. Every item is used.
10. Judge protocol. N/A. Unit tests.
11. D-study for the budget. Yes. Block 1 set 2 runs for the rest (`results/block1/dstudy.md`).

**13.5.4 Analysis and reporting**

12. Intervals, not point estimates. Partly. Every gap has a cluster interval (`analysis`); no SEM
    per condition, by design.
13. Reliability reported. Partly. G is reported for ranking only, and it is low at CoderUJB 12 px
    (item 1.6).
14. Aggregation rule. N/A, but stated: the mean over runs, not best of k (`docs/methodology.md`
    3.2).
15. Judge agreement. N/A.

**13.5.5 Validity and generalization**

16. Content validity. Partly. Item 1.5.
17. Construct validity and external criteria. Partly. Image item logits correlate less with text
    than a one-ability reference predicts (index C at percentile 0.997 on CoderUJB and 1.000 on
    DevEval, `analysis`, GLMM); no criterion outside the benchmarks, and no no-context baseline.
18. Distribution shift. Partly. The gap by context length is reported as an exploratory moderator
    (`analysis`, Context length); no reweighting.
19. Known threats documented. Yes. This file and section 7.

**13.5.6 Maintenance and monitoring**

20. Saturation. Yes, at the floor: no model passes 52.2% to 62.5% of CoderUJB items and 50.6% to
    63.0% of DevEval items in an image condition, and 23.5% and 30.5% in text (`analysis`, floor
    and ceiling), after excluding the 13 DevEval items the splice made unpassable (section 6).
    Claude is at the ceiling on CoderUJB text, 97.4% (`claude`).
21. Contamination monitoring. Partly. One-time copy flag (item 1.3).
22. Recalibration. No. One-shot study.
23. Living item bank. No. Static public benchmarks.

Count: Yes 6 (1, 3, 8, 11, 19, 20), Partly 9 (2, 6, 7, 12, 13, 16, 17, 18, 21), No 4 (4, 5, 22,
23), N/A 4 (9, 10, 14, 15).

## 3. Threats (1.3)

- **Construct-irrelevant variance.** Partly controlled. Wrapper, instruction and decoding are the
  same in every condition, and font size is a design factor; the layout is not: leading
  indentation is 17.3% (CoderUJB) and 18.4% (DevEval) of rendered characters, measured but not
  tested (`layout`). Vision-encoder downscaling differs by model and is not observed, so results are
  per model. Temperature 0.7 for the open models, against the book's preference for 0, was chosen to
  measure run noise (`docs/methodology.md` 3.1).
- **Construct underrepresentation.** Yes, a threat; the claim is narrowed to one function or method
  with repository context (item 1.1).
- **Contamination.** Item 1.3.
- **DIF.** Item 1.2 and 13.5.2-6.

## 4. Evidence (1.2)

- **Content.** Partly. Item 1.5.
- **Criterion.** Partly. Text scores as a concurrent criterion: Pearson correlations of item
  logits between text and an image size are 0.616 to 0.752 (CoderUJB) and 0.587 to 0.738 (DevEval)
  (`analysis`, GLMM); the unit tests are the outcome, not an independent criterion.
- **Construct.** Yes, the main evidence: the rendering is assigned by design to every model and
  item, everything else held fixed, and the gap is that intervention contrast (`analysis`, Gaps).
- **External.** Weak. Two languages, five open models, three sizes; not other renderers or model
  families.
- **Consequential.** No. Only the argument that a token saving counts if accuracy holds.

## 5. Durable evaluator (11.9.1)

- **Validity.** Partly. The construct is published, and the gap replicates across two benchmarks
  (mean of models -28.1 and -25.8 pp, `analysis`).
- **Durability.** No. Both benchmarks are public and static.
- **Faithful execution.** Partly. The plan was frozen before image data was graded and each
  deviation has a dated entry in `docs/decisions.md` (for example the Laplace held-out likelihood,
  2026-11-16, and this audit's deviations, 2026-11-23); the transcription test and the 30-failure
  hand read were not run as planned.

## 6. New checks

Both samples are drawn by `scripts/audit_sample.py` with seed 20261123; ids, labels and short
notes are in `results/audit/`, the counts in `audit`. The labels were drafted by Claude Code from
the requirement, the reference, the answers and the extracted code, and are **not checked by a
person**; nothing was regraded, since the test environments are on /snfs2.

**Hand read** (`results/audit/hand_read.csv`). 40 failed answers of Claude Sonnet 5.5 on DevEval, 10
 per condition. Labels: wrong logic 24, wrong or invented name 10, extraction 4, false fail 2,
 truncated, other function and unclear 0. Wrong names are 2 in text and 5 at 10 px, too few to
 compare conditions. False fails are 2 of 40, 5.0% (exact 95% CI 0.6% to 16.9%), and both are on
 items the harness check below flags. The 4 extraction failures are replies whose first code block
 is a draft and whose second block corrects it: `extract` in `src/codeimg/answers/deveval.py` takes
 the first block that parses and defines the target, and in all 4 the draft parses. Regraded with
 the second block (UFM-33), 2 of the 4 pass. One wrong-logic answer
 (`mopidy.internal.log.get_verbosity_level`) is on an item the next check finds under-specified.

**Items no model passes** (`results/audit/never_passed_check.csv`). 285 items are never passed by
the five open models; the gold run passes all 285 and a Claude model passes 267, leaving 18 (1
CoderUJB, 17 DevEval). Of 10 drawn, 9 are labeled test bug and 1 no bug:

- 6 look like harness artifacts (not regraded). In 4, `body_position` in our source copy starts at
  the `def` or decorator line of the target, so a body answer overwrites the signature. In 2, the
  body holds a triple-quoted string with lines at column 0, and `adjust_indent` (`textwrap.dedent`
  then `textwrap.indent`) shifts them. The gold run cannot catch either: it runs the tests on the
  unmodified source (`benchmarks/deveval/gold_check.py`).
- 3 are under-specified: the tests need behavior the requirement does not state and the context
  does not show (a None config value read as 0, an execution state set around the run, a named
  string helper).
- 1 looks like a real failure of every model (low confidence).

`audit_sample.py harness` then checked all 859 DevEval references for the two patterns
(`results/audit/harness_suspects.csv`; references read from `body_position` by
`codeimg.answers.deveval.gold_answer`). It flags 13 items: 9 offsets, every item of
`datasette/utils/asgi.py`, one of them starting inside the signature; and 4 re-indents, all in
`alembic/testing/env.py`. 12 of the 13 are passed by none of the 7 models, which makes 12 of the 18
items no model passes; 6 of the 12 were desk-checked, the other 6 are flagged by pattern only. The
check is a pattern match: it misses strings indented less than the body but not at column 0, and it
would flag a body that opens with a decorated nested function, which none of the 13 does. The 13th
(`alembic.testing.env.three_rev_fixture`) is passed by some answers, so a re-indent does not always
break the item.

**Regrade and exclusion (UFM-33, `docs/decisions.md` 2026-11-25).** The reference body of each of
the 13 was graded on the cluster through the answer path: all 13 fail with the main run's code and
pass with the fix in `src/codeimg/answers/deveval.py`. The cause is confirmed, so no answer could
pass them in the main run. The 13 are excluded from every reported analysis
(`manifests/excluded/deveval.txt`); DevEval has 846 items. Kept in, they shrank each DevEval gap by
about 1.4% of its size (arithmetic estimate before the rerun); the rerun without them moves the 5
open models' gaps by 0.8% to 1.5% of their size, and every conclusion holds. The model answers on the 13 were not regraded, and
the audit samples above were drawn from all 859.

## 7. Draft limitations for the paper

Each bullet points to the item that backs it. Draft only; UFM-14 writes the paper text.

1. Five open models from 7B to 27B and two closed models run exploratorily (temperature 1.0, no
   seed), so the gap is per model and may not hold for other families (items 1.8 and 4 External).
2. One renderer. Leading indentation is about 18% of rendered characters and its effect is not
   tested (section 3, construct-irrelevant variance).
3. No no-context baseline, so the share of a pass due to reading the context is unknown (item
   13.5.5-17).
4. Contamination and ceiling: other models copy the reference on 25 CoderUJB and 149 DevEval
   items; removing them leaves every gap negative but inflates absolute rates, and Claude is near
   the ceiling on CoderUJB text (items 1.3, 1.8, 13.5.6-20).
5. Reading vs coding is not measured unless UFM-28 lands by 2026-11-28; the misreading evidence is
   an exploratory block-1 count (item 1.9).
6. Item quality: 13 DevEval items could not be passed through our splice (confirmed by grading
   their references) and are excluded, and 3 of the 10 never-passed items checked need behavior
   the prompt does not give; the floor (51% to 63% of items not passed by any model in an image
   condition) partly reflects the items (items 1.4, 13.5.2-7, 13.5.6-20).
7. Item-level evidence: the item:condition variance is clear, but no single item survives BH,
   the hand read covers one model (Sonnet) and 40 answers, and its labels are not checked by a
   person (items 1.2, 1.4, section 6).
8. Narrow construct and static items: one function or method with repository context, in Java and
   Python, from public benchmarks; ranking at CoderUJB 12 px is unreliable (G 0.606) (items 1.1,
   1.5, 1.6, section 5).
