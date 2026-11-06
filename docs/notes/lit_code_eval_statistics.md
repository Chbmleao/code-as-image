# Literature: statistical analysis of LLM code benchmarks and evals

Scope: extends lit_llm_eval_variance.md and gtheory_methods.md in this folder and does not repeat them. Design: 5 VLMs x 2 code benchmarks (CoderUJB Java N=136, DevEval Python N=859) x 4 conditions (text, and image at 10, 12 and 14 px), 3 runs per cell at T 0.7 / top_p 0.95, outcome = binary pass (all target tests pass). Main estimand: per-model text-minus-image gap with a project-clustered CI.

Tags: [web: URL] = claim from a page that was opened. [snippet: URL] = seen only in a search result, not opened, do not rely on it before checking. [ours] = our inference, not a literature result.

## 1. Repeated sampling, pass@k, number of runs

- Miller 2024, "Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations" (Evan Miller), arXiv 2411.00640. [web: https://arxiv.org/html/2411.00640]
  - SE from the CLT, sqrt(Var(s)/n); bootstrap only needed for complicated sampling schemes. For fractional scores the Bernoulli SE is conservative.
  - Clustered SE adds within-cluster cross terms; it can exceed 3x the naive SE (ratios 3.05 DROP, 1.10 RACE-H, 1.88 MGSM).
  - Paired difference: SE_A-B = sqrt(SE_A^2 + SE_B^2 - 2 SE_A SE_B Corr); question-level correlations 0.50 MATH, 0.64 HumanEval, 0.37 MGSM. Recommends the paired version "wherever practicable"; compute the clustered SE on the item-level differences.
  - K resamples per question: Var = (Var(x) + E[sigma^2]/K)/n. Do not pool K*N answers as independent. In the uniform-difficulty example K=2 cuts variance by 1/3, K=4 by 1/2, ceiling 2/3. Advises against lowering temperature to cut variance.
  - Power: n = (z_a/2 + z_b)^2 (omega^2 + sigma_A^2/K_A + sigma_B^2/K_B)/delta^2.
- Chen et al. 2021, "Evaluating Large Language Models Trained on Code", arXiv 2107.03374. [web: ar5iv rendering, first 100k chars]
  - Unbiased pass@k = E[1 - C(n-c,k)/C(n,k)], n >= k; the naive 1-(1-p_hat)^k is biased. They use n=200.
  - [ours] With n=k=3 the estimator is just the empirical any-of-3 rate. Headline should be mean pass rate over runs (pass@1 averaged), with any-of-3 optional.
- Madaan et al. 2024, "Quantifying Variance in Evaluation Benchmarks" (Lovish Madaan et al.), arXiv 2406.10229. [web: https://arxiv.org/html/2406.10229v1]
  - Seed variance is smaller than the 95% CI width but large on small sets (COPA 100, HumanEval 164). Continuous metrics are less noisy.
  - IRT-selected 100-item subsets increased seed variance (ARC-C 0.80 to 1.80) and reversed about 12% of pairwise rankings. Argues against IRT subsetting for variance reduction.
- Bowyer, Aitchison, Ivanova 2025, "Position: Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints", arXiv 2503.01747. [web: https://arxiv.org/html/2503.01747]
  - CLT coverage 92.5% at N=100; intervals can collapse to zero width or leave [0,1]. Recommend Wilson or Beta-Bernoulli. Clopper-Pearson too conservative. Paired Bayes method recommended for correlated comparisons.
  - Appendix D on pass@K says a hierarchical Bayesian model with a per-model latent variable would be needed; no frequentist interval is offered.
  - [ours] CoderUJB N=136 is borderline; DevEval N=859 is fine for the CLT.
- Heineman et al. 2025, "Signal and Noise: A Framework for Reducing Uncertainty in Language Model Evaluation", arXiv 2508.13144. [web: https://arxiv.org/html/2508.13144, first 100k chars]
  - Noise is checkpoint-to-checkpoint, not sampling noise. [ours] Its bits-per-byte advice does not transfer to generative VLM grading.
- Bouthillier et al. 2021, "Accounting for Variance in Machine Learning Benchmarks", arXiv 2103.03098. [web: https://arxiv.org/abs/2103.03098, abstract only] Randomize several sources of variation.
- Biderman et al. 2024, "Lessons from the Trenches on Reproducible Evaluation of Language Models", arXiv 2405.14782. [web: https://arxiv.org/html/2405.14782, first 100k chars] Bootstrap stderr answers question sampling; reruns capture model stochasticity. Share prompts, per-sample outputs, library version.
- Hariri et al., "Don't Pass@k: A Bayesian Framework for Large Language Model Evaluation", arXiv 2510.04265. [web: https://arxiv.org/abs/2510.04265, abstract only] Dirichlet posterior over categorical/graded outcomes; math sets, not code.
- Verine et al., "Estimating Pass@k from Fewer Samples with Hierarchical Bayesian Priors", ICML 2026. [web: https://icml.cc/virtual/2026/68337, page only] Empirical-Bayes pooling across tasks.
- "How Do Large Language Monkeys Get Their Power (Laws)?", arXiv 2502.17578. [snippet: only] Per-problem pass rates modeled as Beta.

## 2. Paired comparisons and multiplicity

- Chandrahas 2026, evalci, arXiv 2607.04429. [web: https://arxiv.org/abs/2607.04429, abstract] Paired permutation test, clustered SEs, power analysis, multiplicity correction; 3 of 8 adjacent MMLU gaps not significant after correcting for 36 comparisons.
- Kotawala 2026, "Resolution Diagnostics for Paired LLM Evaluation", arXiv 2605.30315. [web: https://arxiv.org/abs/2605.30315, abstract] Many pairwise rankings unresolved at (0.05, 0.8); the unpaired Cohen-h-times-(1-rho) shortcut is off by about 2x; report q = N/N*.
- Dror et al. 2018, "The Hitchhiker's Guide to Testing Statistical Significance in NLP", ACL P18-1128. [web: ACL anthology abstract] Test-selection protocol; single-comparison focus.
- Multiplicity snippets only: 2501.18243 (Holm-Sidak default; warns against testing only top vs runner-up), 2505.22910 (BH primary, Holm as a sensitivity check), 2509.26483, 2605.26730. [snippet: arxiv.org/abs/<id>] Check before citing.
- [ours] Family = every per-model, per-condition contrast actually run; Holm for the confirmatory family, BH for exploratory sweeps.

## 3. Partial credit, test pass rates, models for fractions

- ClassEval, Du et al., arXiv 2308.01861. [web: html] Pass@k only; a sample counts only if it passes all tests; no partial credit.
- "Critical review of benchmarks and metrics", arXiv 2406.12655. [web: html] Defines TPR (share of tests passed) and AvgTPR; flags high variance of naive pass@k.
- Keller et al., NIST AI 800-3, "Expanding the AI Evaluation Toolbox with Statistical Models", 2026, DOI 10.6028/NIST.AI.800-3. [web: https://www.nist.gov/publications/expanding-ai-evaluation-toolbox-statistical-models, abstract only; PDF unreadable] GLMMs separate benchmark accuracy from generalized accuracy and give variance decomposition and item difficulty. Random-effects structure not read.
- Bates et al. 2014, lme4, arXiv 1406.5823. [web: abstract] Tool reference.
- Rahman et al. 2025, arXiv 2510.26130. [web: abstract] Real-world class-level benchmark; fractional outcome definition not confirmed.
- GAP: no source found comparing binomial GLMM, beta-binomial, fractional logit or quasi-binomial for per-task test fractions in code evals. [ours] Our outcome is binary pass (all target tests pass), so none of these fraction models is used here; the gap is noted for completeness.
- Snippets only: 2606.16827 (McNemar plus per-test pass percentage), 2410.19792 (mixed-effects logistic).

## 4. Ceiling, floor, zero-variance items

- Bowyer: an all-same-answer sample gives CLT SE = 0. Madaan: item pruning did not reduce variance. lit_llm_eval_variance.md section (d) already covers selection.
- [ours] Keep all-correct and all-wrong items in the paired contrast (they contribute zero but are valid); report the discordant-item count.
- IRT precedents: Rodriguez et al. 2021, ACL (2021.acl-long.346) [web: landing page]; Lalor, Wu, Yu 2016, "Building an Evaluation Scale using Item Response Theory", EMNLP, arXiv 1605.08889 [snippet: https://arxiv.org/abs/1605.08889]; Truong et al. 2025, arXiv 2503.13335 [snippet only]; tinyBenchmarks 2402.14992 and metabench 2407.12844 [web: abstracts].
- DIF: a NeurIPS 2026 poster applies Mantel-Haenszel DIF across model families [snippet: https://neurips.cc/virtual/2026/poster/139203]; a dissertation uses prompt configurations as DIF groups [snippet: https://digital.lib.washington.edu/researchworks/items/203c1f75-82a1-4b3a-825c-21caeefb7c0f]. No DIF paper for input modality found.

## 5. Contamination

- Riddell, Ni, Cohan 2024, arXiv 2403.04811. [web: abstract] Substantial overlap with open corpora; better performance on subsets with similar training solutions.
- LiveCodeBench, Jain et al. 2024, arXiv 2403.07974. [web: abstract] Time-segmented problems.
- DyCodeEval, arXiv 2503.04149 [snippet only].
- Xiao and Cheng, "Contamination Inflates Scores but Rarely Reorders Large Language Model Leaderboards", arXiv 2609.02899. [snippet: https://arxiv.org/pdf/2609.02899] Within-item original vs paraphrase contrast; contamination shifts scores but rarely rankings (3 of 188 cases showed differential contamination). Closest support for the paired-design argument; preprint, read the full text before relying on it.
- GAP: no source states directly that a paired condition contrast neutralizes contamination. [ours] It cancels an item-level memorization advantage only if that advantage is the same under text and image input. Memorization may be modality-dependent (a hypothesis).

## Gaps summary

1. No code-specific literature on fractional-outcome models.
2. No direct paired-design-vs-contamination paper (only the 2609.02899 snippet).
3. Partial reads: Heineman, Chen, Bowyer (read), Truong (snippet), NIST (abstract only).
4. "Learning latent parameters without human response patterns" was not found.
