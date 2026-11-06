# G-theory methods for a G-study and D-study of LLM/VLM code benchmarks

Covers variance-component estimators, G and Phi, a difference-score view of the text-vs-image gap, sampling error of components, and run and item sizing.

Provenance legend used below. [WEB] = read on the linked page. [TEXTBOOK] = standard result from Brennan (2001), Shavelson & Webb (1991), Searle, Casella & McCulloch (1992), written from memory of those books; the book pages could not be retrieved (the NCME Brennan module PDF was image-only, CASMA PDFs returned 404), so check the exact equation numbers against the books before quoting. [OURS] = our own derivation or simulation (code in Appendix). Nothing marked [OURS] should be cited as literature.

Notation: p = models (n_p), i = items (n_i), r = runs (n_r), c = condition (fixed; the contrast treated below is text vs one image size). Y in {0,1} per attempt (pass = all target tests pass).

---

## 1. EMS equations and method-of-moments estimators for the crossed random p x i x r design

### Takeaway
Estimators are linear combinations of ANOVA mean squares (equations below). Negative estimates are common with few levels; Brennan's convention is to report the negative estimate as is in the G-study table, then set it to zero when computing coefficients. The key design insight for this project is that "run" is a replicate of an attempt, not a meaningful crossed facet, so p x i x r should be collapsed to p x i with n_r replicates (section 1, Inferences).

### Cited Findings
- [TEXTBOOK] With one observation per cell, the highest-order term sigma2_pir,e is confounded with residual error. Expected mean squares for the random p x i x r model (Brennan 2001, Ch. 3 and Appendix; Shavelson & Webb 1991, Ch. 3):
  - EMS(p) = s2_e + n_r s2_pi + n_i s2_pr + n_i n_r s2_p
  - EMS(i) = s2_e + n_r s2_pi + n_p s2_ir + n_p n_r s2_i
  - EMS(r) = s2_e + n_i s2_pr + n_p s2_ir + n_p n_i s2_r
  - EMS(pi) = s2_e + n_r s2_pi
  - EMS(pr) = s2_e + n_i s2_pr
  - EMS(ir) = s2_e + n_p s2_ir
  - EMS(pir,e) = s2_e
  where s2_e = sigma2_pir,e. Degrees of freedom: n_p-1, n_i-1, n_r-1, (n_p-1)(n_i-1), (n_p-1)(n_r-1), (n_i-1)(n_r-1), (n_p-1)(n_i-1)(n_r-1).
- [TEXTBOOK] Method-of-moments solutions (set EMS = observed MS and solve):
  - s2_e = MS(pir)
  - s2_pi = [MS(pi) - MS(pir)] / n_r
  - s2_pr = [MS(pr) - MS(pir)] / n_i
  - s2_ir = [MS(ir) - MS(pir)] / n_p
  - s2_p = [MS(p) - MS(pi) - MS(pr) + MS(pir)] / (n_i n_r)
  - s2_i = [MS(i) - MS(pi) - MS(ir) + MS(pir)] / (n_p n_r)
  - s2_r = [MS(r) - MS(pr) - MS(ir) + MS(pir)] / (n_p n_i)
- [WEB] The same logic (T terms, sums of squares, MS = SS/df, each sigma2 = linear combination of MS divided by the product of the other facets' levels) is what GeneralizIT implements, citing Brennan (2001) and Cardinet et al. (1976): [GeneralizIT paper](https://arxiv.org/html/2411.17880v2).
- [WEB] An NCME instructional module summary states that EMS, Bayesian and ML approaches "usually provide very comparable results unless negative variance components are present": snippet in search result for [NCME Module 14 (Brennan)](https://ncme.org/wp-content/uploads/2025/10/Module-14-Generalizability-Theory-Brennan-Winter-1.pdf). The PDF itself could not be read.
- [TEXTBOOK] ANOVA estimators are unbiased (under random-effects model, balanced data) but not constrained to be non-negative. Brennan (2001, Sec. 3.4 and 5.1) recommends: (a) report the negative estimate in the G-study table; (b) for D-study coefficients, replace negative estimates with zero; (c) note that substituting zero introduces some bias, and that, for a component feeding into another component's estimator (e.g. s2_p uses s2_pi indirectly through the MS algebra), the unadjusted estimates should be used in the algebra and zero substituted only for the final component used in the G/Phi formula (Brennan's "negative estimates set to zero after estimation, not before" point; Cronbach et al. 1972 gave the same advice). Check the exact wording in Brennan Sec. 3.4.
- [WEB] Both gtheory and GeneralizIT documentation checks do not describe any negative-variance handling in GeneralizIT ([GeneralizIT paper](https://arxiv.org/html/2411.17880v2)).

### Inferences
- [OURS] Temperature-0.7 runs are exchangeable replicates. Run 1 of model A has no relation to run 1 of model B unless the same seed is deliberately shared, which APIs mostly do not honor. So E[s2_r], E[s2_pr], E[s2_ir] are zero in truth, and the p x i x r model with r crossed wastes degrees of freedom and gives a spurious s2_pr / n_r term in the G formula (estimates will hover around zero and go negative about half the time). The correct model is p x i with n_r replicates per cell (or equivalently p x i x r with r nested in p x i):
  - MS terms: MS(p), MS(i), MS(pi), MS(w) with df n_p n_i (n_r - 1)
  - s2_e(within) = MS(w); s2_pi = [MS(pi) - MS(w)] / n_r; s2_p = [MS(p) - MS(pi)] / (n_i n_r); s2_i = [MS(i) - MS(pi)] / (n_p n_r)
  - G = s2_p / (s2_p + s2_pi/n_i + s2_w/(n_i n_r)) ; Phi adds s2_i/n_i to the denominator.
  The same formula applies when s2_pr = 0, with s2_pir,e relabelled as the within-cell residual. Keep the p x i x r run only as a diagnostic that s2_r, s2_pr, s2_ir are about zero.
- The G formula above is correct for the random p x I x R relative coefficient; Phi additionally needs s2_i/n_i + s2_r/n_r + s2_ir/(n_i n_r) in the denominator.

### Gaps
- Exact page and equation numbers in Brennan (2001) for EMS (Appendix) and for the negative-estimate discussion were not verified.
- No source was found specifying a Brennan rule beyond "report, then zero for D-study"; secondary search returned nothing quoting it.

---

## 2. Relative (G) vs absolute (Phi) coefficients, and which fits each decision

### Takeaway
G (E rho^2) ignores item and run main effects (they shift all models equally), so it fits ranking models on the same items. Phi counts those effects as error, so it fits claims about absolute pass rates. A within-model text-vs-image contrast on shared items is a relative-type comparison for item difficulty, but item x condition variance still enters its error.

### Cited Findings
- [WEB] G (relative): sigma2_p / (sigma2_p + sigma2_REL), where REL error contains every term involving the person (model) including the residual; Phi (absolute): sigma2_p / (sigma2_p + sigma2_ABS), where ABS contains every term except the person main effect. Source: [Mark Lai, PSYC 520 G-theory notes](https://marklhc.quarto.pub/psyc520-2025spring/r-notes/07-gt.html) (also states G and Phi are "analogous to (but not the same as) reliability coefficients").
- [TEXTBOOK] For random p x I x R with n_i, n_r:
  - s2_REL = s2_pi/n_i + s2_pr/n_r + s2_pir,e/(n_i n_r)
  - s2_ABS = s2_REL + s2_i/n_i + s2_r/n_r + s2_ir/(n_i n_r)
  - G = s2_p/(s2_p + s2_REL); Phi = s2_p/(s2_p + s2_ABS)
  (Brennan 2001, Ch. 4; Shavelson & Webb 1991, Ch. 3). Phi <= G always.
- [TEXTBOOK] Brennan also defines SEM-type indices: sigma(Delta) = sqrt(s2_ABS) and sigma(delta) = sqrt(s2_REL), which are more relevant than the ratios when the stakes are a per-model score CI rather than ranking.

### Inferences
- Decision map [MINE, applying the definitions]:
  - Ranking the 5 models on the same items: G (relative). Item difficulty is common to all.
  - Reporting each model's absolute pass rate with a CI on a new item sample: Phi, or better the direct SE sqrt(s2_ABS-type) = SE of the model's mean over items, (s2_i-free because for one fixed model the item main effect is part of what varies, so use s2_i + s2_pi + s2_w terms for that model).
  - Text vs image within a model on identical items: neither G nor Phi is the right primary summary; the object is a difference score per model, handled by error variance of the contrast (section 3).
- With n_p of 2 to 5 and models being the entire population of interest (not a sample), "universe score variance across models" is a descriptive quantity of those models, not an estimate of a population parameter. G then answers "how reproducibly would this model ordering come out with another item/run sample", which is a legitimate but different question from reliability of a measure.

### Gaps
- Brennan page references for SEM indices not checked.

---

## 3. Fixed condition facet and D-study for a text-vs-image contrast

### Takeaway
G theory handles a fixed facet by averaging its interactions into the universe-score or error terms (Brennan's mixed-model rules), but for the real question here (the within-model gap) the cleanest route is to treat the per-model, per-item paired difference as the unit and derive error variance from it. The contrast error variance below is our own derivation; no literature was found specifically on G theory for a two-condition difference score.

### Cited Findings
- [WEB] A facet becomes fixed when the universe of admissible observations is reduced to those levels (Cronbach/Rajaratnam/Gleser lineage): [DTIC report ADA110535](https://apps.dtic.mil/sti/pdfs/ADA110535.pdf) (search-snippet level; not read in full).
- [WEB] Lai's notes show the standard fixed-facet recipe: with a fixed item facet, add sigma2_pi / n_i to the person (universe-score) variance rather than to error, giving universe-score variance sigma2_p + sigma2_pi/n_i; and they warn to treat a facet as fixed only when generalizing beyond its levels is meaningless, otherwise run separate G studies per condition: [Lai notes](https://marklhc.quarto.pub/psyc520-2025spring/r-notes/07-gt.html).
- [WEB] Univariate mixed-model G theory with one fixed facet vs multivariate G theory (each fixed level gets its own variance/covariance components) is compared in Huebner & Skar, PARE: [UMass PARE article](https://openpublishing.library.umass.edu/pare/article/2376/galley/2979/download) (listing seen in search; not read). The multivariate extension is also the subject of an EPM 2021 article (10.1177/00131644211049746; snippet only).
- [TEXTBOOK] Brennan (2001, Ch. 9, multivariate G theory; and Sec. 4.x on restricted universes) states that for a fixed facet with n_c levels, the universe score for object p is the average over the fixed levels, with the p x c interaction folded into universe-score variance: s2_tau(p) = s2_p + s2_pc/n_c. Cardinet, Tourneur & Allal (1976) and Cardinet, Johnson & Pini (2010, EduG book) call this "differentiation of the fixed facet" and note the symmetry of G theory: any facet can be the object of measurement.
- [WEB] No source found treats G theory for change/difference scores head-on. Related lead from search: Jorgensen's work on absolute vs relative differences in variance components (snippet only, source unconfirmed). Classical-test-theory literature on difference-score reliability (Lord 1963; Cronbach & Furby 1970; Bereiter 1963) is the established analogue, recalled from memory and not verified here.

### Inferences (our derivation, [OURS])
Setup: p x i x c with c in {text, image} fixed, items shared across conditions, n_r replicate runs per p-i-c cell, replicate error independent between conditions.

For model p, define the estimated gap d_hat_p = Ybar_p,img - Ybar_p,txt (mean over n_i items and n_r runs). Per-item gap d_pi = mean_r(Y_pi,img) - mean_r(Y_pi,txt). Then:
- Item main effect and model main effect cancel exactly (items shared). The condition main effect is the quantity of interest, not error.
- Remaining random terms: item x condition (ic), model x item x condition (pic), within-cell residual. For a single model p over a fresh item sample:
  - Var(d_hat_p | p) = (s2_ic + s2_pic) / n_i + 2 s2_w / (n_i n_r)
  where s2_ic and s2_pic are the item-by-condition interaction components of the 2-level fixed design (defined so that the variance of the difference of two level effects is twice the component), s2_w is the within-cell residual, assumed equal in both conditions (relax: replace 2 s2_w by s2_w,img + s2_w,txt).
- Empirical equivalent, no components needed: Var(d_hat_p) = s^2(d_pi) / n_i, with s^2(d_pi) the sample variance across items of the per-item gap. This is the paired item-clustered SE of Miller (see section 7). It automatically includes s2_ic, s2_pic and s2_w/n_r.
- Contrast "reliability" across models (does the gap differ between models?): s2_tau,gap = variance across models of the true gap (= 2 s2_pc in the fixed-effects convention); coefficient = s2_tau,gap / (s2_tau,gap + mean over models of Var(d_hat_p|p)). With 5 models this has 4 df and will be extremely imprecise (section 4), and it answers "are the models' gaps distinguishable", not "what is each model's gap". For the stated research question (gap within each model), skip this coefficient and size on CI width for d_hat_p (section 7).
- For the D-study: error of the gap per model with n_i items and n_r runs is the formula above; n_r can only reduce the 2 s2_w/(n_i n_r) term, never the (s2_ic + s2_pic)/n_i term, so there is a floor set by n_i alone.
- Font size nested in image: the same derivation per font-size level; the font-size x item and font-size x model terms are additional fixed-facet interactions. With few levels keep font size fixed and analyze each (text vs size k) gap separately, adjusting for multiplicity.

### Gaps
- No peer-reviewed treatment of G theory for two-condition difference scores found. Derivation above has not been checked against a source or simulated.
- Brennan Ch. 4/9 section numbers for fixed-facet rules not verified.

---

## 4. Sampling variability of variance components with few levels; is 2 models x 20 items x 3 runs enough?

### Takeaway
No. With 2 models, s2_p has 1 df: its estimate has CV about 1.7, one in three estimates is negative, and the G estimate is anywhere from 0 to 0.94 (10th to 90th percentile). With 5 models, s2_p still has CV about 0.8 at 20 to 25 items. A small block can estimate item-side components (s2_i, s2_pi, s2_w) usefully, but not s2_p or G.

### Cited Findings
- [TEXTBOOK] Standard error of an ANOVA-type variance component estimate (Searle 1971; Searle, Casella & McCulloch 1992, Ch. 3; Brennan 2001, Sec. 6.1): under normality,
  Var(s2_hat_alpha) = (2 / m_alpha^2) * sum_beta [ EMS_beta^2 / (df_beta + 2) ]
  where the sum runs over the mean squares in the estimator and m_alpha is the divisor (e.g. n_i n_r for s2_p). In practice plug in observed MS (Brennan recommends MS^2/(df+2) as the plug-in). The normality assumption fails for binary data (next section).
- [WEB] Brennan (2001) treated sampling variability of variance components as central; bootstrap procedures give biased estimates of components and their SEs; Brennan, Harris & Hanson (1987) tested bootstrap schemes for p x i; Wiley (2000) derived bias corrections for p x i and p x i x h; Brennan (2007) extended the correction to any design and any bootstrap procedure; Tong & Brennan (2004, 2007) gave rules for choosing the bootstrap procedure and correction factors for two-facet designs: [Li 2023 PLOS ONE (PMC10348584)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10348584/) and search summary of CASMA reports ([CASMA RR 21](https://education.uiowa.edu/sites/education.uiowa.edu/files/2022-10/casma-research-report-21.pdf), could not fetch).
- [WEB] Li (2023): in simulated p x i data (100 persons x 20 items, 1000 replications), the "unified rules" are boot-p for s2_p, boot-pi for s2_i, boot-i for s2_pi (boot-p resamples persons, boot-i items, boot-pi both); accuracy judged by |relative percent bias| < 25. For dichotomous data, only the bootstrap with a divide-and-conquer strategy gave accurate SEs; traditional SE for s2_i overestimated by about 128.6%, MCMC by about 28.6%, jackknife underestimated SE(s2_i) and SE(s2_pi) by about 42.9% and 43.7%. All four methods estimate the components themselves accurately: [PMC10348584](https://pmc.ncbi.nlm.nih.gov/articles/PMC10348584/). Simulated sizes were 100 x 20 only; 30 x 5 and 30 x 20 are listed as future work, so there is no tested evidence at n_p of 2 to 5.
- [WEB] Tong & Brennan style rules found to give adequate SEs for normal and polytomous data, with some differences for dichotomous data (secondary summary of Tong & Brennan 2007): search result summarizing [CASMA reports](https://education.uiowa.edu/sites/education.uiowa.edu/files/2022-10/casma-research-report-21.pdf).
- [WEB] Bayesian route: Jiang & Skorupski (2018), Behavior Research Methods 50(6), 2193-2214, doi 10.3758/s13428-017-0986-3, estimates multivariate-G variance components with MCMC; De Maeyer's brms walkthrough exists at [sdemaeyer.quarto.pub](https://sdemaeyer.quarto.pub/posts/2021-04-Generalizability/Generalizability_brms.html). Neither was read, so claims about small-sample behavior and prior sensitivity are unverified. Li & Zhang (2009) found MCMC with non-informative priors inadequate, informative priors adequate (search snippet, [Acta Psychologica Sinica](https://journal.psych.ac.cn/acps/EN/Y2009/V41/I09/889)).

### Inferences: quantification [OURS]
Monte Carlo (Appendix, 4000 reps/cell). Truth: latent logistic model, sd_p 0.8, sd_i 1.2, sd_pi 0.8, intercept 0 (about 50% mean pass). Observed-scale components from a huge sample: s2_p 0.0166, s2_i 0.0435, s2_pi 0.0211, s2_w 0.1687; implied G at (20 items, 3 runs) = 0.81, at (25, 3) = 0.84. Estimation by ANOVA on p x i with replicates:

| n_p x n_i x n_r | CV of s2_p | P(s2_p<0) | CV of s2_pi | P(s2_pi<0) | CV of s2_i | G-hat 10th / 50th / 90th pct |
|---|---|---|---|---|---|---|
| 2 x 20 x 3 | 1.67 | 0.33 | 1.24 | 0.22 | 0.68 | 0.00 / 0.61 / 0.94 |
| 5 x 20 x 3 | 0.81 | 0.05 | 0.67 | 0.06 | 0.39 | 0.33 / 0.79 / 0.91 |
| 5 x 25 x 3 | 0.76 | 0.03 | 0.60 | 0.04 | 0.35 | 0.50 / 0.83 / 0.93 |
| 5 x 50 x 3 | 0.71 | 0.01 | 0.41 | 0.00 | 0.25 | 0.72 / 0.91 / 0.96 |
| 5 x 100 x 3 | 0.67 | 0.00 | 0.30 | 0.00 | 0.19 | 0.85 / 0.95 / 0.98 |

Reading: s2_p precision is bounded by n_p, not by items (CV only falls from 0.81 to 0.67 when items go from 20 to 100). Within-cell s2_w is estimated well everywhere (CV 0.06 to 0.17). Rule of thumb from these: to get CV of a component below 0.3 you need that component's own facet to have roughly 30+ levels (CV of a variance estimate is about sqrt(2/df)). Consequently the D-study's "n_i needed for G >= 0.80" is dominated by the uncertainty in s2_p and should be reported as an interval, not a point.
- Practical recommendation: use the D-study block to estimate s2_pi, s2_i, s2_w (which drive paired-comparison SEs) and to check s2_r, s2_pr, s2_ir about zero; do not use it to decide G >= 0.80.

### Gaps
- No simulation evidence found for boot-p/boot-i/boot-pi performance with n_p between 2 and 5. Bootstrapping 2 to 5 models is degenerate (boot-p on 2 models can draw the same model twice, giving zero between-model variance). Use boot-i (resample items, keep models) for items-side components; for s2_p report the F-based or Satterthwaite interval and flag it as unreliable.
- Satterthwaite and Burdick-Graybill/Ting intervals for G theory components: textbook methods (Brennan 2001 Sec. 6.2; Searle et al.), not verified.

---

## 5. Binary outcomes: is ANOVA-based G theory valid?

### Takeaway
ANOVA (EMS) estimators remain unbiased for the observed-scale 0/1 components (no normality needed for unbiasedness), and the simulation evidence says estimates are accurate for dichotomous data; what breaks is normal-theory SEs and CIs, and the interpretation near the floor and ceiling. Latent-scale GLMM components are an alternative with a fixed residual pi^2/3, but they are a different estimand.

### Cited Findings
- [WEB] Li (2023): all four methods (traditional, jackknife, bootstrap, MCMC) estimate variance components accurately for dichotomous p x i data; the SE/CI methods are what differ (numbers in section 4): [PMC10348584](https://pmc.ncbi.nlm.nih.gov/articles/PMC10348584/).
- [WEB] GLMM-based G theory: IRT models written with a latent continuous response give logistic mixed models whose parameters of interest are the variance components (Choi 2013, UC Berkeley dissertation, summarized in search result: [UBC/Berkeley listing](https://open.library.ubc.ca/handle/2429/27193) is the wrong dissertation; see [ECNU paper on GLMM to unify GT and IRT](https://jps.ecnu.edu.cn/EN/Y2021/V44/I2/449)). The ECNU paper reports GLMM difficulty estimates close to Rasch on LSAT (1000 x 5).
- [WEB] Latent-scale residual for logit link: pi^2/3 (about 3.29) (Nakagawa & Schielzeth 2013); a "corrected" 0.8768809 * pi^2/3 variant exists: [rr2 docs, R2_resid](https://search.r-project.org/CRAN/refmans/rr2/html/R2_resid.html); [arXiv 1805.01124](https://arxiv.org/pdf/1805.01124) uses var = pi^2/3 for binary on the linear-predictor scale.
- [TEXTBOOK] Latent-scale ICC / G-analogue for p x i with binomial-logit GLMM: with random effects p, i, pi and residual fixed at pi^2/3 (the logistic variance), G_latent(n_i) = s2_p / (s2_p + s2_pi/n_i + (pi^2/3)/(n_i n_r)). Note this uses the logistic variance as the within-cell error, which is only an approximation when n_r replicates are binary draws from a Bernoulli (the Bernoulli variance is not constant, see ceiling note).
- [WEB] Reported weakness: the 2013 and 2023 studies conclude the Tong-Brennan bootstrap rules gave "some differences" for dichotomous data; hence the divide-and-conquer bootstrap in Li 2023.

### Inferences
- [OURS] Observed-scale vs latent-scale: observed-scale s2_p depends on the base rate. Within-cell Bernoulli variance is p(1-p), so s2_w (and s2_pi) shrinks as pass rates approach 0 or 1, and the components differ by model. With rates near 0 or 1 for one model, pooled homogeneous-variance assumptions are violated (model-specific s2_w). Practical consequences: (1) a ceiling-limited model has tiny s2_w and tiny s2_pi, which inflates apparent G; (2) comparisons between conditions are compressed near the floor; (3) report components separately by condition (text, image) and consider per-model s2_w.
- [OURS] Use latent-scale components as a sensitivity check, not as the primary D-study, because the D-study target (pass-rate precision) lives on the observed scale. Where used, lme4::glmer(y ~ 1 + (1|model) + (1|item) + (1|model:item), family=binomial) with 5 models is not reliably estimable (singular fits for the model variance); fix or regularize with a weak prior (brms), or treat model as fixed and drop s2_p.

### Gaps
- No primary paper was found (Kane/Brennan) explicitly validating ANOVA G theory on dichotomous data beyond the simulation in Li 2023; Brennan 2001 discusses dichotomous data (KR-20 equals alpha equals G for p x i) from memory only. No source located for G theory with p x i x r logistic GLMM and replicates.
- The precise relation between observed-scale and latent-scale components (e.g. delta-method conversions) not sourced.

---

## 6. Software and unbalanced data

### Takeaway
For a balanced design (5 models x items x 3 runs), plain NumPy ANOVA code or lme4/statsmodels is enough and is easy to verify. The R gtheory package is no longer on CRAN. GeneralizIT requires balanced complete data and does not describe negative-variance handling. Unbalanced data (dropped attempts, timeouts, failed renders) need REML mixed models, not EMS.

### Cited Findings
- [WEB] R gtheory was removed from CRAN and archived on 2025-03-24 (maintainer email undeliverable): [CRAN page](https://cran.r-project.org/web/packages/gtheory/index.html). Archived versions are available from CRAN archive; a mirror manual exists at [r-universe](https://canoemoore.r-universe.dev/gtheory/doc/manual.html) (title "Apply Generalizability Theory with R"). Its documented approach is lme4 REML variance components (from memory of the package description; not re-verified).
- [WEB] GeneralizIT (Smith, Kline & Kline, Python, pip install generalizit): ANOVA/EMS-style estimation following Brennan (2001), crossed and nested designs; "The data must be balanced, fully crossed, and must not contain missing values"; negative-variance handling and alternative CIs not described; CI uses a z interval on the expected-score variance; design strings such as "person x rater x item"; D-study via calculate_d_study(levels={...}); JOSS review status pending at the time of the preprint: [arXiv 2411.17880v2](https://arxiv.org/html/2411.17880v2). Also notes the example D-study keys in the docs do not match the facet names in the example data, so check them.
- [WEB] lme4-based G theory (random-effect variance components, G and Phi computed from VarCorr; unbalanced allowed by REML): [Lai notes](https://marklhc.quarto.pub/psyc520-2025spring/r-notes/07-gt.html). The code there hard-codes row positions in VarCorr output; extract by name instead.
- [WEB] Other R packages seen: gtheoryr (fully crossed p x i and simple nested), gt4ireval (G theory for IR evaluation, relevant analogy since it applies G theory to topic x system comparisons): [gt4ireval manual](https://mirror.uned.ac.cr/cran/web/packages/gt4ireval/refman/gt4ireval.html); csemGT ([r-universe](https://rgempp.r-universe.dev/csemGT/csemGT.pdf)).
- [TEXTBOOK] GENOVA (balanced) and urGENOVA (unbalanced nested designs, Brennan) are Fortran programs from the University of Iowa CASMA; EduG (Cardinet, Johnson & Pini 2010) handles balanced designs with a fixed-facet menu and reports CIs; mGENOVA for multivariate. SPSS VARCOMP, SAS PROC VARCOMP/MIXED, statsmodels MixedLM (variance components via vc_formula, awkward for crossed random effects) are alternatives. pingouin has ICC but no G-theory D-study.

### Inferences
- [OURS] Recommended stack: write the balanced EMS estimator in about 30 lines of NumPy (as in the Appendix) for the primary analysis, cross-check once against lme4 (REML) in R or against GeneralizIT on a toy dataset. Use REML (lme4/glmmTMB) for the actual study if cells are missing. Unbalanced EMS variants (Henderson methods) exist but are not worth using.

### Gaps
- Did not verify urGENOVA/EduG current availability for 2026, or whether a pip-installable Python package other than GeneralizIT exists; GeneralizIT's accuracy has no independent validation that was found.

---

## 7. Power and sample-size alternatives to G >= 0.80 for a paired condition comparison

### Takeaway
Because the real question is a within-model gap, size by the half-width of a CI on the pass-rate difference using the paired item-clustered SE, not by G. It is mathematically the same sampling model as the D-study error terms, just a different decision criterion.

### Cited Findings
- [WEB] Miller (2024), "Adding Error Bars to Evals": questions in an eval are draws from a super-population of questions; SE of the mean over questions, cluster-robust SEs when questions share a passage, and variance reduction by pairing when two models are scored on the same questions (paired SE smaller than unpaired when per-question scores positively correlated); a clustered SE adjustment reached up to 3x in his example; resampling to reduce within-question variance is also discussed: [arXiv 2411.00640](https://arxiv.org/pdf/2411.00640). Equation numbers (4, 7, 8) per a secondary summary only; verify.
- [WEB] Follow-up library/papers: `errorbars` on PyPI implements paired differences, cluster-robust SEs (t with G-1 df) and McNemar exact test: [PyPI errorbars](https://pypi.org/project/errorbars/); [arXiv 2608.22659](https://arxiv.org/pdf/2608.22659) (K=2 repeated-measures equals paired t; clustered version adds within-cluster covariance); [arXiv 2607.04429, evalci](https://arxiv.org/pdf/2607.04429). Only search snippets were read.
- [WEB] Cluster-level inference caveat for paired designs: clustering at a wrong level inflates false positives, pair-level clustering is the safe choice (de Chaisemartin & Ramirez-Cuellar): [HAL record](https://hal-sciencespo.archives-ouvertes.fr/hal-03873897).

### Inferences [OURS]
- Per-model gap CI: d_hat +/- t_{n_i-1} * s(d_pi)/sqrt(n_i). Required items for half-width h: n_i = (t * s_d / h)^2, with s_d^2 = s_item^2 + 2 s_w^2 / n_r, where s_item^2 is the between-item variance of the true per-item gap (= s2_ic + s2_pic) and s_w^2 the within-cell Bernoulli variance. D-study block estimates: s_item^2 from the item-level gap variance minus the replicate part; s_w^2 = mean over items of p_i(1-p_i) * n_r/(n_r-1) per condition.
- Illustration with assumed (not measured) values s_item = 0.30, s_w^2 = 0.17 per condition: s_d^2 = 0.09 + 0.34/n_r. n_r = 1: s_d = 0.66; n_r = 3: s_d = 0.45; n_r = infinity: s_d = 0.30. Items needed with z = 1.96 for half-width 0.10: 168 (n_r=1), 78 (n_r=3), 35 (n_r=inf); for half-width 0.05: 672, 312, 138. These numbers are arithmetic from assumed inputs, to be replaced with estimates from the D-study block.
- Cheaper power for the aggregate test across models: pool the 5 models' paired differences with model as a block (cluster by item, and by model if models are treated as exchangeable); this gives about n_p times more information about the average gap but does not answer per-model gaps.
- McNemar uses only discordant item-pairs and ignores replicate structure; with n_r runs use the per-item run-averaged difference (or a paired t / sign test on item-level gaps) rather than treating each run as an independent pair.
- Relation to D-study: the paired SE squared equals the error variance of the contrast from section 3, so the same s2 components (from the D-study block) feed both; G >= 0.80 targets between-model discrimination and is the wrong criterion for the stated question.

### Gaps
- Did not read Miller's equations directly; power-analysis section of Miller not extracted.
- No literature found on power formulas for item-clustered paired designs with binary replicate attempts specifically for G-theory-style designs.

---

## 8. Optimal allocation of items vs runs under a cost model

### Takeaway
Marcoulides and Goldstein's Lagrange-multiplier approach minimizes error variance subject to a linear cost constraint. For the collapsed p x i design with replicates, the optimum has a closed form (derived below, ours): n_r* = sqrt( (s2_w / s2_pi) * (c_i / c_r) ), rounded and floored at 1.

### Cited Findings
- [WEB] Marcoulides (1993), J. Educational and Behavioral Statistics 18(2), 197-206: minimizing mean error variance in G studies under resource constraints: [IDEAS record](https://ideas.repec.org/a/sae/jedbes/v18y1993i2p197-206.html). Marcoulides (1997) "Optimizing measurement designs with budget constraints: the variable-cost case", Educational and Psychological Measurement 57(5), 808-812. Marcoulides & Goldstein (1990, 1991) are the primary sources for the Lagrange method; abstract-level only here ([PMC11486427](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11486427/) application paper using Lagrange multipliers for optimal sample size; Marcoulides, Psychometrika on maximizing G in multifacet D studies: [Cambridge listing](https://resolve.cambridge.org/core/journals/psychometrika/article/maximizing-the-coefficient-of-generalizability-in-multifacet-decision-studies/54B0E1B33A7AABE23DA702E8ED51651B)). The formulas were not read.
- [WEB] Jiang, Shi & Distefano (2021) find the lowest-cost design meeting a target generalizability coefficient: [PMC8451023](https://pmc.ncbi.nlm.nih.gov/articles/PMC8451023).

### Inferences (our derivation, [OURS])
Model: error variance (relative) E(n_i, n_r) = s2_pi/n_i + s2_w/(n_i n_r) (runs exchangeable, s2_pr = 0). Cost C = n_i (c_i + n_r c_r), where c_i = per-item cost incurred once per item (curation, rendering, unit-test checking, per-item overhead) and c_r = cost of one attempt (GPU/API plus automatic grading).
Fix budget C; n_i = C / (c_i + n_r c_r). Then E = (s2_pi + s2_w/n_r)(c_i + n_r c_r) / C. Minimize f(n_r) = (A + B/n_r)(c_i + n_r c_r) with A = s2_pi, B = s2_w:
f = A c_i + A c_r n_r + B c_i / n_r + B c_r; f'(n_r) = A c_r - B c_i / n_r^2 = 0, so
  n_r* = sqrt( s2_w c_i / (s2_pi c_r) ),  n_i* = C / (c_i + n_r* c_r).
Check against the G >= 0.80 target: choose the smallest budget with G >= 0.80, substituting n_i*, n_r*. With D-study-like values s2_w/s2_pi = 8 (section 4 truth): n_r* = sqrt(8 c_i/c_r): if one item costs as much as 2 attempts (c_i/c_r = 2), n_r* = 4; if items are essentially free relative to attempts (c_i/c_r = 0.1), n_r* = 0.9, so use 1 run and as many items as exist. For automatically graded unit-test benchmarks drawn from existing sets, c_i is small, which favors few runs and many items, limited by the finite item pool.
Notes: (a) if s2_pr is nonzero because seeds are shared, add s2_pr/n_r and the optimum shifts, but the exchangeable assumption is better; (b) integer constraint: evaluate floor and ceil; (c) finite pool correction: if the item pool N_i is finite and n_i near N_i, multiply the item-dependent terms by (1 - n_i/N_i) (Brennan treats finite universes as fixed-facet limit); (d) asymmetric condition costs (image rendering) just give separate c_i per condition.

### Gaps
- Marcoulides-Goldstein equations themselves not verified; our closed form should coincide with their Lagrange solution for this two-term case, but a worked example in their papers was not checked.

---

## Appendix: code used for section 4 (Monte Carlo)

Python/NumPy, ANOVA on p x i with R replicates:
MS_p = SS_p/(P-1); MS_i = SS_i/(I-1); MS_pi = SS_pi/((P-1)(I-1)); MS_w = SS_w/(P I (R-1)).
s2_w = MS_w; s2_pi = (MS_pi - MS_w)/R; s2_p = (MS_p - MS_pi)/(I R); s2_i = (MS_i - MS_pi)/(P R).
Data: logit(P(Y=1)) = a_p + b_i + c_pi, a ~ N(0, 0.8^2), b ~ N(0, 1.2^2), c ~ N(0, 0.8^2); 4000 replications per design; seeds fixed (default_rng(1)). Truth taken as the mean of three large-sample (400 x 400 x 3) ANOVA estimates. Models were treated as random draws (the p component's CV would be different for a fixed set of 5 models, but the df argument is the same). G-hat computed after replacing negative components by zero.

Items to settle with the caller before relying on this: (1) whether the 5 models are a sample or the population of interest; (2) whether seeds are shared across models (changes whether runs are crossed or nested); (3) per-item grading cost vs attempt cost (c_i/c_r) for section 8.
