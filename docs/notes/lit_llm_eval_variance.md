# LLM/VLM evaluation variance and run sizing

Covers literature on variance components, run-to-run noise, paired standard errors and item sampling for LLM code evals, and what it implies for sizing runs and items here.

## (a) G-theory and variance-component papers for LLM benchmarks: which component dominates?

### Takeaway
G-theory is now used in LLM evaluation papers, and the dominant component depends on the design: in the one decomposition with numbers (brand-sentiment answers) pure resampling and context interactions are each about a third of variance, and extra repeats stop paying off after about 5. No paper found gives a G-study for pass/fail code benchmarks with VLMs, so the item-by-model and item-by-run split has to come from the D-study block itself.

### Cited Findings
- A crossed random-effects (G-theory) decomposition of 12,933 LLM brand-sentiment responses (20 brands, 8 languages, 3 models) gave: query language 26.5% of single-response variance (largest systematic facet), pure resampling 34.8%, brand-in-context interaction 29.6%, brand identity 1.5% (ICC 0.0146), brand-by-language 8.6%, brand-by-model and brand-by-prompt near zero. Submitted 14 Jul 2026. Source: [Zatuchin, arXiv 2607.13304](https://arxiv.org/abs/2607.13304)
- Same paper: brand-ranking reliability is about 0.01 for a single answer and about 0.36 for the full crossed design; a repeat beyond the fifth reduces relative-error variance by only 0.0003; adding languages and models cuts relative-error variance far more per query than adding repeats. Source: [Zatuchin, arXiv 2607.13304](https://arxiv.org/abs/2607.13304)
- Naive standard errors are 40 to 60% smaller than corrected SEs that account for the extra dependence structure (13 Apr 2026). Only the abstract page was read; no numeric variance components were available there. Source: [Messing, arXiv 2604.11581](https://arxiv.org/abs/2604.11581) (snippet-level, partly unverified)
- Single-judge reliability caps at sigma2_s / (sigma2_s + sigma2_sj) regardless of how many items are added; judging pairs in both orders gives a ceiling of 0.986 (17 Aug 2026). Snippet-level. Source: [Anand, arXiv 2609.27787](https://arxiv.org/abs/2609.27787) (unverified)

### Inferences
- The generic G-theory lesson (error variance has an item part shrinking in n_items and a replication part shrinking in n_items x n_reps, so reps cannot fix item-sampling noise) applies directly to this project, but the weights are design-specific and cannot be borrowed from the brand-sentiment study.
- For a model x item x run design, the object of measurement is the condition effect (image minus text), so the relevant error terms are model x item and item x condition interactions plus residual run noise.

### Gaps
- No G-study found on code-generation benchmarks or on VLMs; no published item/seed/prompt/model variance split for pass@1 with an LLM panel.
- Messing and Anand were not read beyond abstract or snippet; numbers should be re-checked before quoting.

## (b) Seed/run variance numbers and the paired-SE formulas

### Takeaway
Run-to-run noise is large on small benchmarks (5 to 15 pass@1 points across 20 seeds on 30-question sets), and the right inferential unit is the question, not the sample. With K samples per question the within-question term shrinks as 1/K but the between-question term does not, so there is a cap on what extra runs buy.

### Cited Findings
- Law-of-total-variance decomposition for a per-question score with K resamples: the variance of the mean splits into variance of per-question means (does not shrink with K) plus mean within-question variance divided by K. The paper's worked example gives reductions of 1/3, 1/2 and 5/9 of the within-question share at K=2, 4 and 6, with a 2/3 ceiling in that example. Recommends clustered/paired SEs over naive ones. The example numbers were taken from the arXiv HTML. Source: [Miller, Adding Error Bars to Evals, arXiv 2411.00640](https://arxiv.org/abs/2411.00640)
- CLT-based intervals reach only 92.5% coverage at N=100 questions; Wilson, Beta-Bernoulli and Bayesian intervals (including a paired Bayesian comparison) are recommended for small N; questions every model always passes or always fails contribute no information in the CLT interval. Source: [Bowyer et al., arXiv 2503.01747](https://arxiv.org/abs/2503.01747)
- 20 independent runs on 9 models: pass@1 standard deviation 5 to 15 points across seeds on AIME'24 (30 questions) and AMC'23 (40 questions); one question moves pass@1 by 2.5 to 3.3 points; bootstrapping needs K>=30 runs to be stable ("minimal standard"); temperature changes swing results up to 15 points and top_p up to 8; hardware/software changes alone up to 8 points; authors recommend 30 seeds but used 10 as a compromise. Source: [A Sober Look at Progress in Language Model Reasoning, arXiv 2504.07086](https://arxiv.org/abs/2504.07086) (read from the HTML, first 100K characters only)
- Benchmark signal-to-noise ratio predicts decision accuracy (R=0.791 across benchmarks); bits-per-byte scoring lifts SNR on HumanEval from 6.1 to 25.1 and on MBPP from 2.0 to 41.8. Noise here is checkpoint-to-checkpoint noise, not sampling-seed noise (18 Aug 2025). Source: [Signal and Noise, arXiv 2508.13144](https://arxiv.org/abs/2508.13144)

### Inferences
- Paired design here: for model m and item i let d_i = (image pass rate) - (text pass rate) averaged over K runs. SE(mean d) = sd(d_i) / sqrt(n). Var(d_i) contains the between-item part plus (p_img(1-p_img) + p_text(1-p_text)) / K from sampling, so K=3 leaves the second term at one third of the single-run value. These are standard identities consistent with Miller, not quoted from a source.
- When item-level differences dominate, n matters more than K beyond about 3; the D-study block should estimate the ratio directly.
- CoderUJB at 136 items is below the N where Bowyer finds the CLT reliable, so Wilson or Bayesian paired intervals are safer there.

### Gaps
- Madaan et al. (2024, variance in benchmark evaluation) and Biderman et al. (lessons from the trenches) were not retrieved with numbers; Biderman gives no numeric sizing guidance in what was seen.
- The remaining 33K characters of the Sober Look page, and Bowyer's Appendix D on pass@k, were not read.
- The Sober Look numbers are for long-chain math reasoning, not code, and not VLMs.

## (c) Code-generation pass@1 run-to-run variability at T>0

### Takeaway
The pass@k estimator is known, and near-greedy decoding is not fully deterministic, but no source was found quantifying the share of items with intermediate pass probability at T=0.7. That fraction should be measured in the D-study block.

### Cited Findings
- Chen et al. introduce an unbiased pass@k estimator using n >= k samples per problem with c correct: pass@k = E over problems of 1 - C(n-c, k)/C(n, k); the reference implementation refuses to evaluate k > n. Their Figure 2 shows per-problem pass probabilities for example problems, details not read. Source: [Chen et al., arXiv 2107.03374](https://arxiv.org/pdf/2107.03374) (via search summary, paper not fetched)
- ChatGPT code generation is non-deterministic even at temperature 0 on a 829-problem set, and a later Tree of Thoughts approach reduced it. Specific rates were not retained. Source: [Ouyang et al., arXiv 2308.02828](https://arxiv.org/abs/2308.02828) (details unverified)
- Project-local evidence: an earlier test at temperature 1e-6 with 5 seeds gave identical pass/fail in 158 of 160 cells (project data, not a literature source).

### Inferences
- With only 2 of 160 cells varying at T~0, the variance in the main run at T=0.7 will mostly come from items whose pass probability is neither near 0 nor near 1; the share of such items bounds how much K helps.
- Items with p_img = p_text near 0 or 1 contribute essentially zero to both numerator and denominator of the paired effect, so they inflate n without adding power.

### Gaps
- No source found for the fraction of items with intermediate pass probability at T=0.7 (a bimodality search returned nothing directly).
- Ouyang's quantitative results and Chen's per-problem distribution were not read.

## (d) Item selection and sample size: detectable difference, zero-variance items, IRT selection

### Takeaway
Papers on item reduction show that 50 to 100 well-chosen items can reproduce full-benchmark rankings within a few percent, but that is for ranking models, not for estimating a paired condition effect. For detectable differences, the paired SE formula above is what applies.

### Cited Findings
- 100 curated items estimate full-benchmark performance on the MMLU-style benchmarks with about 2% error. Source: [tinyBenchmarks, arXiv 2402.14992](https://arxiv.org/abs/2402.14992)
- Under 3% of items reproduce the metabench aggregate with small error. Source: [metabench, arXiv 2407.12844](https://arxiv.org/abs/2407.12844)
- IRT-based adaptive selection used up to 50 times fewer items for comparable validity. Source: [Fluid Benchmarking, arXiv 2509.11106](https://arxiv.org/abs/2509.11106)
- Small N makes CLT intervals under-cover (92.5% at N=100) and always-pass or always-fail items add no information. Source: [Bowyer et al., arXiv 2503.01747](https://arxiv.org/abs/2503.01747)

### Inferences
- Minimum detectable paired difference at 80% power and alpha 0.05 is about 2.8 x SE(mean d), with SE = sd(d_i)/sqrt(n). For example, if sd(d_i) is 0.3 (assumed value, to be replaced by the D-study estimate), n=136 gives SE 0.026 and MDE about 7 points; n=859 gives SE 0.010 and MDE about 3 points.
- Dropping items that are saturated in both conditions for all models raises the effective sd(d_i) per item but shrinks n; this should be decided from the D-study block, not assumed.

### Gaps
- IRT item-selection papers target ranking models, not a paired text-vs-image effect; no source gives a power rule for that design.
- The three item-reduction papers were read at abstract level only.

## (e) VLM text-as-image studies: sample sizes and seeds

### Takeaway
The closest prior work (CodeOCR, PixelWorld, Glyph, VISTA-Bench) mostly reports single runs on fixed benchmarks with no variance decomposition, so this project would be one of the few to report one.

### Cited Findings
- CodeOCR evaluates code understanding from rendered images with compression ratios; the first 100K characters were read and no seed or variance analysis was seen. Source: [CodeOCR, arXiv 2602.01785](https://arxiv.org/abs/2602.01785)
- PixelWorld compares text, image and mixed inputs for the same content. Source: [PixelWorld, arXiv 2501.19339](https://arxiv.org/abs/2501.19339) (snippet-level, unverified)
- Glyph compresses long text into rendered images for VLM context. Source: [Glyph, arXiv 2510.17800](https://arxiv.org/abs/2510.17800) (snippet-level, unverified)

### Inferences
- If these studies run one seed, their reported accuracy gaps carry the single-run noise quantified in (b), which is a point for the course report's related-work discussion.

### Gaps
- DeepSeek-OCR, "Text or Pixels" and the vision-centric token compression paper were not found or read.
- Sample sizes and seeds for Glyph, PixelWorld and VISTA-Bench were not verified.

## (f) torch_measure as of 2026: G-theory and variance-component tooling

### Takeaway
torch_measure on GitHub main has G-theory tooling (variance components, G coefficients, D-study, bootstrap), but the PyPI release v0.1.0 (2026-05-13) may predate it, so install from GitHub if it is used.

### Cited Findings
- The repo `aims-foundations/torch_measure` has `src/torch_measure/metrics/generalizability.py` with `variance_components`, `g_coefficient`, `intraclass_correlation`, `d_study` and `bootstrap_variance_components`, plus helpers in `_generalizability.py` and `metrics/assumptions.py`, and a "Generalizability" section in `docs/source/api/metrics.rst`. Source: [torch_measure on GitHub](https://github.com/aims-foundations/torch_measure) (source files read directly)
- `variance_components(response_matrix, subject_col, item_col, trial_col, response_col, method="moments", *, facet_cols=None, object_facet=None, interactions="all")` uses Henderson Method I (ANOVA moments), clamps negative components to 0, raises NotImplementedError for method="reml", and in multi-facet mode requires a balanced fully crossed design. Source: [generalizability.py](https://github.com/aims-foundations/torch_measure/blob/main/src/torch_measure/metrics/generalizability.py)
- `d_study` in two-facet mode computes relative error as s_pi/n_items + s_e/(n_items*n_reps) and absolute error as s_i/n_items plus that, returning g_relative, g_absolute, se_relative, se_absolute per (n_items, n_reps) grid cell; multi-facet mode takes a `design_grid`. Source: [generalizability.py](https://github.com/aims-foundations/torch_measure/blob/main/src/torch_measure/metrics/generalizability.py)
- PyPI release torch-measure v0.1.0 dated 2026-05-13. Source: [PyPI JSON](https://pypi.org/pypi/torch-measure/json)

### Inferences
- G-theory commits appeared on main in June and July 2026, after the PyPI release date, so `pip install torch-measure` likely lacks them. This is based on the commit history and was not confirmed by installing the package.
- A model x item x run design needs 3 facets (multi-facet mode), which needs a balanced design: every model must have the same items and the same number of runs per cell, and missing cells must be handled before calling it.
- The two-facet D-study formula implicitly treats the condition effect as part of subject-by-item error, so for a text-vs-image contrast it is cleaner to compute the per-item difference first and then run the variance components on d.

### Gaps
- Not verified by installing or running the library.
- Whether a REML or unbalanced-design path is planned was not checked.
