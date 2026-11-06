# Reading notes: G-theory and run sizing (UFM-17)

Covers: what the course book says about the pilot G-study and D-study used to size the main run: method-of-moments estimators (5.5), the G formula and D-study sweep (5.6), identifiability and replicated trials (5.7), design principles and torch_measure (5.13, 2.8), few models and run facets, informative items, and how the book's framing fits our plan. Source: Truong and Koyejo (2026), "AI Measurement Science". The book PDF is not in the repo. Page numbers are PDF pages; the running header can differ by a small offset, so cite as "PDF p. N".

Quotes are verbatim. "Book says" and "Inference" are kept apart. These notes come from reading only; no formula below was checked by running code.

## 1. Section 5.5: the method-of-moments estimators (crossed model x item, with and without replicated trials)

### Takeaway
The book gives an explicit MoM estimator only for ONE trial per cell (a crossed persons x items design), where interaction and residual stay fused as MS_pi. For replicated trials it gives only the argument (it needs a two-facet G-study) and a plug-in functional-ANOVA simulation, not expected-mean-square equations. The estimator for "model, item, model x item, residual, 3 runs per cell" is therefore NOT written out in the book and has to be derived from standard nested ANOVA (see Inferences).

### Cited Findings
- Binary scores: Y ~ Bernoulli(P_IJ). The decomposition is done on the probability scale, as functional ANOVA (Hoeffding-Sobol). "The orthogonal decomposition that follows needs only that persons and items are sampled independently, not that they are Gaussian." (PDF pp. 126-127) [Book]
- (5.7) P-bar = E_{I,J}[P_IJ], P_i. = E_J[P_iJ], P_.j = E_I[P_Ij]. (5.8) P_ij = P-bar + (P_i. - P-bar) + (P_.j - P-bar) + (P_ij - P_i. - P_.j + P-bar). (5.9) Var(P_IJ) = Var_I(P_I.) + Var_J(P_.J) + E[(P_IJ - P_I. - P_.J + P-bar)^2] = V_person + V_item + V_interaction. (p. 127) [Book]
- (5.10) Var(Y) = Var(E[Y|I,J]) + E[Var(Y|I,J)]; since Var(Y|I,J) = P_IJ(1-P_IJ): (5.11) V_residual = E[P_IJ(1-P_IJ)]. (5.12) Var(Y) = V_person + V_item + V_interaction + V_residual. (5.13) rho = V_person / (V_person + V_item + V_interaction + V_residual), called observed-scale reliability. (pp. 127-128) [Book]
- Residual is "the irreducible measurement noise of a single graded trial, largest near P_ij = 0.5, vanishing as items become trivially easy or impossibly hard." (p. 128) [Book]
- Callout "WHY REPLICATED TRIALS ARE NEEDED": "With a single graded response per cell, the estimated cell probability P_ij-hat is just 0 or 1, and the interaction V_interaction is perfectly confounded with the Bernoulli residual V_residual ... Separating them requires replication: multiple trials per person-item cell, so P_ij-hat is a within-cell average ... it is exactly the move from a one-facet to a two-facet G-study." (p. 128) [Book]
- The only explicit MoM block (p. 129), crossed np persons x ni items, one trial per cell:
  - (5.14) Y-bar_i. = (1/ni) sum_j Y_ij; Y-bar_.j = (1/np) sum_i Y_ij; Y-bar_.. = (1/(np ni)) sum_ij Y_ij
  - (5.15) MS_p = ni/(np-1) sum_i (Y-bar_i. - Y-bar_..)^2; MS_i = np/(ni-1) sum_j (Y-bar_.j - Y-bar_..)^2; MS_pi = sum_ij (Y_ij - Y-bar_i. - Y-bar_.j + Y-bar_..)^2 / ((np-1)(ni-1))
  - (5.16) E[MS_p] = (V_int + V_res) + ni V_person; E[MS_i] = (V_int + V_res) + np V_item; E[MS_pi] = V_int + V_res
  - Solutions: V_person-hat = (MS_p - MS_pi)/ni; V_item-hat = (MS_i - MS_pi)/np. "MS_pi estimates the interaction and residual together, fused until trials are replicated." Described as "cheapest of the three but also the bluntest." [Book]
- Code (pp. 129-131): simulation N, M = 60, 40, gamma_scale = 0.6, theta ~ N(0,1), beta ~ N(0,1.5), P = sigmoid(theta - beta + gamma). `anova_components(Pmat)` returns the means of squared row, column and interaction deviations. `V_resid = (P*(1-P)).mean()`. `estimate_interaction(T, seed)`: `Phat = (rng.rand(T,N,M) < P[None]).mean(0)`, then the interaction of Phat; T in [1,2,3,5,8,12,20,40]. Figure: the estimate overshoots at T=1 and converges by T=40. [Book]
- Section 5.2 (p. 119) latent-scale model: (5.1) logit P(Y_ij=1) = theta_i - beta_j + gamma_ij; (5.2) theta_i ~ N(0, sigma_p^2), beta_j ~ N(0, sigma_i^2), gamma_ij ~ N(0, sigma_pi^2); (5.4) rho_eta = sigma_p^2/(sigma_p^2+sigma_i^2+sigma_pi^2), "idealized reliability" on the log-odds scale. (5.5, p. 120) Var(eta) = sigma_p^2 + sigma_i^2 + sigma_r^2 + sigma_pi^2 + sigma_pr^2 + sigma_ir^2 + sigma_pir^2. [Book]
- Section 5.3 (p. 120): Rasch abilities fitted as fixed effects have empirical variance sigma_p^2 + SE^2, so raw spread is biased upward. [Book]
- Method-of-moments source and software: Henderson (1953) for expected mean squares; REML for unbalanced designs; "The connection between G-theory and mixed-effects models makes modern software (e.g., lme4 in R) directly applicable to G-studies." Also Searle et al. (1992), Brennan (2001), Shavelson and Webb. (p. 168; refs p. 328, 335) [Book]
- Exercise 11 (p. 170): "Implement a G-study for a model x item x rater design: given a 3-way array X[p, i, r], estimate all variance components by expected mean squares, and verify on simulated data that the estimates recover the truth." This is the book's own pointer to the same job as UFM-17, with no solution given. [Book]
- No explicit sigmoid or logit-scale correction formula for the observed-scale components is given. The book only states that the two scales exist (5.4 on logit, 5.13 on observed) and that "the empirical cell proportions P_ij-hat give the same components through the functional ANOVA of Equation 5.9" (p. 129). [Book]

### Inferences
- The `estimate_interaction` code takes the interaction mean square of Phat with no subtraction of V_res/T. By the book's own algebra (within-cell Bernoulli variance P(1-P)/T enters Phat) this should bias the interaction UP by roughly E[P(1-P)]/T, which matches the plotted overshoot at small T. Treat it as a plug-in, not a corrected MoM. Unverified: not run.
- For UFM-17, with persons = models (p), items (i), runs (r) nested within each (p,i) cell, the standard crossed-p x i with n_r replicates ANOVA applies: E[MS_within] = V_res; E[MS_pi] = V_res + n_r V_pi; E[MS_p] = V_res + n_r V_pi + n_i n_r V_p; E[MS_i] = V_res + n_r V_pi + n_p n_r V_i. These follow from standard ANOVA (Henderson/Searle style), not from the book's text. Cite Searle et al. (1992) or Brennan (2001) for them, not the book.
- Because outcomes are binary, V_residual depends on the mean pass rate (5.11). Estimates are for the pilot's item mix and pass rates, so a D-study that reuses them for a different item set or font size assumes similar P distribution.
- Negative MoM estimates are possible with few levels; the book does not mention truncation to zero. Not covered.

### Gaps
- No replicated-trial expected-mean-square equations, no variance-of-the-estimator formulas, no confidence intervals for components (the book points to Bayesian posteriors in 5.4 instead).
- The Bernoulli residual P(1-P) formula in 5.5 assumes binary Y, which matches our outcome (binary pass, all target tests pass). A fraction-of-tests outcome would need a different residual and is not used.

## 2. Section 5.6: the G formula, the D-study sweep, cost-constrained optimization

### Takeaway
The book's G is the relative-error generalizability coefficient for ranking persons (models) over items and raters, with an explicit D-study grid and a cost-constrained search. It has no run or occasion facet in the formula and does not define an absolute-error coefficient (Phi).

### Cited Findings
- G-study estimates components; D-study "plugs the estimated components into this coefficient for a planned design and asks how many items and raters it takes to reach, say, G >= 0.90." (p. 132, Cronbach et al. 1972) [Book]
- Formula (p. 132): G = sigma_p^2 / (sigma_p^2 + sigma_rel^2), with sigma_rel^2 = sigma_pi^2/n_i + sigma_pr^2/n_r + sigma_pir,e^2/(n_i * n_r). Item main effect sigma_i^2, rater main effect sigma_r^2 and sigma_ir^2 are NOT in the error term. [Book]
- Worked example components (p. 132): true_var = {'p':1.0,'i':0.5,'r':0.3,'pi':0.4,'pr':0.3,'ir':0.1,'e':0.2}. [Book]
- Code (p. 133): `G_coeff(ni, nr): rel = true_var['pi']/ni + true_var['pr']/nr + true_var['e']/(ni*nr); return true_var['p']/(true_var['p']+rel)`; grid `n_items = np.arange(5, 51, 5)`, `n_raters = np.arange(1, 11)`, contours at G = 0.80 and 0.90. [Book]
- Cost version (pp. 133-134): cost_item = 1.0, cost_rater = 5.0, budgets = np.arange(50, 501, 10). For each budget B loop ni in range(5, int(B/cost_item)+1), nr = max(1, int((B - ni*cost_item)/(ni*cost_rater))), constraint ni*cost_item + ni*nr*cost_rater <= B, maximize G, report the smallest budget reaching G >= 0.90. Prose: "the D-study becomes a constrained optimization." [Book]
- Exercises (p. 170): 9 "derive the generalizability coefficient G [in a p x i x r design], and show that increasing n_r reduces the contribution of rater variance but not item variance, and vice versa"; 13 "D-study optimizer: Given variance components and costs per item (c_i) and per rater-item pair (c_r), find the cheapest design (n_i, n_r) achieving G >= G*. Solve it as a constrained optimization and visualize the cost surface." Exercise 14 applies G to Chatbot Arena comparisons. [Book]
- Absolute error / Phi / dependability: a text search found no definition. Phi occurs only as a link function in chapter 3; "dependability" occurs only in the Cronbach et al. 1972 title. [Book, negative result]
- Spearman-Brown (5.10, p. 147-148): rho_K = K*rho/(1+(K-1)rho); example "a 50-item benchmark at rho = 0.80 reaches 0.89 at 100 items and 0.94 at 200"; SEM = sigma_X * sqrt(1 - rho_XX') (p. 149). Test-retest is described as "re-running at temperature > 0". [Book]

### Inferences
- The book's example facet is rater, with cost asymmetry (raters expensive). In UFM-17 the second facet is runs (resamples at temperature 0.7), whose cost is not low relative to items: grading CoderUJB is about 300 CPU-s per answer, so cost per run is per (item, run), and the cost function should be per item-run unless inference cost per item and grading cost per answer are separated. Exercise 13's cost structure (per-item plus per rater-item pair) maps to: fixed cost per item (writing, rendering) plus per-run cost (generation plus grading). Mapping is ours.
- Mapping the formula: sigma_pr^2 and sigma_ir^2-type terms vanish when the second facet is runs nested in (p,i) cells, giving sigma_rel^2 = sigma_pi^2/n_i + sigma_res^2/(n_i n_r). Then runs only shrink the residual term, and sigma_pi^2/n_i is a floor that more runs cannot remove. This is what the sweep should show. It follows from the book's formula by deleting the rater terms; the book does not show this case.
- G >= 0.80 in the book's sense says how reliably a fixed set of n_i items ranks models (relative decisions). It says nothing about the precision of a text-vs-image contrast (see section 7).

### Gaps
- No absolute-error coefficient Phi, no D-study for a fixed (non-random) facet, no standard errors on G.
- Book defines no occasion/run facet formula.

## 3. Section 5.7: identifiability, replicated trials, which facets to control

### Takeaway
The book says the design decides which interaction terms are estimable: with one trial per cell sigma_pi^2 is confounded with the Bernoulli residual, and with little replication the simpler model gives a more dependable conclusion. This supports the argument for replicated runs.

### Cited Findings
- "with one trial per cell, the person-by-item interaction sigma_pi^2 is perfectly confounded with the Bernoulli residual (Section 5.5) ... So model selection and design are coupled: the design decides which models are even askable. To test for an interaction, the D-study must budget replicated trials per cell; otherwise the question is unanswerable and the honest move is to fuse interaction and residual into one term." (p. 134) [Book]
- "every added term costs identifiability and estimation variance." Two kinds of interaction: an iid effect gamma_ij ~ N(0, sigma_pi^2), testable only by holding out replicated trials of seen cells; a structured effect (2PL, extra dimensions), tested with Section 7.5.1 masking schemes. (pp. 134-135) [Book]
- Use marginal predictive likelihood, WAIC or PSIS-LOO; the likelihood-ratio test of sigma_pi^2 = 0 is a boundary test with a 1/2 chi2_0 + 1/2 chi2_1 mixture. A held-out simulation (N = M = 50) shows the main-effects model beats the saturated one at low replication even when a real interaction exists, until about T = 32. (p. 135) [Book]
- "Select the model against the decision, not against fit in the abstract." Adding sigma_pi^2 lowers bias in the reliability estimate but raises its variance; "in the small-data regime the simpler model can yield a more dependable conclusion even while slightly biased." (p. 136) [Book]
- Sampling stochasticity (p. 115): "At temperature > 0 the same model gives different outputs to the same prompt on each run - the closest analogue to classical test-retest error. For binary items this is usually minimal (most models answer deterministically), but open-ended generations (summaries, code, essays) can earn different scores across runs. Replicated trials make it possible to measure this run-to-run noise and average it down." [Book]
- Chapter 3 (p. 71): "A stateless model queried at sampling temperature > 0 can be given the same item T times with genuinely independent responses ... and T can be made large." That is why p_ij is observable for AI, unlike for humans. [Book]

### Inferences
- The "T about 32 to overtake" finding is for N = M = 50 and a specific interaction size. It does not transfer as a number to our design (5 models, 3 runs). Suggests that with 3 runs the D-study will mostly not resolve model x item from noise by model comparison, even though the point estimate of V_interaction becomes separable from V_res in the MoM sense. Our reading.
- The statement "model x item can't be separated from noise with 1 run per cell (5.5, 5.7)" is accurate. With 3 runs it is separable in principle but imprecise: MS_pi has (n_p - 1)(n_i - 1) df, which is 4 x 199 = 796 for 5 models and the 200-item DevEval block, but the few model levels still limit the other components.

### Gaps
- No guidance on the minimum T for a stable interaction estimate with n_p = 2 to 5.

## 4. Section 5.13 design principles, torch_measure (2.8), and related checks

### Takeaway
Citations to 5.6, 5.7 and 5.13 principle 1 are accurate. 2.8 documents only dataset loading and `models.Rasch`, but "only ships" is a reading of the book, not a book statement. Principle 5 (temperature 0) contradicts the project's temperature 0.7.

### Cited Findings
- Principle 1 verbatim (p. 167): "Identify the dominant source of variability (Section 5.6). Run a G-study before committing to a design. If rater variability dominates, invest in more raters or clearer rubrics; if item-sampling variability dominates, use more items or D-optimal selection." [Book]
- Principle 2: "Match items to the ability range of interest (Section 5.3) ... ranking frontier models needs items hard enough to discriminate among them." Principle 4: "Report confidence intervals, not just point estimates (Section 5.10)." Principle 5: "Control what can be controlled (Section 5.1). Score at temperature 0, randomize and average over prompt formats, standardize rubrics - these eliminate sources of variability rather than averaging over them." Principle 6: separate reliability from validity. Principle 7: audit items (Section 3.3). (pp. 167-168) [Book]
- p. 146 also advises scoring at temperature 0 to remove sampling stochasticity. Exercise 1 (p. 169) is "Determinism and reliability". [Book]
- Section 2.8 (pp. 56-58): "The torch_measure library provides a PyTorch-native toolkit for loading, inspecting, and analyzing response matrices from real benchmarks. It is the companion software for this book." API shown: `from torch_measure.datasets import load, list_datasets`; `list_datasets("bench")`; `load("bench/swebench")`; attributes `rm.shape, rm.density, rm.subject_means, rm.item_means, rm.observed_mask, rm.n_subjects, rm.n_items, rm.data`; `from torch_measure.models import Rasch`; `Rasch(n_subjects=..., n_items=...)`; `.fit(rm.data, method="mle")`; `.ability`; `.difficulty`; `.predict()`; `list_datasets("intervention")`. Other mentions: pp. 25, 30, 38, 41, 44, 49, 58-59. [Book]
- 2.8.2 prints "Items solved by no model" via `rm.item_means == 0`, the book's own check for zero-variance (all-fail) items. [Book]
- Chapter 6 (p. 182): "For deterministic evaluation (temperature = 0), CAT applies directly. For stochastic evaluation, we may need multiple samples per item, or methods that account for response variability." Cold start: "we must first collect data on a pilot sample of models before CAT can be deployed." Stopping rules include cost and time. [Book]
- Chapter 5.12 pilot (pp. 163-166) is an item-screening pilot: point-biserial discrimination cutoff 0.2, difficulty limits 0.05 and 0.95 proportion correct (cutoffs taken from earlier reading notes, not re-checked against the code). [Book]
- The book has no G-theory API in torch_measure. [Book, negative result]

### Inferences
- The claim "torch_measure only ships datasets and a Rasch model (book 2.8)" is a fair reading of what 2.8 shows but is overstated as a claim about the library; the book only documents those two parts. Safe wording: "the book documents only dataset loading and a Rasch model, so no G-theory helper is available from it."
- Principle 5 and the project's temperature 0.7 are in tension. The project needs T > 0 to have runs at all, so the G-study measures what principle 5 would remove. Worth stating explicitly in the write-up. Seeds 0..2 at T=0.7 are the "occasions".

### Gaps
- The book's treatment of the library beyond 2.8 was not read in full; the library may contain more than the book shows.

## 5. Few models, instability of components, run and seed facet

### Takeaway
The book gives no numerical guidance on how many persons (models) are needed to estimate person variance. It does warn that few levels and few replicates make estimates unstable and recommends simpler models. Treating model as a fixed facet is not contradicted by the book, but the book does not state it either.

### Cited Findings
- Section 5.4 (pp. 122-126): the empirical-Bayes vs full-Bayes posterior for sigma_p is "wide here, because one binary response per cell is weak evidence" (the book's simulation uses 150 models, 40 items, one trial per cell). [Book; partly read, pp. 120-125 not fully read]
- Section 5.1 toy (pp. 116-118): N = 20 models, M = 50 items; rankings flicker between runs and 95% CIs overlap for models of similar ability. [Book]
- Section 5.3 (p. 120): fixed-effect plug-in inflates the spread by SE^2. [Book]
- Section 5.7: small-data regime favors the simpler model (p. 136, quoted in section 3). [Book]
- Earlier reading notes on chapter 5 record that "The book does not say 'fix a facet when it has few [levels]'" and that "Section 5.2 assumes a fully crossed design with all facets random ... It does not discuss nested or fixed facets." A full-text search for fixed/random facet and nested confirms it: hits are only about plates and benchmark-level hierarchical Rasch (pp. 100-101), not G-theory facets. [Book, negative result]
- Chapter 6 p. 182 notes pilot calibration is needed before adaptive selection. [Book]

### Inferences
- With 5 models, sigma_p^2 has 4 degrees of freedom: very imprecise. (With 2 models it would have 1 df, a single squared difference of two model means.) So G for ranking models cannot be pinned down well, and the model variance will mostly reflect which models were picked. This is standard ANOVA reasoning, not a book quote.
- Under that constraint the useful D-study outputs are sigma_pi^2, sigma_i^2 and the residual, which carry the item and run sizing information. This suggests per-model slices.
- A rough guide for the number of runs: the residual term is sigma_res^2/(n_i n_r), so runs only help while sigma_res^2/n_r is comparable to sigma_pi^2. Our inference from the formula.

### Gaps
- No book numbers on minimum persons, no guidance on negative variance estimates, no mention of confidence intervals on variance components for a G-study.

## 6. Items, informativeness, zero-variance items, budget (ch 3, 6, 9)

### Takeaway
Items at floor or ceiling carry no information: the book says the Bernoulli residual vanishes there and conditional reliability collapses. Item selection should target about P = 0.5. The book discusses budget only qualitatively.

### Cited Findings
- (5.11) residual P(1-P) vanishes for trivially easy or impossible items (p. 128). [Book]
- Conditional reliability: "when P_j(theta) -> 1 for all items, I(theta) -> 0 and rho(theta) collapses for frontier models" (section 5.3, targeted item difficulty from Chapter 6). [Book]
- Chapter 6 information: Bernoulli information P(1-P) is largest at P = 0.5 (Eq. 6.1); D-optimal selection spreads difficulties across the target range (pp. 182-185); discussion question 4 (p. 186) asks for a fixed API budget strategy and is left open. [Book]
- Chapter 5.12 item screening (pp. 163-166): drop items with discrimination below 0.2 or pass rate outside 0.05 to 0.95 (see section 4). [Book]
- 2.8.2: `rm.item_means == 0` lists items no model solves (p. 57). [Book]
- Chapter 5 intro (pp. 115-116): a 200-item coding benchmark is one draw from the space of all coding problems; longer tests are more reliable via Spearman-Brown. [Book]
- Chapters 9 and 11: a paired design with every item under every condition removes item difficulty from the contrast; DIF framing for condition as group; subset selection from large suites (pp. 269+). [Book]

### Inferences
- A pilot block where many items are all-pass or all-fail in both conditions contributes mostly to sigma_i^2 and little else; sizing results will understate or overstate depending on that mix. Check the share of all-pass and all-fail items in the pilot before reading the components. This follows the book's P(1-P) point; the book does not make this pilot-specific claim.
- The book does not say how to choose the pilot items. If the block is chosen by a cheap text-condition pre-screen (consistent with 6.2.5 and 5.12), it biases the pilot toward informative items and would inflate the estimated model x item variance relative to the full pool. Flag when reporting.
- DevEval (about 12 CPU-s per answer) is much cheaper to grade than CoderUJB (about 300 CPU-s). The book's cost optimization works with any per-unit costs, so the D-study should be run with benchmark-specific costs; mapping is ours.

### Gaps
- Chapters 7 and 9 were only searched, not read in full, for pilot sizing. No sample-size rule for item counts was found beyond Spearman-Brown.

## 7. Fit between the UFM-17 plan and the book

### Takeaway
The plan's citations are accurate, but a G target (G >= 0.80) for a text-vs-image comparison mixes two estimands. The book's G is about ranking persons; the project's primary question is a condition effect. There are also mismatches on temperature and on what 2.8 says.

### Cited Findings (citation check)
- "Run a G-study before committing to a design" = 5.13 principle 1, p. 167: accurate, verbatim above. [Book]
- "formula in 5.6": accurate, p. 132. [Book]
- "method of moments (5.5)": accurate for the single-trial case (pp. 129-130), but 5.5 does not give the replicated-trial MoM. [Book]
- "With only 1 run per cell, model x item can't be separated from noise (5.5, 5.7)": accurate (p. 128 callout; p. 134). [Book]
- "torch_measure only ships datasets and a Rasch model (book 2.8)": see section 4, partly inference. [Book]
- "G >= 0.80" is the plan's own target; the book's examples use 0.80 and 0.90 contours (p. 133) and say "say, G >= 0.90" (p. 132). Not a book rule. [Book]
- Final Project Guidelines (course document, not in the repo): lists "Applying Generalizability Theory or random-effects models to evaluation pipelines", "Estimating uncertainty in model rankings" and "Diagnosing sources of measurement error across benchmarks" as example topics, and asks the plan to include "Evaluation metrics you plan to use (e.g., predictive accuracy, calibration, ranking stability, reliability estimates, uncertainty quantification, etc.)". It also demands a pre-analysis plan with "everything except experiments", reproducible code and data, and says to "cite relevant lectures/chapters". It sets no specific requirement on a G-study or on G thresholds.

### Inferences (mismatches to flag)
1. Estimand mismatch. 5.6's G ranks persons (models) with relative error from pi and residual only. UFM-17 wants precision for the condition effect (text vs image, and font size). The error for a condition contrast of a model's mean involves item x condition and run noise, not the book's sigma_rel^2 as written. The book has no formula for a contrast. If the target is "text vs image difference", the D-study needs its own error variance (our derivation, e.g. Var(diff) = 2 (sigma_ic^2/n_i + sigma_res^2/(n_i n_r)) for a paired design with items crossed with conditions). If the target is "do conditions rank models consistently", the book's G applies per condition.
2. Few models. G requires sigma_p^2, which has only 4 df with 5 models. A G >= 0.80 target "in both conditions" is therefore driven by an almost unestimable quantity. Better to size on sigma_pi^2, sigma_i^2, residual and report G as a function of an assumed sigma_p^2, or fix model.
3. Temperature. Principle 5 (p. 167) and p. 146 prefer T = 0; the project uses 0.7 with seeds, so runs are a real facet here. Fine, but state it.
4. Second facet. The book's D-study facets are items and raters; runs are an occasion facet (p. 120) not given a formula. Our formula mapping is in section 2.
5. Fixed vs random. The book treats persons and items as random (p. 126) and never covers fixed facets. Condition and font size as fixed facets are therefore outside the book. Font size is also nested in the image conditions (text has no font size), which breaks full crossing; the book does not cover nesting for G-studies.
6. Binary outcome. The 5.11 residual P(1-P) is the binary case, which matches our binary pass outcome. A fraction-of-tests outcome would have a different residual that the book does not cover; it is not used.
7. Absolute error. Phi is not in the book, so any "dependability" claim has to cite Brennan (2001) instead.

### Gaps
- No formula above was verified with code, and torch_measure was not run.
