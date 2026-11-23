# Design decisions

Newest first. Each entry says what was decided and why, so a settled question is not reopened by
accident. The current plan is `docs/methodology.md`; this file explains how it got there.

## 2026-11-14: transcription test (UFM-12)

- **R counts every distinct name of the rendered context**, not the identifiers the reference
  solution needs (3.3 as first written). Names are the identifiers outside comments and strings,
  keywords left out, from the context blocks as the renderer drew them; numbers are lexed first, so
  `0x1F` or `1e-5` yields no name. This needs no rule for which names count. A name is exact,
  underscore-only (equal once underscores are removed), near (Levenshtein 1 or 2, names of 4 or
  more characters) or missing, and R is the exact share. A near match may be another real name of
  the context (`item` for `items`), so the near count is an upper bound on misreads.
- **The request is the main run's pages with only a copy instruction**: all pages of the condition
  in order, the same PNG files (each one's pixels checked against the main run's hash), no task
  text, and for DevEval a separator sentence between the above and below pages. Main-run decoding,
  2 runs, all 995 items and the three sizes, so it covers the pages behind every image answer.
- **32768 server tokens and 16384 output tokens, for this test only**, in a new `[transcription]`
  section; the main-run settings are unchanged. From the main run's token counts, the worst image
  prompt plus a copy as long as the text prompt is 21,162 tokens, and the worst image prompt plus
  16384 is 26,424. A startup check runs first on the items closest to the limit (per model the 3
  largest image14 + text prompts, union over models).
- **Text match is the exact longest common subsequence of the code tokens**, computed bit-parallel,
  instead of difflib as first planned: difflib's matching blocks are not a longest common
  subsequence, and on 20k-token lists full of repeated punctuation it is too slow for 29,850 rows.
  The line and indentation match still use difflib, on lines.
- **The copy runs from the first opening fence to the last closing one**, so a reply that puts the
  two DevEval blocks in two fences, or code that itself contains a fence, stays whole.
- **Lines whose leading spaces cross a row end are left out of the indentation match.** The
  renderer draws those spaces as trailing blanks of the previous row, so the page itself loses
  them; they are counted per item and size (`indent_lost_rows`).
- **The score key is `tr__` + the answer key**, so it never equals a main-run key: a transcription
  run is not the answer run with the same number. UFM-13 joins on (model, benchmark, id,
  condition) and averages over the non-null runs.
- **`generate` cuts an unfinished last line before resuming**, so a job killed mid-write does not
  stop the next job of a chain; the cut key is sent again.

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
