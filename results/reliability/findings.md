# Reliability

Methodology 3.3, on the full answer table (results/full, 3 runs for block-1 items and 2 for the
rest), minus the 13 DevEval items excluded in docs/decisions.md (2026-11-25). Variance components
come from one Gaussian mixed model per benchmark and condition on the 0/1 pass of each run
(analysis/reliability.R, MCMCglmm): model, project (CoderUJB) or repository (DevEval), item,
model:project, model:item, and the run within a cell. Intervals are 95% equal-tailed (type-1
percentiles). Rerun with `uv run python scripts/reliability.py prep`, the R script, then `report`;
every number is in `reliability.json`.

## Run noise and item-score reliability

Run is the occasion component (within-cell variance); the empirical value next to it is the mean
unbiased within-cell variance. rho_n is the Spearman-Brown reliability of a model's item score
averaged over n runs, among items within a model (book p. 147). The empirical rho_1 is the
correlation of run 0 with run 1, pooled over models.

| Benchmark | Condition | Run | Empirical | rho_1 | rho_2 | rho_3 | Empirical rho_1 |
|---|---|---|---|---|---|---|---|
| CoderUJB | text | 0.0789 (0.0721 to 0.0867) | 0.0846 | 0.676 (0.615 to 0.751) | 0.807 (0.761 to 0.858) | 0.862 (0.827 to 0.900) | 0.627 |
| CoderUJB | image10 | 0.0362 (0.0329 to 0.0398) | 0.0387 | 0.623 (0.568 to 0.694) | 0.768 (0.724 to 0.820) | 0.832 (0.797 to 0.872) | 0.594 |
| CoderUJB | image12 | 0.0438 (0.0398 to 0.0482) | 0.0424 | 0.627 (0.573 to 0.690) | 0.771 (0.728 to 0.817) | 0.835 (0.801 to 0.870) | 0.629 |
| CoderUJB | image14 | 0.0529 (0.0482 to 0.0583) | 0.0505 | 0.588 (0.530 to 0.659) | 0.741 (0.693 to 0.794) | 0.811 (0.772 to 0.853) | 0.605 |
| DevEval | text | 0.0602 (0.0579 to 0.0627) | 0.0591 | 0.758 (0.736 to 0.780) | 0.862 (0.848 to 0.877) | 0.904 (0.893 to 0.914) | 0.759 |
| DevEval | image10 | 0.0404 (0.0389 to 0.0420) | 0.0402 | 0.698 (0.676 to 0.722) | 0.822 (0.807 to 0.838) | 0.874 (0.862 to 0.886) | 0.697 |
| DevEval | image12 | 0.0484 (0.0467 to 0.0503) | 0.0492 | 0.675 (0.653 to 0.699) | 0.806 (0.790 to 0.823) | 0.862 (0.849 to 0.875) | 0.664 |
| DevEval | image14 | 0.0555 (0.0534 to 0.0576) | 0.0545 | 0.671 (0.647 to 0.697) | 0.803 (0.786 to 0.821) | 0.860 (0.846 to 0.873) | 0.664 |

Empirical within-cell variance by model:

| Benchmark | Condition | Qwen3.5 27B | Gemma 4 12B | Mistral Small 3.2 24B | Qwen3.5 9B | Qwen2.5-VL 7B |
|---|---|---|---|---|---|---|
| CoderUJB | text | 0.0895 | 0.0404 | 0.1373 | 0.0760 | 0.0797 |
| CoderUJB | image10 | 0.0637 | 0.0368 | 0.0257 | 0.0331 | 0.0343 |
| CoderUJB | image12 | 0.0723 | 0.0147 | 0.0331 | 0.0650 | 0.0270 |
| CoderUJB | image14 | 0.0895 | 0.0147 | 0.0453 | 0.0588 | 0.0441 |
| DevEval | text | 0.0516 | 0.0323 | 0.0688 | 0.0725 | 0.0701 |
| DevEval | image10 | 0.0532 | 0.0165 | 0.0368 | 0.0489 | 0.0455 |
| DevEval | image12 | 0.0585 | 0.0238 | 0.0483 | 0.0599 | 0.0554 |
| DevEval | image14 | 0.0652 | 0.0181 | 0.0626 | 0.0747 | 0.0518 |

## Variance components

Main prior. The model term rests on 5 models (4 df).

| Benchmark | Condition | model | project | item | model:project | model:item | run |
|---|---|---|---|---|---|---|---|
| CoderUJB | text | 0.0190 (0.0043 to 0.1531) | 0.0187 (0.0011 to 0.0888) | 0.1029 (0.0783 to 0.1396) | 0.0014 (0.0000 to 0.0061) | 0.0368 (0.0282 to 0.0466) | 0.0789 (0.0721 to 0.0867) |
| CoderUJB | image10 | 0.0044 (0.0006 to 0.0453) | 0.0052 (0.0002 to 0.0265) | 0.0248 (0.0176 to 0.0347) | 0.0010 (0.0000 to 0.0049) | 0.0270 (0.0219 to 0.0329) | 0.0362 (0.0329 to 0.0398) |
| CoderUJB | image12 | 0.0013 (0.0000 to 0.0175) | 0.0034 (0.0000 to 0.0212) | 0.0357 (0.0259 to 0.0496) | 0.0010 (0.0000 to 0.0056) | 0.0316 (0.0255 to 0.0391) | 0.0438 (0.0398 to 0.0482) |
| CoderUJB | image14 | 0.0093 (0.0020 to 0.0824) | 0.0052 (0.0001 to 0.0305) | 0.0342 (0.0245 to 0.0474) | 0.0004 (0.0000 to 0.0033) | 0.0334 (0.0268 to 0.0412) | 0.0529 (0.0482 to 0.0583) |
| DevEval | text | 0.0116 (0.0029 to 0.0982) | 0.0307 (0.0171 to 0.0525) | 0.1145 (0.1023 to 0.1278) | 0.0013 (0.0003 to 0.0027) | 0.0411 (0.0376 to 0.0449) | 0.0602 (0.0579 to 0.0627) |
| DevEval | image10 | 0.0018 (0.0004 to 0.0184) | 0.0090 (0.0039 to 0.0184) | 0.0605 (0.0542 to 0.0680) | 0.0012 (0.0005 to 0.0022) | 0.0223 (0.0202 to 0.0244) | 0.0404 (0.0389 to 0.0420) |
| DevEval | image12 | 0.0026 (0.0006 to 0.0265) | 0.0105 (0.0049 to 0.0200) | 0.0626 (0.0559 to 0.0703) | 0.0010 (0.0003 to 0.0021) | 0.0262 (0.0238 to 0.0287) | 0.0484 (0.0467 to 0.0503) |
| DevEval | image14 | 0.0049 (0.0012 to 0.0441) | 0.0136 (0.0065 to 0.0255) | 0.0650 (0.0580 to 0.0733) | 0.0022 (0.0011 to 0.0037) | 0.0320 (0.0290 to 0.0351) | 0.0555 (0.0534 to 0.0576) |

## G for ranking the five models

Secondary line. Relative error includes model:project, model:item and run noise for the benchmark's
items and runs. Random-model G uses s2_model, which rests on 4 df and depends on the prior;
finite-population G uses the variance of the five model effects in the same draw.

| Benchmark | Condition | G random, main | G random, inverse-gamma | G finite, main | G finite, inverse-gamma |
|---|---|---|---|---|---|
| CoderUJB | text | 0.962 (0.827 to 0.995) | 0.945 (0.792 to 0.993) | 0.944 (0.858 to 0.968) | 0.935 (0.841 to 0.963) |
| CoderUJB | image10 | 0.902 (0.487 to 0.990) | 0.859 (0.516 to 0.980) | 0.846 (0.486 to 0.930) | 0.814 (0.470 to 0.915) |
| CoderUJB | image12 | 0.712 (0.022 to 0.973) | 0.746 (0.356 to 0.960) | 0.606 (0.014 to 0.856) | 0.620 (0.191 to 0.843) |
| CoderUJB | image14 | 0.947 (0.772 to 0.994) | 0.919 (0.704 to 0.988) | 0.922 (0.795 to 0.955) | 0.898 (0.744 to 0.945) |
| DevEval | text | 0.989 (0.957 to 0.999) | 0.987 (0.955 to 0.998) | 0.984 (0.975 to 0.989) | 0.983 (0.975 to 0.988) |
| DevEval | image10 | 0.952 (0.801 to 0.995) | 0.952 (0.843 to 0.993) | 0.920 (0.847 to 0.953) | 0.919 (0.846 to 0.952) |
| DevEval | image12 | 0.965 (0.861 to 0.997) | 0.963 (0.875 to 0.995) | 0.945 (0.896 to 0.967) | 0.942 (0.895 to 0.964) |
| DevEval | image14 | 0.972 (0.889 to 0.997) | 0.967 (0.884 to 0.995) | 0.955 (0.922 to 0.972) | 0.954 (0.920 to 0.972) |

Moved by the prior (median change over 5%, or over 0.002 below 0.01): CoderUJB text: s2_model;
CoderUJB image14: s2_model; DevEval text: s2_model.

## Items passed by every model or by none

| Benchmark | Condition | All 5 pass | None pass |
|---|---|---|---|
| CoderUJB | text | 8.8% | 23.5% |
| CoderUJB | image10 | 0.0% | 62.5% |
| CoderUJB | image12 | 0.7% | 58.1% |
| CoderUJB | image14 | 0.7% | 52.2% |
| DevEval | text | 15.2% | 30.5% |
| DevEval | image10 | 3.0% | 63.0% |
| DevEval | image12 | 3.0% | 57.7% |
| DevEval | image14 | 3.1% | 50.6% |

## Rank stability

Item-weighted pass rates (each item counts once; its score is the mean of its runs), ranked 1 to 5,
with the 95% interval of the rank over 2000 joint resamples of whole projects or repositories (seed
20261114). Image is the mean of the three sizes. These rates weigh items equally, so they can differ
by a point from results/full/findings.md, which pools answers.

CoderUJB:

| Model | Text | Image | 10 px | 12 px | 14 px |
|---|---|---|---|---|---|
| Qwen3.5 27B | 54.0%, 1 (1 to 1) | 22.4%, 1 (1 to 1) | 20.3%, 1 (1 to 1) | 19.0%, 1 (1 to 2) | 27.8%, 1 (1 to 1) |
| Gemma 4 12B | 44.5%, 2 (2 to 4) | 8.3%, 5 (3 to 5) | 8.8%, 2 (2 to 5) | 9.1%, 5 (3 to 5) | 6.9%, 5 (4 to 5) |
| Mistral Small 3.2 24B | 43.4%, 3 (2 to 4) | 12.3%, 3 (2 to 4) | 8.7%, 3 (2 to 5) | 13.1%, 3 (1 to 4) | 15.1%, 3 (2 to 3) |
| Qwen3.5 9B | 41.4%, 4 (2 to 4) | 12.5%, 2 (2 to 4) | 7.5%, 5 (2 to 5) | 14.1%, 2 (2 to 4) | 15.9%, 2 (2 to 3) |
| Qwen2.5-VL 7B | 22.2%, 5 (5 to 5) | 9.4%, 4 (3 to 5) | 7.8%, 4 (2 to 5) | 11.0%, 4 (2 to 5) | 9.3%, 4 (4 to 5) |

Probability that the pair's order in text and in image is reversed:

| Pair | P(swap) |
|---|---|
| Qwen3.5 27B vs Gemma 4 12B | 0.002 |
| Qwen3.5 27B vs Mistral Small 3.2 24B | 0.003 |
| Qwen3.5 27B vs Qwen3.5 9B | 0.000 |
| Qwen3.5 27B vs Qwen2.5-VL 7B | 0.000 |
| Gemma 4 12B vs Mistral Small 3.2 24B | 0.630 |
| Gemma 4 12B vs Qwen3.5 9B | 0.787 |
| Gemma 4 12B vs Qwen2.5-VL 7B | 0.674 |
| Mistral Small 3.2 24B vs Qwen3.5 9B | 0.632 |
| Mistral Small 3.2 24B vs Qwen2.5-VL 7B | 0.058 |
| Qwen3.5 9B vs Qwen2.5-VL 7B | 0.007 |

DevEval:

| Model | Text | Image | 10 px | 12 px | 14 px |
|---|---|---|---|---|---|
| Qwen3.5 27B | 54.2%, 1 (1 to 1) | 26.0%, 1 (1 to 1) | 21.2%, 1 (1 to 1) | 25.2%, 1 (1 to 1) | 31.6%, 1 (1 to 1) |
| Gemma 4 12B | 46.7%, 3 (2 to 3) | 16.1%, 4 (3 to 4) | 15.8%, 2 (2 to 3) | 16.1%, 4 (2 to 4) | 16.3%, 4 (4 to 5) |
| Mistral Small 3.2 24B | 49.0%, 2 (2 to 3) | 17.5%, 3 (2 to 4) | 15.3%, 3 (2 to 3) | 16.5%, 3 (2 to 4) | 20.7%, 3 (2 to 3) |
| Qwen3.5 9B | 41.8%, 4 (4 to 4) | 18.1%, 2 (2 to 3) | 13.4%, 4 (4 to 5) | 18.3%, 2 (2 to 3) | 22.4%, 2 (2 to 3) |
| Qwen2.5-VL 7B | 30.5%, 5 (5 to 5) | 14.0%, 5 (5 to 5) | 12.3%, 5 (4 to 5) | 14.0%, 5 (5 to 5) | 15.7%, 5 (4 to 5) |

Probability that the pair's order in text and in image is reversed:

| Pair | P(swap) |
|---|---|
| Qwen3.5 27B vs Gemma 4 12B | 0.000 |
| Qwen3.5 27B vs Mistral Small 3.2 24B | 0.002 |
| Qwen3.5 27B vs Qwen3.5 9B | 0.000 |
| Qwen3.5 27B vs Qwen2.5-VL 7B | 0.000 |
| Gemma 4 12B vs Mistral Small 3.2 24B | 0.112 |
| Gemma 4 12B vs Qwen3.5 9B | 0.983 |
| Gemma 4 12B vs Qwen2.5-VL 7B | 0.007 |
| Mistral Small 3.2 24B vs Qwen3.5 9B | 0.742 |
| Mistral Small 3.2 24B vs Qwen2.5-VL 7B | 0.001 |
| Qwen3.5 9B vs Qwen2.5-VL 7B | 0.000 |

## MCMC

13 of 16 fits pass the gate (PSRF at most 1.05 and effective sample size at least 400 for every
component, 2 chains of 60000 iterations, burn-in 10000, thin 25; a fit that fails is rerun once at 3
times the length, which 11 of them needed). Priors: main half-Cauchy(0.5) on each SD, sensitivity
inverse-gamma (V = 1, nu = 0.002). Gates per component are in `mcmc_diagnostics.csv`.

Failing fits: deveval image12 main; deveval image14 ig; deveval image14 main.

Simulation check (one simulated dataset with the CoderUJB design and known components, a wiring
check, not a coverage claim): missed s2_model_project (see docs/decisions.md); gate pass.
