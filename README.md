# Code as Image

Final project for the UFMG course "Medição e Caracterização de IA" (AI Measurement Science).

Coding agents carry a lot of repository context, and tools such as pxpipe render that context as
images because an image token holds more characters than a text token. This project measures what
that saving costs: how much pass rate open vision-language models lose when the repository context
of a coding task arrives as an image instead of text, and how many input tokens the image saves.

## Design in one paragraph

981 items from two repository-level benchmarks, CoderUJB (135 Java methods from Defects4J) and
DevEval (846 Python functions from 79 repositories), each with a reference solution that passes its
tests and a prompt of 2k to 12k tokens. 14 more items were run but are excluded, because their
reference cannot pass our answer path (`manifests/excluded/`, `docs/decisions.md` 2026-11-25 and
2026-11-26). Five open models served with vLLM: Qwen2.5-VL 7B, Qwen3.5 9B and 27B, Gemma 4 12B and
Mistral Small 3.2 24B. Four conditions: text, and the context rendered as packed images at 10, 12
and 14 px, with the task itself always in text. Three runs per item, model and condition for the
first block of 240 items and two for the rest (sized by the D-study in `results/block1/dstudy.md`),
at temperature 0.7, scored pass/fail by the unit tests. The main result is the paired
text-minus-image gap per model with a project-clustered interval. Claude Sonnet 5.5 and Opus 5.5
were added later as an exploratory extension. Full plan in
[`docs/methodology.md`](docs/methodology.md), deviations in [`docs/decisions.md`](docs/decisions.md).

## Quickstart: rebuild the analysis on a laptop

Needs [uv](https://docs.astral.sh/uv/) and, for the R step,
[mamba](https://github.com/conda-forge/miniforge) (or conda). No GPU, no Java, no network after the
installs. Verified on an Apple M4 laptop (10 cores, 24 GB) on 2026-11-26, from a fresh clone.

```
git clone https://github.com/Chbmleao/code-as-image.git
cd code-as-image
uv sync --python 3.12
mamba create -n codeimg-glmm --file analysis/conda-osx-arm64.lock   # macOS arm64
scripts/rerun_analysis.sh
git status --short results/        # empty: every rebuilt file equals the committed one
```

`uv sync --python 3.12` matters: `uv.lock` resolves different numpy, scipy and matplotlib versions
for other Pythons, and the committed figures match the 3.12 set. The analysis code needs
Python 3.11 or later (`tomllib`). On Linux or an Intel Mac, build the R env from
`analysis/environment.yml` (`mamba env create -f analysis/environment.yml`); that path was not
checked byte for byte. `scripts/rerun_analysis.sh --no-r` skips R and keeps the committed GLMM
outputs.

What the script runs, with the time each step took in the fresh-clone check. The commands are
short forms: the script runs `uv run python scripts/<name>` and, for R,
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 mamba run -n $R_ENV Rscript analysis/<name>`.

| Step | Command | Time |
|---|---|---|
| D-study | `dstudy.py` | 3 s |
| Gaps, figures `main_gap.pdf` and `size_curve.pdf` | `analysis.py gaps` | 8 s |
| GLMM input, 5 models | `analysis.py prep --scratch scratch/analysis` | 2 s |
| GLMM, 5 models | `analysis/glmm_main.R --in scratch/analysis --out results/analysis` | 276 s |
| Findings | `analysis.py report` | 1 s |
| GLMM input, 7 models | `analysis.py prep --models all --scratch scratch/analysis_all` | 1 s |
| GLMM, 7 models | `analysis/glmm_main.R --in scratch/analysis_all --out results/claude/analysis` | 289 s |
| Ranks, 7 models | `analysis.py ranks` | 2 s |
| Claude findings and figures | `analysis.py report --models all` | 1 s |
| Reliability input | `reliability.py prep` | 1 s |
| Reliability report (from the committed MCMC draws) | `reliability.py report` | 1 s |
| Audit summary | `audit_sample.py summary` | under 1 s |
| Last-block report | `last_block.py report` | 1 s |
| Total | `scripts/rerun_analysis.sh` | 586 s (10 min) |

`scripts/rerun_analysis.sh --reliability` also refits the MCMC variance components
(`analysis/reliability.R`, 16 fits, 8 of them refit at 3 times the length); that took 4,988 s
(83 min) on the same laptop, with other jobs running on it. It reproduces
`draws_*.csv` byte for byte; the `seconds` column of `mcmc_diagnostics.csv` always differs.

Four steps need the model replies, which are not in the repo (see Data). The script skips them
when the inputs are missing and keeps the committed files: the contamination flags
(`results/analysis/contamination*`, `results/claude/analysis/contamination*`), the Claude gaps
(`results/claude/analysis/gaps.json`) and the Claude reply statistics (`replies.json`).

`uv run pytest` runs the tests (no GPU or network). On a fresh clone 282 pass and 19 skip (2026-11-26); the skipped ones
need the benchmark files under `scratch/ufm7` (see Data).

## Reproducing the study from scratch

Steps 1 to 5 ran on the DCC cluster at UFMG (Slurm); [`CLUSTER.md`](CLUSTER.md) has the commands,
directories and the failures to avoid. Times are the recorded ones, with their source.

| # | Step | Command | Hardware | Recorded time |
|---|---|---|---|---|
| 1 | Item selection and gold checks | `benchmarks/` (see its README) | login node, CPU nodes | not recorded |
| 2 | Prompts and page images | `python -m codeimg prompts --benchmark B --source PROMPTS --ids manifests/<sample>/B.txt --out RUN/B` | login node `phocus4`, no GPU | rest of the run: 11 min CoderUJB (96 items), 67 min DevEval (659 items) (`results/full/run_log.md`, 2026-11-10) |
| 3 | Generation | `slurm/submit_generate.sh CODE RUN` (one job per model, `vllm serve` plus `python -m codeimg generate`) | one RTX 5090 32 GB per job (`medusa` nodes) | block 1: 3.9 GPU hours (`results/block1/findings.md`); rest: 8.45 GPU hours, 1:04 to 2:06 per model (`results/full/run_log.md`) |
| 4 | Answers and grading | `python -m codeimg answers`, then `sbatch slurm/grade_coderujb.sbatch` / `slurm/grade_deveval.sbatch` | 32-core CPU nodes (`gorgonas`, `medusas_shr`) | block 1: 17.8 node hours CoderUJB, about 11 DevEval (`results/block1/findings.md`); rest: 6:27 to 11:42 per model for CoderUJB when graded in one job, DevEval in chained 1:30 jobs and a last 2:50 job (`results/full/run_log.md`) |
| 5 | Answer table | `python -m codeimg collect`, then `scripts/full_table.py build --rest RUN` | login node | not recorded |
| 6 | Claude replies | `python -m codeimg claude count`, `submit`, `fetch`, each with `--model M --run-dir RUN` (`submit` also takes the budget flags, see `--help`; Message Batches API, `ANTHROPIC_API_KEY` in the environment), then steps 4 and 5 with `collect --claude` | laptop and API | first batch 2026-11-15 (`docs/decisions.md`); per-batch times in the run logs of the reply folder |
| 7 | Analysis | `scripts/rerun_analysis.sh` (Quickstart) | laptop | Quickstart table |
| 8 | Contamination inputs | `scripts/contamination_inputs.py` (Data) | laptop | 3 s (2026-11-26) |
| 9 | Layout control | `scripts/layout_share.py --requests DIR` (DIR holds the main run's `requests.jsonl` and `img/` per benchmark) | laptop, CPU | 1,243 s (`docs/decisions.md` 2026-11-26, license entry) |
| 10 | Last-block regrade | `scripts/last_block.py answers`, grading on the cluster, `last_block.py grades --grades F`, `last_block.py report` | laptop, CPU node | grading in one job (`docs/decisions.md` 2026-11-26) |

The sample manifests are committed (`manifests/smoke`, `manifests/block1`, `manifests/rest`);
`python -m codeimg sample` draws block 1 and the smoke sample, and `scripts/rest_manifest.py`
writes the rest. Rendering uses JetBrains Mono (`src/codeimg/assets/`) and Pillow's BASIC layout
engine, so page counts are the same on the cluster and on a Mac; PNG bytes differ between machines
(zlib builds) but the decoded pixels do not (`docs/decisions.md`). The transcription test
(UFM-12) is on branch `transcription-tests` and not on main; it was stopped before it finished
(`docs/decisions.md` 2026-11-26).

## Which script makes which output

Runs on: **laptop** (committed files only), **laptop + R** (the `codeimg-glmm` env), **replies**
(needs the reply folders, not distributed), **cluster**, **API**.

| Output | Made by | Runs on |
|---|---|---|
| `results/analysis/gaps.json`, `never_passed.csv`, `figures/main_gap.pdf`, `figures/size_curve.pdf` | `scripts/analysis.py gaps` | laptop |
| `results/analysis/glmm.json`, `glmm_item_flags.csv`, `glmm_item_model.csv`, `glmm_contrast_cov.csv` | `analysis.py prep`, then `analysis/glmm_main.R` | laptop + R |
| `results/analysis/contamination.json`, `contamination_flags.csv` | `analysis.py contamination --answers scratch/contamination` | replies |
| `results/analysis/findings.md` | `analysis.py report` | laptop |
| `results/claude/analysis/glmm*.json`, `glmm_*.csv` | `analysis.py prep --models all`, then `glmm_main.R` | laptop + R |
| `results/claude/analysis/gaps.json` | `analysis.py gaps --models claude --answers scratch/contamination` | replies |
| `results/claude/analysis/contamination.json`, `contamination_flags.csv` | `analysis.py contamination --models all --answers scratch/contamination` | replies |
| `results/claude/analysis/replies.json` | `analysis.py replies --run-dir ~/UFMG/ufm9-claude/full` | replies |
| `results/claude/analysis/ranks.json` | `analysis.py ranks` | laptop |
| `results/claude/findings.md`, `results/claude/analysis/figures/claude_gap.pdf`, `size_curve.pdf` | `analysis.py report --models all` | laptop |
| `results/claude/full/*.collected.jsonl` | `codeimg claude`, grading, `codeimg collect --claude` | API, cluster |
| `results/claude/smoke/smoke.json`, `smoke.md` | `scripts/claude_smoke.py --run-dir ~/UFMG/ufm9-claude/smoke --out results/claude/smoke` | replies |
| `results/reliability/reliability.json`, `findings.md` | `scripts/reliability.py prep`, then `report` | laptop |
| `results/reliability/draws_coderujb.csv`, `draws_deveval.csv`, `mcmc_diagnostics.csv` | `analysis/reliability.R` | laptop + R |
| `results/reliability/sim_check.csv` | `analysis/reliability.R --sim` | laptop + R (not timed) |
| `results/block1/*.collected.jsonl` | `codeimg collect` | cluster |
| `results/block1/dstudy.json`, `dstudy.md` | `scripts/dstudy.py` | laptop |
| `results/full/*.collected.jsonl`, `checks.json` | `scripts/full_table.py build --rest ~/UFMG/ufm9-open/rest` | replies |
| `results/full/rescore_keys.json`, `rescore.json` | `full_table.py sample`, then `rescore --grades F` after a cluster regrade | laptop, cluster |
| `results/glmm/sim_*.csv`, `lme4_notes_*.csv`, `glmm.md` | `scripts/glmm_cells.py`, then `analysis/glmm_check.R` | laptop + R (not timed) |
| `results/layout/items.csv`, `layout.json`, `findings.md` | `scripts/layout_share.py --requests DIR` | replies (needs the rendered pages) |
| `results/audit/hand_read.csv`, `never_passed_check.csv`, `never_passed_pool.json` | `scripts/audit_sample.py hand-read`, `never-passed`, then labels by hand | laptop |
| `results/audit/harness_suspects.csv` | `audit_sample.py harness --gold scratch/contamination/deveval_gold.jsonl --data scratch/ufm7/deveval/data.jsonl` | replies (the gold file is built with them) |
| `results/audit/summary.md` | `audit_sample.py summary` | laptop |
| `results/last_block/answers.csv` | `scripts/last_block.py answers` | replies |
| `results/last_block/grades.csv` | `last_block.py grades --grades F` after the cluster job | cluster |
| `results/last_block/last_block.json`, `findings.md` | `last_block.py report` | laptop |
| `results/smoke/checks.json`, `cost.json`, `cost.md`, `*.collected.jsonl` | `scripts/check_smoke.py`, `scripts/cost_estimate.py`, `codeimg collect` | cluster |
| `results/block1/findings.md`, `results/full/findings.md`, `results/full/run_log.md` | written by hand | |

The paper's tables and figures (`paper/build_figures.py` for `fig_gap.pdf`, `fig_item_corr.pdf`
and `fig_size_tokens.pdf`, `paper/build_numbers.py` for `numbers.tex`, `paper/build.py` for the
PDF) are on the paper branch `paper/base`, not on main yet. `studies/pilot/`, `studies/model_panel/`
and `benchmarks/` have their own READMEs for what each of their scripts writes.

## Versions

| Part | Version | Source |
|---|---|---|
| Analysis Python | CPython 3.12 (3.12.12 in the 2026-11-26 checks); numpy 2.5.5, scipy 1.18.1, matplotlib 3.11.2, Pillow 13.0.0, anthropic 2.8.0, pytest 9.2.0 | `uv.lock` resolution for 3.12 |
| R | R 4.5.3, glmmTMB 1.1.14, TMB 1.9.19, lme4 2.0-6, Matrix 1.7-5, MCMCglmm 2.36 (conda-forge) | `analysis/environment.yml`, full lock `analysis/conda-osx-arm64.lock` |
| Generation venv (cluster) | Python 3.12.1, vLLM 0.32.0, torch 2.13.0, transformers 5.19.0, openai 3.36.1, Pillow 13.0.0 | `results/full/run_log.md`, the `versions` field of every generation meta file |
| CoderUJB grading | Defects4J v2.0.1 (commit a83e479), OpenJDK 8 from conda-forge (build not recorded) | `benchmarks/coderujb/setup_d4j.sh`, `results/full/run_log.md` |
| DevEval grading | Python 3.9.18 venv with DevEval's `requirement.txt` and the pins in the script | `benchmarks/deveval/setup_env.sh`, `results/full/run_log.md` |
| Claude | `claude-sonnet-5-5` and `claude-opus-5-5`, API version 2026-10-21, Message Batches | `configs/experiment.toml`, `[claude]` |

Models, from `configs/experiment.toml`; every GPU job ran with `HF_HUB_OFFLINE=1` on the one
snapshot below (`results/full/run_log.md`, generation meta files):

| Model | Hugging Face repo | Revision |
|---|---|---|
| Qwen2.5-VL 7B | `Qwen/Qwen2.5-VL-7B-Instruct` | `cc594898137f460bfe9f0759e9844b3ce807cfb5` |
| Qwen3.5 9B | `Qwen/Qwen3.5-9B` | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` |
| Gemma 4 12B | `google/gemma-4-12B-it` | `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` |
| Qwen3.5 27B (AWQ 4-bit) | `cyankiwi/Qwen3.5-27B-AWQ-4bit` | `9d8d63632afafe90bdfcb70164d3e2a0955619f7` |
| Mistral Small 3.2 24B (AWQ) | `jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym` | `49ec31ec0975e46a1aeef24186a45f11be3042b8` |

Sampling for the open models is in `configs/experiment.toml` (`[sampling]`, sent on every request).
The Claude requests send no temperature and no seed, so both models sample at 1.0.

## Seeds

| Step | Seed | Where |
|---|---|---|
| Block-1 and smoke samples | 20261105 | `configs/experiment.toml:5`, used in `src/codeimg/sample.py:89` |
| Generation, open models | run number r is sent as the vLLM seed | `src/codeimg/generate.py:92` |
| Generation, Claude | none (the API takes no seed) | `src/codeimg/claude.py` docstring |
| D-study bootstrap | 20261110 | `src/codeimg/analysis/dstudy.py:43` |
| Re-score sample | 20261111 | `src/codeimg/analysis/full_table.py:31` |
| Cluster resample (gaps, ranks, reliability ranks) | 20261114, stream `f"{SEED}-{benchmark}"` | `src/codeimg/analysis/resample.py:10` |
| Matched random removal (contamination control) | 20261118 | `src/codeimg/analysis/contamination.py:19` |
| GLMM held-out folds and simulations | 20261115 and 20261117 | `analysis/glmm_main.R:38-39` |
| MCMC chains | 20261114 plus an offset per benchmark, condition, prior and chain | `analysis/reliability.R:37`, `:164` |
| GLMM simulation check | 20261112 | `analysis/glmm_check.R:37` |
| Audit samples | 20261123 | `scripts/audit_sample.py:46` |

## Data

**Benchmarks.** Each license below was read on the source page on 2026-11-26, and each revision
was checked against the main run's inputs the same day (`docs/decisions.md` 2026-11-26).

| Dataset | Where we took it (revision) | License, and the page it was read on |
|---|---|---|
| CoderUJB `complete` items | HF dataset `ZHENGRAN/code_ucb_complete` at `78cb042`, `data/train-00000-of-00001.parquet` | The dataset card declares no license (huggingface.co/datasets/ZHENGRAN/code_ucb_complete). The CoderUJB code is Apache-2.0 (github.com/WisdomShell/ujb, LICENSE); the paper is CC BY 4.0 (arxiv.org/abs/2403.19287) |
| Defects4J | github.com/rjust/defects4j, v2.0.1 | MIT (`license.txt` in the repo). The projects inside keep their own licenses (`benchmarks/README.md`, Licenses) |
| DevEval items and prompts | github.com/seketeam/DevEval at `02e768c`: `data.tar.gz` (`data.jsonl`) and `Experiments/prompt/local_infilling/gpt-4-1106_prompt.jsonl` | The GitHub repo has no LICENSE file and its README states none |
| DevEval source code | HF dataset `LJ0815/DevEval` at `16ff740`, `Source_Code.tar.gz` | CC BY 4.0 (dataset card metadata, huggingface.co/datasets/LJ0815/DevEval). Each repository inside keeps its own license |
| HumanEval (pilot only) | github.com/openai/human-eval, committed as `studies/pilot/HumanEval.jsonl.gz` | MIT (LICENSE in the repo) |

The per-item lists are committed: `benchmarks/coderujb/results/final_ids.txt` (136 items) and
`benchmarks/deveval/results/inrange_ids.txt` (859), which still include the excluded items, the
manifests under `manifests/`, and the 14 excluded items in `manifests/excluded/` (13 DevEval, 1 CoderUJB). The
analysed sets are 846 DevEval and 135 CoderUJB items; `results/full/`, `results/audit/`,
`results/glmm/` and `results/layout/` are on all 995 and say so.

The prompt files the requests were built from come from the same sources:
`uv run --quiet benchmarks/coderujb/make_prompts.py complete.parquet
benchmarks/coderujb/results/gold_pass_ids.txt > coderujb_prompts.jsonl` for CoderUJB, and DevEval's
`gpt-4-1106_prompt.jsonl` as shipped. Their sha256 (`35a539f0...` and `cc3b88ed...`) are those in
`results/full/run_log.md`.

**Benchmark files under `scratch/ufm7`** (git-ignored). Some tests, `scripts/last_block.py
answers`, `audit_sample.py harness` and `scripts/contamination_inputs.py` read them. Without them,
19 tests skip. From the repo root:

```
mkdir -p scratch/ufm7/coderujb scratch/ufm7/deveval
curl -fL -o complete.parquet https://huggingface.co/datasets/ZHENGRAN/code_ucb_complete/resolve/78cb042ad6abab321de85fe159f0c65b8aa47d36/data/train-00000-of-00001.parquet
uv run --quiet benchmarks/coderujb/make_items.py complete.parquet > scratch/ufm7/coderujb/items.jsonl
curl -fL https://github.com/seketeam/DevEval/raw/02e768c172171fc17c96e5366381232cab77d6c4/data.tar.gz | tar -xz -C scratch/ufm7/deveval
curl -fL https://huggingface.co/datasets/LJ0815/DevEval/resolve/16ff740d87f5fa97567d6dffd4bcbf299231211c/Source_Code.tar.gz | tar -xz -C scratch/ufm7/deveval
```

The last download is 917 MB. The parquet and `items.jsonl`, `data.jsonl` and the
`Source_Code.tar.gz` file have the sha256 `38db89f4...`, `46a002dc...`, `f3e52e7e...` and
`c7e501a0...`.

**Model replies: not distributed.** The replies quote benchmark code, and neither the CoderUJB
dataset nor the DevEval repo declares a license, so the main-run replies (open models,
`~/UFMG/ufm9-open`, 0.8 GB) and the Claude replies (`~/UFMG/ufm9-claude`, 1.3 GB, which cannot be
regenerated: temperature 1.0, no seed) stay off the repo, like the prompt text and the page
images. The committed results hold ids, verdicts and counts only. Each reply folder has a
`MANIFEST.sha256` (check with `shasum -a 256 -c MANIFEST.sha256` inside it), whose own sha256 is:

| Folder | Files | sha256 of `MANIFEST.sha256` |
|---|---|---|
| `~/UFMG/ufm9-claude/` | 9861 | `baecd9932b9a21ad33aa7950cdaa588fd43d30b5d9326d3647963666e60bb528` |
| `scratch/contamination/` | 8 | `4132ec13aff8c4c37446ff22b25cb50560fef4eff0b4dcd5043e849137862fd8` |

`~/UFMG/ufm9-open/` has its own `MANIFEST.sha256` and `VERIFY.tsv` from the copy off the cluster.
The calibration logs in `benchmarks/*/results/gen_*.jsonl` keep token counts and timings, not the
replies. The pilot and model-panel replies, on HumanEval, are committed.

**Rebuilding `scratch/contamination/`.** The contamination step reads the text answers of every
model and the DevEval references from there. With the reply folders and the `scratch/ufm7` files
in place:

```
uv run python scripts/contamination_inputs.py
```

It writes the 8 files and checks each against the sha256 the committed results were computed from
(it exits 1 on any difference). DevEval goes through `src/codeimg/answers/deveval.py` as it was in
the main run, read with `git show` from `bd045fc` (the last commit before the UFM-33 span and
re-indent fix in `59a9c12`), so the script needs a full clone, not a shallow one.

## Repo layout

| Path | What it holds |
|---|---|
| `docs/methodology.md` | The written plan: design, construct, analysis, open items |
| `docs/decisions.md` | Dated log of design decisions and what was dropped |
| `docs/validity_audit.md` | The validity checklist answered for this study |
| `docs/paper/` | Draft paragraphs the paper uses |
| `docs/notes/` | Reading notes on the course book and the literature behind the plan |
| `deliverables/presentations/` | Proposal and methodology slides (in Portuguese, as presented) |
| `studies/pilot/` | First pilot: Qwen2.5-VL 7B on 20 HumanEval problems, text vs image |
| `studies/model_panel/` | Model choice: fit on one RTX 5090, text floor screen, image token cost |
| `benchmarks/` | Benchmark choice, item filters, gold checks, token counts, contamination check |
| `src/codeimg/` | The experiment pipeline, `python -m codeimg <stage>` |
| `src/codeimg/analysis/` | The analysis logic behind `scripts/analysis.py`, `dstudy.py`, `full_table.py`, `glmm_cells.py` and `reliability.py` |
| `configs/experiment.toml` | Every setting of the main study: sizes, runs, seed, sampling, image limit, models |
| `manifests/` | Item ids of the smoke sample, block 1, the rest and the excluded items, and page counts |
| `analysis/` | R scripts (GLMM, reliability) and the pinned R environment |
| `scripts/` | Entry points of the analysis, the one-study scripts, checks, the rerun script and the cluster sync |
| `slurm/` | Job templates for generation and grading |
| `results/` | Outputs small enough to commit (no reply text) |
| `deliverables/banner/` | The poster and its build script |
| `CLUSTER.md` | How to run jobs on the DCC cluster (Slurm) |

The pipeline stages, each reading the previous one's files:

| Stage | Does | Runs on |
|---|---|---|
| `prompts` | Builds the text and image requests for a manifest; renders the pages | login node |
| `sample` | Draws the block-1 and smoke manifests from the seed | laptop |
| `generate` | Sends every (item, condition, run) to a vLLM server, resumable; `--runs-from` takes the run count from the D-study | GPU node |
| `claude` | The same requests through the Message Batches API | laptop |
| `answers` | Extracts the code from each reply into grader input | login node |
| `codeimg.grade.coderujb`, `codeimg.grade.deveval` | The graders; the DevEval one writes each row as soon as its answer is graded | CPU node |
| `collect` | One row per answer with `passed` and `reason`; fails on any gap in the grid | login node |

## License

Apache-2.0 (`LICENSE`), for the code and documents written for this project. Not covered: JetBrains
Mono (`src/codeimg/assets/` and `studies/pilot/fonts/`, SIL OFL, `OFL.txt` beside it), the banner
fonts (`deliverables/banner/fonts/`, each with its license file), the UFMG and PPGCC logos
(`deliverables/banner/assets/`), HumanEval (`studies/pilot/HumanEval.jsonl.gz`, MIT), and the
benchmark code quoted in `benchmarks/*/results/`, which keeps the license of its source.
