# Reading notes: DIF, reliability, factor models and MTMM

Covers: differential item functioning (5.11), multitrait-multimethod matrices (5.11.5), reliability coefficients (5.8, 5.10), Bayesian intervals for few-level facets (5.4), design principles (5.13) and factor models (chapter 7), and which of these the Code as Image design can use with 5 models. Source: Truong and Koyejo (2026), "AI Measurement Science". Printed page = PDF page (checked against running headers).

Tags: [book p. N] = stated or shown on that page. [ours] = our inference, not in the book.

## 0. Bottom line

- The book has no method for "same or separate ability" with 5 models. Every method in 5.8, 5.10, 5.11, 7.x takes models as the sampled persons and assumes tens to hundreds of them. [ours]
- Condition-DIF, MTMM across conditions, and a text/image two-factor model would all be reinterpretations of the book. The book does not cover them, and they are not used in this project. [ours]
- What survives with 5 models: the per-model paired gap with a project-clustered interval, run-level test-retest, full-Bayes intervals on variance components. [ours]

## 1. DIF with condition as the group (5.11)

- The framing: the item x group interaction "becomes a bias to detect rather than a variance to average down". [book p. 150]
- Eq. 5.24 conditions on theta_j (model ability). Groups are "model families, architectural types, or training paradigms", so groups partition models. [book p. 150]
- Mantel-Haenszel: stratify models by total score, build a 2x2 (group x correct) table per stratum, pool odds ratios (Eq. 5.25). [book pp. 150-151]
- Logistic-regression form (uniform and non-uniform DIF): Eq. 5.26. [book p. 151]
- Demo: 200 models (100 per group), 30 items, 5 quintile strata, 0.8 logit DIF injected on 5 items. [book pp. 151-154]
- Flag rule: |log OR| > log 1.5 = 0.41. [book p. 153 plot, p. 154 printout]
- The demo code reports no significance test and states no minimum N. [book pp. 151-154]
- No purification, anchor items, or iterative matching score anywhere in the DIF material (searched the full text, no hit). [ours, negative finding]
- The book never treats the same respondents appearing in both groups. Nearest material is paired response matrices (2.5), where respondents are humans and the treatment is a many-facet Rasch facet tau_t with a theta x tau interaction. [book pp. 44-47]

Application to our design.
- Condition-DIF is not in the book. It would be our reinterpretation: item x condition interaction. [ours]
- What MH needs: independent groups, and enough models per total-score stratum. [book pp. 150-151] for the procedure; the sample-size requirement is [ours].
- With 5 models there are at most 5 distinct total scores per condition, so strata are empty or singletons. MH is not usable. [ours]
- Same models in both conditions violates the independent-group setup. [ours]
- What we use instead: the per-model paired gap (image minus text pass, averaged over items and runs) with a project-clustered interval. The 0.41 log-OR cut is a book convention, not a tested threshold, and we do not adopt it. [ours]

## 2. MTMM (5.11.5)

- Traits = constructs, methods = benchmark formats. Four blocks: reliability diagonal, monotrait-heteromethod (convergent), heterotrait-monomethod, heterotrait-heteromethod. Four Campbell-Fiske criteria. [book p. 159]
- Demo: 200 models, 3 traits x 2 methods, 6 score columns correlated across models. [book pp. 158-162]
- Caveat: single-format benchmarks cannot assess discriminant validity. [book p. 162]
- Convergent/discriminant validity first introduced with GSM8K vs MATH. [book pp. 18-19]
- No disattenuated correlation (correction for attenuation) anywhere in the book. [ours, negative finding]

Application to our design.
- Exact table in the book: the 6x6 correlation matrix of trait-method scores with the four blocks marked. [book p. 159]
- Our design has one trait (coding) and several methods (text, image at 10, 12 and 14 px). Only the convergent block exists; no discriminant block can be formed. [ours, consistent with book p. 162]
- Across models, n = 5, so r is nearly uninformative (a 95% interval for r at n = 5 spans most of [-1, 1]). [ours]
- MTMM is therefore not a planned analysis. The convergent idea (text and image scores of the same items should agree) is cited as validity evidence in book_validity_and_causality.md.

## 3. Reliability coefficients (5.8, 5.10)

- Omega (Eq. 5.17-5.18) with models as rows; simulation N = 600 models, M = 8 items. [book pp. 136-138]
- Alpha understates reliability when loadings are heterogeneous. [book pp. 136-138]
- omega_h is only mentioned (Revelle and Zinbarg 2009 in the bibliography); the pointer to 5.10 for it is not delivered. [book p. 168 bibliography]
- 5.10: Spearman-Brown (Eq. 5.22), test-retest by rerunning at temperature > 0, split-half, alpha (Eq. 5.23), alpha warning box, SEM = sigma_X sqrt(1 - rho) with worked example. Simulation 100 models x 100 items. [book pp. 147-150]

Application to our design.
- Omega, alpha, SEM treat models as the sampled persons. With 5 models, sigma_X and rho per condition are not meaningful. [ours]
- The book never uses items as persons. A swap (items as persons, models x runs as the "items") is possible in principle but is not in the book. [ours]
- Test-retest by rerun is the usable analogue: 3 runs per cell give item-level run reliability directly. [book p. 148 for the method; applying it per item is ours]

## 4. Bayesian intervals for few-level facets (5.4)

- Empirical Bayes vs full Bayes; the demo uses N = 150, M = 40, T = 1, flat hyperprior. [book pp. 124-126]
- Quote: "full Bayes keeps the spread, which is the honest uncertainty about sigma_p^2 from a finite sample". [book p. 125]
- With one binary response per cell the interval is wide. MCMC via NumPyro or PyMC for multi-facet models. [book pp. 125-126]
- No half-Cauchy/half-normal advice, no guidance for 3 to 5 levels. [ours, negative finding]

Application to our design.
- Book recommendation: full Bayes with credible intervals; accept the width. [book p. 125]
- For 5 models (4 df) a flat prior on sigma_p^2 would give a very wide, prior-dominated interval. A weakly informative prior with a sensitivity check is [ours], not in the book.

## 5. Design principles (5.13)

- Seven principles. Relevant: 4 (report CIs, not just point estimates), 6 (reliability is not validity), 7 (audit items, e.g. negative item-total correlations). [book pp. 167-168]
- Principle 7 maps to our calibration finding (items passed by no model or all models): such items carry no information about p or condition contrasts. [ours]

## 6. Chapter 7 (factor models, discovery)

- 7.1 Parallel analysis (Horn) on the item correlation matrix, models as observations; demo 300 models, 20 items. [book pp. 189-192]
- 7.2 Logistic factor model P(Y_ij = 1) = sigma(U_i^T V_j + Z_j), K = 2, fit by cross-entropy and L-BFGS. [book pp. 192-194]
- 7.3 Structure matrix S_jk. [book pp. 194-195]
- 7.4 GMM + BIC on structure vectors; cluster means per model correlated across models to assess construct overlap. [book pp. 195-196]
- 7.5 Masking and holdout schemes (row/column); AUC 92-97% on random masking. [book pp. 196-200]
- 7.6 GGM and Ising networks; networks and factor models can look alike. [book pp. 200-203]
- Correlated-factors and bifactor models can imply the same covariance (Fig 1.2). [book pp. 16-17]
- Rotational indeterminacy and choice of K are listed as the new challenges (Discussion 2). [book p. 205]
- Not in the book: sample-size guidance, Q-mode vs R-mode discussion, a bifactor test procedure, any small-N warning. [ours, negative finding after reading 7.1-7.8]

Application to our design.
- The book fits with models as observations and items as variables only. With 5 models the 136- or 859-item correlation matrix has rank at most 4, so parallel analysis and a K = 2 fit are degenerate. [ours; the rank argument is arithmetic, the book's setup is [book pp. 189-194]]
- For that reason no factor model is used in this project.
- Limit: the book says the same data fit a single latent axis, correlated axes, or a sparse network. Fit alone will not settle "same or separate ability". [book pp. 200-203, p. 205 Discussion 1]
- Nothing in ch. 7 speaks directly to "same or separate ability" for two input formats. [ours]

## 7. Supported vs not supported (our design)

Supported by the book, usable as is:
- Full-Bayes interval for variance components, accepting width. [book p. 125]
- Test-retest by rerun at temperature > 0. [book p. 148]
- CIs, not point estimates (principle 4). [book p. 167]
- Convergent-validity idea in MTMM (monotrait-heteromethod correlation), as a descriptive argument only. [book p. 159]

Not supported (out of reach with 5 models, or not in the book):
- Mantel-Haenszel or logistic-regression DIF with condition as group. [book pp. 150-151 assume independent model groups]
- MTMM across models. [book pp. 158-162 use n = 200]
- Omega, alpha, SEM per condition. [book pp. 136-150 use N = 100 to 600]
- Parallel analysis or factor fit with models as observations. [book pp. 189-194 use n = 300]
- Bifactor or correlated-factor discrimination (indistinguishable by fit). [book pp. 16-17]
- Disattenuated correlations, purification, anchor items, few-level priors: not in the book at all.
