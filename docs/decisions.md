# Design decisions

Newest first. Each entry says what was decided and why, so a settled question is not reopened by
accident. The current plan is `docs/methodology.md`; this file explains how it got there.

## 2026-11-26: checksum manifests for the laptop-only inputs

Two inputs of committed results exist only on the laptop and are not copied anywhere else (UFM-37).
Each folder now has a `MANIFEST.sha256` (one `sha256  path` line per file, checked with
`shasum -a 256 -c MANIFEST.sha256` from inside the folder) and a `VERIFY.tsv` (path, line count
for jsonl files, sha256).

| Folder | What it holds | Files | sha256 of `MANIFEST.sha256` |
|---|---|---|---|
| `~/UFMG/ufm9-claude/` | every Claude reply, requests and page images (1.3 GB); input of `results/claude/` | 9861 | `baecd9932b9a21ad33aa7950cdaa588fd43d30b5d9326d3647963666e60bb528` |
| `scratch/contamination/` | the copy-check input of `results/analysis/contamination*.json` and the Claude gaps (74 MB) | 8 | `4132ec13aff8c4c37446ff22b25cb50560fef4eff0b4dcd5043e849137862fd8` |

- The Claude replies cannot be regenerated (temperature 1.0, no seed), so the manifest is the only
  way to show the files the results were computed from have not changed.
- The 8 contamination files match the earlier list in `scratch/ufm33/contamination_sha256.txt`.
- `~/UFMG/ufm9-open/` already had both files, from the copy off the cluster.

## 2026-11-26: the transcription test is stopped

The transcription test (UFM-12), and with it reading vs coding (UFM-28), will not finish before
the paper is due (2026-11-30). This settles the bonus rule of 2026-11-23 early: the paper reports
the test as planned in methods 3.3 and not finished.

- **Why.** Every cluster GPU we can use failed again on 2026-11-26. On medusa4 the GPU failed
  under Mistral Small 3.2 24B (job 92682, 08:53) and then under Qwen3.5 27B (92928, 08:59);
  medusa5 and medusa6 fail every probe, and medusa3 is drained ("gpu fell off the bus"). Another
  user's jobs now hold both medusa4 GPUs for about 2 days.
- **Where it stopped.** Two of the five models have complete generations: Qwen2.5-VL 7B and
  Qwen3.5 9B. On DevEval the other three stopped at 4735 (Qwen3.5 27B), 2523 (Mistral) and 1275
  (Gemma 4 12B) of 5154 rows each.
- **The partial work stays on branch `transcription-tests`** (the stage, the scorer and
  `results/transcription/run_notes.md`) and does not go to main.
- **Methods are left as written** (lines 196, 212 to 218 and 393 to 394). The only evidence on
  misreading stays the exploratory block-1 check in `results/block1/findings.md`.

## 2026-11-26: last-block sensitivity regrade of DevEval

A post hoc sensitivity analysis, added after the main gaps were seen (UFM-35). It changes nothing
in 3.3: the main analysis keeps the frozen first-block rule, and the line carries no Holm
adjustment.

- **Why.** `extract` in `src/codeimg/answers/deveval.py` grades the first fenced block that defines
  the target. Some replies write a draft and then revise it in a later block, almost only Qwen3.5
  9B on images, so the first-block rule could inflate its gap.
- **Rule.** A reply on the kept items is in scope when 2 or more of its fenced blocks define the
  target (`body_via_ast` not None). It is regraded on the last of them, with `deveval.answer`'s
  fields and re-indent. When that answer equals the first-block one, the main-run verdict stands;
  an empty last body is a fail. Fences only match closed blocks, so a truncated reply uses its
  last closed block.
- **Grading.** Every reply whose last-block answer differs was graded on the cluster in one job
  (95473, `medusas_dev`, CPU only, because `gorgonas` had no slot before 2026-11-30), last block
  and first block both. Flips are counted within that job; the first-block regrade against the
  main-run verdict measures grading drift. The first-block gaps the script recomputes must equal
  the committed `gaps.json` of both lines, or it stops.
- **Effect.** The gaps under both rules, the flips and the drift, per model, are in
  `results/last_block/findings.md` (`scripts/last_block.py report`); no number here is typed by
  hand. No model's gap moves enough to change a reading of the main analysis; the largest move is
  Qwen3.5 9B's, which shrinks its image loss slightly.
- `results/last_block/` holds keys, roles, verdicts and seconds only. The answers sent to the
  grader and its raw output, which quotes reply code, stay in `scratch/ufm35/`.

## 2026-11-26: CoderUJB Jsoup 93 is excluded

The reference of Jsoup 93 (`chompBalanced`, task_id `979ad380...`) cannot pass the main run's
answer path (UFM-36). Same criterion as the 13 DevEval items of 2026-11-25, fixed before any rerun
number was seen. This is a deviation from 3.3, logged as the freezing rule asks.

- **Cause.** `stop_at_function` in `src/codeimg/answers/coderujb.py` (copied from CodeUJB) ends the
  method by counting braces outside strings, and the char literal `'"'` in this method flips its
  string toggle. Written as a fenced reply, the reference keeps the closing fence; the other 135
  references come back equal up to whitespace. 0 of 56 main-run answers pass the item. Not run:
  javac or defects4j on the spliced file. The extraction is not changed.
- **Excluded through `manifests/excluded/coderujb.txt`**, the same mechanism as DevEval. The
  findings notes now cite each benchmark's entry (`EXCLUDED_ON` in `scripts/reliability.py`).
- **CoderUJB now has 135 items in 13 clusters.** Jsoup 93 was the only Jsoup item, so the primary
  CoderUJB interval is a project-clustered t interval with 12 df (13 projects), not the 13 df of
  3.3, and the held-out folds split 13 projects.
- **Rerun, same commands as 2026-11-25:** `results/analysis/`, `results/claude/analysis/`,
  `results/claude/findings.md` and `results/reliability/`. Before the change, every Python output
  and the 5-model GLMM were rerun into scratch and matched the committed files byte for byte. After
  it, DevEval is unchanged except the `holm` and `bh` fields, which pool both benchmarks; the
  DevEval reliability input, draws and diagnostics are byte-identical (the reliability fits were
  rerun for CoderUJB only; seeds are per benchmark). The copy flags do not change (Jsoup 93 was
  never copied).
- **Effect.** The 5 open models' CoderUJB gaps grow by 0.1 to 0.3 points (pooled -28.1 to -28.3),
  Sonnet's by under 0.1 point; every interval stays below zero and the GLMM tests keep their
  conclusions (Wald 40.2, LRT 14.0). The held-out difference is 5.2 (SE 4.8; was 4.8, SE 5.1).
  Claude's CoderUJB text rate is 98.1% (was 97.4%). 30 CoderUJB items are passed by no open model
  (was 31). Finite G and the 1- and 2-run reliabilities move by at most 0.008.
- **Two more reliability fits fail the gate, on s2_model only.** CoderUJB text and image12 with the
  inverse-gamma prior (PSRF 1.14 and 1.16 after the rerun at 3 times the length); their other five
  components pass. With the three DevEval fits of 2026-11-25, 11 of 16 fits pass. The rule is
  one rerun, so they are reported as failed; the random-model G of those cells is not to be cited.
  The simulation check was rerun on the 135-item design and covers all six components (on 136 it
  missed s2_model_project); it is a wiring check, not a coverage claim.
- **Left on all 136:** `results/full/`, `results/audit/`, `results/glmm/`, `results/layout/` and
  `replies.json`. `results/block1/` and the D-study are unaffected: Jsoup 93 is not a block-1 item.

## 2026-11-25: the 13 harness-broken DevEval items are excluded

The 12 items the harness check flags, and `alembic.testing.env.three_rev_fixture`, cannot be
passed through the main run's answer path (UFM-33). This replaces the "stay in, for now" bullet
of 2026-11-23 and is a deviation from 3.3, logged as the freezing rule asks.

- **The cause is confirmed by a regrade.** The reference body of each of the 13 items was graded
  through the answer path on the cluster (job 94403, `gorgonas`, code dir
  `/sonic_home/carlosleao/ufm9/20261125-1652-bd045fc-dirty`, files_sha256
  `5d6f59f94efb552f9e50aa91c8f2a441cabe87cfe96320dd30e907f09dac776a`). With the main run's
  `deveval.py`, all 13 fail, both as the bare reference body and as the reference written as a
  perfect reply; with the fixed one, all 13 pass. Two defects: our copy of
  `datasette/utils/asgi.py` is 1 to 2 lines longer than the file DevEval annotated, so the 9 spans
  start at the def, the decorator or inside the signature; and in `alembic/testing/env.py` a
  string with column-0 lines makes `adjust_indent` push the code too deep.
- **The fix is in `src/codeimg/answers/deveval.py`, for future runs only.** `BODY_POSITION_FIX`
  corrects the 9 spans in `load_items`, and `adjust_indent` leaves string lines alone when they
  sit left of the code. Rebuilt with both versions, the 859 references and the 52,103 main-run
  answers (open and Claude) change only on the 13 items. The main-run answers were not regraded.
- **Excluded, not regraded.** Regrading every model answer on the 13 (about 750 answers, several
  hours of serial grading on a contested partition) did not fit before 2026-11-28. The criterion is the
  reference failing in our harness, fixed before any rerun number was seen. `three_rev_fixture`
  is excluded too: some answers pass it, but a correct answer shaped like the reference failed.
- **One id list, `manifests/excluded/deveval.txt`.** Every table is still checked against its full
  grid (859 items); the excluded items leave right after the check, in `analysis.py` (5-model,
  Claude and the 7-model line, before the DROP_RULE), in the copy tallies and in
  `reliability.py`. `gaps.json`, `ranks.json` and `reliability.json` carry `excluded` per
  benchmark, and the findings say so next to the item counts.
- **Rerun, same commands:** `results/analysis/`, `results/claude/analysis/`,
  `results/claude/findings.md` and `results/reliability/`. Before the change, every Python output
  and the 5-model GLMM were rerun into scratch and matched the committed files byte for byte, so
  the differences are the exclusion. CoderUJB is unchanged except the `holm` and `bh` fields,
  which pool both benchmarks; its reliability draws are byte-identical.
- **DevEval now has 846 items in 79 clusters.** The 5 open models' gaps grow by 0.8% to 1.5% of
  their size (pooled -25.8 to -26.1 points), the Claude gaps by under 0.05 points; every interval
  stays below zero, the GLMM tests and the item flags keep their conclusions, and the copy flags
  do not change (no excluded item was copied). 242 DevEval items are passed by no open model
  (was 254). Finite G and the 1- and 2-run reliabilities move by at most 0.0014.
- **Three reliability fits fail the gate, on s2_model only.** After the automatic rerun at 3 times
  the length, DevEval image12 main (PSRF 1.21), image14 main (1.08) and image14 inverse-gamma
  (1.11) stay above 1.05 for s2_model; their other five components pass, and the other 13 fits
  pass. The rule fixed on 2026-11-14 is one rerun, so they are reported as failed and not run
  longer. The paper cites finite G and the run reliabilities, which do not use s2_model; the
  random-model G of those three cells is not to be cited.
- **Left on all 859:** `results/full/` (the graded table), `results/block1/` (exploratory, earlier
  stage; `Request.post_body` is a block-1 item), `results/audit/` (the samples were drawn from the
  859) and `replies.json` (reply behavior, not grading).
- **Sonnet's 4 extraction answers, regraded with their second block:** 2 pass
  (`boltons.cacheutils.ThresholdCounter.most_common`, `faker.providers.misc.Provider.binary`) and
  2 fail. The first-block rule in `extract` is unchanged.

## 2026-11-23: transcription test becomes a bonus; audit samples

The cluster's GPUs and /snfs2 are down (/snfs2 has given "Communication error on send" on part of
the files since 2026-11-19, and a listing of the run directory hung on 2026-11-23), with the
transcription generation about 70% done. The paper is due 2026-11-30. This is a deviation from
methods 3.3, logged here as the freezing rule there asks.

- **The transcription test (UFM-12) and reading vs coding (UFM-28) are a bonus.** They go into the
  paper only if UFM-28 is done by 2026-11-28. If not, the paper says they were planned and not
  finished (superseded on 2026-11-26: the test is stopped). Methods promised them in three places, left as written: line 196 (the item:condition
  evidence is "strongest if" the items with the largest penalties are the ones the transcription
  test shows were misread), lines 212 to 218 ("Reading vs coding failures") and the addendum,
  lines 393 to 394. Without them the item:condition evidence rests on the variance component, the
  held-out log-likelihood and the correlation checks in `results/analysis/findings.md`, and the
  only evidence on misreading is the exploratory block-1 check in `results/block1/findings.md`.
- **Hand read: Claude Sonnet 5.5 on DevEval, 10 failures per condition.** Methods lines 238 to 240
  plan 30 failures per condition of one model. The open models' image replies are on /snfs2, so
  they cannot be read now; Sonnet's replies in all four conditions are on the laptop. This entry is
  the dated entry the addendum (line 393) asks for before the hand read is done for Claude; no new
  request is made. The sample is cut to 10 per condition to fit the deadline. The labels are
  drafted by Claude Code and not checked by a person. A false-fail share from Sonnet speaks to the
  shared extraction and grading, not to the open models' own failure modes.
- **Test-bug check: 10 of the 18 items no model passes.** Of the 285 items no open model passes in
  any condition (31 CoderUJB, 254 DevEval), the gold solution passed all 285 in the gold run and a
  Claude model passes 267, which shows their tests can be passed. The 10 are drawn from the 18 left
  (1 CoderUJB, 17 DevEval) (superseded on 2026-11-25 and 2026-11-26: 13 of the 18 are excluded; on
  the analysed items the counts are 272 and 5). The check reads the requirement, the reference, the
  gold time against the grader budget and the models' answers; it does not regrade and does not see
  the test bodies, which are on /snfs2.
- **The 12 DevEval items the harness check flags stay in, for now** (superseded on 2026-11-25:
  confirmed and excluded, with a 13th). The check (`audit_sample.py
  harness`, `results/audit/harness_suspects.csv`) finds 12 items no answer seems able to pass:
  9 in `datasette/utils/asgi.py`, where `body_position` starts at the def or decorator line or
  inside the signature, and 3 in `alembic/testing/env.py`, where re-indenting shifts column-0
  string lines. They have not been regraded, so the cause is not confirmed, and every reported
  number still includes them. They shrink each DevEval gap by about 1.4% of its size and are
  reported as a limitation (`docs/validity_audit.md`, section 6) (superseded on 2026-11-25:
  excluded instead; the rerun moved the 5 open models' DevEval gaps by 0.8% to 1.5% of their size).
- `scripts/audit_sample.py` draws both samples with seed 20261123 and counts the labels;
  `results/audit/` holds the ids, the labels and the counts, never reply text. The answers are in
  `docs/validity_audit.md`.

## 2026-11-17: layout control, step 1 and 5 only

CodeShrink (arXiv 2607.29637) lifts completion by rendering code without blank space, so a
reviewer can ask whether our gap is the modality or our layout (UFM-30). Our packed renderer
already drops line-break blank space; what is left is leading indentation. This is exploratory and
outside methods 3.3.

- **Only steps 1 and 5 of UFM-30.** `scripts/layout_share.py` measures, with `render.layout` on the
  contexts the main run rendered, the share of rendered characters that are leading spaces, and
  the pages and page area each item would need without them. No renderer option, no model run, no
  GPU. The limitations paragraph in `results/layout/findings.md` comes from those numbers.
- **The measure is characters.** Leading spaces of each line (after the renderer's tab expansion
  and `rstrip`) over all rendered characters, the newline marker counting as one. Lines flow
  across rows, so rows and lines do not map one to one; the share is the same at every size. The
  page area of the what-if is the proxy for tokens, since the 5 models tokenize images
  differently.
- **The local render is checked first.** Every page of the main run (9,722) is rendered again
  and compared by `pixels_sha256` and size with the main run's `requests.jsonl`, and the page
  counts with `manifests/pages/`. Any mismatch stops the script.
- **Threshold, fixed before the numbers.** The share is "small" when, in every benchmark and size,
  removing the indentation cuts the median per-item page area by less than
  1 - (15/86)/(18/75) = 0.2733 (unrounded in the code). That is the smallest step of our font
  sweep (14 to 12 px) in the area a character costs under `layout` (`PAGE_W * line_height /
  columns`).
  Small means stop at the limitations paragraph; large means report it and decide on steps 2 to 4.
- **Result (added 2026-11-18): small.** Every page matched the main run (995 items, 9,722 pages). Leading spaces are
  17.3% (CoderUJB) and 18.4% (DevEval) of the rendered characters, item means; removing them
  saves a median 16.2% to 16.4% and 18.1% to 18.3% of an item's page area across the three sizes.
  Steps 2 to 4 are not run unless decided later. Numbers: `results/layout/`.
- **The threshold's first rationale was wrong and is withdrawn; the rule stands.** It was proposed
  on the belief that the font sweep left pass rates nearly equal. It did not: 14 px beats 12 px by
  4.1 to 8.8 points, with the interval above zero, for Qwen3.5 27B on both benchmarks and for
  Mistral Small 3.2 24B and Qwen3.5 9B on DevEval (`results/analysis/findings.md`, differences
  between sizes). So
  "small" only says the indentation is less area than one font step; it does not rule out a layout
  effect, since freed area spent on a larger font could help. The limitations paragraph says so.
  The rule was kept as fixed rather than changed after seeing the numbers.

## 2026-11-17: Claude extension analysis

The addendum's analyses ran on the collected Claude tables (UFM-27). `results/claude/findings.md`
holds every Claude number and a paragraph for the paper; the JSON and figures it reads are in
`results/claude/analysis/`. Everything in it is exploratory. The 5-model outputs did not change:
`gaps`, `contamination` and `report` of the 5-model analysis were rerun into a scratch folder and
their files compared byte for byte with `results/analysis/`. The 5-model GLMM was not rerun.

- **Claude gaps: `gaps --models claude`.** The same `benchmark_gaps` code on the Claude table
  alone, minus the 5-model-only parts (pooled gap, ranks, length moderator, all/none shares, items
  no model passes). Holm over the 4 size-averaged gaps; one BH set of 40 over the 12 per-size
  gaps, the 12 size differences and the 16 gaps without flagged items, as the addendum puts them
  together.
- **Deviation: a short Claude cell stops the command.** The addendum drops a short cell's item
  from that condition. The collected tables have no short cell, so that rule is not built; the
  request_error sensitivity line therefore equals the main line.
- **Deviation: the token ratio is the median per-item ratio**, as the open models' size curve
  uses. The addendum's wording is the item mean; both are written, the median is the one plotted.
  The two differ by under 0.01 here.
- **Contamination for the Claude gaps** uses the copies of every text run of the other 6 models,
  the other Claude model included. A model's own exact copies never flag it; they are counted
  apart. The matched random removal bins on the 2 Claude models' mean text score. On CoderUJB
  only 10 (Sonnet) and 30 (Opus) of 136 items are unflagged, so the control cannot match the
  flagged set there; `findings.md` says so next to the table.
- **Replies come from the run directory** (`replies --run-dir`), since the collected rows carry
  no stop reason and no thinking count. Each gen row joins to its one succeeded result in the run
  log; the command stops if the rows, fail reasons or max_tokens counts disagree with the
  collected table. Claude output tokens there leave thinking out.
- **c is computed in Python** from `glmm_contrast_cov.csv`, which `analysis/glmm_main.R` now
  writes (L V L' of the logit contrasts, unrounded). Nothing else in the R script changed. A
  one-off R refit of the 7-model GLMM gave the same c and SE (difference under 1e-6).
- **The 7-model report is `results/claude/findings.md`**, one level up from the analysis folder,
  and it replaces the line's own `findings.md` planned in the entry below.
- **The fits ran locally**: the 7-model GLMM took 45 s on CoderUJB and 434 s for both benchmarks,
  so the cluster was not needed.

## 2026-11-17: model set option for the 7-model line

`scripts/analysis.py` takes `--models main|all` on `prep`, `contamination` and `report`, and a new
`ranks` command builds the rank table of the 7-model line. `main`, the default, is `[models]` and
writes exactly what it wrote before (all outputs compared byte for byte). `all` is `[models]` then
the `[claude]` models in config order; its results go to `results/claude/analysis/` and its
answers CSVs to `scratch/analysis_all/`.

- **One config, not a second one.** The 2026-11-16 entry planned to rerun the commands with a
  different config. The Claude settings already live in `[claude]` and the Claude rows are a
  separate table (`results/claude/full/`), so the option reads both instead. The Claude display
  names are `name` keys in `[claude.*]`.
- **Deviation from the addendum's drop rule.** The addendum drops an item with a Claude cell short
  of 2 scored runs from that condition only (all four for delta_mb). The line drops it from all
  four conditions for every model. `analysis/glmm_main.R` stops on a missing cell for the
  correlations and the common slope, so its input has to hold only items with all four conditions
  anyway; the per-condition ranks are the only place the two rules differ. On the collected
  tables no Claude cell is short, so 0 items are dropped. The count and the rule are printed in
  `findings.md` of the line.
- **The grids are checked before the trim.** The open rows are checked against today's grid and
  the Claude rows against 2 runs on every item; a null seed is allowed for Claude (none is sent)
  and a null verdict only for `request_error`. Then every model keeps runs 0 and 1.
- **Contamination in the line is the flags only**, over every item (dropped ones included) and
  every text run of the other 6 models, run 2 of the open models included, as the addendum says.
  A Claude answer that never reached grading (refusal, over budget, another stop reason) needs no
  reply in `claude_<b>_text.jsonl`. No gaps, control or GLMM overlap: those are 5-model-only.
- **`glmm_main.R` is unchanged.** Run with `--in scratch/analysis_all --out
  results/claude/analysis`, it also writes `glmm_item_flags.csv` and `glmm_item_model.csv`; they
  belong to 5-model-only analyses and the line's report does not use them.

## 2026-11-16: main analysis

Deviations from 3.3, which stays frozen. The commands are in `scripts/analysis.py` and
`analysis/glmm_main.R`; the numbers are in `results/analysis/findings.md`.

- **The M-1 df test of equal penalties is a Wald test** on the delta-method contrasts, not an LRT.
  The contrast is a mean over sizes of fixed-effect differences, and constraining it to be equal
  across models needs a reparametrized fit per constraint; the Wald test uses the one fit. A
  check in the script confirms the statistic does not change with the reference model.
- **The common slope is also reported divided by r**, the correlation between the text logits of
  run 0 and run 1. Text logits from one run are noisy, which pulls the raw slope toward 0; the
  raw slope and R^2 stay in the table.
- **Context length is by the three length buckets only**, with no spline. The buckets are the
  `[sample].deveval_buckets` ranges as [lo, hi), applied to both benchmarks.
- **The token ratio is measured** from the `prompt_tokens` of run 0 (median over items of image
  over text), not taken from the estimates in `docs/notes/token_costs.md`.
- **"Three runs" is 2 or 3 per cell** (block-1 items have 3, the rest 2, the Nov 13 run count).
  Each cell's score is the mean of its runs, so every item weighs the same in the rates and gaps.
- **The held-out log-likelihood is integrated with Laplace**, not Monte Carlo. Each held-out
  cluster is scored by glmmTMB at the training fit's parameters (all fixed, nothing re-estimated),
  the same approximation the fit and the LRT use. Plain Monte Carlo over the random effects did not
  work: on the largest DevEval repository (82 items) two seeds at 2000 draws differed by about 285
  log units, and at 20000 draws the full-minus-reduced difference still changed sign between
  seeds, while sitting about 3300 log units below the Laplace value. The built-in check (d) is now
  that this Laplace evaluation on the fitted data returns the fit's own log-likelihood.
- **The model set is read from `configs/experiment.toml`** by one function, so the Claude
  extension reruns the same commands with a different config into a different folder. Only the
  run with the five open models in `results/analysis/` is the confirmatory family.
- **The contamination inputs were not copied with rsync of the full answer files.** The text rows
  were streamed over ssh into `scratch/contamination/` (gitignored), nothing was written on the
  cluster, and the DevEval reference is rebuilt from `Source_Code` lines `body_position`, the same
  splice `grade_answers.py` uses. The command fails if a graded text answer has no reply there.
- **Two exploratory checks come from related work** (`docs/notes/lit_main_results_comparison.md`),
  outside 3.3 and outside every multiplicity family. Output tokens per model and condition, since
  Reading, Not Thinking ties its gap to shorter image-mode answers: our image answers are 0.58 to
  1.84 times the text length, and Gemma 4, which loses most, does not write shorter answers. And
  the gap on the flagged items alone next to the rest, with the model's own text rate on each set:
  flagged items are much easier in text and lose much more, which fits recall through the text
  path but also the larger room to fall, so it is read as an association.

## 2026-11-16: second Console organization for Opus run 1

- **The rest of Opus run 1 is paid from the Max plan's monthly API credit of a second Console
  organization**, under the same conditions as the first. The Console read on Nov 16 showed US$100
  of promotional credit available, a $0 purchased balance, no payment method, $0 spent this month
  and a monthly spend limit of $100. Auto-reload is not shown, and with no payment method it has
  nothing to charge. The first organization's grant ran out on Nov 15 after 64 requests of Opus run
  1 (US$99.95 of 100 spent). Waiting for its next grant on Dec 7 would hold the analysis three weeks.
  Model ids, settings, anthropic-version and Batch prices are the same, and the returned model id
  is logged per reply, so the organization does not change what is measured.
- **The budget rule reads the second organization's balance.** All batches of the first
  organization have ended and been billed, so none counts as unbilled there.
- **Which organization ran a batch is read from the run log**: every Claude batch recorded before
  this entry ran in the first organization, and every batch whose code commit is this entry or a
  later one runs in the second.
- **The first organization's monthly spend limit was raised from $1 to $100** before Sonnet run 0
  (first batch 2026-11-15 13:34 UTC). It is logged here, as the Nov 14 entry requires.

## 2026-11-14: Claude smoke projection

- **The smoke batches are projected from token counts, not from measured cost.** The budget rule
  takes the cost per request from the smoke, so it has nothing to measure for the smoke itself.
  Before each smoke batch, input tokens come from the count_tokens endpoint (free) for the model
  that will run, every reply is counted at its full max_tokens, both at Batch prices, and the sum is
  multiplied by 1.1. This is a ceiling; the run log keeps it next to the measured cost.
- **The smoke is the main run's smoke manifest at run 0**: 5 items per benchmark in all 4
  conditions, 40 requests per model, one batch per model. Sonnet's batch ends before Opus's is
  submitted, so whether the $1 spend limit blocks credit usage can be read from one batch.
- **The client runs on the laptop with page images copied from the cluster**, not re-rendered, so
  Claude gets the same PNG bytes as the open models.
- **If the code is not committed when a batch is submitted**, the run log records HEAD and a
  sha256 of the uncommitted changes (`git diff HEAD` plus untracked files) next to the commit hash,
  as the main run did with its file-listing hash (Nov 13).
- **A cut batch takes the cheapest pending requests first**, since the addendum cuts to the largest
  number of requests that fits. Nothing is dropped: the rest go in a later batch.

## 2026-11-14: Claude extension pre-registered

- **Claude Sonnet 5.5 and Opus 5.5 are added as an exploratory extension**, with the rules in the
  methodology addendum. This entry and the addendum are committed before the first Claude request,
  so they are the pre-registration. The 5-model analysis of 3.3 is not changed and is reported
  first.
- **Every setting the API allows is the main run's; every one it does not, or that thinking would
  make unequal, is a reported deviation.** On anthropic-version 2026-10-21 sending temperature,
  top_p or top_k returns a 400, even at the default value, and there is no seed. Both models
  therefore sample at temperature 1.0, and run-to-run spread is not comparable with the open models.
- **Effort `low` for both, the least thinking each model allows.** Sonnet's
  `thinking: {type: "between_tools"}` gives no thinking before the answer. Opus returns a 400 for
  `thinking: disabled` at every effort, so it thinks at `low`.
- **Opus gets max_tokens 16,000 and fails a reply over 2,048 non-thinking tokens.** Its thinking
  counts toward max_tokens, so 2048 would cut answers for a reason the open models never had. The
  API reports thinking tokens in usage, so the open models' answer budget can still be applied.
  Failing those replies before grading is simpler to audit than cutting the text at 2,048 Claude
  tokens; in the main run only 38 of 1,335 truncated replies passed, so the two rules differ
  little.
- **Replies stopped at max_tokens are graded, and refusals fail.** The first follows the Nov 10
  rule for the open models. A refusal is the model's answer to the item, so it is a failure, not a
  missing cell; Batch API refusals come back as `succeeded` with `stop_reason: "refusal"`, and
  fallbacks are not supported in batches.
- **No item is excluded up front and request errors are not failures.** The open models excluded
  none and had no request errors. A request still failing after 3 resubmissions is left out of
  scoring, because an API error says nothing about the model. Billing and spend-limit errors do not
  use up the 3, so the state of the account cannot drop items.
- **2 runs on every item, set by budget.** The open models have 3 on the 240 block-1 items; the
  D-study rule of 3.1 is not applied to Claude. One run would widen the gap intervals by about 4
  to 21% (block-1 1-run to 2-run standard error ratios; Claude's run noise at temperature 1.0 may
  differ).
- **Claude gaps get their own Holm family of 4**, so adding models does not change the 10
  confirmatory tests. The 7-model line uses runs 0 and 1 for every model, because the analysis code
  assumes the same runs per item across models. G and run reliability stay 5-model only, because a
  pooled run variance would mix temperature 1.0 with 0.7.
- **Open vs closed is a GLMM contrast, not a fixed term.** A closed/open term would be aliased with
  the model fixed effects, so Claude's mean image-minus-text effect minus the open models' mean is
  reported per benchmark with a Wald interval and no test.
- **Only the Max plan's monthly API credit is spent.** The Console read on Nov 14 showed the Start
  tier, one unused US$100 grant (expires 2026-12-09 00:00 UTC), $0 purchased balance and no payment
  method, so usage cannot go past the credit. The next grant is due Dec 7. The organization's
  monthly spend limit shows $1; whether it blocks credit usage is not documented and was not tested,
  and it stays for now (the smoke will show it). Raising it to the credit amount needs no new entry
  and is logged. Estimated cost at batch prices, with Qwen3.5 27B token counts as a proxy: Sonnet
  about US$50 to 137 and Opus about US$100 to 275 for 2 runs, so the runs span several grants. There
  is no cutoff date; the analysis waits for all 4 runs.

## 2026-11-14: reliability on the full data

- **The reliability components are fitted on the observed 0/1 pass of each run**, not the logit
  scale, so rho and G read on the scale the pass rates are reported on. One Gaussian model per
  benchmark and condition, MCMCglmm 2.36 (added to `analysis/environment.yml`), with model,
  project or repository, item, model:project and model:item as random terms and the residual as the
  run (`analysis/reliability.R`). Main prior: half-Cauchy(0.5) on each SD (parameter expanded);
  sensitivity prior: inverse-gamma (V = 1, nu = 0.002).
- **The project and model:project terms were added** to the model x item design of 3.3, because
  items are clustered in projects and repositories and the resample treats them as the unit. The
  relative error of G counts model:project once per cluster.
- **G is reported twice**: random-model G from s2_model, which rests on 4 df and depends on the
  prior, and finite-population G from the variance of the five model effects in the same draw. No G
  moved by more than 5% between priors; s2_model did move in CoderUJB text, CoderUJB image14 and
  DevEval text, which is why the finite line is the one the paper cites.
- **Ranks use item-weighted pass rates** (each item's score is the mean of its runs). They differ
  from the pooled rates of `results/full/findings.md` by at most 0.0061, and in 7 of 40 cells at
  whole-percent rounding. A test checks that the pooled rates of the reliability input equal
  `results/full/checks.json`.
- **3.3 says "the three runs"; block-1 items have 3 and the rest 2** (the Nov 13 run count). The
  model takes the unbalanced design as is, G uses the mean of 1/runs, and rho is reported for 1, 2
  and 3 runs.
- **Rank stability uses the joint cluster resample in `scripts/resample.py`** (2000 draws, seed
  20261114), so the main analysis can use the same draws.
- **8 of 16 fits needed the automatic rerun at 3 times the length** to pass the gate (PSRF at most
  1.05, ESS at least 400): CoderUJB text, image10, image12 and image14 with the inverse-gamma prior,
  CoderUJB image14 main, DevEval text with both priors and DevEval image14 main. All 16 pass.
- **The simulation check missed one of six components and was not reseeded.** On one simulated
  dataset with the CoderUJB text design, s2_model_project (truth 0.005) came out 0.0112 (0.0052 to
  0.0227); the other five were covered. The realized variance of the simulated effects was 0.0046,
  the inverse-gamma prior gave 0.0106 (0.0048 to 0.0215), and REML (lme4) on the same dataset gave
  0.0105, so the prior and the sampler are not the cause. The cause is the draw: in Compress,
  Closure and Math the simulated model:item effects of one model happened to lean the same way, so
  their mean per model and project was 2.1 to 3.3 times its expected size, a real model x project
  pattern in that dataset. Dropping the four 1-item projects left the estimate at 0.0104, so small
  projects are not the cause. Over 500 simulated datasets REML is unbiased for this term (mean
  0.0049) and 0.0112 or more comes up in 1% of them; over 20 MCMCglmm datasets (main prior, base
  length, gate not checked) its interval covered the truth 20 times, median of medians 0.0046, and
  117 of 120 component intervals covered. The same 20 runs put s2_model's median of medians at
  0.0139 against 0.01, the 4-df upward pull that keeps random-model G a secondary line. The probe
  is `analysis/reliability_sim_probe.R`. On the real data model:project is small (0.0004 to
  0.0023).
- **Headline numbers** (`results/reliability/findings.md`): single-run reliability 0.59 to 0.68 on
  CoderUJB and 0.67 to 0.76 on DevEval; 2-run, the design of 96 of 136 CoderUJB and 659 of 859
  DevEval items, 0.74 to 0.81 and 0.80 to 0.86; finite G 0.85 to 0.94
  on CoderUJB except image12 (0.61, 0.01 to 0.86) and 0.92 to 0.98 on DevEval. Qwen3.5 27B is first
  everywhere; the middle three models swap between text and image.

## 2026-11-13: the rest of the main run

- **The main run is complete: 44,600 answers** (block 1 plus 755 items at 2 runs), in
  `results/full/` with no reply text. No missing, extra or duplicate key, no null `passed`, and
  every seed equals its run. Raw rates and cost are in `results/full/findings.md`.
- **The DevEval grader writes each answer's row as soon as it is graded** and skips rows already
  written, instead of writing a repository when it is done. This replaces the repository split of
  Nov 10. It let grading run as a chain of 1:30 jobs on gorgonas_dev while the long partitions
  were full: 16 jobs hit their limit and each next one resumed where the last stopped.
- **The run count comes from `results/block1/dstudy.json`** (`generate` and `collect`
  `--runs-from`), and the rest manifest is drawn by `scripts/rest_manifest.py` (every final item
  not in block 1). Run r is sent with seed r, as in block 1; no (item, condition, run) key repeats
  a block-1 key, since no item is in both parts.
- **The code that ran is identified by the hash of its file listing**, not the commit:
  `sync_cluster.sh` writes the sorted sha256 of every synced file, and the run log records that
  hash next to the commit, because the tree was not committed when the run started.
- **CoderUJB grades for 3 models were finished on `/sonic_home`** after /snfs2 stopped taking
  writes on Nov 12. The complete rows were copied there and the grader resumed from them; one torn
  last line was dropped. `collect` reads the grades from both places.
- **Re-score gate: any verdict mismatch not explained by a DevEval timeout or a known flaky test
  blocks Done until explained** (user, Nov 13). The re-score samples 20 CoderUJB and 50 DevEval
  graded answers with a fixed seed, extracts and grades them again from the saved replies, and
  never changes the table.

## 2026-11-13: mixed model checked

- **The 3.3 model fits and recovers the known components on simulated data with the real design**
  (859 DevEval and 136 CoderUJB items, 3 runs for block items and 2 for the rest, so most cells
  now have 2 runs). It was simulated twice, 50 replications per benchmark each: once with
  plausible standard deviations and once with the block-1 estimates. Every gated check passes
  (convergence, item, item:model and item:condition SDs within 20%, text cell logits and
  size-averaged penalties within 0.15 logit; also project and project:condition on DevEval in
  the plausible scenario and project:condition on DevEval in the block-1 one). Tables are in
  `results/glmm/glmm.md`; the model is unchanged.
- **What is biased.** The gated SDs come out 5 to 15% low. The size-averaged penalty comes out
  0.03 to 0.13 logit too small (toward no penalty) for every model in both scenarios. The cell SD
  cannot be recovered with 2 or 3 runs: near 0 at a truth of 0.5, 30 to 35% low at 1.3 to 1.4,
  so the overdispersion term of 3.3 is weakly identified with 2-run cells.
- **The block-1 fit gives item SDs of 4.0 (CoderUJB) and 4.8 (DevEval)**, about 3 times the
  plausible 1.5, and a project SD of 0 on both. That is why the second scenario exists.
- **glmmTMB is the engine; lme4 is a cross-check.** On the same 2 replications lme4 agreed
  within 0.05 on DevEval, but it stopped at its iteration limit on 3 of 4 refits. Run alone, an
  lme4 fit took 41 s on CoderUJB and 228 s on DevEval, against 2 s and 11 s for glmmTMB.
- **It runs on the Mac, no cluster install.** In the block-1 scenario a DevEval fit takes a
  median 57 s and a mean 132 s with 6 in parallel (slowest 644 s), 33 s alone, with 0.75 GB
  peak (1.1 GB when an lme4 refit runs in the same process); CoderUJB takes about 10 s and 0.5 GB.
- **TMB is pinned to 1.9.19** because glmmTMB 1.1.14 was built against it (1.9.23 warned of a
  version mismatch). Installing that pin moved R from 4.4 to 4.5.3. All versions are in
  `analysis/conda-osx-arm64.lock`.

## 2026-11-10: D-study on block 1

- **Every model and benchmark runs twice for the rest of the main run**; block items keep their 3
  runs. SE(2 runs) / SE(3 runs) of delta_mb on CoderUJB: Qwen3.5 27B 1.035, Gemma 4 12B 1.013,
  Mistral Small 3.2 24B 1.072, Qwen3.5 9B 1.041, Qwen2.5-VL 7B 1.085. On DevEval, in the same
  order: 1.039, 1.014, 1.052, 1.074, 1.075. The pipeline reads the run count from `rows[].runs` in
  `results/block1/dstudy.json`; components and intervals are in `results/block1/dstudy.md`.
- **Moment estimators per model and benchmark, each condition with its own run variance.** Block 1
  is balanced, so the ANOVA estimators are exact and need no R. Run noise differs by condition
  (Mistral Small 3.2 24B on CoderUJB: 0.1167 on text, 0.0250 at 10 px), so a pooled run variance
  would weight the conditions wrongly. The estimator was fixed in the spec before any ratio was
  computed.
- **The rule is applied to the point estimate of the ratio.** The Nov 8 entry did not say estimate
  or interval; this reading was also fixed before the run. Intervals over items and over projects
  or repositories only label a call firm or close. Three are close: Mistral Small 3.2 24B and
  Qwen2.5-VL 7B on CoderUJB, Qwen2.5-VL 7B on DevEval.
- **This replaces "intervals and the D-study come from the mixed model" in the entry below.** The
  D-study does not wait for the mixed model (UFM-21).
- **The reliability analysis of methodology 3.3 moves to its own issue**, on the full data.

## 2026-11-10: block 1 graded

- **All 14,400 block-1 answers are graded**, and collect found no gaps (`results/block1/`, no reply
  text). Generation had 0 errors. Pass rates on text are 22 to 52% (CoderUJB) and 30 to 58%
  (DevEval); on images, 6 to 30% depending on model and size. These are raw rates; intervals and
  the D-study come from the mixed model (UFM-21, UFM-17).
- **Truncated replies count as failures.** Qwen3.5 9B hit the output limit in 39 CoderUJB and 237
  DevEval answers, mostly repetition loops in image conditions (others: 0 to 37). A truncated
  reply is the model's answer at the frozen budget, so it is graded like any other.
- **The extra image failures are mostly name errors, not worse code.** On DevEval, name errors
  (`NameError`, `AttributeError`, `ImportError`) go from about 8% of text answers to 31% of image
  answers, while wrong results stay at about 30% and 28%. On CoderUJB, `cannot find symbol` goes
  from about 17% to 40%. About 400 DevEval image name errors differ from a real name in the context
  only by underscores (`determine_alterations` for `_determine_alterations`), against 2 on text.
  The DevEval gap also doubles with length: 13 points for items of 1 to 2 pages at 14 px, 26 for
  3 or more.
- **Why the pilot showed no gap.** Its context was unrelated HumanEval padding the model never had
  to read, and HumanEval is likely memorized. Block 1 needs exact names from a real repository,
  which is where reading from images fails. The pilot measured whether code in an image is
  legible, not whether it can be used.
- **DevEval grading splits a repository when it is long.** The grader writes a repository's rows
  only when the whole repository is done. python-for-android (720 answers, about 17 s each, one at
  a time) needs about 3.4 h alone and did not finish inside a 4 h job while sharing the node with
  other repositories, so the job lost all its work on it. Its answers were split into 8 files of 90
  and graded as separate jobs (23 to 27 min each). The rest of the run has larger repositories
  (boltons 82 items, mrjob 66), so it needs this split, or a grader that writes rows as it goes
  (UFM-11). Details and run cost in `results/block1/findings.md`.

## 2026-11-08: D-study margin

- **2 runs are enough when SE(2 runs) / SE(3 runs) is at most 1.10**, per model and benchmark,
  with the standard error of the text-minus-image gap projected from the block-1 components. Set
  before any block-1 answer was graded. The ratio is bounded by 1.00 and sqrt(3/2) = 1.22, and
  1.10 sits near the middle: 1.05 would keep 3 runs almost always, 1.15 would almost always cut
  to 2.

## 2026-11-06: experiment pipeline and smoke run

- **Smoke answers are a pipeline check only.** 5 items per benchmark, 4 conditions, run 0, all 5
  models (`manifests/smoke/`). Pass rates from it are not reported. DevEval passed 3 of 100, all on
  one item; the calibration was already bimodal (13 of 30 items passed by no model), and the tails
  show wrong code reaching the tests, not a grading fault. All 10 checks in `scripts/check_smoke.py`
  pass (`results/smoke/checks.json`).
- **Image limit 9, every item kept.** The longest smoke item needs 9 pages at 14 px. vLLM is
  started with `--limit-mm-per-prompt '{"image": 9}'`; nothing is excluded for page count.
- **The block sentence is frozen** in `configs/experiment.toml` and replaces the context block in
  place, so text and image prompts differ only in that block.
- **Renderer pinned to Pillow's BASIC layout engine.** With raqm (on the cluster, not on the
  laptop) glyph advances change and one item went from 6 to 7 pages at 12 px. With BASIC all 995
  page counts match on both machines.
- **Renders are compared by decoded pixels (`pixels_sha256`), not PNG bytes.** The PNG bytes
  depend on the zlib build (1.2.11 on the cluster, zlib-ng on the laptop) while the pixels are
  identical: 58 CoderUJB and 61 DevEval pages match. Page 1 of CoderUJB 869a9afc was inspected by
  eye at each size (pixels sha256 prefixes 48e13b7d at 10 px, 41587e44 at 12, 082b50f8 at 14).
- **CoderUJB grading budgets pinned to 600 s per test and 1200 s per suite, on 32 CPUs.** The
  grader defaults of 120 and 180 s timed out the gold solution of Closure 107, whose compile alone
  takes minutes. These are the budgets the calibration ran with.
- **Grading is verified on calibration answers.** 35 calibration answers regraded through the new
  pipeline give the same verdict. One CoderUJB suite stage flipped (Lang 1, suite_fail to pass) on
  the flaky StopWatchTest; the primary outcome is the trigger tests, so the check gates on the
  verdict and only reports suite flips.
- **The seed does not make a reply repeatable for 3 of 5 models.** The same item at seed 0 twice
  gave identical replies for both Qwen3.5 models, but diverged after 500 to 1300 characters for
  Qwen2.5-VL, Gemma 4 and Mistral. Seed 1 always differed. The likely cause is GPU numerics
  (for example the second request reusing the prefix cache); not verified. Runs are still
  independent draws, but the logged replies, not a rerun, are the record.
- **vLLM logs are not scanned for tracebacks.** They print benign ones: torch compile-cache misses
  that recompile, and an EngineDeadError when the job stops the server after the last reply. The
  log check covers the generation and grading job logs.
- **Cost from the smoke run** (`results/smoke/cost.md`, order of magnitude): about 6 GPU hours for
  block 1 and 22 for the full study at 3 runs, plus model load (5 to 12 min per job). CoderUJB
  grading is the slow part: about 290 s per answer per grader worker, so about 650 worker hours for
  the full study, against 11 s for DevEval. Image tokens per page are about 1000 (Qwen2.5-VL,
  Mistral), 750 (Qwen3.5) and 266 (Gemma 4).

## 2026-11-05: methodology presentation

- **Construct narrowed.** Completing one function or method in a Java or Python repository from
  its task description, with the repository's code as context. Not debugging, code review or
  multi-file edits. Reading the results as coding ability in general would be the construct
  underrepresentation the book warns about (Truong and Koyejo 2026, sec. 1.3.2).
- **Contamination flag uses exact copies only.** An item is flagged for model m when one of the
  other 4 models copies the reference token for token in a text run (tokenizer in
  `benchmarks/shared/contamination.py`). No near-copy threshold to tune.
- **Cuts if compute runs short:** (1) fewer DevEval items, (2) drop 10 px. The text condition is
  never cut. This replaces an earlier "one image size only" cut, and 10 px replaces 14 px as the
  size to drop. Whether to cut is decided after the first block, from its measured run time.
- **Detailed plan delivered** as the methodology presentation video. `docs/methodology.md` stays as
  the written plan the analysis is frozen against.

## 2026-11-04: methods

- **Outcome is pass/fail per run**, not the fraction of tests passed. The GLMM, the G-study and
  the power simulation all use pass/fail.
- **CoderUJB (Java, 136 items) replaces CodeFlowBench.** DevEval stays (859 items). See
  `benchmarks/README.md`.
- **Packed rendering.** Lines flow across 616 px rows with a newline marker. The goal is saving
  tokens, and the line-per-row renderer saved almost none in the pilot.
- **Task in text, only the repository context as image.** It matches how an agent would send it,
  the task is 3 to 4% of the prompt, and it removes the wrong-function failures seen in the pilot.
- **3 runs, then a D-study after the first block.** If 2 runs are enough by a margin fixed before
  that block is graded, the rest runs with 2. The margin is not set yet.
- **The first block is all 5 models on a sample:** 200 DevEval items stratified by token bucket
  and 40 CoderUJB items stratified by project, 4 conditions, 3 runs, 14,400 answers. Chosen over
  one model on all 995 items because run noise differs by model (a model near the ceiling barely
  varies), so one model could decide wrongly for the other four.

## 2026-10-26: model checks on the cluster

- **Exact repos.** Qwen/Qwen2.5-VL-7B-Instruct, Qwen/Qwen3.5-9B, google/gemma-4-12B-it (16-bit);
  cyankiwi/Qwen3.5-27B-AWQ-4bit and jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym
  (4-bit). Qwen's own GPTQ-Int4 27B keeps attention in 16-bit (30 GB) and does not fit.
- **Mistral NVFP4 dropped.** RedHatAI's NVFP4 build compiles its kernel at load time, and the
  cluster's CUDA toolkit is older than 12.9, the minimum for SM 12 (the RTX 5090). The W4A16 build
  uses kernels that ship prebuilt with vLLM.
- **27B needs smaller profiling limits.** With defaults it ran out of memory after loading the
  weights. It runs with `--max-num-batched-tokens 4096 --max-num-seqs 16 --mm-processor-kwargs
  '{"max_pixels": 1048576}'`. Our pages are under that pixel cap, so token counts are unaffected.
- **Floor screen passed** for all 5, text only, on the pilot's 20 HumanEval problems with 3 runs
  each: Qwen2.5-VL 38/60, Qwen3.5-9B 50/60, Gemma 4 58/60, Qwen3.5-27B 55/60, Mistral 51/60.
- **Image tokens per 616x1540 page:** Qwen2.5-VL 1212, Qwen3.5 9B and 27B 914 (same encoder),
  Gemma 4 262, Mistral 1265 (28 px cells plus a break token per row).
- **Results files are per model.** Two jobs on different nodes appending to one JSONL over NFS
  lost a row.

## 2026-10-22: model choice

- **Thinking off for every model.** Qwen3.5 thinks by default; Qwen2.5-VL, Gemma and Mistral do
  not. Leaving it on mixes reading the image with reasoning length and inflates output tokens.
  Scores will sit below vendor numbers; the comparison is text vs image within a model.
- **Pages capped at 1540 px tall for all models.** Mistral downscales anything taller, which makes
  10 px text unreadable. Every model gets the same images; long contexts become more pages.
- **Gemma 4 stays in.** It spends a fixed budget of about 256 tokens per image (262 for a 616x1540
  page), so tall pages are downscaled more. If it fails at 10 px, that is a compression vs
  readability finding, not a wasted model.
- **Panel is 5 models on one RTX 5090 (32 GB).** 16-bit: Qwen2.5-VL 7B, Qwen3.5 9B, Gemma 4 12B.
  4-bit: Qwen3.5 27B, Mistral Small 3.2 24B. Size and precision are confounded and reported
  together. Two GPUs per node would allow a 16-bit 27B with tensor parallel, but that doubles the
  queue wait on a full cluster.

## 2026-10-14: proposal feedback

- **Rendering is a condition (a facet), not a construct.** Tokens saved is an observed property of
  the input, not an ability. This follows the professor's feedback on the proposal presentation and the book's
  definition of a construct as a property of the model that causes the responses (sec. 1.1).
- **One ability or two.** The proposal asked whether coding from images is the same ability as
  coding from text. With 5 models a second ability cannot be established, so the analysis asks the
  narrower question of whether the image penalty is the same across items and models (3.3).
- **The rebuilt pilot is not valid as is.** Most image failures were the model completing the wrong
  function. Fixed by sending the task as text (Nov 4). Details in `pilot/README.md`.

## Dropped (do not bring back)

- Image reading as construct-irrelevant variance with coding as the construct (September).
- Cost-benefit as the construct: tokens saved is counted directly, so it is not latent.
- Ollama on a laptop as the serving stack: replaced by vLLM on the cluster. The laptop was only
  for the first pilot.
- Fraction of tests passed as the outcome, and the "mixed" and "all-image" conditions (Nov 4).
- Mantel-Haenszel DIF and a two-factor model as planned analyses: 5 models is too few.
- A near-copy threshold for contamination (Nov 5).
