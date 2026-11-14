# GLMM check on simulated data

The methodology 3.3 model, fitted with glmmTMB (family binomial, Laplace) to data simulated with the real design and known components, to see whether it recovers them. Package versions are pinned in `analysis/conda-osx-arm64.lock`. Run: `analysis/glmm_check.R`, inputs from `scripts/glmm_cells.py`.

Replications per benchmark and scenario: 50, seeds 20261112 + r.
Design: every in-range item (859 DevEval, 136 CoderUJB) x 5 models x 4 conditions; 3 runs per cell for block-1 items and 2 for the rest (17,180 and 2,720 cells).
Truth: cell logits are the block-1 pooled pass rates on the logit scale rounded to 0.1. Two scenarios differ only in the standard deviations: the plausible values (item 1.5, item:model 0.8, item:condition 0.5, project 0.5, project:condition 0.3, cell 0.5, not estimates) and the block-1 estimates.
The convergence gate is a rough screen. The cell standard deviation is reported but not gated: with only 2 or 3 runs per cell the Laplace approximation is known to estimate it low, so a shortfall there is expected.

## Scenario 1: plausible standard deviations

### CoderUJB

- PASS: Convergence, 50 of 50 fits converged (need 48). A rough screen.
- PASS: Standard deviations, the mean estimate is within 20% of the truth for item, item:model, item:condition (largest gap 9%).
- PASS: Fixed effects, the mean of each model's text cell logit and size-averaged penalty is within 0.15 logit of the truth (largest gap 0.091).

Standard deviations (logit scale), glmmTMB, mean over converged fits:

| Term | Truth | Mean | MC SE | Bias | Role | Fits at boundary |
|---|---|---|---|---|---|---|
| item | 1.50 | 1.41 | 0.01 | -6% | gated | 0 |
| item:model | 0.80 | 0.73 | 0.01 | -9% | gated | 0 |
| item:condition | 0.50 | 0.47 | 0.01 | -6% | gated | 0 |
| project | 0.50 | 0.36 | 0.04 | -29% | reported | 13 |
| project:condition | 0.30 | 0.22 | 0.02 | -28% | reported | 7 |
| cell | 0.50 | 0.07 | 0.02 | -85% | reported | 32 |

Not-pdHess fits: 0 of 50.

Gated fixed-effect quantities (text cell logit and size-averaged penalty):

| Model | Quantity | Truth | Mean | MC SE | Bias |
|---|---|---|---|---|---|
| Qwen3.5 27B | logit | 0.10 | 0.11 | 0.04 | +0.008 |
| Gemma 4 12B | logit | -0.20 | -0.18 | 0.04 | +0.020 |
| Mistral Small 3.2 24B | logit | -0.30 | -0.28 | 0.04 | +0.024 |
| Qwen3.5 9B | logit | -0.40 | -0.35 | 0.04 | +0.047 |
| Qwen2.5-VL 7B | logit | -1.30 | -1.26 | 0.04 | +0.035 |
| Qwen3.5 27B | penalty | 1.50 | 1.42 | 0.03 | -0.080 |
| Gemma 4 12B | penalty | 2.37 | 2.28 | 0.04 | -0.091 |
| Mistral Small 3.2 24B | penalty | 1.87 | 1.81 | 0.03 | -0.053 |
| Qwen3.5 9B | penalty | 1.60 | 1.53 | 0.03 | -0.070 |
| Qwen2.5-VL 7B | penalty | 0.87 | 0.81 | 0.03 | -0.052 |

Other cell logits (reported, not gated):

| Model | Condition | Truth | Mean | MC SE | Bias |
|---|---|---|---|---|---|
| Gemma 4 12B | image10 | -2.50 | -2.36 | 0.05 | +0.137 |
| Gemma 4 12B | image12 | -2.40 | -2.28 | 0.05 | +0.116 |
| Gemma 4 12B | image14 | -2.80 | -2.72 | 0.04 | +0.079 |
| Mistral Small 3.2 24B | image10 | -2.40 | -2.27 | 0.04 | +0.128 |
| Mistral Small 3.2 24B | image12 | -2.40 | -2.34 | 0.05 | +0.064 |
| Mistral Small 3.2 24B | image14 | -1.70 | -1.66 | 0.04 | +0.040 |
| Qwen2.5-VL 7B | image10 | -2.60 | -2.47 | 0.04 | +0.130 |
| Qwen2.5-VL 7B | image12 | -1.90 | -1.84 | 0.04 | +0.064 |
| Qwen2.5-VL 7B | image14 | -2.00 | -1.93 | 0.04 | +0.068 |
| Qwen3.5 27B | image10 | -1.30 | -1.20 | 0.04 | +0.102 |
| Qwen3.5 27B | image12 | -1.70 | -1.59 | 0.04 | +0.106 |
| Qwen3.5 27B | image14 | -1.20 | -1.14 | 0.04 | +0.055 |
| Qwen3.5 9B | image10 | -2.60 | -2.44 | 0.04 | +0.159 |
| Qwen3.5 9B | image12 | -2.00 | -1.88 | 0.04 | +0.117 |
| Qwen3.5 9B | image14 | -1.40 | -1.33 | 0.04 | +0.073 |

lme4 (glmer, nAGQ = 1) against glmmTMB on the same replications; agreement tolerance 0.05:

| Rep | Largest gap | Gaps over tolerance | Which | lme4 error | lme4 warnings |
|---|---|---|---|---|---|
| 1 | 0.064 (sd:cell) | 2 | sd:project, sd:cell | none | none |
| 2 | 0.055 (sd:cell) | 1 | sd:cell | none | failure to converge in 10000 evaluations; convergence code 4 from Nelder_Mead: failure to converge in 10000 evaluations |

### DevEval

- PASS: Convergence, 50 of 50 fits converged (need 48). A rough screen.
- PASS: Standard deviations, the mean estimate is within 20% of the truth for item, item:model, item:condition, project, project:condition (largest gap 15%).
- PASS: Fixed effects, the mean of each model's text cell logit and size-averaged penalty is within 0.15 logit of the truth (largest gap 0.071).

Standard deviations (logit scale), glmmTMB, mean over converged fits:

| Term | Truth | Mean | MC SE | Bias | Role | Fits at boundary |
|---|---|---|---|---|---|---|
| item | 1.50 | 1.42 | 0.01 | -5% | gated | 0 |
| item:model | 0.80 | 0.75 | 0.00 | -6% | gated | 0 |
| item:condition | 0.50 | 0.46 | 0.00 | -8% | gated | 0 |
| project | 0.50 | 0.42 | 0.01 | -15% | gated | 0 |
| project:condition | 0.30 | 0.27 | 0.00 | -10% | gated | 0 |
| cell | 0.50 | 0.01 | 0.00 | -99% | reported | 47 |

Not-pdHess fits: 0 of 50.

Gated fixed-effect quantities (text cell logit and size-averaged penalty):

| Model | Quantity | Truth | Mean | MC SE | Bias |
|---|---|---|---|---|---|
| Qwen3.5 27B | logit | 0.30 | 0.31 | 0.02 | +0.006 |
| Gemma 4 12B | logit | 0.00 | 0.03 | 0.01 | +0.026 |
| Mistral Small 3.2 24B | logit | -0.20 | -0.17 | 0.02 | +0.028 |
| Qwen3.5 9B | logit | -0.30 | -0.26 | 0.02 | +0.041 |
| Qwen2.5-VL 7B | logit | -0.80 | -0.74 | 0.02 | +0.062 |
| Qwen3.5 27B | penalty | 1.40 | 1.34 | 0.01 | -0.064 |
| Gemma 4 12B | penalty | 1.57 | 1.50 | 0.01 | -0.064 |
| Mistral Small 3.2 24B | penalty | 1.40 | 1.33 | 0.01 | -0.071 |
| Qwen3.5 9B | penalty | 1.17 | 1.12 | 0.01 | -0.049 |
| Qwen2.5-VL 7B | penalty | 1.10 | 1.07 | 0.01 | -0.027 |

Other cell logits (reported, not gated):

| Model | Condition | Truth | Mean | MC SE | Bias |
|---|---|---|---|---|---|
| Gemma 4 12B | image10 | -1.60 | -1.50 | 0.02 | +0.097 |
| Gemma 4 12B | image12 | -1.50 | -1.41 | 0.02 | +0.087 |
| Gemma 4 12B | image14 | -1.60 | -1.51 | 0.02 | +0.088 |
| Mistral Small 3.2 24B | image10 | -1.70 | -1.58 | 0.01 | +0.121 |
| Mistral Small 3.2 24B | image12 | -1.70 | -1.62 | 0.02 | +0.085 |
| Mistral Small 3.2 24B | image14 | -1.40 | -1.31 | 0.02 | +0.091 |
| Qwen2.5-VL 7B | image10 | -2.00 | -1.89 | 0.02 | +0.109 |
| Qwen2.5-VL 7B | image12 | -1.90 | -1.82 | 0.02 | +0.081 |
| Qwen2.5-VL 7B | image14 | -1.80 | -1.72 | 0.02 | +0.077 |
| Qwen3.5 27B | image10 | -1.30 | -1.22 | 0.02 | +0.080 |
| Qwen3.5 27B | image12 | -1.10 | -1.03 | 0.01 | +0.072 |
| Qwen3.5 27B | image14 | -0.90 | -0.84 | 0.01 | +0.058 |
| Qwen3.5 9B | image10 | -1.80 | -1.68 | 0.01 | +0.115 |
| Qwen3.5 9B | image12 | -1.40 | -1.33 | 0.02 | +0.075 |
| Qwen3.5 9B | image14 | -1.20 | -1.12 | 0.02 | +0.080 |

lme4 (glmer, nAGQ = 1) against glmmTMB on the same replications; agreement tolerance 0.05:

| Rep | Largest gap | Gaps over tolerance | Which | lme4 error | lme4 warnings |
|---|---|---|---|---|---|
| 1 | 0.024 (sd:cell) | 0 | none | none | failure to converge in 10000 evaluations; convergence code 4 from Nelder_Mead: failure to converge in 10000 evaluations |
| 2 | 0.007 (penalty:Mistral Small 3.2 24B) | 0 | none | none | failure to converge in 10000 evaluations; convergence code 4 from Nelder_Mead: failure to converge in 10000 evaluations |

## Scenario 2: block-1 standard deviations

The block-1 item standard deviations (4.0 and 4.8) are about three times the plausible 1.5, so the same design was simulated again with the standard deviations of the block-1 fit (rounded to 0.1, see the Block-1 fit section) as the truth. Same gates and thresholds. The standard deviations gated are those with a nonzero truth among item, item:model and item:condition, plus project:condition on DevEval; terms with a truth of 0 are reported as an absolute mean. glmmTMB only, no lme4 refits.

### CoderUJB

- PASS: Convergence, 50 of 50 fits converged (need 48). A rough screen.
- PASS: Standard deviations, the mean estimate is within 20% of the truth for item, item:model, item:condition (largest gap 11%).
- PASS: Fixed effects, the mean of each model's text cell logit and size-averaged penalty is within 0.15 logit of the truth (largest gap 0.128).

Standard deviations (logit scale), glmmTMB, mean over converged fits:

| Term | Truth | Mean | MC SE | Bias | Role | Fits at boundary |
|---|---|---|---|---|---|---|
| item | 4.00 | 3.57 | 0.04 | -11% | gated | 0 |
| item:model | 1.30 | 1.17 | 0.02 | -10% | gated | 0 |
| item:condition | 1.00 | 0.91 | 0.02 | -9% | gated | 0 |
| project | 0.00 | 0.11 | 0.03 | +0.11 (absolute) | reported | 38 |
| project:condition | 0.00 | 0.02 | 0.01 | +0.02 (absolute) | reported | 47 |
| cell | 1.40 | 0.98 | 0.02 | -30% | reported | 0 |

Not-pdHess fits: 0 of 50.

Gated fixed-effect quantities (text cell logit and size-averaged penalty):

| Model | Quantity | Truth | Mean | MC SE | Bias |
|---|---|---|---|---|---|
| Qwen3.5 27B | logit | 0.10 | 0.16 | 0.06 | +0.058 |
| Gemma 4 12B | logit | -0.20 | -0.17 | 0.06 | +0.028 |
| Mistral Small 3.2 24B | logit | -0.30 | -0.26 | 0.06 | +0.039 |
| Qwen3.5 9B | logit | -0.40 | -0.33 | 0.07 | +0.069 |
| Qwen2.5-VL 7B | logit | -1.30 | -1.25 | 0.06 | +0.049 |
| Qwen3.5 27B | penalty | 1.50 | 1.46 | 0.04 | -0.039 |
| Gemma 4 12B | penalty | 2.37 | 2.24 | 0.04 | -0.128 |
| Mistral Small 3.2 24B | penalty | 1.87 | 1.76 | 0.04 | -0.106 |
| Qwen3.5 9B | penalty | 1.60 | 1.49 | 0.04 | -0.111 |
| Qwen2.5-VL 7B | penalty | 0.87 | 0.82 | 0.04 | -0.051 |

Other cell logits (reported, not gated):

| Model | Condition | Truth | Mean | MC SE | Bias |
|---|---|---|---|---|---|
| Gemma 4 12B | image10 | -2.50 | -2.34 | 0.06 | +0.156 |
| Gemma 4 12B | image12 | -2.40 | -2.29 | 0.07 | +0.108 |
| Gemma 4 12B | image14 | -2.80 | -2.60 | 0.07 | +0.204 |
| Mistral Small 3.2 24B | image10 | -2.40 | -2.23 | 0.05 | +0.171 |
| Mistral Small 3.2 24B | image12 | -2.40 | -2.27 | 0.07 | +0.132 |
| Mistral Small 3.2 24B | image14 | -1.70 | -1.57 | 0.06 | +0.133 |
| Qwen2.5-VL 7B | image10 | -2.60 | -2.45 | 0.07 | +0.151 |
| Qwen2.5-VL 7B | image12 | -1.90 | -1.84 | 0.07 | +0.059 |
| Qwen2.5-VL 7B | image14 | -2.00 | -1.91 | 0.07 | +0.091 |
| Qwen3.5 27B | image10 | -1.30 | -1.16 | 0.07 | +0.139 |
| Qwen3.5 27B | image12 | -1.70 | -1.62 | 0.06 | +0.084 |
| Qwen3.5 27B | image14 | -1.20 | -1.13 | 0.06 | +0.068 |
| Qwen3.5 9B | image10 | -2.60 | -2.38 | 0.06 | +0.219 |
| Qwen3.5 9B | image12 | -2.00 | -1.82 | 0.07 | +0.176 |
| Qwen3.5 9B | image14 | -1.40 | -1.25 | 0.07 | +0.146 |

### DevEval

- PASS: Convergence, 50 of 50 fits converged (need 48). A rough screen.
- PASS: Standard deviations, the mean estimate is within 20% of the truth for item, item:model, item:condition, project:condition (largest gap 13%).
- PASS: Fixed effects, the mean of each model's text cell logit and size-averaged penalty is within 0.15 logit of the truth (largest gap 0.106).

Standard deviations (logit scale), glmmTMB, mean over converged fits:

| Term | Truth | Mean | MC SE | Bias | Role | Fits at boundary |
|---|---|---|---|---|---|---|
| item | 4.80 | 4.22 | 0.02 | -12% | gated | 0 |
| item:model | 1.10 | 0.99 | 0.01 | -10% | gated | 0 |
| item:condition | 1.10 | 0.99 | 0.01 | -10% | gated | 0 |
| project | 0.00 | 0.09 | 0.03 | +0.09 (absolute) | reported | 41 |
| project:condition | 0.70 | 0.61 | 0.01 | -13% | gated | 0 |
| cell | 1.30 | 0.85 | 0.01 | -35% | reported | 0 |

Not-pdHess fits: 0 of 50.

Gated fixed-effect quantities (text cell logit and size-averaged penalty):

| Model | Quantity | Truth | Mean | MC SE | Bias |
|---|---|---|---|---|---|
| Qwen3.5 27B | logit | 0.30 | 0.29 | 0.04 | -0.008 |
| Gemma 4 12B | logit | 0.00 | 0.03 | 0.03 | +0.033 |
| Mistral Small 3.2 24B | logit | -0.20 | -0.17 | 0.03 | +0.029 |
| Qwen3.5 9B | logit | -0.30 | -0.24 | 0.03 | +0.062 |
| Qwen2.5-VL 7B | logit | -0.80 | -0.71 | 0.03 | +0.092 |
| Qwen3.5 27B | penalty | 1.40 | 1.29 | 0.03 | -0.106 |
| Gemma 4 12B | penalty | 1.57 | 1.46 | 0.03 | -0.106 |
| Mistral Small 3.2 24B | penalty | 1.40 | 1.30 | 0.02 | -0.103 |
| Qwen3.5 9B | penalty | 1.17 | 1.09 | 0.03 | -0.075 |
| Qwen2.5-VL 7B | penalty | 1.10 | 1.04 | 0.02 | -0.060 |

Other cell logits (reported, not gated):

| Model | Condition | Truth | Mean | MC SE | Bias |
|---|---|---|---|---|---|
| Gemma 4 12B | image10 | -1.60 | -1.44 | 0.03 | +0.157 |
| Gemma 4 12B | image12 | -1.50 | -1.37 | 0.04 | +0.126 |
| Gemma 4 12B | image14 | -1.60 | -1.47 | 0.03 | +0.133 |
| Mistral Small 3.2 24B | image10 | -1.70 | -1.54 | 0.04 | +0.162 |
| Mistral Small 3.2 24B | image12 | -1.70 | -1.56 | 0.03 | +0.138 |
| Mistral Small 3.2 24B | image14 | -1.40 | -1.30 | 0.03 | +0.096 |
| Qwen2.5-VL 7B | image10 | -2.00 | -1.83 | 0.03 | +0.167 |
| Qwen2.5-VL 7B | image12 | -1.90 | -1.75 | 0.03 | +0.146 |
| Qwen2.5-VL 7B | image14 | -1.80 | -1.66 | 0.03 | +0.144 |
| Qwen3.5 27B | image10 | -1.30 | -1.19 | 0.03 | +0.108 |
| Qwen3.5 27B | image12 | -1.10 | -1.01 | 0.03 | +0.092 |
| Qwen3.5 27B | image14 | -0.90 | -0.81 | 0.03 | +0.095 |
| Qwen3.5 9B | image10 | -1.80 | -1.64 | 0.04 | +0.165 |
| Qwen3.5 9B | image12 | -1.40 | -1.27 | 0.03 | +0.126 |
| Qwen3.5 9B | image14 | -1.20 | -1.08 | 0.03 | +0.119 |

## Time and memory

Apple M4, 10 cores, 24 GB. Wall seconds per fit, measured inside the script, with 6 fits running at once (the 2 lme4 fits per benchmark ran in the same worker pool, so they shared the machine too):

| Scenario | Benchmark | Engine | Fits | Median s | Max s |
|---|---|---|---|---|---|
| plausible | CoderUJB | glmmTMB | 50 | 2 | 3 |
| plausible | CoderUJB | lme4 | 2 | 67 | 69 |
| plausible | DevEval | glmmTMB | 50 | 32 | 41 |
| plausible | DevEval | lme4 | 2 | 512 | 513 |
| block1 | CoderUJB | glmmTMB | 50 | 8 | 10 |
| block1 | DevEval | glmmTMB | 50 | 57 | 644 |

One replication with one worker under `/usr/bin/time -l` (maximum resident set size). The plausible runs also include the lme4 refit of that replication, the block1 runs are glmmTMB only:

| Scenario | Benchmark | Peak MB | Wall s |
|---|---|---|---|
| plausible | CoderUJB | 573 | 44 |
| plausible | DevEval | 1072 | 241 |
| block1 | CoderUJB | 468 | 9 |
| block1 | DevEval | 748 | 33 |

## Block-1 fit

The same model on the real block-1 cells (3 runs each), glmmTMB. Only the standard deviations and the level counts are kept; fixed effects are not written. Block 1 covers 56 of 79 DevEval repositories and 10 of 14 CoderUJB projects, so the CoderUJB project terms are indicative only. The truth column is the simulated value, not an estimate.

CoderUJB: converged yes, pdHess yes, 0 s.

| Term | Simulated truth | Block-1 estimate | Levels |
|---|---|---|---|
| item | 1.50 | 4.00 | 40 |
| item:model | 0.80 | 1.29 | 200 |
| item:condition | 0.50 | 0.99 | 160 |
| project | 0.50 | 0.00 | 10 |
| project:condition | 0.30 | 0.00 | 40 |
| cell | 0.50 | 1.44 | 800 |

DevEval: converged yes, pdHess yes, 3 s.

| Term | Simulated truth | Block-1 estimate | Levels |
|---|---|---|---|
| item | 1.50 | 4.76 | 200 |
| item:model | 0.80 | 1.13 | 1000 |
| item:condition | 0.50 | 1.09 | 800 |
| project | 0.50 | 0.00 | 56 |
| project:condition | 0.30 | 0.67 | 224 |
| cell | 0.50 | 1.30 | 4000 |

