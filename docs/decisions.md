# Design decisions

Newest first. Each entry says what was decided and why, so a settled question is not reopened by
accident. The current plan is `docs/methodology.md`; this file explains how it got there.

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
