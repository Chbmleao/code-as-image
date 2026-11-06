# Reading notes: validity evidence, threats, causal framing and the book checklist

Covers: validity evidence (1.2), threats to validity (1.3), the causal framing of chapter 9, temperature and repeated runs, and the chapter 13.5 checklist, applied to the Code as Image design (CoderUJB 136 + DevEval 859, 5 VLMs, text vs image at 10, 12 and 14 px, 3 runs at T 0.7). Source: Truong and Koyejo (2026), "AI Measurement Science". Printed page = PDF page (checked on running headers of pp. 229, 264, 274, 313).

Tags: [book p. N] = stated or quoted from the book; [ours] = our reasoning, not in the book. Companion note on chapter 5 and temperature: book_gtheory_and_run_sizing.md.

## 0. What the book does NOT contain (state this before leaning on it)

- No estimand formula such as ATE over items, and no recommendation on per-model vs pooled effects. Chapter 9 defines do(X), back-door adjustment (9.1) and covariate shift, nothing about treatment-effect estimators. The nearest object is the treatment facet tau_t in the many-facet Rasch model of 2.5.1. [book p. 44]. The ATE_m wording is [ours].
- No guidance on image resolution, token count, or any modality-changing confound. A search for resolution, token count, prompt length returned only the CIV mention of prompt length (p. 21). [ours: searched the full text]
- No argument that a threat shared by all conditions cancels from a contrast. [ours: searched; see 2.3]
- Multimodal evaluation is declared out of scope: "Extending measurement theory to vision, audio, multi-modal, and embodied AI evaluation raises new questions about construct definition and response modeling." [book p. 315]. Cite this as the reason construct definition for image context is ours to justify.

## 1. Section 1.2 validity evidence: which types we can provide

Book framing: validity is unitary, "the degree to which evidence supports the intended interpretation of test scores", with five evidence forms; Table 1.1 lists typical evidence per form. [book p. 17, p. 20]. Covariance cannot identify the causal structure (bifactor vs correlated factors give the same covariance), so evidence must accumulate. [book pp. 16-17]

| Form [page] | Can we provide it? | Concrete analysis |
|---|---|---|
| Content [pp. 17-18]: expert review of domain coverage; "frequently skipped" | Partly | Blueprint table: per benchmark, which coding tasks are covered (CoderUJB: Java method regeneration; DevEval: Python function body in repo context) and what is not (debugging, multi-file edits, review). The book's own example of failure is "coding ability" tested only by function completion [book p. 17, p. 22]. Both of our benchmarks are of that type, so say so. All items are used, so there is no item sampling to defend, but also no expert review of items. |
| Criterion [p. 18]: concurrent correlation with a gold standard | Partly | Text-condition scores as the concurrent criterion for the image-condition scores: per model, item-level agreement of text vs image pass. Caveat in the book: the criterion must itself be trustworthy and circularity is acute in AI. [book p. 18]. Unit tests are the outcome criterion, not an independent one. No predictive criterion (developer outcomes) is available. |
| Construct [pp. 18-19]: convergent and discriminant evidence, MTMM (5.11.5) | Yes, this is the main one | Convergent: image-condition item difficulty should track text-condition difficulty across items (item-by-model pass rates). With one trait (coding) and methods that differ only in context format, no discriminant block can be formed; 5 models give very few "persons", so any multitrait-multimethod layout would be descriptive at best. Book: construct validity is testable by intervention "raise the ability, hold all else fixed", and "such clean interventions are rare". [book p. 19] Our render intervention is one of the rare clean ones on the input side. |
| External [p. 19]: other contexts, populations, times | Weak | Only within-study: two languages, 5 models, three font sizes. Not tested: other renderers, other VLM families, real long contexts. List as limits. Book flags score-after-model-update and clean-vs-noisy inputs as examples. |
| Consequential [pp. 19-20] | No | Only the argument that a token saving counts only if accuracy holds. No impact analysis or misuse audit. State as not assessed. |

[ours] Honest count: construct (main), criterion (partial), content (descriptive blueprint), external (limits only), consequential (none).

## 2. Section 1.3 threats: what the book recommends and what we can do

### 2.1 Construct-irrelevant variance (CIV) [book p. 21]
- Book: systematic, "does not average out with more items"; model Y_ij = lambda_j theta_i + gamma_j N_i + z_ij. Observed N: "it can be controlled for or randomized away (counterbalancing position decorrelates it from the score)". Latent N: "confounded with theta: a single benchmark cannot separate the two", and MTMM (5.11.5) is the tool. [book p. 21]
- Ours, observed N: font size, characters per row, image resolution, instruction order. All are explicit design factors or fixed, so they are controlled by design.
- Ours, latent N: vision-encoder downscaling and tiling. Differs by model, cannot be observed. Five VLMs from different families are the "multiple methods"; report per model, do not pool.
- Key conceptual point [ours]: because reading the image is part of the construct, the reading effect is not CIV. CIV is whatever changes the score and is neither coding nor reading (a resolution cap that makes text unreadable at any font; a layout that truncates context). The 10, 12 and 14 px conditions separate "legible" from "illegible" regimes, which is the CIV-vs-construct boundary.
- Prompt formatting sensitivity is the book's first listed CIV source (Mizrahi). Keep wrapper and instruction text identical across conditions, and say so. [book p. 21, p. 212]

### 2.2 Construct underrepresentation [book p. 22]
Book example is exactly ours: "Coding ability tested only through function-completion tasks, missing debugging, architecture design, code review, documentation, and refactoring." [book p. 22]. Recommendation is implicit: narrow the claim. [ours] Claim "coding from image context for method/function generation with repo context", not coding ability generally.

### 2.3 Contamination [book pp. 22-23, 210-212]
- Book: direct or indirect; detection by canary strings, membership inference, chronological splits, public/private gaps, "Performance discontinuities: If a model's accuracy on 'seen' items is dramatically higher than on matched 'unseen' items, contamination is likely." Causal reading: a path D -> Y that bypasses theta. [book p. 23, p. 210-211]. Chapter 9 approximations: chronological splits, canaries, item-fit. [book p. 212]
- The book does not say that a threat common to all conditions leaves the contrast unbiased. The argument is [ours]:
  - If memorization adds a constant to the logit in both conditions, it shifts difficulty and the within-item contrast is unchanged. This is the additive case.
  - It fails when memorization interacts with modality. Ceiling: an item the model can regurgitate passes in text and also in image from a fragment of the signature, which compresses the gap toward zero. Floor: items nobody passes contribute zero to the contrast but still count in the denominator for pass-rate comparisons. So the gap is biased toward zero for memorized items, not unbiased.
  - With 22 of 30 DevEval calibration items passed by all or none and a third of CoderUJB items passed by none, the contrast is carried by a minority of items. The effective sample for the gap is those items; the project-clustered interval reflects the sample actually available.
- Feasible mitigations with our data [ours]:
  1. Contamination flag: an item is flagged when one of the other 4 models copies the reference exactly in a text run. Report the gap with and without flagged items. This is the nearest to the book's "seen vs matched unseen" discontinuity test, using verbatim reproduction as the "seen" marker.
  2. Report the gap among items with intermediate text pass rate (non-ceiling, non-floor) as a sensitivity analysis.
  3. Chronological split only if release dates of the repos are known and a cutoff for each model is documented; not assumed available.
  4. Rewritten items are not part of the design.
- Say plainly that contamination is flagged, not removed, and that absolute accuracies are inflated.

### 2.4 DIF [book p. 23, 212]
- Book: DIF is "an item-by-group interaction", groups are "model families, architectures, or training paradigms"; methods Mantel-Haenszel, logistic regression, IRT tests in 5.11.1. Counterfactual form: would item i's response differ if the model were in the other group at the same theta. Stratify on total score. [book pp. 23, 212]
- Ours: DIF is not used as an analysis. Five models are too few to stratify on total score, and the same models appear in both conditions. The item-level contrast is carried by the per-model paired gap. See book_reliability_dif_and_factors.md.

## 3. Chapter 9: the rendering as an intervention

### 3.1 How to state it
- Book hierarchy: association P(Y|X), intervention P(Y|do(X=x)), counterfactual P(Y_x|X=x'). "Most benchmark analyses operate at Level 1" while the claims wanted are Level 2 or 3. [book pp. 209-210]
- Rule: a score difference is causal only if "all paths from the data-generating process to Y that do not pass through theta are blocked"; named unblocked paths: training overlap, prompt formatting, evaluation order. [book p. 212]; valid iff the only systematic path passes through theta [book p. 211].
- [ours] Methods wording: "The condition R in {text, image at 10 px, 12 px, 14 px} is assigned by us to every (model, item), so the comparison is an intervention contrast (level 2). Item, task text, wrapper, instruction text, decoding settings, tests and model weights are held fixed; only the format of the repository context changes." Add: R is a bundle (modality, token count, layout, encoder path); the estimate is the total effect of the bundle, not of "modality" in isolation.

### 3.2 Estimand
- Book gives none (see section 0). The book's closest structure is the treatment facet: log P(Y=1)/P(Y=0) = theta_i - beta_j + tau_t, with theta_i x tau_t "heterogeneous treatment effects". [book p. 44, p. 46]. Caution: there the subjects are humans and the target is the effect of AI help; ours are models and the treatment is input format. [book p. 44]
- [ours] Defensible choice: per-model contrast, delta_m = mean over items of (Y_m,i(image) - Y_m,i(text)) on binary pass, with a project-clustered interval (Miller 2024, not read from the book). Heterogeneity across models is read from the per-model gaps and from the binomial GLMM with condition as a facet; a pooled contrast is not a common effect.
- Variance accounting [ours]: because delta_m is a fixed-item average, items are the population unit; runs are nested replicates and are averaged inside each cell before the contrast. The book's reliability chapter measures run noise as test-retest error. [book p. 147]
- Aggregation rule must be stated: mean over the 3 runs, not best-of-3. The book makes the same point for red-teaming: comparing Top-1-of-K with one-shot "is not comparing model safety ... it is comparing estimands". [book p. 285]; checklist 13.5.4 [book p. 314]. Our use is by analogy only.

### 3.3 Paired / within-item design
- Book: paired response matrices give Y_ij^(t) for the same subject and item under condition t; treatment is a facet. [book p. 44]. Chapter 9 notes the same-item pair is not a true counterfactual (individual counterfactuals are level 3, p. 209). [ours] Same item x same model x two conditions is the empirical stand-in for the counterfactual, with runs providing the noise floor for the stand-in.
- Back-door: Z must contain no descendant of X and block all back-door paths. [book p. 211]. Since R is assigned by design, no adjustment is needed; if some items are dropped in a condition (images too large, context exceeds window), compare on the common set and report counts. [ours]
- [ours] Do not adjust for token count or image size as a covariate: they are descendants of R, so the book's criterion (i) forbids conditioning on them when estimating the total effect. Use them only for mediation-style description or as a reported covariate in a separate exploratory model.

### 3.4 Confounds that change with modality
Book silent on image resolution and token count (section 0). From its rules:
- Token count / prompt length is an observed N: "control for it or randomize it" [book p. 21]. It cannot be fixed while keeping the intervention. Report per-model tokens per condition (tokenizers differ, book p. 21 lists tokenization artifacts) and state that effects are bundled with length.
- Resolution and font size: the 10, 12 and 14 px conditions are explicit factor levels (this is the book's "control for it"), and are the place to detect a threshold where reading fails.
- Distribution shift view (9.3): a new renderer or model version is concept drift, P(Y|X) changes, "old estimates do not carry over" [book p. 214]. Pin and publish render parameters and versions.

### 3.5 Section 9.6 causal audit [book pp. 229-230]
Five steps: draw DAG; check shift; doubly robust (DR) estimate; conformal intervals; diagnose contamination by pre/post cutoff split with item-fit. Steps 3 and 4 (DR, conformal) are not needed for an in-sample contrast. Steps 1, 2, 5 map to our DAG, content-validity limit, and contamination flag. Step 1 for us: D -> Y (memorization), F -> Y (wrapper), R -> Y (intervention), A x R (model by modality interaction).

## 4. Temperature and repeated runs

- Book advice against our choice: "score at temperature 0 to remove sampling stochasticity" [book p. 146]; Principle 5, "Control what can be controlled ... Score at temperature 0, randomize and average over prompt formats ... these eliminate sources of variability rather than averaging over them." [book p. 167]
- Book support for our choice: "A stateless model queried at sampling temperature > 0 can be given the same item T times with genuinely independent responses ... and T can be made large", making p_ij observable [book p. 71]; test-retest by "re-running at temperature > 0" [book p. 147]; sampling stochasticity is the analogue of test-retest error and "Replicated trials make it possible to measure this run-to-run noise and average it down" [book p. 115]. Chapter 6: stochastic evaluation "may need multiple samples per item" [book p. 182].
- What the methods section must say [ours]:
  1. T 0.7 is deliberate: we need repeated runs to estimate run noise, and greedy decoding would make runs identical and the run component unidentifiable. Acknowledge that the book's Principle 5 prefers T 0 for a point estimate.
  2. The reported contrast is a mean over 3 runs (a D-study on the first block of 200 DevEval and 40 CoderUJB items may cut this to 2); the D-study quantifies how much the run-averaged result still varies. If the run variance component is small relative to item variance, T 0 would have sufficed; say what the D-study showed.
  3. One T for every model is not one comparable setting across model families (T 0.7 means different entropy per model). Treat as a limitation; same sampling parameters are held across conditions, which is what matters for the contrast.
  4. Seeds: record per-run seeds, as vLLM nondeterminism can add noise beyond sampling.
  5. T affects text and image conditions possibly unequally (image runs may be noisier), so run variance is itself reported per condition.

## 5. Section 13.5 checklist, verbatim-ish, with status for our design

Pages 313-314 contain items; 13.5.5 is on p. 314. Status: Y yes, P partly, N no.

### 13.5.1 Construct Definition [book p. 313]
1. "Write an explicit construct definition: what is the benchmark intended to measure, and what is it not intended to measure?" Y (coding from image-rendered repository context, reading included). Needs the "not intended to measure" sentence: not OCR alone, not repository-scale agentic work, not general coding.
2. "Specify the content domain and develop a test blueprint mapping sub-domains to item counts (Chapter 1)." P. Blueprint by benchmark, language, repo, context length; no expert sub-domain taxonomy.
3. "Distinguish between the construct (latent ability) and the indicator (observed score). A benchmark score is evidence about ability, not ability itself (Chapter 3)." Y. Binary pass is the indicator; contamination flag and reading effect are the gap between the two.

### 13.5.2 Item Development and Calibration [p. 313]
4. "Calibrate items using IRT: estimate difficulty, discrimination, and (if applicable) guessing ... on a diverse set of models." N. 5 models is too few for IRT calibration, and a third of CoderUJB items and most DevEval items are all-fail or all-pass, so difficulty is unidentified for them. Item effects enter the GLMM as nuisance terms.
5. "Screen for problematic items using item-total correlations, tetrachoric correlations, and fit statistics. Remove or revise items that misfit." P. Compute and report; every item is used, so no removal. Say so and give a sensitivity analysis excluding zero-variance items.
6. "Check for DIF: do items function differently across model families, sizes, or training paradigms? Differential functioning may indicate construct-irrelevant variance (Chapter 1)." N. Not used with 5 models (see 2.4).
7. "Audit item content for errors: incorrect keys, ambiguous wording, grading bugs, culturally-embedded assumptions." P. Gold check done on 30 calibration items for each benchmark (repo history); not a full audit. Items nobody passes may be grading bugs, so check a sample of all-fail items.

### 13.5.3 Evaluation Design [pp. 313-314]
8. "Choose the response format (binary, probability, preference, rubric) that best captures the construct. Binary ... discard[s] information; empirical probabilities and rubric scores preserve richer signals." Y with a stated cost: the outcome is binary pass (all target tests pass), which discards the partial-credit information the book mentions. Repeated runs recover some of it as a per-item pass rate.
9. "Consider adaptive testing ..." N, not applicable (all items used).
10. "For judge-based evaluation, design the rating protocol ..." Not applicable (unit tests).
11. "Run a D-study to allocate the evaluation budget optimally across items, judges, and replications (Chapter 5)." P. The D-study on the first block of 200 DevEval and 40 CoderUJB items is the planned version (UFM-17).

### 13.5.4 Analysis and Reporting [p. 314]
12. "Report confidence intervals, not just point estimates. ... models whose scores overlap within +/-2 x SEM may not be meaningfully different." Y (project-clustered interval on the per-model gap) plus SEM per condition.
13. "Report the reliability of the evaluation (Cronbach's alpha, G-coefficient, or IRT-based conditional reliability). If reliability is low, ranking differences are uninterpretable." P. The book's G is about ranking persons (see book_gtheory_and_run_sizing.md), so say what it does and does not support.
14. Red-teaming aggregation rule. Not applicable, but analogous: state mean-of-3 aggregation (section 3.2).
15. Judge inter-rater agreement. Not applicable.

### 13.5.5 Validity and Generalization [p. 314]
16. "Assess content validity: does the item pool representatively sample the intended construct domain?" P (section 1).
17. "Assess construct validity: does dimensionality analysis support the intended interpretation? Do scores correlate with external criteria?" P. No dimensionality analysis is planned; external criterion: text-condition scores, and the text-vs-image agreement of item pass rates as descriptive convergent evidence.
18. "Consider distribution shift: will the evaluation generalize to the deployment context? If not, apply importance weighting or DR corrections (Chapter 9)." P. Discuss only; report effect by item difficulty and context length so readers can reweight.
19. "Document known validity threats and limitations. ... transparency about limitations is itself a form of quality assurance." Y (this is the limitations section).

### 13.5.6 Maintenance and Monitoring [p. 314]
20. "Monitor for benchmark saturation: when the top models all score above 95%, the benchmark no longer discriminates." Y in the opposite direction: floor effects (a third of CoderUJB, most of DevEval all-fail or all-pass). Report share of items with no variance.
21. "Monitor for contamination: periodically check ... using the diagnostics from Chapter 1." P (section 2.3).
22. "Recalibrate item parameters periodically." N, one-shot study; say so.
23. "Maintain a living item bank: retire compromised items, add new items, and recalibrate regularly." N. Static public benchmarks.

Count over the 23 numbered lines: Y 6 (1, 3, 8, 12, 19, 20), P 9 (2, 5, 7, 11, 13, 16, 17, 18, 21), N 5 (4, 6, 9, 22, 23), not applicable 3 (10, 14, 15). Item 14 is not applicable but a mean-of-3 statement is still required. Recount if items are reclassified.

### 11.9.1 Three properties of a durable evaluator [book p. 275]
- Validity: "The score carries its intended construct meaning: it tracks C, not merely the distribution D that operationalizes it", secured by publishing the construct and proxies (11.6) [book p. 275, p. 264]. Ours: P. We publish the construct; two public benchmarks function as proxies for one construct (a mild version of 11.6's protocol: does the text-vs-image gap replicate across CoderUJB and DevEval?).
- Durability: "stays informative as it is optimized against, because D stays private". Ours: N. Both benchmarks are public and static; Table 11.3 lists "static benchmark" as "- (fails)". [book p. 274]
- Faithful execution: "The evaluator runs exactly the announced procedure ... no after-the-fact adjustment." [book p. 275]. Ours: Y if the analysis plan is frozen before the main run and deviations logged. Use as the argument for pre-specifying the estimand and the contamination subset.

## 6. Points that complicate the design

1. T 0.7 vs book Principle 5 and p. 146 (section 4). Not a contradiction of the design, but needs an explicit methods paragraph.
2. The contamination "shared across conditions" argument is not in the book and is only valid in the additive case; claim "shifts difficulty and may compress the gap", not "leaves the contrast unaffected" (section 2.3).
3. Book has no estimand guidance for the contrast; do not cite it as supporting ATE or per-model choice (section 0).
4. Book G-coefficient is for ranking subjects; the text-vs-image contrast is a difference estimand (see book_gtheory_and_run_sizing.md). Do not report G as "reliability of the gap".
5. With all-fail and all-pass items, IRT calibration (13.5.2 first item) is not estimable for much of DevEval; report the Rasch-based checklist items as not done or limited.
6. Durability (11.9.1) fails by construction; say so.
