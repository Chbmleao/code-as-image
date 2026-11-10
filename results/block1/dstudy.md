# Block 1 D-study

Estimated from the block-1 answers (`coderujb.collected.jsonl` and `deveval.collected.jsonl`, 3 runs
per item and condition): the two components of the size-averaged gap delta_mb for each model and
benchmark, and the ratio of the gap's standard error with 2 runs to that with 3. The rule, set on
Nov 8, is 2 runs when the ratio is at most 1.10 and 3 otherwise, applied to the estimate. The
standard errors for 1, 2 and 3 runs are in `dstudy.json`; rerun with `uv run python
scripts/dstudy.py`.

## Decisions

| Benchmark | Model | Ratio SE(2)/SE(3) | Interval over items | Interval over projects/repositories | Runs | Firm or close call |
|---|---|---|---|---|---|---|
| CoderUJB | Qwen3.5 27B | 1.035 | 1.016 to 1.068 | 1.016 to 1.048 | 2 | firm |
| CoderUJB | Gemma 4 12B | 1.013 | 1.003 to 1.029 | 1.005 to 1.025 | 2 | firm |
| CoderUJB | Mistral Small 3.2 24B | 1.072 | 1.043 to 1.128 | 1.038 to 1.114 | 2 | close call |
| CoderUJB | Qwen3.5 9B | 1.041 | 1.018 to 1.086 | 1.014 to 1.062 | 2 | firm |
| CoderUJB | Qwen2.5-VL 7B | 1.085 | 1.038 to 1.203 | 1.040 to 1.225 | 2 | close call |
| DevEval | Qwen3.5 27B | 1.039 | 1.028 to 1.052 | 1.030 to 1.050 | 2 | firm |
| DevEval | Gemma 4 12B | 1.014 | 1.008 to 1.019 | 1.008 to 1.022 | 2 | firm |
| DevEval | Mistral Small 3.2 24B | 1.052 | 1.038 to 1.069 | 1.034 to 1.080 | 2 | firm |
| DevEval | Qwen3.5 9B | 1.074 | 1.056 to 1.097 | 1.060 to 1.095 | 2 | firm |
| DevEval | Qwen2.5-VL 7B | 1.075 | 1.055 to 1.103 | 1.054 to 1.109 | 2 | close call |

A close call does not change the decision; the rule uses the estimate. A call is firm when both
intervals sit on the same side of 1.10 as the estimate. The intervals are 95% percentile intervals
from 2000 bootstrap resamples (seed 20261110), one over items and one over whole projects (CoderUJB)
or repositories (DevEval).

## Gap components

Run noise per condition is the within-cell variance over the 3 runs, averaged over items. The run
noise of a one-run gap weights text by 1 and each size by 1/9, the squares of delta_mb's weights.

| Benchmark | Model | item:condition (spread of the gap across items) | run noise of a one-run gap | Run noise, text | 10 px | 12 px | 14 px |
|---|---|---|---|---|---|---|---|
| CoderUJB | Qwen3.5 27B | 0.1258 (0.0776 to 0.1594) | 0.0630 (0.0296 to 0.1019) | 0.0417 (0.0083 to 0.0750) | 0.0417 (0.0083 to 0.0750) | 0.0583 (0.0250 to 0.1000) | 0.0917 (0.0500 to 0.1417) |
| CoderUJB | Gemma 4 12B | 0.2047 (0.1495 to 0.2396) | 0.0333 (0.0074 to 0.0676) | 0.0250 (0.0000 to 0.0583) | 0.0250 (0.0000 to 0.0500) | 0.0250 (0.0000 to 0.0500) | 0.0250 (0.0000 to 0.0500) |
| CoderUJB | Mistral Small 3.2 24B | 0.1006 (0.0464 to 0.1441) | 0.1296 (0.0843 to 0.1796) | 0.1167 (0.0750 to 0.1667) | 0.0250 (0.0000 to 0.0583) | 0.0250 (0.0000 to 0.0583) | 0.0667 (0.0250 to 0.1083) |
| CoderUJB | Qwen3.5 9B | 0.1231 (0.0604 to 0.1745) | 0.0731 (0.0361 to 0.1167) | 0.0583 (0.0250 to 0.1000) | 0.0250 (0.0000 to 0.0500) | 0.0583 (0.0250 to 0.1000) | 0.0500 (0.0167 to 0.0917) |
| CoderUJB | Qwen2.5-VL 7B | 0.0459 (0.0035 to 0.0922) | 0.0759 (0.0370 to 0.1176) | 0.0583 (0.0250 to 0.1000) | 0.0167 (0.0000 to 0.0417) | 0.0667 (0.0333 to 0.1083) | 0.0750 (0.0333 to 0.1167) |
| DevEval | Qwen3.5 27B | 0.1307 (0.1054 to 0.1566) | 0.0731 (0.0565 to 0.0915) | 0.0533 (0.0383 to 0.0717) | 0.0500 (0.0350 to 0.0683) | 0.0550 (0.0383 to 0.0733) | 0.0733 (0.0533 to 0.0933) |
| DevEval | Gemma 4 12B | 0.1960 (0.1690 to 0.2240) | 0.0339 (0.0215 to 0.0474) | 0.0267 (0.0150 to 0.0400) | 0.0200 (0.0100 to 0.0317) | 0.0233 (0.0117 to 0.0367) | 0.0217 (0.0117 to 0.0333) |
| DevEval | Mistral Small 3.2 24B | 0.1139 (0.0889 to 0.1372) | 0.0917 (0.0713 to 0.1133) | 0.0783 (0.0583 to 0.0983) | 0.0333 (0.0200 to 0.0467) | 0.0317 (0.0183 to 0.0450) | 0.0550 (0.0367 to 0.0733) |
| DevEval | Qwen3.5 9B | 0.0825 (0.0585 to 0.1052) | 0.1093 (0.0874 to 0.1320) | 0.0867 (0.0667 to 0.1083) | 0.0517 (0.0350 to 0.0683) | 0.0633 (0.0450 to 0.0817) | 0.0883 (0.0667 to 0.1083) |
| DevEval | Qwen2.5-VL 7B | 0.0690 (0.0462 to 0.0923) | 0.0943 (0.0731 to 0.1159) | 0.0767 (0.0567 to 0.0967) | 0.0500 (0.0333 to 0.0667) | 0.0517 (0.0350 to 0.0700) | 0.0567 (0.0400 to 0.0750) |

## Precision

CoderUJB: 40 items in 10 projects (sizes 11, 7, 6, 4, 4, 2, 2, 2, 1, 1). Estimates whose interval
over items is wider than the estimate itself: Qwen3.5 27B B; Gemma 4 12B B; Qwen3.5 9B B; Qwen2.5-VL
7B A and B. Close calls: 2 of 5. The interval over projects rests on 10 projects, so it is rough.

DevEval: 200 items in 56 repositories. Estimates whose interval over items is wider than the
estimate itself: none. Close calls: 1 of 5.

## Reference: G-study components (descriptive, not used for the decision)

Brennan's balanced design, item x condition x (run:item x condition), with condition random. Its
item:condition is per condition, on a different scale from A above. Run is the mean of the four run
noises above.

| Benchmark | Model | item | item:condition | run |
|---|---|---|---|---|
| CoderUJB | Qwen3.5 27B | 0.0784 (0.0366 to 0.1179) | 0.0497 (0.0313 to 0.0631) | 0.0583 |
| CoderUJB | Gemma 4 12B | 0.0358 (0.0026 to 0.0762) | 0.0537 (0.0361 to 0.0672) | 0.0250 |
| CoderUJB | Mistral Small 3.2 24B | 0.0451 (0.0093 to 0.0877) | 0.0301 (0.0134 to 0.0444) | 0.0583 |
| CoderUJB | Qwen3.5 9B | 0.0505 (0.0144 to 0.0895) | 0.0448 (0.0264 to 0.0618) | 0.0479 |
| CoderUJB | Qwen2.5-VL 7B | 0.0446 (0.0114 to 0.0798) | 0.0143 (-0.0001 to 0.0288) | 0.0542 |
| DevEval | Qwen3.5 27B | 0.0998 (0.0805 to 0.1166) | 0.0449 (0.0362 to 0.0533) | 0.0579 |
| DevEval | Gemma 4 12B | 0.0857 (0.0637 to 0.1063) | 0.0624 (0.0537 to 0.0715) | 0.0229 |
| DevEval | Mistral Small 3.2 24B | 0.0733 (0.0536 to 0.0925) | 0.0447 (0.0358 to 0.0527) | 0.0496 |
| DevEval | Qwen3.5 9B | 0.0779 (0.0600 to 0.0954) | 0.0258 (0.0180 to 0.0334) | 0.0725 |
| DevEval | Qwen2.5-VL 7B | 0.0589 (0.0420 to 0.0756) | 0.0218 (0.0135 to 0.0298) | 0.0588 |
