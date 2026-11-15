# Reliability (draft paragraph)

Every number below is in `results/reliability/reliability.json`, rounded to two decimals.

We treat run-to-run variation as test-retest error (book p. 147) and estimate it on the observed
0/1 pass of each run, with one Gaussian mixed model per benchmark and condition: model, project
(CoderUJB) or repository (DevEval), item, model x project and model x item, with runs nested in
cells (pp. 119-120, 128; 3 runs for the first block of items, 2 for the rest). Components were
estimated by MCMC with a half-Cauchy prior on each standard deviation (p. 125); all 16 fits passed
the convergence gate, and an inverse-gamma prior moved no G coefficient by more than 5%. The
single-run reliability of a model's item score is 0.59 to 0.68 on CoderUJB and 0.67 to 0.76 on
DevEval across the four conditions, close to the observed correlation between two runs (0.59 to
0.63 and 0.67 to 0.76). Every item has at least two runs, so the item scores we analyse have a
reliability of 0.74 to 0.81 on CoderUJB and 0.80 to 0.86 on DevEval (Spearman-Brown); the 40
CoderUJB and 200 DevEval items of the first block have a third run, which gives 0.81 to 0.86 and
0.86 to 0.90. For ranking the five models, the
G coefficient that treats them as a fixed set is 0.92 to 0.98 on DevEval and 0.85 to 0.94 on
CoderUJB, except CoderUJB at 12 px (0.61, 95% interval 0.01 to 0.86); the version that treats them
as a sample rests on 4 degrees of freedom and is a secondary line. Over 2000 joint resamples of
projects and repositories, Qwen3.5 27B ranks first in every condition on both benchmarks and
Qwen2.5-VL 7B last in text, but the middle three are not stable: Gemma 4 12B and Qwen3.5 9B
reverse their text order in image with probability 0.79 on CoderUJB and 0.98 on DevEval.
