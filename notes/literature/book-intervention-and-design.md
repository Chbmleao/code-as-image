# Book notes: intervention and benchmark design

Source: Truong, Sang T. and Koyejo, Sanmi. AI Measurement Science, 2026. Chapter 9 (Intervention) and Chapter 11 (Design). Page numbers are the printed ones (they match the PDF page index in the local copy). Sections read: 9.1, 9.2, 9.3, 11.4, 11.6, 11.8, 11.9 (plus the 11.2 object-first framing only as it is referenced from these sections; I did not read 11.2 in full).

Project shorthand: the question is whether giving the long context of a coding problem to a VLM as a rendered image instead of text changes accuracy, and how many tokens that saves. Conditions are Text / Mixed / All-image, crossed with font size. Items are scored by unit tests. Contamination is checked with rewritten items.

Notation used below follows the book: theta is latent ability, Y the observed score, D training data, A architecture, B benchmark design, beta item properties, F formatting (in 9.1.3). In Chapter 11, F is the task universe, S the realized set, D (= pi_E) the operationalizing distribution, C the construct, mu the social-relevance weighting. The book reuses the letter F for two things, so I write "F (formatting)" and "F (task universe)" when it matters.

---

## 9.1 From Association to Causation in Benchmark Scores (pp. 209-211)

### Definitions

- Motivating point (p. 209): E[Y | Model = A] > E[Y | Model = B] is an association. It does not show that A has more ability, because A's training data may have overlapped the items. The chapter builds the causal machinery behind Borsboom's realist validity (Chapter 3): a test is valid for an attribute iff the attribute exists and variation in the attribute causally produces variation in the scores.
- Pearl's causal hierarchy (p. 209), each level needing stronger assumptions:
  1. Association, P(Y | X).
  2. Intervention, P(Y | do(X = x)): set X to x regardless of what would have happened naturally. Needs causal structure, not only the joint distribution.
  3. Counterfactual, P(Y_x | X = x'): what Y would have been had X been x, given that X = x' was observed. Reasons about individual cases.
  The book's claim (p. 210): most benchmark analyses sit at level 1 (a leaderboard reports P(Y | Model)), while the claims people want ("better reasoning ability") are level 2 or 3.
- Structural Causal Model (p. 210): M = (U, V, F, P(U)) with exogenous U, endogenous V = {V_1..V_n}, structural equations V_i = f_i(pa(V_i), U_i), and a distribution P(U). Each SCM induces a DAG; conditional independence V_i indep V_j | S holds if S d-separates them.

### The evaluation DAG (p. 210)

Endogenous variables: D (training data), A (architecture), theta (latent ability), B (benchmark design), beta (item properties), F (formatting: prompt template, few-shot examples, system prompt), Y (observed score).

Edges: D -> theta, A -> theta, theta -> Y, beta -> Y, B -> beta, F -> Y.

A valid benchmark has the main path from D and A to Y passing through theta. Item properties beta moderate the relation (harder items, lower score at equal ability) but do not confound it.

Validity threats as DAG pathologies (pp. 210-211):

- Contamination: a direct path D -> Y bypassing theta (memorization).
- Construct-irrelevant variance: a path F -> Y not through theta (prompt format changes the score independent of ability).
- Differential item functioning: A -> Y not mediated by theta (an architecture is favored on some items independent of ability).

Boxed rule (p. 211): a benchmark is valid iff the only systematic path from the data-generating process to Y passes through theta. Every unblocked non-theta path is a validity threat. The Section 5.11 tools (DIF, dimensionality, item fit) are empirical tests for such paths.

### How it applies to our project

The render intervention is a new node on the evaluation DAG. Call it R (input modality of the context: text, mixed, image, plus font size and resolution as sub-parameters). R sits alongside F as a formatting-type variable, so the default expectation in the book's language is an F-like path R -> Y that does not go through the construct. That is exactly what we want to measure, but we also need to be clear about which construct we claim. Two readings:

1. Construct = "solve coding problems given the context", modality-invariant. Then R -> Y is construct-irrelevant variance and the accuracy drop is a validity threat to the benchmark, quantified by our study.
2. Construct = "solve coding problems from image-rendered context" (see 11.6 below). Then R is part of the definition and the threat we worry about is different (for example OCR-like reading errors that are not about coding ability).

The DAG also tells us what to hold fixed. The prompt template, the instruction text, decoding settings, and the item must not change across conditions, otherwise F -> Y contaminates the R -> Y contrast. Model identity A is a second axis: the render effect may differ by architecture (a vision encoder that is weak at small text). That is an A x R interaction, which the book's DIF framing (9.2.3) covers. Contamination (D -> Y) is handled by the rewritten-item check described under 9.2 and 11.4.

We should say plainly in the write-up that a leaderboard-style comparison of text accuracy vs image accuracy across models is level 1 (association) unless the item and everything else are held fixed by design.

---

## 9.2 Interventional and Counterfactual Diagnostics (pp. 211-213)

### Definitions and formulas

- Back-door criterion (p. 211). A set Z satisfies it relative to (X, Y) if (i) no node in Z is a descendant of X and (ii) Z blocks every path between X and Y that has an arrow into X. Then, eq. (9.1):

  P(Y | do(X = x)) = sum_z P(Y | X = x, Z = z) P(Z = z)

  The book's use: to estimate the causal effect of theta on Y, adjust for every confounder acting through non-theta paths.

- Contamination as an interventional question (pp. 211-212). Let D_overlap be the part of the training data that overlaps benchmark items. The check is whether

  P(Y | do(D_overlap = empty)) = P(Y | D_overlap = empty)

  If equal, removing the overlap changes nothing beyond what the smaller training set explains. If they differ, the overlap supplied a direct D -> Y path (memorization). We cannot intervene on trained models, so the book lists three approximations (p. 212):
  - Chronological splits: items created after the training cutoff cannot be memorized; pre vs post-cutoff score gaps estimate the contamination effect.
  - Canary detection: unique strings in items, test whether models reproduce them (Jacovi et al. 2023).
  - Item-fit analysis: infit/outfit (Section 5.11.4) flags items where some models do unexpectedly well.

- Counterfactual DIF (p. 212). Item i has DIF between groups g = 0 and g = 1 if

  P(Y_{i,g=1} = 1 | theta) != P(Y_{i,g=0} = 1 | theta)

  read as "for a model of ability theta, would the response to item i differ if the model belonged to the other group, holding ability fixed?". In the DAG this is A -> Y not through theta. Mantel-Haenszel (Section 5.11.2) estimates it by stratifying on theta (total score as proxy), blocking A -> theta -> Y and isolating the direct effect.

- "When is a score difference causal" box (pp. 212-213): Y_A - Y_B reflects a real ability difference only if every non-theta path from the data-generating process to Y is blocked. Listed unblocked paths: training data overlap (D -> Y), prompt formatting (F -> Y), evaluation order (position bias in LLM-as-judge). Causal diagnostics here and statistical diagnostics in 5.11 are complementary.

### How it applies to our project

Estimand for the render intervention. Using the book's do-notation, per model m and per item i:

- Item-level effect: Y_i(R = r) - Y_i(R = text), where Y_i(.) is the unit-test pass outcome under the given rendering. The book calls Y_x a counterfactual; the same-item text vs image pair is its closest empirical stand-in, because the same item and same model are observed under both conditions.
- Population estimand (average render effect for model m): ATE_m(r) = E_items[ Y(do(R = r)) ] - E_items[ Y(do(R = text)) ], estimated as the difference in pass rates on the same item set, for r in {mixed, all-image} and each font size. Report it per model and as a pooled contrast with a model random effect.
- Because R is assigned by us and randomized (or fully crossed) over items, the back-door adjustment (9.1) is trivial: nothing confounds R and Y by design, so the simple difference of means is the interventional quantity. The adjustment formula matters only if some conditions are run on different item subsets (for example if an image is too tall to fit for some items and they are dropped). Dropped items are a selection problem, not an intervention. We should report how many items are dropped per condition and compare on the common set.
- Counterfactual pair design: every item is run under Text, Mixed, and All-image at every font size, with identical prompt wrapper, identical instruction text, identical decoding settings and unit tests. Paired analysis (McNemar type contrasts or a mixed logistic model with item random effects) uses the pairing directly.
- Interaction with model (A x R): treat as DIF on the render intervention. If the render effect differs by architecture at the same overall ability, that is the DIF signature in 9.2.3. We can stratify by a text-only ability proxy (each model's Text pass rate) as Mantel-Haenszel stratifies on total score.
- Contamination: 9.2.2 gives the shape of the check but not a recipe for our setting. Our concrete plan is the rewritten-item check: compare the render effect and the absolute accuracy on original vs rewritten versions of the items. A large gap in absolute accuracy between original and rewritten items in the Text condition signals a D -> Y path. A render effect that differs between original and rewritten items would mean memorization interacts with modality (for example, a memorized item survives image rendering because the model recognizes it from a fragment). Chronological splits (items newer than each model's cutoff) are a second, independent check when dates are available. Canary strings only work if we control item creation, so probably not usable for public HumanEval.
- Extra unblocked paths worth listing: F -> Y (prompt template), position or truncation effects when the rendered image is downscaled by the model's preprocessor, and evaluation order if any LLM judge is used (we use unit tests, so this one should not apply).

---

## 9.3 Distribution Shift and Transportability (pp. 213-216)

### Definitions

- Setup (p. 213): P^(s)(X, Y) is the source (benchmark) distribution, P^(t)(X, Y) the target (deployment) one. Factorization P(X, Y) = P(Y | X) P(X) gives a shift taxonomy.
- Covariate shift: P^(s)(X) != P^(t)(X) but P^(s)(Y | X) = P^(t)(Y | X). Item mix changes, conditional behavior stable. The book (p. 213) says it is the most common and most correctable; it is content-validity failure seen as a shift (poor sampling of the construct domain). Importance weighting suffices (p. 214).
- Label shift (prior probability shift): P^(s)(Y) != P^(t)(Y) but P^(s)(X | Y) = P^(t)(X | Y). Example: 50% correct in the benchmark, 10% in deployment.
- Concept drift: P^(s)(Y | X) != P^(t)(Y | X). Causes listed (p. 214): model updates, prompt template changes (zero-shot to few-shot changes P(Y | X) for the same items), and temporal evolution. No reweighting of the source recovers target performance; re-evaluate on target data or model the drift explicitly.
- Transportability (p. 214): Bareinboim and Pearl (2016) selection diagrams add selection nodes S marking mechanisms that differ between environments. A causal effect is transportable if differences encoded by S can be adjusted away using the causal structure. For evaluation: a result transports if we can name what changed and the evaluation DAG lets us adjust for it. Only the item distribution changed: importance weighting. Model behavior changed: extra assumptions or new target data.

### How it applies to our project

Two separate transport questions arise.

1. From padded HumanEval (source) to real long coding contexts (target, for example RepoBench or CodeFlowBench style repository context). Padding is synthetic: it changes P(X) (what the context looks like, how relevant the padding is) and possibly P(Y | X) because the answer-relevant fraction of the context differs. If the padded filler is unrelated text, the result on it is probably covariate-shift-limited at best; we should not claim the accuracy drop transfers to real repo context without running RepoBench-style items. Treat any such claim as a transport claim with explicit assumptions.
2. From one rendering setup to another. Font size, resolution, colors, line wrapping, syntax highlighting, and the VLM's own image preprocessing (tiling, downscaling) are mechanisms that can differ. Our effect is defined for a specific render pipeline (pxpipe-like), so the selection node S would mark "rendering pipeline" and "image preprocessing of the specific VLM". A new renderer or a new model version is concept drift in the book's sense: P(Y | X) changes, so old estimates do not carry over. Model version changes also count.

Practical steps: (a) state the render pipeline version and parameters as part of the estimand; (b) report the effect by context length and by item difficulty (Text-condition pass rate) so readers can reweight to their own mix, which is the covariate-shift correction; (c) keep the prompt template fixed across conditions and say that switching templates is concept drift (book, p. 214); (d) avoid the unqualified statement "image context loses X points" and instead phrase it as "under this pipeline, on this item mix". The token-saving measurement is a separate quantity that is far less shift-sensitive, but it also depends on the VLM's image token accounting, which differs by model, so it is reported per model.

---

## 11.4 Hiding the Set (pp. 248-250)

(The section runs from p. 248 through the start of 11.5 on p. 251. The section intro sits at the bottom of p. 248.)

### Definitions and formulas

- What is hidden: the realized test set S. The construct and sampling distribution may be public. This is the regime of held-out test sets, where deterministic machinery works, provided leakage from scores is bounded (p. 248).
- Failure of transparent mechanisms (p. 248, proposition). If the builder observes the realized set S* and the reward is non-degenerate on it (for example additive r(theta, S) = sum over f in S of f(theta)), the builder's best response is theta* in argmax over theta of sum over f in S* of f(theta). When |S*| < |F| there are task universes F and weightings mu for which this is socially suboptimal, u_E(theta*) < max u_E(theta). This is Goodhart's adversarial variant and construct underrepresentation from a strategic angle. The culprit is transparency, not determinism: a deterministic rule with hidden S* is not covered by the proposition, though any leak collapses it back to the transparent case (p. 249).
- Ladder algorithm (Blum and Hardt 2015; p. 249). Scores leak information about the holdout even if items are never seen (adaptive data analysis). Procedure: keep best published score b_0 = -infinity. For each submission theta_t:
  1. Compute holdout score r_H(theta_t) = (1/|S|) sum over f in S of f(theta_t).
  2. Draw noise xi_t ~ Laplace(0, 1/epsilon) and pick threshold eta > 0.
  3. If r_H(theta_t) > b_{t-1} + eta + xi_t, publish b_t = round of r_H(theta_t) to step eta; else publish b_t = b_{t-1}.
- Noise-gated holdout (p. 249). Publish a reference set S_0 of size n_0 drawn from pi_E. Each round: draw holdout S_t of size k and noise xi_t; compute reference score r_T and holdout score r_H; if |r_H + xi_t - r_T| < eta publish r_T (silent round), else publish r_H + xi_t (alarm round). A non-gaming builder triggers the alarm with probability p_alarm = e^{-epsilon eta}; effective leakage per round is about e^{-epsilon eta} * k. Setting epsilon*eta = 3 gives roughly 20 times slower learning. This is a differential-privacy construction (Sparse Vector mechanism; Dwork et al. 2015; Dwork and Roth 2014).
- Limits (pp. 250-251). A hidden, leak-bounded set protects only S. If D = pi_E is biased and fixed, a builder can still specialize to it (best response arg max E_{f ~ pi_hat_E}[f(theta)]). Dynamic benchmarks (DynaBench, LiveBench, Chatbot Arena) refresh S' ~ D each period: this defeats item-level contamination but (i) does not hide D, since repeated samples let the builder estimate D, and (ii) does not fix a D that deviates from the construct: misalignment is on the order of TV(mu, D) regardless of refresh rate. "Dynamic benchmarks fix contamination; they do not fix construct misalignment" (p. 250).

### How it applies to our project

We are not a leaderboard with adaptive submitters, so the Ladder and noise-gated holdout are overkill. What carries over:

- Rewritten items are the practical analogue of a hidden set. Public HumanEval (and RepoBench, CodeFlowBench) items are a transparent set S*: the models we test may have seen them. Our rewritten items are a fresh draw S' from a similar D that the tested models cannot have memorized. The book's point is that this defeats item-level contamination only. It says nothing about whether our item distribution D matches the construct. So rewritten HumanEval-with-padding still only measures "HumanEval-like short algorithmic functions plus padding", not "repository-scale coding from rendered context".
- Keep a private split. Write the rewritten items, freeze them, and do not tune render parameters (font size, resolution, wrapping) on them. Choose the rendering settings on a development split, then report once on the frozen set. This is a small-scale version of not letting score feedback leak the holdout: if we iterate on render settings against the test items until the image condition looks good, we overfit S with our own choices, which is the adaptive data analysis problem the Ladder addresses. If we do tune, we should say how many configurations we tried.
- Report how the rewrite was done (who or what rewrote, how test cases were preserved) so the text-vs-rewritten gap can be read as a contamination estimate.
- Limits to state: only S is hidden; D is public (HumanEval style is well known). A model that is specialized to HumanEval-style problems would be a distribution-level overfit our rewrite does not detect. This should go in the threats-to-validity section.
- The book gives no instruction on how large a rewritten set must be; the sample size should come from our power analysis, not from this chapter.

---

## 11.6 Publishing the Construct: The Construct-Validity Protocol (pp. 264-265; only p. 264 is used here, p. 265 starts 11.7)

### The protocol (p. 264)

The evaluator:

1. Publishes the construct C: a precise statement of the capability measured (content domain and boundaries), not a benchmark.
2. Keeps D and S private, evaluated only inside a controlled pipeline.
3. Publishes one or more proxy distributions D', D'' that operationalize the same C (the book's example is GSM8K as a public proxy for a private competition-math distribution). Builders train and self-evaluate on proxies.

Logic: if D and D' operationalize the same construct, capability should transfer between them. The falsifiable check needs no exposure of D: compare a model's private score with what its public-proxy performance predicts. Real capability transfers; proxy-specific gaming shows up as beating the proxy but underperforming the predicted private score. The private benchmark is a held-out construct probe. C should be public because that is what gives the score meaning (validity) and gives builders a legitimate target. The book calls this aspirational rather than a closed theory: making "transfer across operationalizations" a precise testable guarantee is itself an open predictive-evaluation question (p. 264).

### How it applies to our project

We are not hiding anything, so the value here is the discipline: state C precisely, separate C from the item sets that operationalize it, and use more than one operationalization to check that the finding transfers.

Draft construct statement for our study (to be edited and versioned in the repo):

> Construct C: the ability of a vision-language model to produce a correct solution to a programming task, as judged by unit tests, when the task's background context (the long part: prior code, docstrings, specification text, filler) is supplied as one or more rendered images, and the task instruction is supplied as [text / the same image; decide and fix].
> Content domain: single-function Python completion with long supplied context (padded HumanEval style), and, if included, repository-level completion (RepoBench) and multi-step code flow tasks (CodeFlowBench). Excluded: tasks requiring execution feedback, tool use, or multi-turn repair; non-Python languages; handwriting or photographed code; images that are not renders of text.
> Boundary conditions: monospace or proportional font at sizes X to Y px, render width W, defined color scheme, no syntax highlighting (or with, stated), defined image preprocessing per model.
> Not claimed: that accuracy under this condition reflects general code reasoning independent of reading the image; that results transfer to other renderers.

Operationalizations (the analogue of D, D', D''):

- D' = padded HumanEval (public proxy).
- D'' = rewritten padded items (contamination control).
- D''' = a RepoBench and/or CodeFlowBench subset, if time allows.
- The transfer check the book proposes becomes: does the render effect and the model ranking under D' predict those under D'' and D'''? A model that appears unaffected by rendering on padded HumanEval but collapses on RepoBench would be the analogue of "beats the proxy, underperforms the predicted private score". Concretely: compute the render effect per model on each set and check rank agreement across sets (Spearman or Kendall, with bootstrap CIs) and whether effect sizes agree within an interval.

Additional checks that follow from the construct statement (my mapping, not from the book):

- Readability check: a text-extraction (OCR) sanity test on the rendered images at each font size to confirm the information is legible; failure here is a rendering problem, not a modality effect on the model.
- Answer-in-context control: a subset of items where the answer-relevant span is in the context vs in the instruction, to separate "cannot read image" from "cannot use long context".
- Publish the render parameters, code, item ids, and construct statement with the results.

The book explicitly says this protocol is partly aspirational (p. 264 and the bibliographic note, p. 277), so we should call our use of it "a protocol in the spirit of 11.6" and not claim that it is validated.

---

## 11.8 Representative Benchmark Selection (pp. 269-271)

### Definitions and formulas

- Problem (p. 269): choose a subset of a large suite (BIG-bench to BIG-bench Lite with 24 metrics, HELM to HELM Lite, Cal Hospital Compare 12 measures) that approximates the induced distribution D and so the construct C at lower cost. Formal setting (Procaccia et al. 2025): n metrics, m alternatives (models); metric i produces a ranking sigma_i over models; choose K a subset of N = [n].
- Positional representation (p. 269). K satisfies it for group size g if for every rank cutoff r in [m] and every alternative a:

  C(K, r, a) >= floor( C(N, r, a) / g ), where C(S, r, a) = |{ i in S : sigma_i(a) <= r }|.

  If a is in the top r on at least l*g metrics of N, it must be in the top r on at least l metrics of K. Smaller g means finer representation but larger |K|. Bounds: Omega( (n/g) * log m / log(n log m / g) ) <= |K| <= O( (n/g) log m ). The upper bound comes from a polynomial-time greedy set-cover algorithm (p. 270): color entries as an alternative accumulates g appearances, then greedily pick metrics that cover the most remaining colors.
- Positional proportionality (p. 270). K satisfies epsilon-positional proportionality if for all a and r:

  | C(N, r, a)/|N| - C(K, r, a)/|K| | <= epsilon.

  Bounds: Omega( (1/epsilon^2) log m ) <= |K| <= O( (1/epsilon^2) log m ), tight up to constants; a random subset of size O(epsilon^-2 log m) works with high probability (Chernoff-type argument).
- Scoring-rule approximation (p. 270): if K is epsilon-proportional, then for any scoring rule with score vector s and any alternative a, | f_s(a, sigma_N) - f_s(a, sigma_K) | <= epsilon, where f_s(a, sigma_S) = (1/|S|) sum over i in S of s_{sigma_i(a)}. So a proportional subset approximates any scoring rule on the full set.
- The book ties this to Section 7.1 (dimensionality) and its Exercise 8 (implement the greedy algorithm).

### How it applies to our project

The book's setting is selecting metrics (each giving a ranking of models), not selecting test items for a single pass-rate. The direct mapping is loose, and I should not overstate it. Two uses that do fit:

1. Choosing which items (or which benchmarks) to run under the compute budget. Treat each item, or each item cluster or benchmark, as a "metric" whose ranking is over the models plus conditions (or over models within a condition). The book's guarantee is then that a random subset of size about (1/epsilon^2) log m preserves, up to epsilon, each model's fraction in the top r positions. With m about 5 models and epsilon = 0.1, log m is small but the constant is unspecified, so the bound tells us the scaling (shrink epsilon by 2, quadruple the subset) more than a usable number. This is a sizing intuition; a direct bootstrap on the pilot data will give the number we actually need.
2. A representativeness criterion for the item pool. In the book's terms, the subset should have an induced distribution close to D and hence to C. For us: stratify the chosen items by context length, gold solution length, difficulty (Text pass rate across models from a pilot), and problem type, and require the chosen pool to match the full benchmark on those strata (a proportionality-style check: compare stratum fractions, tolerate epsilon). Random sampling within strata is the version supported by the book's Chernoff argument, and it is preferable to hand-picking "interesting" items, which the book (p. 274, principle 6) discourages: use formal representation criteria rather than ad hoc selection.
3. Consistency check: rank models under the sampled item pool and under the full available benchmark (for the text condition, where running the full set is cheap), and report the rank agreement. This is the empirical version of "the lite set preserves the ranking" from the right panel of the book's illustration (p. 273).

The greedy positional-representation algorithm is not needed for a study with 3 to 5 models.

---

## 11.9 Synthesis: Design Principles for Strategic Benchmarks (pp. 274-275)

### Content

Six principles (Table 11.2, p. 274), with formal basis and recommendation:

1. Randomize and Refresh. Single-sample alignment (TV bound) and the transparent-failure proposition. Use randomized evaluation with task renewal; fixed transparent benchmarks are Goodhart-vulnerable.
2. Correct and Grow. Gap-targeted correction theorem, optimal k*. Invest in correcting the distribution toward the construct mu; the optimal k* ~ sigma*sqrt(rho|F|) grows with the correction rate rho.
3. Gate Information Release. Holdout mechanism, learning-slowdown proposition. Use threshold tests to condition information flow on builder behavior.
4. Align Metrics with Welfare. ATO regret and TT zero-regret propositions (from 11.7). Score total treatment effect, not averages; account for counterfactual baselines.
5. Allow Partial Transparency. Garbling dominance. Calibrated noise in reporting can Pareto-improve over full transparency and full opacity.
6. Ensure Representative Subsets. Positional representation and proportionality bounds. Use formal criteria for lite benchmarks.

Channels (p. 274): principles 1 to 3 concern the information channel, 4 the metric channel, 5 the developer channel, 6 the scope channel.

Three properties of a durable evaluator (11.9.1, p. 275):

- Validity: the score tracks C, not merely D. Secured by publishing the construct and proxies (11.6) and welfare-aligned metrics (11.7).
- Durability: the benchmark stays informative under optimization, because D stays private and is corrected toward mu faster than it is learned (11.5). Hiding S buys time; hiding and correcting D buys durability.
- Faithful execution: the evaluator runs exactly the announced procedure for every subject, with no special access or after-the-fact adjustment. Natural implementation: a sealed, auditable pipeline that draws S ~ D, scores, emits only the agreed signal, and logs that the protocol was followed.

Table 11.3 (p. 275) summarizes: hide nothing (static benchmark, fails); hide S (reusable holdout, bounded durability); hide D (randomization plus correction, durability); hide D and S while publishing C and D' (construct-validity protocol, validity plus durability); hide the protocol itself (secure auditable pipeline, faithful execution).

### How it applies to our project

Our study is a measurement study with no adversarial builder, so principles 2, 3 and 5 are mostly not applicable and I would not cite them. The ones that transfer:

- Principle 4, counterfactual baselines. The book's TT metric subtracts the counterfactual baseline (y minus mu_0-hat(x)). Our headline metric is already of this form: image accuracy minus text accuracy on the same item, per model. Reporting only raw image-condition accuracy would be the analogue of the ATO metric that the book warns rewards selection. Also report the effect relative to a baseline of "no context" or "context removed" if we want to show how much the model actually uses the long context (an extra control, not from the book).
- Principle 1, randomize and refresh. Randomize item order and the assignment of items to render seeds where relevant, and rely on the rewritten items as the refreshed set. Note the caveat from 11.4.3: refreshing addresses contamination but not construct mismatch.
- Principle 6, representative subsets: use stratified or random item selection, per 11.8.
- Validity and faithful execution (11.9.1): publish the construct statement and proxy sets (11.6), and run a single scripted pipeline for every model and condition, with logs of exact prompts, image files, decoding settings, model versions, and seeds, so the procedure can be audited. This is the small-scale meaning of "same sampling, scoring and reporting for every subject". Specifically: no per-model prompt tweaks after seeing results, no re-runs of failed conditions unless done for all, no dropping of items after unblinding without a stated rule.

A checklist that combines these sections for the paper:

1. Estimand written in do-notation, with the render pipeline as part of the intervention (9.1, 9.2).
2. Same-item counterfactual pairs across Text, Mixed and All-image at each font size (9.2).
3. Contamination checked with rewritten items, plus chronological split if dates exist; results reported for original and rewritten sets (9.2.2, 11.4).
4. Development and frozen test splits for render tuning (11.4).
5. Construct statement and two or more operationalizations, with a transfer check on the render effect (11.6).
6. Effect reported as a difference to the text baseline, with the shift and transport limits named (9.3, 11.9).
7. Representative item selection by stratification, with a rank-agreement check against the fuller pool (11.8).
8. Single audited pipeline, logged (11.9.1).

---

## Caveats on these notes

- I read only the sections listed at the top, plus the front-matter contents list. I did not read 11.2, 11.5, 11.7 in full, and only used 11.7 content that appears in the 11.9 table.
- The "How it applies" paragraphs are my proposals for the project, not statements from the book. Where I mapped the book's setting (model-ranking metrics in 11.8, strategic builders in 11.4 and 11.9) onto ours, I flagged the mapping as loose.
- Page attributions: each page header sits at the top of the extracted page text, and I assigned content to the page whose header precedes it. Section boundaries should be double-checked when quoting a specific page.
