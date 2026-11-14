# Main run findings

The whole main run (UFM-11): block 1 (UFM-20) plus the rest, 755 items (96 CoderUJB, 659 DevEval)
not in block 1, at 2 runs per model and benchmark from the D-study. 5 models, 4 conditions,
44,600 answers. The rest was generated Nov 10 and graded Nov 11 to 13; what happened on the
cluster, step by step, is in `run_log.md`.

`coderujb.collected.jsonl` and `deveval.collected.jsonl` next to this file are the full table
(block 1 and the rest, no reply text). `checks.json` holds the checks below, per cell.

The pass-rate tables are raw rates, pooled over runs and both parts, with no intervals. The
mixed model is UFM-21.

## Row counts and checks

| | CoderUJB | DevEval |
|---|---|---|
| Block 1 (3 runs) | 40 items, 2,400 rows | 200 items, 12,000 rows |
| Rest (2 runs) | 96 items, 3,840 rows | 659 items, 26,360 rows |
| Full table | 6,240 rows, 312 per model and condition | 38,360 rows, 1,918 per model and condition |

`scripts/full_table.py build` found no missing or extra key, no duplicate key, no null `passed`
and no row whose seed is not its run. No request was refused by the server in either part.
Answers with no code to grade (counted as failures): 84 on CoderUJB, 24 on DevEval.

## Pass rates

Percent of answers that pass the item's tests (the trigger tests on CoderUJB). The gap is text
minus image, in points.

DevEval, 1,918 answers per cell:

| Model | Text | 10 px | 12 px | 14 px | Gap at 10 / 12 / 14 |
|---|---|---|---|---|---|
| Qwen3.5 27B | 54 | 21 | 25 | 31 | 33 / 29 / 23 |
| Mistral Small 3.2 24B | 48 | 15 | 16 | 20 | 33 / 32 / 28 |
| Gemma 4 12B | 47 | 16 | 16 | 16 | 31 / 31 / 30 |
| Qwen3.5 9B | 41 | 13 | 18 | 22 | 28 / 23 / 19 |
| Qwen2.5-VL 7B | 30 | 12 | 14 | 15 | 18 / 16 / 15 |

CoderUJB, 312 answers per cell:

| Model | Text | 10 px | 12 px | 14 px | Gap at 10 / 12 / 14 |
|---|---|---|---|---|---|
| Qwen3.5 27B | 54 | 21 | 19 | 27 | 33 / 35 / 27 |
| Gemma 4 12B | 45 | 9 | 9 | 7 | 36 / 36 / 38 |
| Mistral Small 3.2 24B | 43 | 9 | 12 | 15 | 35 / 31 / 28 |
| Qwen3.5 9B | 41 | 7 | 14 | 16 | 34 / 28 / 25 |
| Qwen2.5-VL 7B | 22 | 8 | 11 | 10 | 14 / 11 / 13 |

- The block-1 pattern holds on the full table: every model loses 11 to 38 points on images and
  the ranking on images follows the ranking on text. On DevEval a larger font narrows the gap for
  the Qwen models and Mistral while Gemma 4 stays flat; on CoderUJB, with 6 times fewer answers
  per cell, the gap does not shrink at every step (Qwen3.5 27B 33 / 35 / 27).
- Across all models, DevEval passes 44% on text and 15, 18 and 21% at 10, 12 and 14 px; CoderUJB
  41% and 11, 13 and 15%.

Truncated answers (output limit reached, counted as failures), text / image:

| Model | DevEval | CoderUJB |
|---|---|---|
| Qwen3.5 9B | 75 / 727 | 36 / 71 |
| Qwen2.5-VL 7B | 30 / 99 | 7 / 13 |
| Gemma 4 12B | 5 / 95 | 1 / 6 |
| Qwen3.5 27B | 65 / 57 | 23 / 16 |
| Mistral Small 3.2 24B | 0 / 9 | 0 / 0 |

Qwen3.5 9B is the outlier, as in block 1: 13% of its DevEval image answers hit the limit.

## Re-score

A sample drawn from the full table with a fixed seed (20261111), among answers that were graded:
20 CoderUJB and 50 DevEval answers. Their code was extracted again from the saved replies and
graded again on the cluster. Every re-extracted answer equals the original one.

- CoderUJB: 20 of 20 regraded, 0 verdicts differ.
- DevEval: 50 of 50 regraded (10 pass, 40 fail), 0 verdicts differ.

No mismatch, so gate (a) in `docs/decisions.md` has nothing to explain.

`rescore.json` lists the keys and any mismatch with both reasons.

## Run cost

The rest of the run against the estimate in `results/block1/findings.md` (2 runs):

| | Rest | Estimate |
|---|---|---|
| Generation | 8.4 GPU hours (5 jobs, model load included) | about 8 GPU hours |
| CoderUJB grading | 45.0 node hours (8 jobs) | 29 node hours |
| DevEval grading | 26.9 node hours (20 jobs) | 25 node hours |

- CoderUJB grading took 1.5 times the estimate; the cause was not checked. Two of its jobs
  (8.4 node hours) crashed when /snfs2 stopped taking writes on Nov 12; their rows were kept and
  the grading resumed from the last complete row.
- DevEval grading ran mostly as a chain of 1:30 jobs on gorgonas_dev, because the 3 gorgonas
  nodes were held by jobs with no time limit and medusas_shr had no free memory. In that chain the
  per-answer test time was 3 to 5 times block 1's, with pytest waiting on NFS reads; the last
  10,167 answers ran in one job on gorgona5 at about 60 a minute, 4 times the chain's speed.
- Wall time from the first grading submission to the last row: about 51 hours (Nov 11 09:01 to
  Nov 13 12:09).
