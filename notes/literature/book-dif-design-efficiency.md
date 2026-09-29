# Book notes: item-level diagnostics (DIF), design principles, and efficient item selection

Reference: Truong, Sang T. and Koyejo, Sanmi. AI Measurement Science, 2026. Local copy: docs/AI-Measurement-Science.pdf.

Scope: Sections 5.11, 5.12 (light), 5.13, 6.1, and a light pass on 6.2. Page numbers below are the printed page numbers in the page headers (they coincide with the PDF page index in this copy). Equation numbers are the book's. Anything marked "project reading" is my interpretation for our study, not a claim from the book.

Project shorthand: items are coding problems scored by unit tests (binary correct/incorrect). "Models" are the 3 to 5 local VLMs. "Conditions" are Text, Mixed, All-image, crossed with font size.

---

## 1. Section 5.11 Item-Level Diagnostics (pp. 150-162)

### 1.1 Framing (p. 150)

The section reads structure out of the same variance decomposition used for reliability. The person-by-item interaction gamma_ij of Section 5.2 (canonical example: a question "idiosyncratically easy for one model family") is treated as variance to average down when it is not indexed by anything. Once the interaction is indexed by a meaningful group, it becomes a bias to detect. That is what differential item functioning (DIF) does. The four tools in the section are DIF, dimensionality assessment, item fit, and the multitrait-multimethod (MTMM) matrix. They operationalize the validity threats of Section 1.3 (p. 150).

### 1.2 Differential Item Functioning, 5.11.1 (pp. 150-151)

Definition (p. 150): DIF occurs when an item is systematically easier or harder for one subgroup than for another, after controlling for overall ability. In AI evaluation the "groups" may be model families, architectural types, or training paradigms.

Formal condition (Eq. 5.24, p. 150): item i exhibits DIF if

P(X_ij = 1 | theta_j, g = 1) != P(X_ij = 1 | theta_j, g = 0)

where theta_j is model j's ability and g is group membership. The book stresses that conditioning on theta_j is the critical part: the question is whether equally able models from different groups behave differently on the item.

Two forms (p. 150):
- Uniform DIF: the item is consistently easier or harder for one group across all ability levels. The two groups' item characteristic curves (ICCs) are shifted but do not cross.
- Non-uniform DIF: the item favors one group at some ability levels and the other at different ones. The ICCs cross.

Mantel-Haenszel (MH) procedure (Holland and Wainer 1993; pp. 150-151):
- Stratify examinees by ability, using total score as the proxy.
- At each stratum k build the 2 x 2 table (correct/incorrect by group) with entries A_k, B_k, C_k, D_k and stratum size N_k.
- Combine into a common odds ratio (Eq. 5.25):

  alpha_MH = sum_k (A_k D_k / N_k) / sum_k (B_k C_k / N_k)

- An odds ratio of 1 means no DIF. Values significantly different from 1 indicate DIF (p. 151).

AI example given (p. 151): a math benchmark comparing open-source and proprietary models, where LaTeX-formatted items favor proprietary models because of training data composition, independent of mathematical reasoning. The formatting advantage inflates scores for one group without reflecting the target construct.

### 1.3 DIF Analysis, 5.11.2 (pp. 151-154)

Logistic-regression alternative (Zumbo 1999; Eq. 5.26, p. 151):

log[ P(X_ij = 1) / P(X_ij = 0) ] = beta_0 + beta_1 theta_j + beta_2 g_j + beta_3 (theta_j x g_j)

theta_j is the ability proxy (total score), g_j is group membership, beta_3 is the interaction.
- Test beta_2 = 0 to detect uniform DIF.
- Test beta_3 = 0 to detect non-uniform DIF.

Simulation in the book (pp. 151-154): 200 simulated models (100 per group, same ability distribution N(0,1)), 30 Rasch items with difficulties linspace(-2, 2), 5 items with planted DIF of 0.8 logits easier for group 1. Ability strata are the 5 quintiles of total score. Flagging rule used in the code and text (p. 153-154): |log OR| > log(1.5) = 0.41, drawn as dashed threshold lines at +/-0.41. The book's code labels its chi-square as "simplified" and stores only the log odds ratio, so the plotted analysis is an effect-size threshold and not a significance test (pp. 152-153). Right panel (p. 154): ICCs for a non-DIF item coincide for both groups; for a DIF item, group 1's curve is shifted left, which is uniform DIF.

Book's remark (p. 154): in practice DIF for AI benchmarks would compare model families (autoregressive vs encoder-decoder), training paradigms (RLHF vs base), or architectural features (mixture-of-experts vs dense).

### 1.4 Dimensionality, 5.11.3 (pp. 154-155)

A benchmark claiming one construct should show one dominant latent factor. Discovery of the number of factors is developed in Section 7.1 (parallel analysis, Horn 1965: retain a factor only if its eigenvalue exceeds that of random data of the same shape). Here the use is confirmatory. If unidimensionality fails, the composite conflates constructs, and the remedy is subscores per factor or revising the benchmark (p. 155).

### 1.5 Item fit and contamination, 5.11.4 (pp. 155-158)

Rasch fit statistics (Wright and Masters 1982), with P_ij = expit(theta_j - beta_i):
- Standardized residual: z_ij = (X_ij - P_ij) / sqrt(P_ij (1 - P_ij)).
- Outfit_i = (1/N) sum_j z_ij^2. Unweighted; sensitive to surprising responses far from the item's difficulty.
- Infit_i = sum_j (X_ij - P_ij)^2 / sum_j P_ij (1 - P_ij). Information-weighted; sensitive to surprising responses near the item's difficulty.
- Expected value is 1.0. Above 1.3 suggests underfit (noise, possibly multidimensionality). Below 0.7 suggests overfit (too predictable, redundancy or dependency). Above 2.0 is serious misfit (p. 155).

Contamination signature (pp. 155-156, 158): memorizing models get the item right despite low ability, which inflates outfit especially. Observed proportions correct exceed the Rasch curve at low ability. The book notes this diagnostic does not need to know which models or items are compromised (p. 158). The book's simulation uses 150 models, 25 items, 5 contaminated items, 30 contaminated models (p. 156).

### 1.6 MTMM matrix, 5.11.5 (pp. 158-162)

Campbell and Fiske (1959). Traits are constructs; methods are formats. Four blocks (p. 159):
1. Monotrait-heteromethod (same trait, different methods): should be high (convergent validity).
2. Heterotrait-monomethod (different traits, same method): lower than block 1 (discriminant validity).
3. Heterotrait-heteromethod: lowest.
4. Reliability diagonals: highest, they set the ceiling.

The four Campbell-Fiske criteria (p. 159): convergent coefficients are non-zero and large enough to pursue; higher than same row/column heterotrait-heteromethod values; higher than heterotrait-monomethod values; trait intercorrelation pattern consistent across method blocks. Caveat (p. 162): if all benchmarks use the same format (for example multiple choice), discriminant validity cannot be assessed because method variance is confounded with trait variance.

### 1.7 How it applies to our project

DIF with condition as the grouping. Our comparison is different from the book's example in one important way. The book's groups partition models (open vs proprietary), so each model sits in one group. In our design the same models are run in every condition, so "group" is a within-model factor (Text, Mixed, All-image, and font size levels). The book's formulas do not cover this pairing. Two ways to run it while staying inside the book's tools:

1. Treat each (model, condition) run as a separate "examinee". Then the Eq. 5.24 conditioning variable theta is the total score of that run, and g is the condition. This matches the book's MH and logistic setup directly, but the rows are not independent (the same model appears in several conditions), so the p-values should be read with care. This is a project reading, and I did not see the book address dependence between groups.
2. Use the logistic form (Eq. 5.26) with theta taken from a matching score that is defined without condition information, for example the model's total score on the Text condition (project reading). The book uses total score as the proxy in both MH and logistic regression (pp. 150-151), so this is a variation, not the book's recipe.

Concrete procedure for pairwise comparisons (Text as reference, Image as focal):
- Build a model-by-item 0/1 matrix per condition (unit tests pass or fail).
- Stratify by ability proxy. With only 3 to 5 models the book's five-quintile strata would be almost empty, so the number of strata has to be tiny or the data need to be pooled over runs (multiple sampled runs per model, or many (model, font size) cells). This is a real limit: the book's simulation uses 200 examinees, and I did not see a minimum sample size stated.
- Compute alpha_MH (Eq. 5.25) per item and take log alpha_MH. Or fit Eq. 5.26 and test beta_2 (uniform) and beta_3 (non-uniform).
- What counts as a flag, using only what the book states: |log OR| > log(1.5) = 0.41 in the effect-size version (p. 153-154), and beta_2 or beta_3 significantly different from zero in the logistic version (p. 151). The direction is read from the sign: the book's planted items have a negative shift meaning easier for group 1 (p. 152). For us, the flag of interest is items much harder in image conditions, meaning the group-odds shift points against the image group. A significance test is separate from the effect-size cut; the book's code reports the effect-size rule only.
- Expect mostly uniform DIF if image rendering shifts difficulty on all model abilities by a constant (project reading). Non-uniform DIF would mean images hurt weaker models more than stronger ones, or the reverse; beta_3 tests exactly that.
- Font size as DIF: make each font size a group in a separate contrast (for example 8 pt vs 12 pt within the image condition), and run the same tests. The book gives no font-specific guidance.

Confound to name explicitly (project reading, following the book's own AI example on p. 151): the book says DIF is a formatting advantage that does not reflect the target construct. That is the definition of our target effect. An item that becomes much harder only as an image is measuring image reading (OCR ability) as a nuisance factor, not coding ability. The dimensionality check (5.11.3) is the book's suggested way to see whether "reading rendered text" acts as a second dimension. With so few models, parallel analysis is likely to be unstable; this is my judgment, and the book does not give a minimum size.

Other diagnostics for us:
- Item fit (5.11.4): a Rasch fit on the Text condition first, then check outfit/infit per item. Items above 1.3, or above 2.0 for serious misfit, are candidates for review. Contamination is a separate risk for coding items (public benchmarks may be memorized); the outfit signature on p. 155-156 applies, though with 3 to 5 models it will be noisy.
- MTMM (5.11.5): the book's logic could be borrowed by treating condition as a method and problem category as trait, but the book presents MTMM for constructs by formats and I did not see it applied to rendering conditions. Optional.

---

## 2. Section 5.12 Building Trustworthy AI Evaluations (pp. 162-167), light pass

Section purpose (p. 162): build benchmarks with validity designed in. The item-level tools double as construction aids: MTMM supports the nomological network, and DIF and item fit confirm items behave as the construct theory predicts.

5.12.1 Principled item construction (pp. 162-163), six steps:
1. Define the construct (what it measures and what it does not).
2. Specify the domain with a blueprint (sub-domains, difficulty levels, item types).
3. Generate candidate items (experts, existing material, or LLM-generated).
4. Pilot and analyze: difficulty (p-value or IRT beta), discrimination (a parameter or point-biserial), and fit (infit/outfit).
5. Screen for validity threats: DIF (Section 5.11.2), dimensionality (Section 7.1), contamination via fit statistics and public/private splits.
6. Revise and iterate.

Book's pilot simulation (pp. 163-166): item screening uses a discrimination cutoff of 0.2 on the point-biserial and difficulty limits of 0.05 and 0.95 proportion correct (dashed and dotted lines in the code on p. 165). The text on p. 166 confirms the 0.2 threshold and says flagged items are revised or replaced.

5.12.2 Six item-design principles (p. 166-167):
1. Start with the construct, not the data.
2. Use multiple methods (at least two formats), enabling MTMM.
3. Check dimensionality before reporting a single composite.
4. Screen for DIF whenever the population has distinct subgroups.
5. Monitor for contamination (held-out private pool, public vs private comparison, fit statistics).
6. Document validity evidence, claim by claim (claim-centered approach).

A worked summarization example (p. 167) applies all six. Its DIF step flags items where domain-specific vocabulary gives an irrelevant advantage.

### How it applies to our project

The three-step usable core for us is step 4 (pilot statistics), step 5 (DIF and contamination screen), and principle 6 (document limits). Practical reading: run a pilot on the item pool with the Text condition, drop items with near-zero or negative discrimination and items at 0 or 100 percent pass rate, then run condition DIF on what remains. Contamination is relevant for coding problems from public sets; the book's private held-out pool advice would mean adding some newly written problems if we can (project reading). We meet principle 2 in a loose sense, since the conditions are different presentation formats of the same content (a method facet), but the book's meaning is different formats to measure a trait, so I would not claim MTMM validity.

---

## 3. Section 5.13 Design principles (pp. 167-168)

Seven principles listed (pp. 167-168). Section references are the book's.
1. Identify the dominant source of variability (Sec 5.6). Run a G-study before committing to a design. If item-sampling variability dominates, use more items or D-optimal selection.
2. Match items to the ability range of interest (Sec 5.3). Conditional reliability varies across ability; ranking strong models needs harder items.
3. Use multiple judges when scoring is subjective (Sec 5.9).
4. Report confidence intervals, not just point estimates (Sec 5.10). Scores that overlap within +/-2 SEM may not differ meaningfully.
5. Control what can be controlled (Sec 5.1). Score at temperature 0, randomize and average over prompt formats, standardize rubrics.
6. Separate reliability from validity (Chapter 1). A benchmark can be reliable and still measure the wrong thing (contamination, shortcut features, length bias).
7. Audit items, do not just score them (Sec 3.3). Negative item-total correlations signal flipped keys, ambiguity, or grading bugs (p. 168).

### How it applies to our project (met, partly met, at risk)

- P1 (dominant variance source): partly. We can estimate item-by-condition and model-by-condition components with a variance decomposition if we have replicates. Not something I verified is planned.
- P2 (match ability range): at risk. Small local VLMs on hard coding items may sit near the floor, which gives little information (see Section 4 below). Items should be near 50 percent pass for these models.
- P3 (multiple judges): met by design, since unit tests are objective. The book's rationale (subjective scoring) does not bite here.
- P4 (confidence intervals): to meet. With few items and few models, report intervals on per-condition accuracy and on DIF effect sizes, not just point values.
- P5 (control what can be controlled): should meet with temperature 0 and fixed rendering settings. Font, renderer, and prompt wording should be held fixed except for the manipulated factor. Note that Ollama VLMs may not be deterministic even at temperature 0; I did not read anything on this in these sections, so verify on our side.
- P6 (reliability vs validity): the key risk. High agreement across runs does not show that image accuracy reflects coding ability. A model failing an image item may fail at reading, which is construct-irrelevant.
- P7 (audit items): to meet. Check that each item's unit tests pass on the reference solution in every condition, and inspect items with negative item-total correlation.

From 5.12.2, principle 3 (dimensionality) and principle 6 (documented validity evidence) also apply. Principle 2 (multiple methods) is loosely met, as noted above.

---

## 4. Section 6.1 The Design Problem in AI Evaluation (p. 174) and choosing items under compute limits

### 4.1 What the book says

Chapters 3 and 4 took the response matrix Y as given. In practice someone designs the evaluation, and the decisions affect quality and efficiency (p. 174). Two efficiency questions:
1. Item selection: given a pool of candidates, which subset maximizes the precision of the measurements?
2. Scoring rules: sum scores, weighted scores, or latent factor scores. The choice interacts with the measurement model, since sum scores are sufficient for Rasch but not for 2PL (p. 174).

The chapter frames the aim as high measurement precision with minimal cost, drawing on classical experimental design and information theory (p. 174).

### 4.2 Light pass on 6.2 Optimal Experimental Design (pp. 174-185)

Fisher information for item selection (p. 174-175). For a Rasch item j with P_j(theta) = sigma(theta - beta_j):

I_j(theta) = P_j(theta) (1 - P_j(theta))   (Eq. 6.1)

It is maximized at P = 0.5, meaning theta = beta_j (item difficulty matches ability). Items that are answered right or wrong 99 percent of the time say almost nothing. The maximum value is 1/4 (Exercise 3.1, p. 186). Under local independence, information is additive: I_total(theta) = sum over selected items of I_jk(theta) (p. 175).

Computerized Adaptive Testing (CAT, p. 176). Four steps iterated: select the most informative item given the current ability estimate, administer it, update the ability estimate, check a stopping criterion.

Stopping rules (p. 182): reliability threshold (R = 1 - sigma_post / sigma_prior >= 0.95), standard error threshold (SE(theta_hat) <= 0.3), fixed length K, or an information threshold. Practical constraints for AI: cost, time, and contamination (p. 182).

Caveats the book states for AI evaluation (p. 182): CAT assumes deterministic responses (temperature 0 works directly; stochastic sampling needs multiple samples per item). CAT also requires pre-calibrated item parameters, so a new benchmark needs a pilot sample of models first (cold start; pointer to Section 8.1).

D-optimal design (p. 182-183, 185). For a fixed test of K items from a pool of M candidates, with K-dimensional factor model and item loading vectors V_j:

Information matrix I(theta; J) = sum over j in J of P_j(theta)(1 - P_j(theta)) V_j V_j^T

Criteria: D-optimal maximizes det(I); A-optimal minimizes tr(I^-1); E-optimal maximizes the smallest eigenvalue (p. 182-183). The book's finding in its simulation (p. 185): D-optimal selection spreads difficulties across the target ability range, while random selection clusters near the center of the pool's difficulty distribution and leaves the tails poorly covered. I only read the prose of that simulation, not the code output.

Paired comparisons (p. 185): the Bradley-Terry information I_ik = P_ik (1 - P_ik) is maximized when models are evenly matched. Relevant to arenas, less to us.

Discussion question 4 of the chapter (p. 186) is closest to our situation: a fixed budget of API calls to evaluate many models on a benchmark, and the task is to design a strategy that maximizes precision under that constraint. The book does not answer it in the sections I read. The bibliographic notes (p. 186) mention Truong, Tu, et al. (2025), who report comparable decision accuracy with 50 questions per benchmark by combining IRT-calibrated item parameters with Elo-based adaptive selection. I only read the one-sentence summary, not the paper.

### 4.3 How it applies to our project: picking items under a compute budget

The budget structure. Total runs = items x models x conditions x font sizes (x replicates). Image conditions cost more per call on a Mac. So the number of items is the main lever.

Using the book's tools (with my adaptations marked):

1. Cold start and calibration (p. 182). CAT needs pre-calibrated difficulties. Our pilot can be the Text condition on a larger pool of candidate items, run once per model. This is cheap compared with image runs, because the only reason to use the image conditions is to compare against Text. Fit a Rasch model on the Text pilot data (or just use proportion correct as a difficulty proxy, as the book's own simulation on p. 156 does) to get beta_i.
2. Select items near P = 0.5 for the models we test (Eq. 6.1). If the 3 to 5 VLMs differ a lot in strength, one item cannot be at 0.5 for all of them. The book's D-optimal design idea (spread difficulties across the range of abilities we care about, p. 185) suggests choosing K items with difficulties spread over the range that covers the models, rather than all at one point. I did not read a formula for the 1-D Rasch case beyond Eq. 6.1 and additivity, so the selection rule (greedy maximization of summed I_j across the model ability grid) is my construction from those two pieces.
3. Keep items informative for DIF too (project reading). The book selects for ability precision. Our DIF question needs items where condition might change the outcome, so items at floor or ceiling in Text are useless: a text-solved item at 100 percent that drops in image is informative, but an item at 0 percent in Text carries no signal about image loss. So the Text pilot filter should drop items with near-0 pass rate for all models, and it may keep near-100 percent items since they can show large image drops. This departs from the pure Fisher rule; it is my argument, not the book's.
4. Adaptive selection (CAT) is probably not worth it here. With 3 to 5 models and fixed pool size, a fixed selected set is simpler, and the book itself lists conditions where fixed vs adaptive choice matters as a discussion question (p. 186). CAT also requires deterministic responses, which need checking on Ollama (p. 182).
5. Stopping/size rules. The book's SE threshold of 0.3 (p. 182) and reliability threshold of 0.95 are for CAT ability estimates and would not transfer directly to our DIF question. Sample size for DIF was not addressed in the sections I read. With few models the practical route is many items and replicates so that strata are populated.
6. Report uncertainty (Principle 4, p. 167), since the budget forces small samples.

Limits of what I read: for Section 6.2 I did light reading only. I did not read the implementation code of CAT (pp. 176-181) or the D-optimal simulation code (pp. 183-185) in detail, and I did not check any numerical results.

---

## 5. Open points to decide

- Pairing structure: DIF in the book compares independent groups of models; ours compares the same models across conditions. Decide whether to use pooled (model, run) rows and treat dependence as a caveat, or a different method (for example a mixed-effects logistic model, which the book mentions only in the G-theory context on p. 168, not for DIF).
- Number of ability strata for MH with 3 to 5 models.
- Whether to check determinism of the Ollama VLMs at temperature 0 (Principle 5, p. 167; CAT caveat, p. 182).
- Whether to treat OCR ability as a separate dimension (Section 5.11.3) and how to test it with so few models.
