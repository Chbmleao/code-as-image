# Book Chapter 5: Reliability and Generalizability Theory (notes)

Reference: Truong, Sang T. and Koyejo, Sanmi. AI Measurement Science, 2026. Chapter 5, Reliability.
Sections covered: 5.1 (light), 5.2, 5.3 (light), 5.4 (light, Bayesian focus), 5.6, 5.7.
Page numbers are the printed book pages (running header), not PDF pages. Section 5.5 (method of
moments) was not read; where these sections lean on it, I say so.

Notation used by the book in this chapter: p = person (in AI evaluation, a model), i = item,
r = rater, N = number of persons/models, M = number of items. Latent (logit-scale) effects:
theta_i ability, beta_j difficulty, gamma_ij person-by-item interaction.

## 5.1 Sources of Variability in AI Measurement (pp. 114-118)

Main idea. Reliability is the consistency or reproducibility of a measurement procedure. It is not
accuracy: a thermometer that always reads two degrees high is reliable but inaccurate (p. 115).
Reliability is necessary for validity: if repeating the evaluation gives different results, the
score is noise (p. 115). The opening example is a model ranking that reshuffles when a colleague
reruns the same evaluation with small procedural differences (pp. 114-115).

The book names four mechanisms of variability (pp. 115-116):

1. Prompt sensitivity. Prompt format, answer format, few-shot order shift results even at
   temperature 0. Analogue: the test-format effect in educational testing.
2. Sampling stochasticity. At temperature > 0 the same prompt gives different outputs per run.
   Analogue: classical test-retest error. Small for binary items answered deterministically, but
   open-ended generations (the book lists code) can score differently across runs. Replicated
   trials let you measure the run-to-run noise and average it down.
3. Annotator and judge disagreement. Needs its own facet (Section 5.6); LLM judges are in 5.9.
4. Benchmark sampling. A benchmark is a sample from a larger domain (the book's example: a
   200-item coding benchmark is one draw from all coding problems). Longer tests are more
   reliable (Spearman-Brown, Section 5.10, not read).

The simulation on pp. 116-118 (20 models, 50 items, knobs for prompt, rater, stochastic noise)
shows that which mechanism dominates decides the remedy: "adding items does nothing if the problem
is rater disagreement" (p. 115). In that toy run, rater disagreement dominated, prompt and item
perturbations averaged out over 50 items, and single-trial stochasticity was small. Models of
similar ability swap ranks between runs, and their 95% intervals overlap (p. 118). That toy result
is a simulation with planted values, not evidence about any real benchmark.

How it applies to our project. Our mechanisms map as follows: prompt sensitivity is the
condition (Text / Mixed / All image) and font size; sampling stochasticity is the run facet
(temperature > 0 code generation; the book explicitly lists code as a case where runs differ);
benchmark sampling is the item facet; there is no rater facet because unit tests score the output
automatically. Dropping the rater facet removes the mechanism the book's toy example found
dominant, so our dominant error source is more likely item sampling and run noise. That is a
hypothesis for the G-study to check, not a finding.

## 5.2 From the Response Model to Variance Components (pp. 118-120)

Motivation. We rarely care about these items, this judge, this day; we care about the universe of
items, judges and occasions we might have used. A score is dependable only insofar as it
generalizes from sample to universe. Each source of variation is a way the sample can misrepresent
the universe, so attributing variance quantifies the threat to generalization (p. 118). The
generalizability coefficient is the share of score variance carried by genuine differences between
subjects rather than by luck of which items or judges were drawn (pp. 118-119).

Response model (Rasch plus interaction), Y_ij in {0,1}, person i (i = 1..N), item j (j = 1..M):

    logit P(Y_ij = 1) = theta_i - beta_j + gamma_ij                          (5.1)
    P_ij = sigma(theta_i - beta_j + gamma_ij)

gamma_ij lets a particular model be unusually good or bad on a particular item beyond what ability
and difficulty predict (memorization of one question, an item idiosyncratically easy for one model
family) (p. 119).

Random-effects populations (both persons and items drawn from populations):

    theta_i ~ N(0, sigma_p^2),  beta_j ~ N(0, sigma_i^2),  gamma_ij ~ N(0, sigma_pi^2)   (5.2)

Because independent effects add on the log-odds scale:

    Var(theta_I - beta_J + gamma_IJ) = sigma_p^2 + sigma_i^2 + sigma_pi^2   (5.3)

One-facet generalizability coefficient (reliability), idealized on the latent scale:

    rho_eta = sigma_p^2 / (sigma_p^2 + sigma_i^2 + sigma_pi^2)               (5.4)

It is the idealized reliability, what we would get if we observed the log-odds directly. Real
binary responses add irreducible Bernoulli sampling error, which the book carries through the
sigmoid in Section 5.5 (not read) (p. 119).

Extension to more facets. For models (p), items (i), raters (r), each facet brings a main effect
and interactions, and all add on the log-odds scale (pp. 119-120):

    Var(eta) = sigma_p^2 + sigma_i^2 + sigma_r^2 + sigma_pi^2 + sigma_pr^2 + sigma_ir^2 + sigma_pir^2   (5.5)

The first three terms are Eq. 5.3, the rest are what the rater adds. Every mechanism of 5.1 is one
component: rater disagreement is sigma_r^2 and sigma_pr^2, and "run-to-run drift adds an occasion
facet" (p. 120). Categorical rater verdicts are instead summarized by Cohen's kappa (Section 5.9,
not read).

Design points (crossed vs nested, fixed vs random). Section 5.2 assumes a fully crossed design
with all facets random (persons, items, raters drawn from populations). It does not discuss nested
or fixed facets; those choices appear only implicitly in 5.6 and 5.7 (see below).

How it applies to our project. The book's "person" is the model. Ours differs in an important way:
the research question is about a condition effect, and the models are few (3 to 5), so treating
model as a random facet with a variance component sigma_p^2 is weakly supported by so few draws.
That matches the plan to keep model fixed for the main test. Sketch of the components for a
one-model slice (model fixed), with item i random, run r random, condition c fixed, font f fixed:

    item main effect sigma_i^2, item-by-condition sigma_ic^2, item-by-font, item-by-run,
    residual (item x condition x run and higher, confounded with Bernoulli noise if 1 run/cell).

In book terms, "person" (the object of measurement) is replaced by whatever we want to compare.
For "does accuracy drop under images", the object of measurement is the condition contrast, and
the error terms are those that vary with items and runs. Note this re-mapping of the book's
p x i x r layout onto condition is my own adaptation, not something Section 5.2 spells out. Also,
unit-test pass/fail is binary, so the latent-scale coefficient in Eq. 5.4 is the idealized one;
if scored as pass rate over several tests per item, the scale differs and needs checking.

## 5.3 Variance Estimation via Plug-in Method (pp. 120-124), light

Estimand is sigma_p^2, sigma_i^2, sigma_pi^2 (Eq. 5.2). Plug-in: fit Rasch abilities theta_hat_i by
maximum likelihood with difficulties fixed, take their empirical variance (p. 120).

Bias. theta_hat_i = theta_i + e_i, Var(e_i) = SE(theta_hat_i)^2, independent of theta_i, so

    Var(theta_hat_i) = sigma_p^2 + SE(theta_hat_i)^2

The naive empirical variance targets sigma_p^2 + mean(SE^2), so it overstates the between-model
variance. Bias-corrected estimate:

    sigma_p^2_hat = (1/N) sum_i (theta_hat_i - mean(theta_hat))^2 - mean(SE^2)

which the book says is the method-of-moments estimator of 5.5 on the logit scale (p. 121).
Standard error from Fisher information: SE(theta_hat_i) = ( sum_j P_ij_hat (1 - P_ij_hat) )^(-1/2).
Bias shrinks like 1/M. For sigma_pi^2 the confound with the residual never disappears without
replicated trials (p. 121).

Conditional reliability (Eq. 5.6, p. 123):

    rho(theta) = 1 - 1 / (I(theta) * sigma_p^2),   I(theta) = sum_j P_j(theta)(1 - P_j(theta))

A single overall rho hides saturation: when P_j(theta) -> 1 for all items, I(theta) -> 0 and
rho(theta) collapses for frontier models. The fix is targeted item difficulty (Chapter 6).

How it applies to our project. Two lessons. First, with very few models the between-model spread is
poorly determined and any naive variance of per-model fits will be inflated by estimation error.
Second, conditional reliability warns about ceiling and floor items: small local VLMs may fail
most coding items, or pass only trivial ones, which makes I(theta) small. Reporting pass rates per
model and checking that items are not all near 0 or 1 is worthwhile before trusting a single
reliability figure.

## 5.4 Variance Estimation via Bayesian Method (pp. 124-126), light

Framing. The random-effects model (Eq. 5.2) is already a Bayesian hierarchical model: theta_i ~
N(0, sigma_p^2) is a prior on each ability and the variance components are hyperparameters (p. 124).
Two ways to treat the hyperparameters:

- Empirical Bayes (marginal maximum likelihood). Integrate abilities out and maximize the
  evidence over the variance:

      L(s^2) = integral [ prod_ij P_ij^Y_ij (1 - P_ij)^(1 - Y_ij) ] p(theta, beta, gamma | s^2) d theta d beta d gamma
      sigma_hat^2 = argmax_{s^2} log L(s^2)

  The Bernoulli noise is inside the likelihood, so no separate residual correction is needed and
  estimates are on the logit scale. With difficulties fixed and abilities random the evidence is a
  product of 1-D integrals that a grid evaluates exactly (pp. 124-125).

- Full Bayes. Put a hyperprior p(s^2) on the variance and report the posterior
  p(s^2 | Y) proportional to L(s^2) p(s^2), summarized by mean and 95% credible interval.
  Empirical Bayes is the special case that keeps only the peak (under a flat hyperprior). Full
  Bayes keeps the spread, "the honest uncertainty about sigma_p^2 from a finite sample". For
  multi-facet models the posterior is sampled by MCMC (NumPyro or PyMC) (p. 125).

In the book's simulation (150 models, 40 items, one binary trial per cell) the posterior for
sigma_p is wide because one binary response per cell is weak evidence (p. 126). The chapter also
says both Bayesian variants, like plug-in, work on the latent scale (p. 126).

How it applies to our project. This is the section that supports the plan to use Bayesian
intervals where model-level variance is reported. With 3 to 5 models, a variance component for the
model facet is estimated from very few groups, so a point estimate (empirical Bayes or REML) will
look precise but rest on almost no information; the full posterior with its credible interval
exposes that. Practical route: a hierarchical logistic model in PyMC or NumPyro with random
effects for item, run, and the interactions we keep, hyperpriors on the standard deviations, and
posterior summaries of each sigma^2 and of derived G values. A caution I take from the book's own
message: the wide interval is the result, not a defect, and should be reported. The book gives no
guidance on hyperprior choice in these sections (it uses a flat hyperprior in the toy case), so
the prior choice for a 3-to-5-model design has to be justified by us and checked with a
sensitivity analysis.

## 5.6 Design for Generalizability (pp. 132-134)

G-study vs D-study. A G-study estimates the variance components from data (method of moments or
REML, Sections 5.5 and 5.4). The D-study, the distinctive step of generalizability theory (Cronbach
et al. 1972), uses the components to design the evaluation: how many items and raters achieve a
target reliability (p. 132).

Formulas as printed for a model x item x rater design (p. 132):

    G = sigma_p^2 / (sigma_p^2 + sigma_rel^2)

    sigma_rel^2 = sigma_pi^2 / n_i + sigma_pr^2 / n_r + sigma_pir,e^2 / (n_i * n_r)

Here sigma_p^2 is true-score (model) variance, sigma_rel^2 is relative error variance, n_i the
number of items, n_r the number of raters. Only interactions with the object of measurement enter
the relative error. The book's simulation takes seven components as given: p=1.0, i=0.5, r=0.3,
pi=0.4, pr=0.3, ir=0.1, residual=0.2 (p. 132), sweeps n_i in 5..50 and n_r in 1..10, and draws
contours at G = 0.80 and 0.90 (p. 133).

Trade-offs (p. 132). If rater variance dominates (sigma_pr^2 large), raising n_r is more
cost-effective than raising n_i; if item sampling variance dominates (sigma_pi^2 large), more items
help more. Beyond a point, adding the cheaper facet stops helping (p. 133).

Costs. With item cost 1 and rater cost 5 in the toy example, the D-study becomes a constrained
optimization: for each budget, pick (n_i, n_r) maximizing G, and find the minimum budget for
G >= 0.90 (pp. 133-134).

Design choices. The book's design is fully crossed (every model sees every item under every
rater). It does not print the absolute error variance or a Phi (dependability) coefficient in this
section; the book only defines the relative-error G. Phi (absolute decisions, which adds main
effects of the facets to the error) is standard in generalizability theory in general but I did not
read it in these pages, so it is not attributed to the book here.

How it applies to our project. Sketch of the G-study. Data: for each of 3 to 5 VLMs, each coding
item is attempted under each condition (Text, Mixed, All image), under each font size for the image
conditions, with several sampled runs per cell. Score: unit-test pass (binary) per attempt.
Facets and treatment:

- model: fixed for the main test (few levels); analyzed one model at a time or as a fixed effect,
  with a separate model-level random-effects analysis reported with Bayesian intervals.
- item: random, crossed with everything (the same items appear in all conditions and fonts).
- condition: fixed (three chosen levels, no interest in generalizing to other conditions).
- font size: fixed, and nested within the image conditions in the obvious layout, since the Text
  condition has no font size. This makes the design not fully crossed; a clean approach is to run
  the condition analysis (Text vs Mixed vs All image at one font) and the font analysis (font
  levels within image conditions) as two linked sub-designs. Book note: this nested and fixed
  treatment is not covered in 5.6; it is our design decision.
- run: random, crossed with items (repeated sampled attempts).

Components to estimate, per model: sigma_i^2, sigma_ic^2 (item difficulty depends on condition),
sigma_if^2, sigma_ir^2 (run-to-run variation per item, which with one run per cell is confounded
with the residual, see 5.7), and the residual. The D-study analogue of the book's formula treats
the item-by-condition interaction and the run terms as error for the condition contrast:

    error variance of a condition contrast roughly  sigma_ic^2 / n_i + sigma_(icr,e)^2 / (n_i * n_r)

so the D-study answers: how many items n_i and runs n_r reach a target precision on the
condition difference (or a target G for detecting a chosen accuracy drop)? If sigma_ic^2 dominates,
more items help and more runs do not; if the residual dominates, extra runs are cheap value. Costs
matter here: a run on a local VLM has a compute cost, and image inputs cost more tokens, so the
cost-optimization idea of pp. 133-134 (choose (n_i, n_r) under a budget) applies directly, with
GPU time as the cost. I have written the error term above by analogy to the book's formula, not
copied from it, and it should be derived properly once the design is frozen.

## 5.7 Model Selection: Which Facets to Control (pp. 134-136)

Main claim. Controlling more sources of variation yields more dependable conclusions and reduces
bias from misattributed variance, but each added term costs identifiability and estimation
variance, so "more is not free" (p. 134).

Identifiability first (p. 134). With one trial per cell, the person-by-item interaction
sigma_pi^2 is perfectly confounded with the Bernoulli residual. "The design decides which models are
even askable." To test an interaction the D-study must budget replicated trials per cell;
otherwise fuse interaction and residual into one term.

Two interactions, two held-out tests (pp. 134-135):
- iid interaction gamma_ij ~ N(0, sigma_pi^2): says nothing about unseen cells (its posterior there
  is the prior), so it is testable only by holding out replicated trials of seen cells.
- structured interaction (unequal discriminations as in 2PL, extra latent dimensions): changes
  predictions for unseen cells, tested by holding out cells (masking schemes, Section 7.5.1, not
  read). The book says this is usually the real question ("is Rasch enough?").

Criterion (pp. 134-135). Held-out likelihood, with three refinements: (i) use the marginal
predictive likelihood with random effects integrated out, not the conditional likelihood at point
estimates (which flatters the richer model); (ii) hold out the right thing (cells vs trials);
(iii) WAIC and PSIS-LOO (Watanabe 2010; Vehtari et al. 2017) approximate the held-out likelihood
cheaply. A likelihood-ratio test of sigma_pi^2 = 0 is a boundary test, with reference law a mixture
(1/2) chi^2_0 + (1/2) chi^2_1 instead of a plain chi^2_1, and is easy to misuse, so the book prefers
cross-validation. Pair with residual diagnostics such as Rasch infit/outfit (Section 3.3).

Simulation result (pp. 135-136): with no real interaction, the main-effects model generalizes
better than the saturated model, badly so at low replication; with a real interaction, the
saturated model needs enough replicated trials before it overtakes the simpler one.

What decides it (p. 136). Select the model against the decision, not against fit in the abstract:
adding sigma_pi^2 lowers bias in the reliability estimate but raises its variance. A term that is
statistically significant but leaves the ranking untouched has not earned its place; one that drops
reliability from 0.9 to 0.6 has.

How it applies to our project. This section bears on which terms to keep in the G-study.
1. Replication decides identifiability. If we run one sample per item per condition, item-by-run
   is confounded with the residual, and item-by-condition cannot be separated from run noise. The
   several runs per item planned in the project are what make sigma_ic^2 separable from noise; the
   book's argument says to budget them for that reason, not only to average noise down.
2. The key candidate term is item-by-condition. If images change which items a model solves (not
   just how many), that shows up in sigma_ic^2 and it should stay in the model; a main-effects-only
   analysis would understate uncertainty on the condition effect. Test it by held-out likelihood
   (PSIS-LOO or WAIC in the Bayesian model, holding out runs, since the iid interaction is only
   testable with replicated trials).
3. Choose terms by their effect on the decision: keep a term if dropping it changes the
   estimated condition drop or its interval materially; drop it if it does not. With small item
   counts, a simpler model can give a steadier conclusion even if slightly biased, per p. 136.
4. Model as a facet: with 3 to 5 models, sigma_p^2 and model-by-condition are barely estimable
   as random components. Keeping model fixed for the main test, and reporting model-level
   variance only with Bayesian credible intervals, is consistent with the book's caution that
   extra terms cost estimation variance. (The book does not say "fix a facet when it has few
   levels" in these pages; that is our inference from the identifiability and variance argument.)

## Summary of the project design implied by these sections (my synthesis)

- G-study: per model, items x conditions x fonts (font nested in image conditions) x runs, binary
  unit-test outcomes, Bayesian hierarchical logistic model with random item, item-by-condition,
  item-by-font, and run/residual terms; report posterior for each variance component and for G.
- D-study: plug posterior draws of the components into a relative-error formula in the style of
  p. 132, sweep n_i and n_r, and report the (n_i, n_r) needed for a target G or target interval
  width on the condition contrast, with a compute-cost constraint as on pp. 133-134.
- Not verified: I did not run any of the book's code or any analysis. The formulas for our
  condition-contrast error variance are an adaptation to be derived and checked, not book text.
