# Block 1 findings

Block 1 of the main run (UFM-20): 200 DevEval and 40 CoderUJB items, 5 models, 4 conditions,
3 runs, 14,400 answers. Generated Nov 8, graded Nov 9 to 10. Every answer is graded and collect
found no gaps. The rows are in `coderujb.collected.jsonl` and `deveval.collected.jsonl` next to
this file (no reply text).

The pass-rate tables are raw rates, pooled over runs, with no intervals. The project clustered
intervals and the mixed model are UFM-13 and UFM-21; the D-study is in its own section below.

## Pass rates

Percent of answers that pass the item's tests (the trigger tests on CoderUJB). The gap is text
minus image, in points.

DevEval, 600 answers per cell:

| Model | Text | 10 px | 12 px | 14 px | Gap at 10 / 12 / 14 |
|---|---|---|---|---|---|
| Qwen3.5 27B | 58 | 21 | 25 | 30 | 36 / 33 / 28 |
| Gemma 4 12B | 50 | 17 | 18 | 17 | 34 / 32 / 34 |
| Mistral Small 3.2 24B | 46 | 15 | 16 | 20 | 31 / 30 / 26 |
| Qwen3.5 9B | 42 | 14 | 20 | 23 | 28 / 21 / 19 |
| Qwen2.5-VL 7B | 30 | 12 | 13 | 14 | 19 / 17 / 16 |

CoderUJB, 120 answers per cell:

| Model | Text | 10 px | 12 px | 14 px | Gap at 10 / 12 / 14 |
|---|---|---|---|---|---|
| Qwen3.5 27B | 52 | 22 | 16 | 23 | 31 / 37 / 29 |
| Gemma 4 12B | 45 | 8 | 8 | 6 | 38 / 37 / 39 |
| Mistral Small 3.2 24B | 42 | 8 | 8 | 15 | 34 / 34 / 28 |
| Qwen3.5 9B | 41 | 7 | 12 | 19 | 34 / 29 / 22 |
| Qwen2.5-VL 7B | 22 | 7 | 12 | 12 | 15 / 9 / 10 |

- Every model loses 9 to 39 points on images, on both benchmarks.
- The ranking on images follows the ranking on text.
- A larger font narrows the gap for the Qwen models and Mistral. Gemma 4 stays flat across sizes,
  which fits its fixed budget of about 266 tokens per page: a larger font means more pages, each
  downscaled the same way.
- Qwen3.5 9B hit the output limit in 214 DevEval and 28 CoderUJB image answers, mostly repetition
  loops. They count as failures. The other models truncated 0 to 30 image answers per benchmark.

## Tokens

Mean prompt tokens on images as a fraction of text (whole prompt, task text included):

| Model | DevEval 10 / 12 / 14 px | CoderUJB 10 / 12 / 14 px |
|---|---|---|
| Gemma 4 12B | 0.17 / 0.20 / 0.24 | 0.13 / 0.17 / 0.21 |
| Qwen3.5 9B and 27B | 0.33 / 0.46 / 0.61 | 0.32 / 0.44 / 0.59 |
| Qwen2.5-VL 7B | 0.45 / 0.63 / 0.85 | 0.44 / 0.62 / 0.84 |
| Mistral Small 3.2 24B | 0.51 / 0.67 / 0.87 | 0.49 / 0.66 / 0.86 |

Smaller fonts save more tokens and, for most models, lose more points. Gemma saves the most and
loses about the same at every size.

## Why image answers fail

Failures were classified from the error each grader printed. The classification ran on the cluster
over every failed answer; the grader output is not in the collected files, so it cannot be rerun
from this folder. It is an exploratory check: the planned measure of reading is the transcription
test (UFM-12).

Share of all answers, by failure type:

| | DevEval text | DevEval image | CoderUJB text | CoderUJB image |
|---|---|---|---|---|
| Missing name (`NameError`, `AttributeError`, `ImportError`; Java `cannot find symbol`) | 8% | 31% | 17% | 40% |
| Wrong result (test assertion fails) | 30% | 28% | 23% | 16% |

- **Most of the gap is names the model got wrong, not logic.** Wrong results stay level from text
  to image; missing names grow by 23 points on both benchmarks.
- **Many are misreadings of a real name.** About 400 DevEval image answers use a name that differs
  from one in the context only by underscores (`determine_alterations` for
  `_determine_alterations`, `darwin_get_brew_formula_location_prefix` for
  `_darwin_get_brew_formula_location_prefix`), against 2 on text. Others are one letter off
  (`modelable_params` for `modellable_params`, `formatannotations` for `formatannotation`).
- **The gap grows with length.** On DevEval at 14 px, items of 1 to 2 pages lose 13 points and
  items of 3 or more pages lose 26.

On CoderUJB the missing names are less often near copies of a context name. Java errors often name
library types or methods outside the context, so this part of the check is weaker there.

## Why the pilot showed no gap

The pilot (Qwen2.5-VL 7B, 20 HumanEval problems) passed 60 of 100 on text and 60 of 100 at packed
14 px. Block 1 gives the same model 30% and 14% on DevEval. Likely reasons, most likely first:

1. The pilot's context was unrelated HumanEval code used as padding, so nothing in it had to be
   read. Block 1 needs exact names from the real repository, and that is where the failures are.
2. HumanEval is probably memorized, so the function name alone can be enough. Not checked.
3. Block-1 contexts are longer: up to 12k tokens and 9 pages, against about 12k characters and 1
   to 2 pages.
4. 20 problems: the pilot's own notes say differences of 5 to 10 points are not meaningful there.
5. Different decoding (near greedy with a repetition penalty on Ollama, against T 0.7 on vLLM).
   This explains the repetition loops, not a gap of this size.

The pilot shows that packed code is legible; block 1 shows that using it is a different matter.

## D-study

All 10 model and benchmark pairs run twice for the rest of the main run (UFM-17). The ratio of the
gap's standard error with 2 runs to that with 3 is 1.013 to 1.085 on CoderUJB and 1.014 to 1.075 on
DevEval, all under the 1.10 margin set on Nov 8, so the 2-run figures under Run cost apply. Three
calls are close, with an interval that reaches past 1.10: Mistral Small 3.2 24B and Qwen2.5-VL 7B
on CoderUJB, and Qwen2.5-VL 7B on DevEval. The rule uses the estimate, so they still run twice.
CoderUJB has 40 block items in 10 projects, so its intervals are wider than DevEval's. Components,
intervals and decisions are in `dstudy.md`.

## Run cost

| | Block 1 | Smoke estimate |
|---|---|---|
| Generation | 3.9 GPU hours (5 jobs, model load included) | 5.9 GPU hours |
| CoderUJB grading | 17.8 node hours (5 jobs on 32 CPUs) | 192 CPU hours (6 node hours) |
| DevEval grading | about 11 node hours, including one job whose work on one repository was lost | 36 CPU hours (1 node hour) |

CoderUJB grading took about 3 times the smoke estimate and DevEval about 10 times. DevEval grades
one answer at a time per repository, so the largest repositories set the wall time. In node hours, the rest of the main run (96
CoderUJB and 659 DevEval items) needs about 43 for CoderUJB and 37 for DevEval at 3 runs, or 29
and 25 at 2 runs. The gorgonas partition has 3 nodes shared with other users. Generation for the
rest is about 12 GPU hours at 3 runs.

DevEval grading writes a repository's rows only when the whole repository is done.
python-for-android (720 answers, about 17 s each, one at a time) did not finish inside a 4 h job
while sharing the node, so its answers were split into 8 files of 90 and graded as separate jobs.
The rest of the run has larger repositories than that (boltons 82 items, mrjob 66, against 33 for
python-for-android in the full set), so it needs the same split or a grader that writes rows as it
goes (UFM-11).
