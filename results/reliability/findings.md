# Reliability

Methodology 3.3, on the full answer table (results/full, 3 runs for block-1 items and 2 for the
rest), minus the 1 CoderUJB (2026-11-26) and 13 DevEval (2026-11-25) items excluded in
docs/decisions.md. Variance components come from one Gaussian mixed model per benchmark and
condition on the 0/1 pass of each run (analysis/reliability.R, MCMCglmm): model, project (CoderUJB)
or repository (DevEval), item, model:project, model:item, and the run within a cell. Intervals are
95% equal-tailed (type-1 percentiles). Rerun with `uv run python scripts/reliability.py prep`, the R
script, then `report`; every number is in `reliability.json`.

## Run noise and item-score reliability

Run is the occasion component (within-cell variance); the empirical value next to it is the mean
unbiased within-cell variance. rho_n is the Spearman-Brown reliability of a model's item score
averaged over n runs, among items within a model (book p. 147). The empirical rho_1 is the
correlation of run 0 with run 1, pooled over models.

| Benchmark | Condition | Run | Empirical | rho_1 | rho_2 | rho_3 | Empirical rho_1 |
|---|---|---|---|---|---|---|---|
| CoderUJB | text | 0.0793 (0.0722 to 0.0872) | 0.0852 | 0.674 (0.616 to 0.748) | 0.806 (0.763 to 0.856) | 0.861 (0.828 to 0.899) | 0.624 |
| CoderUJB | image10 | 0.0364 (0.0332 to 0.0401) | 0.0390 | 0.623 (0.564 to 0.703) | 0.768 (0.721 to 0.826) | 0.832 (0.795 to 0.877) | 0.594 |
| CoderUJB | image12 | 0.0440 (0.0402 to 0.0484) | 0.0427 | 0.627 (0.573 to 0.687) | 0.771 (0.728 to 0.815) | 0.834 (0.801 to 0.868) | 0.628 |
| CoderUJB | image14 | 0.0532 (0.0486 to 0.0585) | 0.0509 | 0.587 (0.529 to 0.662) | 0.740 (0.692 to 0.797) | 0.810 (0.771 to 0.854) | 0.604 |
| DevEval | text | 0.0602 (0.0579 to 0.0627) | 0.0591 | 0.758 (0.736 to 0.780) | 0.862 (0.848 to 0.877) | 0.904 (0.893 to 0.914) | 0.759 |
| DevEval | image10 | 0.0404 (0.0389 to 0.0420) | 0.0402 | 0.698 (0.676 to 0.722) | 0.822 (0.807 to 0.838) | 0.874 (0.862 to 0.886) | 0.697 |
| DevEval | image12 | 0.0484 (0.0467 to 0.0503) | 0.0492 | 0.675 (0.653 to 0.699) | 0.806 (0.790 to 0.823) | 0.862 (0.849 to 0.875) | 0.664 |
| DevEval | image14 | 0.0555 (0.0534 to 0.0576) | 0.0545 | 0.671 (0.647 to 0.697) | 0.803 (0.786 to 0.821) | 0.860 (0.846 to 0.873) | 0.664 |

Empirical within-cell variance by model:

| Benchmark | Condition | Qwen3.5 27B | Gemma 4 12B | Mistral Small 3.2 24B | Qwen3.5 9B | Qwen2.5-VL 7B |
|---|---|---|---|---|---|---|
| CoderUJB | text | 0.0901 | 0.0407 | 0.1383 | 0.0765 | 0.0802 |
| CoderUJB | image10 | 0.0642 | 0.0370 | 0.0259 | 0.0333 | 0.0346 |
| CoderUJB | image12 | 0.0728 | 0.0148 | 0.0333 | 0.0654 | 0.0272 |
| CoderUJB | image14 | 0.0901 | 0.0148 | 0.0457 | 0.0593 | 0.0444 |
| DevEval | text | 0.0516 | 0.0323 | 0.0688 | 0.0725 | 0.0701 |
| DevEval | image10 | 0.0532 | 0.0165 | 0.0368 | 0.0489 | 0.0455 |
| DevEval | image12 | 0.0585 | 0.0238 | 0.0483 | 0.0599 | 0.0554 |
| DevEval | image14 | 0.0652 | 0.0181 | 0.0626 | 0.0747 | 0.0518 |

## Variance components

Main prior. The model term rests on 5 models (4 df).

| Benchmark | Condition | model | project | item | model:project | model:item | run |
|---|---|---|---|---|---|---|---|
| CoderUJB | text | 0.0189 (0.0047 to 0.1527) | 0.0191 (0.0010 to 0.0893) | 0.1021 (0.0775 to 0.1370) | 0.0014 (0.0000 to 0.0061) | 0.0370 (0.0281 to 0.0471) | 0.0793 (0.0722 to 0.0872) |
| CoderUJB | image10 | 0.0043 (0.0007 to 0.0394) | 0.0053 (0.0002 to 0.0290) | 0.0247 (0.0177 to 0.0349) | 0.0011 (0.0000 to 0.0051) | 0.0272 (0.0221 to 0.0330) | 0.0364 (0.0332 to 0.0401) |
| CoderUJB | image12 | 0.0014 (0.0000 to 0.0174) | 0.0032 (0.0000 to 0.0207) | 0.0359 (0.0256 to 0.0491) | 0.0011 (0.0000 to 0.0056) | 0.0319 (0.0256 to 0.0391) | 0.0440 (0.0402 to 0.0484) |
| CoderUJB | image14 | 0.0096 (0.0021 to 0.0877) | 0.0053 (0.0001 to 0.0312) | 0.0344 (0.0246 to 0.0480) | 0.0004 (0.0000 to 0.0034) | 0.0336 (0.0270 to 0.0415) | 0.0532 (0.0486 to 0.0585) |
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
| CoderUJB | text | 0.961 (0.832 to 0.995) | 0.946 (0.790 to 0.993) | 0.944 (0.856 to 0.968) | 0.935 (0.843 to 0.963) |
| CoderUJB | image10 | 0.895 (0.493 to 0.989) | 0.857 (0.525 to 0.979) | 0.843 (0.481 to 0.927) | 0.815 (0.485 to 0.915) |
| CoderUJB | image12 | 0.722 (0.025 to 0.970) | 0.748 (0.352 to 0.958) | 0.613 (0.016 to 0.855) | 0.620 (0.176 to 0.836) |
| CoderUJB | image14 | 0.949 (0.781 to 0.994) | 0.920 (0.704 to 0.989) | 0.922 (0.801 to 0.955) | 0.899 (0.737 to 0.946) |
| DevEval | text | 0.989 (0.957 to 0.999) | 0.987 (0.955 to 0.998) | 0.984 (0.975 to 0.989) | 0.983 (0.975 to 0.988) |
| DevEval | image10 | 0.952 (0.801 to 0.995) | 0.952 (0.843 to 0.993) | 0.920 (0.847 to 0.953) | 0.919 (0.846 to 0.952) |
| DevEval | image12 | 0.965 (0.861 to 0.997) | 0.963 (0.875 to 0.995) | 0.945 (0.896 to 0.967) | 0.942 (0.895 to 0.964) |
| DevEval | image14 | 0.972 (0.889 to 0.997) | 0.967 (0.884 to 0.995) | 0.955 (0.922 to 0.972) | 0.954 (0.920 to 0.972) |

Moved by the prior (median change over 5%, or over 0.002 below 0.01): CoderUJB text: s2_model;
CoderUJB image14: s2_model; DevEval text: s2_model.

## Items passed by every model or by none

| Benchmark | Condition | All 5 pass | None pass |
|---|---|---|---|
| CoderUJB | text | 8.9% | 23.0% |
| CoderUJB | image10 | 0.0% | 62.2% |
| CoderUJB | image12 | 0.7% | 57.8% |
| CoderUJB | image14 | 0.7% | 51.9% |
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
| Qwen3.5 27B | 54.4%, 1 (1 to 1) | 22.6%, 1 (1 to 1) | 20.5%, 1 (1 to 1) | 19.1%, 1 (1 to 2) | 28.0%, 1 (1 to 1) |
| Gemma 4 12B | 44.8%, 2 (2 to 4) | 8.3%, 5 (3 to 5) | 8.9%, 2 (2 to 5) | 9.1%, 5 (3 to 5) | 6.9%, 5 (4 to 5) |
| Mistral Small 3.2 24B | 43.7%, 3 (2 to 4) | 12.4%, 3 (2 to 4) | 8.8%, 3 (2 to 5) | 13.2%, 3 (1 to 4) | 15.2%, 3 (2 to 3) |
| Qwen3.5 9B | 41.7%, 4 (2 to 4) | 12.6%, 2 (2 to 4) | 7.5%, 5 (2 to 5) | 14.2%, 2 (2 to 4) | 16.0%, 2 (2 to 3) |
| Qwen2.5-VL 7B | 22.3%, 5 (5 to 5) | 9.5%, 4 (3 to 5) | 7.9%, 4 (2 to 5) | 11.1%, 4 (2 to 5) | 9.4%, 4 (4 to 5) |

Probability that the pair's order in text and in image is reversed:

| Pair | P(swap) |
|---|---|
| Qwen3.5 27B vs Gemma 4 12B | 0.001 |
| Qwen3.5 27B vs Mistral Small 3.2 24B | 0.003 |
| Qwen3.5 27B vs Qwen3.5 9B | 0.000 |
| Qwen3.5 27B vs Qwen2.5-VL 7B | 0.000 |
| Gemma 4 12B vs Mistral Small 3.2 24B | 0.627 |
| Gemma 4 12B vs Qwen3.5 9B | 0.782 |
| Gemma 4 12B vs Qwen2.5-VL 7B | 0.675 |
| Mistral Small 3.2 24B vs Qwen3.5 9B | 0.643 |
| Mistral Small 3.2 24B vs Qwen2.5-VL 7B | 0.055 |
| Qwen3.5 9B vs Qwen2.5-VL 7B | 0.003 |

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

11 of 16 fits pass the gate (PSRF at most 1.05 and effective sample size at least 400 for every
component, 2 chains of 60000 iterations, burn-in 10000, thin 25; a fit that fails is rerun once at 3
times the length, which 8 of them needed). Priors: main half-Cauchy(0.5) on each SD, sensitivity
inverse-gamma (V = 1, nu = 0.002). Gates per component are in `mcmc_diagnostics.csv`.

Failing fits: coderujb image12 ig; coderujb text ig; deveval image12 main; deveval image14 ig;
deveval image14 main.

Simulation check (one simulated dataset with the CoderUJB design and known components, a wiring
check, not a coverage claim): every true value inside its 95% interval; gate pass.
