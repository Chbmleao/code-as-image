# Book notes: Chapter 3 (MODELS), Rasch and IRT

Source: Truong, Sang T. and Koyejo, Sanmi. AI Measurement Science, 2026. Chapter 3, printed pp. 61-79 (PDF page numbers matched printed numbers in the pages I read). Sections read: 3.1 to 3.6 in full. Exercises (3.7, p. 79 onward) only skimmed at the top; Bibliographic Notes (3.8) not read. I did not read the end of 3.4 (roughly the last third of p. 70).

Naming note: the book calls 3.6 "The n-Parameter Logistic Model" (n, not K), with item vector beta_j = (beta_j1, ..., beta_jn).

Marking convention: text under "From the book" is what the chapter says. Text under "How it applies to our project" is my own reasoning, not the book's. Chapter 3 does not cover many-facet Rasch or estimation (the book says estimation is Chapter 4), so the MFRM parts below are my extrapolation from the plain Rasch model and are unverified against the book.

Notation: theta_i ability of model i, beta_j difficulty of item j, Y_ij binary response, sigma(z) = 1/(1+e^-z).

---

## 3.1 What Does It Mean to Measure? (pp. 62-65)

From the book:
- Measurement is a homomorphism phi from an empirical relational structure (objects, order, maybe concatenation) into the reals: a >= b iff phi(a) >= phi(b), and phi(a o b) = phi(a) + phi(b) (p. 63).
- A representation theorem says axioms on observable relations guarantee such a phi exists. A uniqueness theorem gives the admissible transformations, which fixes the scale type (p. 63-64).
- Ordinal: any strictly increasing transformation. Interval: positive affine, phi -> a*phi + b. Ratio: phi -> a*phi (true zero) (p. 64).
- A statement is meaningful only if its truth is invariant under the admissible transformations. "The gap A to B exceeds the gap C to D" is meaningful on interval, not ordinal (p. 64).
- Accuracy of 0.86 is a ratio-scale count of correct answers, but as a measure of ability it is at best interval, and without a fitted model only ordinal (p. 64).
- Ability has no concatenation operation, so the best it can reach is interval, via conjoint measurement. For humans the axioms can only be assumed, since the response probability is never observed. For AI systems they are testable, because response probability can be estimated by repeated sampling (p. 65).

How it applies to our project:
- Our headline quantity "accuracy drop between Text and image conditions" is a difference of accuracies. The book's point is that such differences are only licensed as meaningful if the interval structure holds. Report raw accuracy differences as descriptive, and treat logit differences from the Rasch fit as the interval-scale claim, conditional on passing the checks in 3.5.
- Token savings are a true ratio-scale quantity (counts), so "X% fewer tokens" needs no such justification. Only the accuracy side does.

---

## 3.2 Additive Conjoint Measurement (pp. 65-67)

From the book:
- Two conjoint factors A (models) and X (items); observe an order on A x X by how likely a correct response is (p. 65).
- Single cancellation (independence): the model ranking is the same whichever item is fixed, and vice versa. A model-by-item interaction violates it (p. 65).
- Double cancellation (Thomsen): (a1,x2) >= (a2,x1) and (a2,x3) >= (a3,x2) imply (a1,x3) >= (a3,x1). The book walks through this on a 3x3 grid (p. 66-67).
- Restricted solvability and the Archimedean condition are idealizations, not separately testable on coarse data (p. 66).
- Additive representation theorem: (a,x) >= (a',x') iff f(a)+g(x) >= f(a')+g(x'); f and g are interval scales with a common unit, unique up to a common positive affine map (p. 66).
- Putting the additive index in a monotone link gives P(Y_ij = 1) = Phi(theta_i - beta_j). Logistic Phi is Rasch; normal CDF is probit (p. 67).
- Specific objectivity: in Rasch the odds ratio P(Y_ij=1)/P(Y_ij=0) divided by the same for model k equals exp(theta_i - theta_k), and beta_j drops out. This gives test-free comparison and subject-free calibration (p. 67).

Assumptions: additivity of ability and difficulty in some monotone link, no model-by-item interaction, one dimension.

How it applies to our project:
- Single cancellation is the assumption that a model that is better than another under Text is also better under image conditions on every item. If one VLM handles rendered text much worse than another does, that is exactly an interaction, and it is what our research question probes. So a condition-by-model interaction is both a substantive finding and a violation of the strict additive model. Plan to test it explicitly rather than assume it away (see 3.5).
- Specific objectivity is what would let us compare models across different item subsets (for example if some items get dropped in one font-size condition). It only holds if Rasch fits.

---

## 3.3 Sufficiency and Rasch Model (pp. 67-69) [in depth]

From the book:
- Model: P(Y_ij = 1 | theta_i, beta_j) = sigma(theta_i - beta_j) (p. 67).
- Local independence: P(Y_i1..Y_iM | theta_i, beta) = product over j of P(Y_ij | theta_i, beta_j). Testable via residual correlations between item pairs. Violated by shared context, such as items on the same passage, dataset split, or few-shot template (p. 68).
- Sufficiency: reporting an average score is justified only if the sum score S_i = sum_j Y_ij carries all the information about theta_i (p. 67).
- Theorem (p. 69): among additive models P = Phi(theta_i - beta_j) with strictly increasing Phi, sum-score sufficiency holds iff Phi is logistic, i.e. the model is Rasch (Andersen 1973; Fischer and Molenaar 1995). The converse holds too.
- Proof sketch (p. 69): with local independence the log-likelihood splits into a term in sum_j Y_ij * logit Phi(theta_i - beta_j) plus a term free of which items were right. S_i is sufficient iff logit Phi(theta_i - beta_j) = c*theta_i + d_j with a common slope c, forcing logit Phi to be linear. Under Rasch, P(Y_i | theta_i, beta) = exp(theta_i*S_i - sum_j Y_ij*beta_j) / prod_j(1 + exp(theta_i - beta_j)), which factors into a function of (S_i, theta_i) and a function of (Y_i, beta).
- With per-item discrimination (2PL) a discrimination-weighted score is sufficient instead of the raw count (p. 69).
- Consequence stated by the book: before trusting average benchmark scores, test whether Rasch fits (p. 69).
- Diagnostic application (Truong et al. 2025, p. 75): under Rasch all inter-item tetrachoric correlations and all item-total correlations should be non-negative. Items with negative values or low Mokken scalability are flagged as possibly invalid. The book reports up to 84% precision at the top-50 flagged items across nine benchmarks (p. 75). Flagged items should be inspected, not deleted blindly, since low correlation can also mark a real second skill (p. 76).

How it applies to our project:
- Our data are item-level pass/fail from unit tests, which is the Y_ij the model wants. Sufficiency says: if Rasch holds, each model's number of items passed (within a condition) is all we need to estimate its ability, and the item-by-item pattern adds nothing. Conversely, if we report mean pass rate per model and condition, we are implicitly asserting Rasch. So the mean-accuracy table in the report should be paired with a Rasch fit check.
- Local independence is a real risk for us. Items drawn from the same repository or file, or several turns of the same conversation, share context. Items rendered in the same image style share a rendering. Group items by source and check residual correlations; if problems appear, that argues against treating them as independent Bernoulli trials and inflates the apparent precision of standard errors.
- Cheap first diagnostic (from the book's Truong et al. recipe): compute leave-one-out item-total correlation per item and flag items with values at or below zero. For unit-test-scored coding items this will also catch broken tests or miskeyed items before we blame the VLM. Caveat: with only 3 to 5 models, the total score takes very few values, so item-total correlations will be noisy and coarse. Treat as a screen, not a verdict.
- Adding condition and font as facets (my extrapolation, not in Chapter 3): the Rasch logit becomes theta_i - beta_j - c_k - f_l, where c_k is a condition effect (Text, Mixed, All image) and f_l a font-size or characters-per-row effect. Each extra facet enters additively in the logit, which is the same additive-conjoint structure extended to more than two factors. Sufficiency then applies to the facet-specific sums. Identification needs sum-to-zero (or one reference level) constraints per facet, and per-model-by-condition ability, which the project wants, corresponds to letting theta vary by (model, condition) rather than adding a separate c_k. These are two different parameterizations and the report should say which is used. The book defers estimation to Chapter 4, so check there or a many-facet Rasch reference for the fitting method and standard errors.
- Because Chapter 3 says nothing about standard errors, do not cite it for them.

---

## 3.4 Reinterpreting the Second Conjoint Factor (pp. 69-70) [light]

From the book:
- Bradley-Terry: P(i beats j) = sigma(theta_i - theta_j). It is the Rasch structure with the item slot filled by a second competitor drawn from the same pool, so strengths inherit the interval scale (p. 70).
- Elo is Bradley-Terry with online updates: R_new = R + K(y - E), with E = sigma((R_j - R_i)/400 * ln 10) (p. 70). Chatbot Arena uses this (p. 70).
- Intransitive, "rock-paper-scissors" capabilities break the single-strength ranking (p. 70).

How it applies to our project:
- Only marginally relevant. We score against unit tests, not pairwise preference, so Bradley-Terry is not our model. One indirect use: conditions could be compared pairwise (Text beats Mixed on a given item), but per-item pass/fail under Rasch with a condition facet is more direct.

---

## 3.5 Testing for an Interval Scale (pp. 71-76)

From the book:
- For AI, a stateless model sampled at temperature > 0 can be queried T times on the same item, so p_hat_ij = (1/T) sum_t Y_ijt estimates p_ij directly. We then have a real-valued model x item array and can test conjoint structure: additive structure holds iff there is a monotone Phi with Phi^-1(p_ij) = theta_i + delta_j, equivalently the array satisfies double cancellation (p. 71).
- Rasch bundles two assumptions, an additive index and a logistic shape. Bad Rasch fit cannot say which failed (p. 71).
- Nonparametric additive model (ADISOP, Scheiblechner 1999): P(Y_ij = 1) = F(theta_i - beta_j) with F an unknown non-decreasing link. Estimated by isotonic regression (pool-adjacent-violators), alternating with updates of theta and beta (p. 72).
- Reading the residual (p. 72): small residual but poor Rasch fit means additive and interval still hold, only the logistic shape was wrong (you give up sum-score sufficiency). Large residual after the best monotone F means additive conjoint measurement is rejected.
- The isotonic model always fits at least as well as Rasch, so a smaller residual alone proves nothing. The sharp comparison is against 2PL, which adds a slope per item. If the parallel single-index fit suffices, additivity holds. If per-item slopes are needed, the unit of theta is item-dependent and additivity fails (p. 72).
- Ladder of weakening commitment: Rasch, then nonparametric additive (still interval), then doubly-monotone (non-crossing curves, ordinal), then monotone (p. 72). Probit is a cheap stand-in that changes only the link, since isotonic tools have limited software (p. 72).
- What failure means (p. 73): a verdict on this item set crossed with these models, not on the instrument in general. If models rank the same way on every item but spacings do not align, you keep an ordinal ranking and lose only interval status. Ranking itself fails only when models reorder across items. Two causes: bad items (curation may restore additivity) or genuine multidimensionality (restrict the claim or use a multidimensional model, Section 7.2).
- Three caveats (p. 73): (1) the link is free, so passing gives additive conjoint measurement, not Rasch specifically; (2) p_hat has O(1/sqrt(T)) error, so the axioms need an order-restricted probabilistic test (Karabatsos 2001; Scheiblechner 1995), and raising T is the remedy; (3) you can almost always force additivity by deleting enough items, so a pass counts only if curation was principled.
- Passing certifies quantitative structure, not validity. The book's example: a scraped-coding benchmark can be additive in memorization, not coding ability (p. 73).
- The Rasch model is the probabilistic analogue of conjoint measurement, not a deduction from it (Brogden 1977; Perline et al. 1979). Bridging deterministic axioms and stochastic responses is contested (Michell 2008; Kyngdon 2008) (p. 75).
- Visual check (p. 73-74): sort the model x item matrix by row and column totals. A near-triangular gradient is the signature of additive structure.

How it applies to our project:
- This is the section that answers "can we claim an interval scale". Our design suits it: we can sample each (model, item, condition) cell T times with local Ollama models at temperature > 0, so p_hat_ij is directly available. The cost is compute: cells = models x items x conditions x font x chars-per-row settings, times T. Decide T early, since the error is 1/sqrt(T).
- Sorted-matrix plot per condition is a cheap first look and needs no fitting.
- Practical limit: with 3 to 5 models, double cancellation has very few triples (a 3x3 grid uses 3 models and 3 items, and there are many item triples, but only 1 to 10 model triples). The test has power mostly across items, less across models. State that limitation in the report.
- Testing the interaction of interest: treat condition as a second factor and ask whether the additive structure survives across conditions. If the ranking of models is stable across Text, Mixed and All image but the gaps change, the book's language says we keep ordinal ranking and may lose interval status. If models reorder across conditions, single cancellation fails and one "ability" per model is not defined; then per-condition abilities are the honest report. This is my reading of the book's failure discussion applied to the condition facet.
- Because passing needs principled curation (caveat 3), decide item-exclusion rules before looking at fit results, and record them.
- Validity caveat applies directly: unit-test pass rate on public coding problems may reflect memorization. Consider this when choosing items.
- Fitting ADISOP needs custom code (the book says software is limited). Probit Rasch is the suggested cheap substitute and can be fit with standard GLM tools.

---

## 3.6 The n-Parameter Logistic Model (pp. 76-78)

From the book:
- Motivation: when the data do not fit Rasch, even the isotonic version, no interval scale can be licensed, but a useful ordinal scale can still be built with a richer class (p. 76).
- Item vector beta_j in R^n. Rasch is n = 1. The plate diagram is identical to Rasch (p. 77).
- 2PL: P(Y_ij = 1 | theta_i, beta_j) = sigma(beta_j2 * (theta_i - beta_j1)), where beta_j1 is difficulty and beta_j2 is discrimination. Higher discrimination gives a steeper item characteristic curve (p. 77).
- Scale consequence (p. 77): the log-odds gap between models i and k on item j is beta_j2 * (theta_i - theta_k). Sign is the same on every item, so single cancellation and consistent ordering survive. Magnitude is scaled per item, so the unit of theta is item-dependent, double cancellation fails, and theta is not a fundamental additive conjoint interval scale. It is identified only up to positive affine transformation, fixed by convention (typically theta ~ N(0,1)), so it is interval by stipulation. Rasch is the case beta_j2 = 1 for all items. The book frames this as a prescriptive (Rasch school) versus descriptive (general IRT) trade-off (p. 77).
- 3PL: P = beta_j3 + (1 - beta_j3) * sigma(beta_j2 * (theta_i - beta_j1)), with guessing beta_j3 in [0,1]. For 4-option multiple choice, about 0.25 (p. 77).

Assumptions: same local independence and unidimensionality as Rasch, plus a normal prior or a convention to pin the scale for 2PL and 3PL.

How it applies to our project:
- 3PL is not needed. Our items are coding problems scored by unit tests, not multiple choice, so the chance floor is near zero and a guessing parameter has no interpretation. Skip it.
- 2PL is not feasible with 3 to 5 models in my judgment (this is inference, the book gives no sample-size guidance in Chapter 3). A discrimination parameter per item is estimated from how sharply pass rate changes with ability, and with 3 to 5 distinct ability levels each item has 3 to 5 Bernoulli cells (times T repeats, but repeats do not add ability levels). The slope would be very poorly identified and the normal prior on theta is hard to justify with so few models. Chapter 4 may give estimation details; I have not read it.
- Use 2PL, if at all, as a diagnostic contrast rather than the main model: the book says the sharp test of additivity is Rasch/isotonic versus 2PL (p. 72). With so few models, a likelihood comparison would have little power, so a non-significant result is weak evidence.
- Recommended stance for the report: fit Rasch (with facets) as primary. If fit is poor, fall back to the ordinal claim (rankings and pass rates with uncertainty) instead of a 2PL, and say interval status was not established.

---

## Summary checklist for the project

1. State that reported accuracy differences are interval-meaningful only if additivity is tested (3.1, 3.5).
2. Sample each cell T times to get p_hat and test additivity (3.5); choose T with the 1/sqrt(T) error in mind.
3. Screen items with item-total correlation and residual correlations before fitting (3.3); group items by source for local independence.
4. Fit Rasch with condition and font as additive terms in the logit (my extrapolation; estimation methods are Chapter 4).
5. Check model-by-condition interaction: reordering across conditions breaks single cancellation.
6. Skip 3PL; treat 2PL as at most a weak diagnostic given 3 to 5 models.
7. Do not treat passing the additivity test as proof of coding-ability validity (p. 73).
