# Benchmarks

UFM-7: picks the benchmarks for the main study. The study fits Rasch/IRT and G-theory models with
the 5 VLMs as respondents and compares code shown as images against the same code as text. A
benchmark is useful only if its items spread the panel out: items that every model passes or every
model fails carry no information. The pilot's HumanEval was too easy (Gemma 58/60, the 27B 55/60).

Outcome: **CoderUJB (Java, 136 items)** and **DevEval (Python, 859 items)**. Both have long,
naturally occurring context (a whole source file), land between 30% and 70% for the panel in the
text condition, and run offline on the cluster. Everything below was run on the DCC cluster in
October 2026, text condition only, one sample per model and item.

## What we asked of a benchmark

- Panel mean pass rate in the text condition between about 30% and 70%, with most items passed by
  one to four of the five models.
- Long context as part of the task, not padding: several pages of code per item.
- At least about 100 items, spread across context length and difficulty.
- Grading that runs on the GPU and CPU nodes without Docker or network access.
- A license we can cite, a contamination check, and a note on which part of the construct each
  benchmark covers.

The context window is the same as in model_panel: `--max-model-len 16384`, 2048 reply tokens. To
leave room for the reply and for the image condition, items are kept to 2k to 12k prompt tokens
counted with the Qwen3.5 tokenizer. 12k tokens is about 6 pages at 12 px, and 6 pages cost about
7600 tokens on Mistral, the most expensive model per page.

## Panel and settings

Same 5 models and serving setup as model_panel (vLLM 0.32.0 on one RTX 5090 per job).

| Model | HF repo |
|---|---|
| Qwen2.5-VL 7B | Qwen/Qwen2.5-VL-7B-Instruct |
| Qwen3.5 9B | Qwen/Qwen3.5-9B |
| Gemma 4 12B | google/gemma-4-12B-it |
| Mistral Small 3.2 24B | jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym |
| Qwen3.5 27B | cyankiwi/Qwen3.5-27B-AWQ-4bit |

Sampling is the SAMPLING dict of model_panel/text_baseline.py (temperature 0.7, top_p 0.95, top_k
-1, min_p 0, repetition_penalty 1.0, every field sent), seed 0, thinking off, max_tokens 2048. The
27B needs `--max-num-batched-tokens 4096 --max-num-seqs 16 --mm-processor-kwargs
'{"max_pixels": 1048576}'` as before.

max_tokens is 2048, not 1024 as in model_panel: Qwen3.5 9B explains its approach before the code
and hit 1024 on 10 of the 30 CoderUJB calibration items. With 2048, one reply per benchmark still
hit the cap (CoderUJB: Qwen3.5 9B and 27B, one each; DevEval: Qwen3.5 9B once).

The calibration ran with the chat template's default system prompt, not an empty one. On Mistral
the default is about 557 tokens and includes the current date; on Qwen2.5-VL it is "You are a
helpful assistant.". We decided not to rerun Mistral for the calibration. The main-study runner
still needs the empty system prompt (`EMPTY_SYSTEM=1` in shared/generate.py does it).

## Candidates

The long list and the reasons for each rejection are in
scratch/notes/literature/ufm7-non-python-candidates.md. CodeFlowBench (repo split) was the last
alternative checked and was rejected on paper: its prompts are about 0.3k to 2k tokens and the
task is multi-turn, so it fails the long-context requirement. Nothing was run for it.

Go was considered through two candidates; neither was run on any model:

- MRG-Bench has 254 Go items in 9 projects. Its in_file prompts (built as its eval script does,
  Qwen3.5 tokens) have a median of 2,230 and a max of 5,732: 128 items reach 2k, none reaches 8k,
  and kitex alone is 59 of those 128. So it covers only the short half of our length range, from
  few projects. The repo has no LICENSE file, and grading runs `go test` inside a Docker image
  whose Go version is not recorded; without Docker we would need a user-space Go and the module
  downloads done on phocus4 beforehand. Not used: the study stays with Java and Python.
- LiveRepoReflection has 403 Go items, but published pass@1 for 8B to 32B models is 0.2 to 9.0,
  which would floor our panel.

## CoderUJB

### Structure

CoderUJB (Zeng et al., ISSTA 2024, arXiv 2403.19287) builds Java tasks on Defects4J projects. We
use the `complete` task from the HF dataset `ZHENGRAN/code_ucb_complete` (238 items): the model
regenerates one method from its doc comment and signature, and the method is graded by splicing it
back into the source file and running the project's JUnit tests through Defects4J v2.0.1.

Each item has a task_id (a sha256), a Defects4J project and bug id, the full source file, the
target method's line range (start, end), its signature, and the test methods that exercise it.
Grading mirrors code_ujb/tasks/code_ujb_complete.py: check out the fixed version of the bug, write
the patched file, run each target test with `defects4j test -t` (120 s each), and only if they all
pass, the full suite (180 s). Two scores come out of that:

- **target tests**: the item's own test methods pass. This is the primary score.
- **full suite**: the target tests and then the whole suite pass.

Of the 136 final items, 94 have 3 target tests, 18 have 2 and 24 have 1.

**Prompt change.** CoderUJB ships the context as an abstract-class skeleton of the file (signatures
only). We replaced the skeleton with the whole source file minus the target method and its doc
comment, because the full file is the long, natural context the image condition is about. The
instruction and the trailing block (doc comment plus signature, which the model continues) are kept
as CoderUJB ships them, so grading still splices the generated method into lines start..end. The
signature is appended because CoderUJB's method extraction matches it verbatim. See
coderujb/make_prompts.py.

### Gold check

The reference methods were graded with the same pipeline before any model ran
(coderujb/gold_check.py, coderujb/results/gold_results.jsonl):

| Stage | Items |
|---|---|
| pass (target and full suite) | 224 |
| suite_fail (target pass, suite fails) | 9 |
| suite_timeout | 4 |
| test_fail (a target test fails) | 1 |

237 of 238 pass their target tests. Median check time was 762 s per item, most of it Defects4J
compiling the project.

### Final items: 136

The 224 gold-passing items by Qwen3.5 prompt tokens: <2k 20, 2k-4k 56, 4k-8k 48, 8k-12k 32,
12k-16k 33, >=16k 35. The final set is every gold-passing item in 2k to 12k, 136 items
(coderujb/results/final_ids.txt).

| Measure (min / median / max) | Value |
|---|---|
| Qwen2.5-VL tokens | 1880 / 4251 / 10210 |
| Qwen3.5 tokens | 2069 / 4666 / 11033 |
| Gemma 4 tokens | 2163 / 4831 / 11726 |
| Mistral tokens | 1914 / 4528 / 10723 |
| Characters | 7853 / 19002 / 47105 |
| Pages at 10 / 12 / 14 px (median) | 2 / 3 / 4 |
| Pages at 12 px (min / max) | 1 / 6 |

Pages are the packed 616x1540 layout from the pilot (shared/count_tokens.py). The 136 items come
from 14 projects, one bug snapshot each:

| Project (bug) | Items | Project (bug) | Items |
|---|---|---|---|
| Math 1 | 36 | Collections 28 | 7 |
| Closure 107 | 23 | Codec 18 | 5 |
| Lang 1 | 21 | JacksonCore 26 | 3 |
| Chart 1 | 15 | Gson 18 | 2 |
| Time 1 | 12 | JacksonDatabind 112 | 1 |
| Compress 47 | 8 | JxPath 22, Csv 16, Jsoup 93 | 1 each |

Math, Closure, Lang and Chart hold 95 of the 136 items, so items share files and tests (see open
points).

### Calibration

30 items, 10 from each Qwen3.5 bucket (2k-4k, 4k-8k, 8k-12k), all inside the final set
(coderujb/pick_calib.py, coderujb/results/calib_items.jsonl). The prompt leak check found no item
whose method body still appears in the context. 150 answers: 147 were graded, and 3 had no method
the extractor could find (all Math 1: the 27B, Gemma and Mistral), which count as failures.

| Model | Target tests | Full suite |
|---|---|---|
| Qwen2.5-VL 7B | 4/30 (13%) | 2/30 (7%) |
| Qwen3.5 9B | 11/30 (37%) | 9/30 (30%) |
| Gemma 4 12B | 13/30 (43%) | 9/30 (30%) |
| Mistral Small 3.2 24B | 12/30 (40%) | 12/30 (40%) |
| Qwen3.5 27B | 17/30 (57%) | 17/30 (57%) |
| Panel mean | 38.0% | 32.7% |

How many models pass each item (number of items):

| Models passing | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Target tests | 10 | 6 | 2 | 4 | 5 | 3 |
| Full suite | 12 | 5 | 2 | 5 | 5 | 1 |

By bucket (target / full suite): 2k-4k 38% / 36%, 4k-8k 48% / 40%, 8k-12k 28% / 22%. Of the 147
graded answers, 52 did not compile, 38 failed a target test, 8 passed the targets but failed the
suite, and 49 passed everything.

A third of the items are passed by no model (10 of 30 on target tests, 12 on the full suite), more
than we want. The other items spread across one to five models.

Cost: generation took about 170 to 280 s per model for the 30 items. Median prompt tokens: 5108
(7B), 5639 (Qwen3.5), 5929 (Gemma), 5829 (Mistral). Grading is the expensive part: 43,619
CPU-seconds for 147 answers (mean 297 s, median 189 s, max 798 s per answer). The main study,
136 items x 5 models x 3 seeds x 2 conditions, is 4080 answers, about 340 CPU-hours at that mean.

## DevEval

### Structure

DevEval (Li et al. 2024, arXiv 2405.19856, HF dataset `LJ0815/DevEval`, code at seketeam/DevEval)
has 1825 Python functions from 115 real repositories in 10 topics, each with requirement text,
dependencies and the repo's own pytest tests. We use the `local_infilling` setting: the model sees
the file around the target function and writes the function body. The prompts are the ones DevEval
ships for gpt-4-1106 (Experiments/prompt/local_infilling/gpt-4-1106_prompt.jsonl), unchanged
(deveval/make_prompts.py). Grading splices the body into body_position the way DevEval's pass_k.py
does and runs the item's pytest ids (deveval/grade_answers.py). Pass means every test passes.

### Gold check

The unmodified repos were tested first (deveval/gold_check.py, deveval/results/gold_results.jsonl):
1591 Pass, 229 Error, 5 TimeOut. A regrade of 30 items through the full answer pipeline with the
reference body as the answer passed 30 of 30 (deveval/results/gold_smoke.jsonl).

### Final items: 859

By Qwen3.5 prompt tokens (all items / gold-passing): <2k 583 / 519, 2k-12k 1017 / 859, 12k-16k
101 / 94, >=16k 124 / 119. The final set is every gold-passing item in 2k to 12k, 859 items
(deveval/results/inrange_ids.txt): 389 in 2k-4k, 350 in 4k-8k, 120 in 8k-12k.

| Measure (min / median / max) | Value |
|---|---|
| Qwen2.5-VL tokens | 1777 / 3947 / 10824 |
| Qwen3.5 tokens | 2003 / 4248 / 11172 |
| Gemma 4 tokens | 2055 / 4609 / 12503 |
| Mistral tokens | 1834 / 4137 / 11192 |
| Pages at 10 / 12 / 14 px (median) | 2 / 2 / 3 |
| Pages at 12 px (min / max) | 1 / 6 |

The 859 items come from 79 repos. By topic: Utilities 187, System 117, Database 104, Internet 97,
Security 86, Multimedia 77, Communications 72, Scientific-Engineering 57, Software-Development 39,
Text-Processing 23. Largest repos: boltons 82, mrjob 66, boto 44, mingus 39, datasette 34,
python-for-android 33, sacred 30, bentoml 29, Mopidy 28, alembic 26.

### Calibration

30 gold-passing items, 10 per Qwen3.5 bucket, one per repo (deveval/pick_calib.py,
deveval/results/calib_items.jsonl). The longest prompt was 10,883 Mistral tokens. All 150 answers
were graded: 61 Pass, 89 Error.

| Model | Pass |
|---|---|
| Qwen2.5-VL 7B | 10/30 (33%) |
| Qwen3.5 9B | 11/30 (37%) |
| Gemma 4 12B | 13/30 (43%) |
| Mistral Small 3.2 24B | 13/30 (43%) |
| Qwen3.5 27B | 14/30 (47%) |
| Panel mean | 40.7% |

| Models passing | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Items | 13 | 3 | 3 | 1 | 1 | 9 |

The per-item distribution is bimodal: 22 of 30 items are passed by all models or by none, and the
spread between models is small (33% to 47%). DevEval separates items better than it separates
models. With 859 items there are still many in the middle, but expect a large share of zero-variance
items. By bucket: 2k-4k 34%, 4k-8k 44%, 8k-12k 44%.

Cost: generation took about 133 to 250 s per model. Median prompt tokens: 5341 (7B), 5619
(Qwen3.5), 6078 (Gemma), 6214 (Mistral), max 11,712 (Gemma). Grading took 1835 CPU-seconds for 150
answers (mean 12.2 s, median 9.4 s, max 54 s). The main study, 859 x 5 x 3 x 2 = 25,770 answers,
is about 90 CPU-hours, less than CoderUJB with six times the items.

## Contamination

shared/contamination.py compares each answer with the reference method after dropping comments and
whitespace (Python tokenizer for DevEval, a regex tokenizer for Java). Exact means the token
sequences are equal; near-exact means a difflib ratio of 0.95 or more. Per-answer rows are in
*/results/contamination.jsonl. For CoderUJB "passed" in those rows is the full-suite score.

| | CoderUJB | DevEval |
|---|---|---|
| Answers compared | 147 | 150 |
| Exact copies | 14 | 24 |
| Near-exact (incl. exact) | 24 | 24 |
| Exact among passing answers | 13 of 49 | 24 of 61 |
| Median ratio, passing / failing | 0.85 / 0.46 | 0.86 / 0.37 |

Per model, exact (near-exact) copies on CoderUJB: 7B 1 (2), 9B 2 (4), Gemma 3 (8), Mistral 2 (4),
27B 6 (6). On DevEval, exact: 7B 3, 9B 4, Gemma 6, Mistral 5, 27B 6.

On CoderUJB the exact copies fall on 8 items, all from Chart 1, Math 1 and Lang 1, and 17 of the
49 passes are near-exact. One exact copy (Gemma) still failed the tests. On DevEval all 24 exact
copies pass, concentrated on a few items: fs.info.Info.created (5 models), asyncssh.misc.write_file,
zxcvbn.matching.spatial_match, diffprivlib.tools.utils.nanstd and
aioxmpp.forms.fields.BoundSingleValueField.value (4 each), then one each on three others.

A copy is not proof of memorisation: short methods with an obvious body come out identical
anyway. But a large share of the passes on both benchmarks are verbatim reference code, so part of
what we measure is recall. The published evidence points the same way for CoderUJB, whose code is
Defects4J (Apache and Google projects, 2004 to 2016):

- Ramos et al. 2024 (arXiv 2411.13323): Defects4J has the lowest negative log-likelihood of the
  benchmarks they tested, consistent with being in training data.
- Kong et al., FSE 2025 (doi 10.1145/3729390): 79% (GPT-3.5) and 87% (CodeLlama-7B) of correct
  Defects4J patches match the developer patch exactly.
- De Koning et al. 2026 (arXiv 2604.21579): semantics-preserving rewrites of Defects4J lower repair
  rates by 4 to 16 points.
- An LLM4Code (ICSE 2025 workshop) study reports 80% of Defects4J repos are in The Stack.

No paper we found reports contamination of CoderUJB itself. DevEval is newer (2024), but its repos
are public PyPI projects, several of them old and widely used (boto, jinja2, alembic), and it
copied the reference more often than CoderUJB in our calibration (24 vs 14 exact). For the
main study this matters less than it would for a leaderboard: both conditions see the same items,
so contamination shifts item difficulty, not the image vs text contrast. The per-item ratios can be
used as a covariate or to drop the worst items.

## Licenses

Not legal advice.

| | Benchmark | Code inside the items |
|---|---|---|
| CoderUJB | UJB code Apache-2.0; paper CC BY 4.0; the HF dataset declares no license | Defects4J is MIT. 12 of the 14 projects are Apache-2.0, Jsoup is MIT, JFreeChart (Chart) is LGPL |
| DevEval | GitHub repo seketeam/DevEval has no LICENSE file; HF dataset LJ0815/DevEval | Each of the 115 repos keeps its own license |

The Chart items (15) stay in the study. For the release, publish item ids, scripts and results, not
the prompt text or rendered images, and let others rebuild the prompts from the datasets. That is
also why the results here keep no prompt text.

## Construct coverage

| | CoderUJB | DevEval |
|---|---|---|
| Language | Java | Python |
| Task | regenerate a method from its doc comment and signature | fill in a function body |
| Context | the whole source file | the file around the function |
| Grading | Defects4J JUnit (target tests, full suite) | repo pytest ids |
| Contamination | high: 2004 to 2016 Apache and Google code, 14 of 147 answers exact copies | also present: 24 of 150 answers exact copies |
| Context length (Qwen3.5 tokens) | 2k to 12k, median 4.7k | 2k to 12k, median 4.2k |

Not covered by either: context spread over several files, and diagrams or other non-code images.

## Decisions

- Languages: Java (CoderUJB) and Python (DevEval). No Go benchmark (see Candidates).
- CoderUJB: keep all 136 in-range gold-passing items.
- DevEval: keep all 859 in-range gold-passing items.
- Mistral is not rerun with an empty system prompt for the calibration. The main study uses the
  empty system prompt for every model.

## Open points

- The CoderUJB instruction still says "abstract Java class context" although the context is now the
  full file. Overloads of the target method stay in the file.
- Items cluster by bug: four snapshots hold 95 of 136 CoderUJB items. The analysis should check
  local dependence within project.
- The 9 suite_fail and 4 suite_timeout gold items may include tests that flip under load (timing).
  This is why the target-test score is the primary one.
- DevEval at 859 items is about 6x the CoderUJB run. A stratified sample would cut generation time,
  grading is cheap either way. Not decided.
- One calibration run per model and item on both benchmarks; the main study's 3 seeds will show how
  much of the per-item pattern is sampling noise.

## Files

```
shared/
  count_tokens.py     prompt tokens with each panel tokenizer, packed pages at 10/12/14 px
  generate.py         one reply per prompt from a running vLLM server (both benchmarks)
  contamination.py    answer vs reference similarity
coderujb/
  setup_d4j.sh        Defects4J v2.0.1 without root or Docker (JDK 8, svn from conda-forge)
  make_items.py       1. parquet to items for the gold check
  gold_check.py       2. gold check (gorgonas, CPU); the same script grades model answers
  gold_check.sbatch
  make_prompts.py     3. full-file prompts for the gold-passing items
  pick_calib.py       4. the 30-item sample
  generate.sbatch     5. generation (GPU), calls shared/generate.py
  make_answers.py     6. extract the method and splice it into the source, then grade with step 2
  results/
deveval/
  setup_env.sh        uv, the DevEval Python 3.9 venv and requirements, DevEval Source_Code
  make_prompts.py     1. shipped prompts to {"id", "text"} rows for shared/count_tokens.py
  gold_check.py       2. gold check (CPU); run_item is reused by grade_answers.py
  gold_check.sbatch
  analyze.py          3. gold results against the token counts
  pick_calib.py       4. the 30-item sample
  generate.sbatch     5. generation (GPU), calls shared/generate.py
  make_answers.py     6. extract the function body
  grade_answers.py    7. grading (CPU)
  grade.sbatch
  report.py           8. pass rates per model and per item
  results/
```

Setup scripts run on phocus4 (internet). The .sbatch files expect this same layout under
`/sonic_home/carlosleao/ufm7` on the cluster; data and outputs go to `/snfs2/carlosleao/ufm7`
(subfolders `coderujb`, `deveval`, `deveval_calib`, `d4j`), and generation reuses the vLLM venv
in `/snfs2/carlosleao/ufm8/venv`. The other scripts run anywhere with the downloaded datasets;
the ones with a `# /// script` header need `uv run`. `deveval/make_prompts.py` was written for
this folder to record the prompt step; its output matches the prompts used, for all 1825 items.

`results/` in each benchmark folder:

- `gold_results.jsonl`: gold check per item.
- `prompt_counts.jsonl`: tokens per tokenizer and pages per item.
- `final_ids.txt` (CoderUJB) and `inrange_ids.txt` (DevEval): the items for the main study.
  CoderUJB also has `gold_pass_ids.txt` (all 224 gold-passing items).
- `calib_items.jsonl`: the 30 calibration items.
- `gen_<model>.jsonl`: one row per calibration reply (tokens, finish_reason, seconds).
- `skipped.jsonl` (CoderUJB): replies with no extractable method.
- `grade_results.jsonl`: grading of the calibration answers.
- `contamination.jsonl`: similarity per answer.
- `gold_smoke.jsonl` (DevEval): the 30-item regrade of the reference bodies.

To keep the folder small and avoid redistributing third-party source, the reply text, prompt text
and grading output tails were stripped. The full files are on the cluster under
`/snfs2/carlosleao/ufm7`.
