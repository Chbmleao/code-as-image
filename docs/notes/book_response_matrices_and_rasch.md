# Reading notes: response matrices, Rasch/IRT and what they imply for our design

Covers: paired response matrices (2.5), outcomes that are not binary, extreme items, estimation with 5 models, local independence, and the torch_measure library (2.8). Source: Truong and Koyejo (2026), "AI Measurement Science" (printed page = PDF page).

Tags: [book p. N] is the book (short quotes where useful); [ours] is our inference or application.

Our setup, for reference: CoderUJB (136 items, 1 to 3 target tests each, 95 items from 4 project snapshots), DevEval (859 items, repo pytest ids), 5 open VLMs, conditions text and image at 10, 12 and 14 px, 3 runs per cell at T 0.7, outcome = binary pass (all target tests pass).

## 1. What 2.5 requires of paired designs, and how to analyse them

- Paired matrix definition: Y_ij^(t) is subject i on item j under condition t; "typically with and without AI assistance" (deployment RCTs, uplift studies) [book p. 44].
- The only model given is many-facet Rasch with treatment as a facet: logit P(Y_ij^(t)=1) = theta_i - beta_j + tau_t, with a theta_i x tau_t interaction for heterogeneous effects [book p. 44]. The book lists heterogeneous treatment effects as the first thing paired matrices enable, analysed with many-facet Rasch and DIF [book p. 46].
- Collab-CXR is described as a within-subject crossed design, "ideal for many-facet analysis" [book p. 45]. METR is block-diagonal because items are developer-specific, which limits IRT [book p. 45].
- Negative result: the book gives no McNemar test, no paired-difference formula, no sample-size rule and no requirement checklist for paired designs. Full-text search for McNemar finds nothing relevant. Section 2.5 is a dataset inventory plus the one equation. [book pp. 44-47, negative result]
- All datasets in 2.5 have human subjects and the target is a causal effect of AI on humans [book p. 44]. Our subjects are models and our "treatment" is the delivery format, so the book's causal framing is borrowed, not applied.
- [ours] Our design is fully crossed (every model sees every item in every condition) and runs are replicated. That is the favourable case in the book's terms (Collab-CXR, not METR).
- [ours] Analysis we can defend without the book: item-level paired comparison of each image condition against text per model (the per-model paired gap on binary pass). These are standard methods; cite a statistics source, not the book.
- [ours] The book-based analysis: a many-facet logit with model, item and condition, which we fit as a binomial GLMM with condition as a facet. The theta x tau term corresponds to the "image hurts some models more" question.

## 2. The book's model for fraction or count outcomes

Our outcome is binary pass, so these notes are kept as a record of what the book offers and why we do not use it.

- Standard IRT (Rasch, 2PL, 3PL) is "designed for binary data". Continuous Y in [0,1] arises from "partial credit scoring, pass@k estimation ... or rubric-based evaluation" and "motivate[s] extensions like Beta-IRT" [book p. 29].
- Graded response and partial credit models "extend IRT to ordinal data, but these are less common in current AI evaluation" [book p. 29]. Only a citation to Masters (1982) appears later [book p. 332]. No partial-credit or rating-scale model is developed.
- Beta-IRT: replaces the Bernoulli loss with a Beta loss on mean sigma(d_j(theta_i - z_j)) and a precision phi; "reliable calibration with as few as 2 test takers (30-60x fewer than Binary-IRT)" [book p. 111]. This is the book's only model for pass-rate outcomes. It is mentioned in one paragraph, no equations beyond the mean, no software shown.
- No binomial (k of n tests) Rasch is given. The word binomial appears only in simulation code (pp. 152, 156, 164) as a sampler.
- [ours] For binary pass the book's Rasch likelihood (p. 87) and CMLE (p. 95) apply directly. The tests inside an item check one fix and are not independent trials of ability, which is one reason to score pass-all-tests and not the fraction of tests passed.

## 3. Extreme scores and the fraction of extreme items

- Extreme persons: MLE gives infinite or very large estimates for all-correct or all-wrong models; MAP "regularizes these to finite, sensible values" with shrinkage controlled by prior variance [book p. 104].
- Regularisation is framed as a Bayesian prior with cross-validated hyperparameters (learning objective 8) [book p. 85]. Priors on difficulty are N(0, sigma_beta^2) with sigma_beta chosen once [book p. 100].
- Item-level screen in the pilot: flag items with p-value > 0.95 or < 0.05 as "Extreme difficulty", point-biserial < 0.2 as low discrimination, infit > 1.3 as misfit, infit < 0.7 as overfit [book p. 164]. Items are removed or revised after flagging [book p. 163].
- Negative result: the book gives no threshold for "what fraction of extreme items makes the parameters useless". The 0.05/0.95 cutoffs are a screen on single items. Search for "extreme", "perfect", "zero variance" turns up no population-level rule. [book negative result]
- Why this matters for us [ours]: a Rasch item with all models at 0 has beta -> +infinity under MLE; it adds nothing to theta and nothing to tau estimates (it contributes no within-item contrast). With only 5 persons, "no model passed" and "all passed" are common (CoderUJB: a third of items passed by no model; DevEval: 22 of 30 calibration items all-or-none). Under the book's own cutoff (p < 0.05 or > 0.95) those items are screened out of the pilot. We should report how many items are informative per condition and fit on those, with a MAP fit as the sensitivity check. The informative share, not the extreme share, is the number to state.
- Related: with 3 runs and T 0.7 an item can be mixed (1 of 3 runs) even when the model is "mostly" failing, so pooling runs per (model, item, condition) makes fewer items extreme than a single run does. [ours]

## 4. What Rasch can estimate with 5 persons and many items; role reversal; SE

What the book says:
- Rasch parameters are identified only up to an additive constant; solutions are sum-to-zero, a fixed anchor, or a prior [book p. 88]. "For AI benchmarks, we typically use sum-to-zero" [book p. 88].
- JMLE suffers the incidental parameter problem: with M fixed and N growing, item estimates are inconsistent [book p. 94]. Persons are the incidental parameters whose count grows. The cure for Rasch is CMLE, possible because the sum score is sufficient; "for the 2PL or 3PL models, sum scores are not sufficient, and CMLE cannot be applied" [book p. 95]. MMLE treats persons as random and is consistent for beta as N grows [book p. 95].
- SE of ability: SE(theta_hat_i) = (sum_j P_ij(1-P_ij))^(-1/2) = I(theta_hat_i)^(-1/2), "each item contributing P(1-P), most when it sits near the model's ability"; SE^2 shrinks like 1/M [book p. 121]. Plug-in variance of abilities is inflated by SE^2 and corrected by subtracting it [book pp. 120-121].
- Ch3 itself has no SE or estimation content; estimation is Ch4 [book p. 87 onward].
- Beta-IRT calibrates with as few as 2 test takers [book p. 111].
- Negative results: no "role reversal" (treating items as the sampled units and models as fixed) discussion; no statement of how many persons Rasch item estimation needs; no many-facet estimation procedure; no SE formula for item parameters or for a facet parameter tau. Searches for "few models", "role revers", "linking" (only p. 49, a safety-framework idea), "anchor items", "testlet", "local dependence" return nothing usable. [book negative results]

What follows for N = 5, M = 136 or 859 [ours]:
- Abilities theta_i are well determined: SE about 1/sqrt(sum P(1-P)); with 100 informative items near ability the SE is roughly 0.2 logits. The ranking of 5 models can be stated; the model-population variance sigma_p^2 cannot (4 df).
- Item difficulties are weakly determined: one item contributes at most 5 x 0.25 = 1.25 information from 5 models, so SE(beta_j) >= about 0.9 logits per item and condition. With 3 runs per cell the trials share theta_i, so they do not add independent persons; counting 15 trials as independent would understate the SE. Per-item difficulty claims are not supportable; item effects should be treated as a random or nuisance factor.
- Role reversal [ours]: the stable estimand is the condition effect tau_t averaged over many items, with items as the sampled units and models fixed (5 levels). This is the logic of the G-theory notes (book_gtheory_and_run_sizing.md), not something the book states. In the many-facet form, tau_t is estimated from M items x 5 models x 3 runs paired cells; its SE comes from the items, not the models.
- Many-facet with condition as a facet: the book writes the model (p. 44) but gives no fitting recipe. torch_measure in 2.8 documents only the two-way Rasch (see section 6). A many-facet logit is a plain logistic regression with model, item and condition effects (and optionally model x condition); we fit it as a binomial GLMM. Label this as our implementation of the book's equation.
- Sum-to-zero on the 5 models fixes the scale per fit. Cross-condition comparison needs a common item set and one joint fit (the facet absorbs the shift). Separate Rasch fits per condition would re-centre each time and make tau uninterpretable; the book's anchor language (p. 88) is the only support for fixing a reference.

## 5. Local independence

- Definition: "responses are conditionally independent given the latent parameters" [book p. 68]. "Local independence can be tested by residual correlations analysis between item pairs." It can be violated by "shared context between items, where multiple items on the same reading passage, dataset split, or few-shot prompt template share information that theta does not model" [book p. 68].
- The likelihood factorises over all cells only under this assumption [book p. 87]. Sufficiency of the sum score is derived assuming it [book p. 69].
- Hierarchical Rasch with items nested in benchmarks and partial pooling is offered for nested items [book p. 100]. The book does not mention testlet models.
- Negative result: no discussion of repeated runs of the same cell. Section 5.7 treats replicated trials as separate draws that make the person x item interaction estimable [book p. 134]; that is a G-theory statement, not an IRT independence statement.
- [ours] Two violations in our data. (1) CoderUJB: 95 of 136 items come from 4 project snapshots, so project shares a latent effect (setup, build, library idioms). This is the book's "shared context" case; project-clustered intervals or a project random effect is the repair, the hierarchical prior (p. 100) is the closest book tool. (2) Runs: the 3 runs of a cell are conditionally independent given p_ij only if p_ij is the cell parameter. Under a Rasch model with only theta - beta they also share the item x model interaction. Collapse runs to k of 3 per cell (binomial) or add a cell-level random effect. Do not treat 3 runs as 3 independent persons. (3) The 1 to 3 tests within an item share the item.
- Check available from the book: residual correlations between item pairs (p. 68). With 5 models the item-pair correlation has 5 observations and will be noise. A within-project vs between-project residual comparison is the usable form. [ours]
- Same items across conditions are also dependent; a paired analysis (item as the blocking unit) handles that. [ours]

## 6. torch_measure (2.8) and condition as a facet

- 2.8 describes it as "a PyTorch-native toolkit for loading, inspecting, and analyzing response matrices", the companion software [book pp. 56-58].
- API shown: load(...) of datasets, response-matrix attributes (shape, density, subject_means, item_means, observed_mask, data), and models.Rasch(n_subjects, n_items).fit(rm.data, method="mle") with .ability and .difficulty [book pp. 56-58]. No facet argument, no third axis, no polytomous or binomial likelihood is shown.
- Conclusion: the book does not show torch_measure fitting a condition facet or counts. A two-way Rasch could be run per condition, or on a stacked matrix with model-by-condition as rows (rows = 20 pseudo-subjects for 5 models x 4 conditions). The stacked form is a hack: it treats each model-condition pair as an independent person and gives no tau. [ours]
- The book's own example for checking all-fail items is `rm.item_means == 0` in 2.8.2 [book p. 57]; useful for the extreme-item count in section 3.
- Caveat: the library may contain more than the book shows; its source was not read. [ours]

## 7. What the book offers for item-level checks (supporting)

- DIF: Mantel-Haenszel over ability strata and the odds ratio [book pp. 150-151]; logistic regression with theta, group and theta x group (uniform DIF tests beta_2, non-uniform tests beta_3) [book p. 151]. The book's DIF example has 200 models in two groups of 100 [book p. 152], so its procedure assumes far more persons than our 5. [ours] With 5 models, stratification by ability is not feasible, so DIF is not used; item x condition differences are handled by the per-model paired gap.
- Infit and outfit defined from standardised residuals under the fitted Rasch model [book p. 155]; flag > 1.3 and < 0.7 [book p. 164]. Both need P_ij from a fit, so the same 5-person limit applies. [ours]
- Pilot recipe: administer to a representative sample of models, compute difficulty, discrimination and fit, run DIF and dimensionality, iterate [book p. 163].

## 8. What the methods section should commit to

1. Primary estimand: the per-model paired gap in pass rate, image (at each size) vs text, averaged over items, with a project-clustered interval. [ours, anchored on the book p. 44 equation]
2. Primary model: a binomial GLMM with condition as a facet, plus model x condition for heterogeneity. State it is our implementation of the idea on p. 44. [book p. 44; ours]
3. Outcome: binary pass-all-tests. No fraction or Beta model is used. [book pp. 29, 111; ours]
4. Extreme items: report the count of items passed by no model/all models per condition (book cutoff 0.05/0.95, p. 164) and use MAP for any Rasch-type fit (p. 104). No book threshold exists for how many is too many. [book pp. 104, 164; ours]
5. Estimation claims: ability and condition effects only. No 2PL (not CMLE-able, p. 95; infeasible with 5 persons). No item-parameter claims. [book p. 95; ours]
6. Dependence: project clustering and run replication handled by clustered intervals or random effects, not by assuming local independence. [book p. 68; ours]
7. Scale: if a Rasch-type fit is reported, sum-to-zero over the 5 models and one joint fit across conditions. [book p. 88; ours]

## 9. Where the book's models do not fit our data

- Subjects: the book's paired matrices and DIF examples have hundreds of human or model subjects; we have 5.
- Facets: the multi-facet Rasch equation is stated with no estimator, no SE and no software. torch_measure shows only two-way Rasch.
- Dependence: local independence is named and a hierarchical prior is offered, but nothing on clustered projects or replicated runs.
- Sample-size guidance and an extreme-item threshold are absent.
