# Methods

The written plan behind the methodology presentation (`presentations/methodology.pdf`). Section
numbers follow the course's detailed-plan template. Last revised on Nov 5, 2026. The reasons for
each revision are in `docs/decisions.md`, and the book and literature notes it draws on are in
`docs/notes/`. The analysis is frozen against this text before any image-condition answer is
graded (see "Reporting and freezing" in 3.3).

## 3. Methods

### 3.1 Design

**Items.** We use two repository-level code benchmarks with long, naturally occurring context.
CoderUJB (Zeng et al. 2024) gives 136 Java items: the model regenerates one method of a Defects4J
project from its doc comment and signature, with the rest of the source file as context. DevEval
(Li et al. 2024) gives 859 Python items from 79 repositories, each asking for one function body
with its repository context. Both sets keep only items whose reference solution passes our grader
and whose prompt is 2k to 12k tokens (Qwen3.5 tokenizer). Every item in both sets is used unless
compute runs short (end of 3.3); the first block in 3.1 is a stratified sample of them.

**Models.** Five open-weight VLMs served with vLLM 0.32.0 on one RTX 5090 each: Qwen2.5-VL 7B,
Qwen3.5 9B and Gemma 4 12B at 16-bit, Qwen3.5 27B and Mistral Small 3.2 24B at 4-bit. Size and
precision are confounded and reported together. The five models are the population of interest,
so model is a fixed factor and no claim is made about VLMs in general.

**Conditions.** Each (model, item) pair is presented in four conditions:

| Condition | Text part of the prompt | Image part |
|---|---|---|
| text | whole prompt (instruction, target signature and doc comment, context) | none |
| image 10 px | task part (instruction, target signature and doc comment) plus one fixed sentence | repository context rendered |
| image 12 px | same | same |
| image 14 px | same | same |

The task part is the benchmark's own text, unchanged, so it is identical in all four conditions and
only the form of the context varies. This matches how context-to-image tools are used (the request
stays text, the context becomes image), and it keeps "finding the task" out of the gap: in the Oct 5
rebuilt pilot, image answers mostly completed the wrong function, and the failures went away once
the prompt named it (pilot/README.md). On 30 calibration items per benchmark the task part is a
median of 3 to 4% of the prompt (about 150 to 180 tokens, at most 12%), estimated from its share of
characters. The fixed sentence, "The code context for this task is in the images. In the images, ⏎
marks a line break.", opens every image-condition prompt and is identical for every item. Each
context code block is replaced by its pages in place, so in DevEval the pages of the code above and
below the target sit under their own headers, as the text prompt has them.

Images are rendered packed in JetBrains Mono: lines flow across rows of 616 px with a visible newline
marker, and leading spaces are kept, so indentation survives. Pages are 616 px wide and at most
1540 px tall; when the context needs more than one page, its rows are spread evenly over the pages
and each page is cut to the height of its rows. The pages are the same images for every model, and
the same on every machine (src/codeimg/render.py). At most 9 pages go in one request (CoderUJB
needs at most 4, 6 and 8 at 10, 12 and 14 px, DevEval 5, 6 and 9), so the image limit drops no
item. Packed rendering is used because the project asks what saving tokens costs:
in the pilot, line-per-row images matched text accuracy but saved almost no tokens on Qwen2.5-VL,
while packed images at 14 px matched text with 64% of the text tokens. We do not designate a primary
size: all three sizes are reported, and the comparison between sizes is itself a result (3.3).

Rendering is an intervention we assign, not an observed attribute, so each image-vs-text difference
is an interventional contrast (book level 2, pp. 209-212). The intervention is a bundle: modality,
token count, page layout and vision encoder change together. We estimate the total effect of the
bundle and do not adjust for token count or page count, which are descendants of the condition
(back-door criterion, book p. 211). The effect is conditional on this renderer, this fixed
sentence, these three sizes and temperature 0.7; no claim is made about other layouts or prompts.
Token counts per item, model and condition are reported descriptively.

**Runs and decoding.** Three runs per (model, item, condition) cell, a fixed recorded seed per run, temperature 0.7,
top_p 0.95, thinking off, at most 2048 output tokens, a 16,384-token context window and no
system message. Settings are identical across conditions. The book prefers temperature 0 for a point
estimate (Principle 5, p. 167); we sample at 0.7 because repeated runs are needed to measure
run-to-run noise as test-retest error (p. 147), and greedy decoding would make the runs identical.
The cell score is the mean of the three runs, never the best of three (p. 285).

The number of runs is checked with a D-study (book pp. 132-133, 314) after a first block of data:
all 5 models, all 4 conditions and 3 runs on 200 DevEval items, sampled by prompt-token bucket in
proportion to the set (91 in 2k-4k, 81 in 4k-8k, 28 in 8k-12k), and 40 CoderUJB items, sampled by
project in proportion to project size. The sample uses a fixed seed and its item ids are saved
before any generation. The block is 14,400 answers and about 240 CPU-hours of grading, almost all
of it CoderUJB (297 s per answer against 12 s for DevEval). It covers every model because run
noise depends on how close a model sits to 0 or 1, so the rule is applied per model and benchmark.
We estimate the item, item:condition and run components of the gap and project the standard error
of delta_mb with 1, 2 and 3 runs. The number of items cancels out of the 2-run to 3-run ratio; it
only sets how precise the components are (relative standard error of the item:condition component
about sqrt(2/n), so about 10% at 200 items and 22% at 40) [ours]. If 2 runs give a standard error
within a margin fixed before the block is graded (the 2-run standard error at most 1.10 times the
3-run one, set Nov 8; open item 6), the remaining items of
that model and benchmark run twice, the block items keep their 3 runs, and the freed budget keeps
the 10 px condition and the full DevEval set. The rule is
part of the frozen plan. No repeated runs at temperature 0.7 exist yet: the pilot ran at
temperature 1e-6, and the calibration runs have one run per item.

**Outcome.** Binary pass per answer: CoderUJB passes when all of the item's target JUnit tests pass
(Defects4J v2.0.1), DevEval when all of the item's pytest ids pass. Both graders stop at the first
failing test, so no fraction of tests passed is recorded. The full response matrix is
model x item x condition x run, 5 x 995 x 4 x 3 = 59,700 answers. Generation runs on the GPU nodes;
grading runs on CPU nodes (about 845 CPU-hours, mostly CoderUJB).

**Exclusions.** An item that does not fit the context window or the per-request image limit in some
condition is dropped from that condition's contrasts only, and the counts per size are reported.
All contrasts are computed on the items present in both conditions, and size comparisons on the
items present in all four. Dropped items are the longest ones, so they are not missing at random; a
sensitivity analysis counts them as failures in the image conditions.

### 3.2 Construct and estimands

The target construct is completing one function or method in a Java or Python repository from its
task description, with the repository's code as context. It is narrower than coding ability: it
excludes debugging, code review, multi-file edits and screenshots of real IDEs, and reading the
results as coding ability in general would be the construct underrepresentation the book warns
about (book 1.3.2). The candidate second construct is reading code from an
image. Rendering is treated as a facet of measurement under the working hypothesis of one ability;
whether it carries a construct of its own is the question in 3.3, so the framing does not assume
the answer. Tokens saved is an observed property of the input.

For model m, benchmark b and size s, the paired gap is

  delta_mbs = (1/n_b) sum_i [ Y_mi(image s) - Y_mi(text) ],

where Y is the run-averaged pass rate of the cell and items are the unit. The confirmatory
estimand is the size-averaged gap

  delta_mb = (1/3) sum_s delta_mbs,

computed on the items present in all four conditions. It weights the three sizes equally, so no
size is privileged. Its value depends on the grid we chose (10, 12, 14 px) and is read as the
average penalty over that grid, not over font sizes in general. The pooled gap across models is
reported as the mean of the five per-model gaps, not as a common effect, with an interval from one
joint cluster resample (projects or repositories resampled once for all models and conditions,
runs kept inside their cells), since the five gaps share items.

The gap is on the probability scale and is bounded by floor and ceiling: a model near 0% in text
cannot drop far. Each gap is therefore reported next to that model's text accuracy and next to the
logit-scale model x condition contrast from the GLMM (3.3), and comparisons of probability gaps
across models are read as ordinal (book pp. 64-65). We also report, per model and condition, the
share of items with 0 of 3 and 3 of 3 passes.

### 3.3 Analysis

**Main result: paired gap per model.** Each delta_mb and delta_mbs gets a paired, item-clustered 95% interval
(Miller 2024). CoderUJB items are not independent: 95 of the 136 come from four project snapshots
(Math, Closure, Lang, Chart). For CoderUJB the primary interval is a project-clustered t interval
with 13 df (14 projects); the item-clustered interval is reported as a second line, along with a
leave-one-project-out table for the four large projects. DevEval intervals are clustered by
repository (79). In a simulation with assumed variance components, the project-clustered interval
covered 0.91 to 0.93 against 0.72 to 0.90 for the item interval when the gap varied by project.

Power, from the same simulation and from analytic power at the pilot's item-gap SD: DevEval
detects a 5-point drop per model at a single size with power 0.83 to 1.0; CoderUJB only reliably
detects drops of about 10 points. The size-averaged gap uses three image cells per item and should
have at least this power, but it was not simulated. The simulated item-gap SD (0.29 to 0.32) is
below the pilot's 0.46 to 0.51, so these numbers are optimistic. The simulated rejection rates
come from 95% intervals, one test per model (alpha 0.05, no Holm); with Holm over the 10 primary
tests the smallest p-value is compared with 0.005, so the real power is lower again. We therefore treat DevEval as the benchmark for small gaps and read CoderUJB as a
replication on another language. These numbers rest on assumed components; the first image data
will replace them.

**Mixed-effects logistic model.** We fit a binomial GLMM on the cell counts (k of 3 runs passed):

  logit P(pass) = model x condition (fixed) + item + item:model + item:condition + project
                  + project:condition + cell (random intercepts),

separately per benchmark, with glmmTMB (Laplace) or lme4. The item:model term is the model-by-item
interaction of book p. 119, identifiable because each cell has 3 runs (p. 134); without it,
model-specific item difficulty would leak into item:condition and inflate check 2 below. The cell
term absorbs overdispersion of the k-of-3 counts. This extends the book's treatment-facet model
(p. 44, where subjects are random and there is no item x condition term) with items as the random
facet; item x condition is the additivity test of p. 65. Individual item difficulties are not
reported: with 5 models each item's standard error is at least about 0.9 logits. The code is first
validated on simulated data with known components, because the variational GLMM in statsmodels
undercovered (0.60 to 0.69) in our check.

**Same ability or two.** An ability is a property of the models, and there are five, so this study
cannot establish or rule out a second model-level dimension; a two-factor model (book ch. 7) is not
identified with 5 respondents. What the items can show is whether the image penalty is uniform
across items. We cite the book as the source of the question, not of the method:

1. Item order. Correlate item logits (empirical logits with a continuity correction, and Spearman
   as a check) between text and each image size, and between pairs of image sizes. The reference is
   a parametric bootstrap from the fitted GLMM with the item:condition variance set to zero, since
   a uniform logit shift does not give a correlation of exactly 1 on observed rates. Image sizes
   correlating clearly more with each other than with text points to a method factor (book
   pp. 158-159).
2. Item x condition variance. Report the item:condition component with its interval and upper
   bound. Before reading it as item-specific penalties, check two one-ability explanations the
   book names (pp. 72, 77): a common slope (regress image item logits on text item logits estimated
   from different runs; a slope below 1 with small residual means the image compresses the scale),
   and the link (refit with probit). The LRT with the halved p-value is kept as a secondary line;
   the primary comparison is held-out log-likelihood with whole items held out by project or
   repository (pp. 134-135, 197).
3. Model x condition. The 4-df test of whether the size-averaged penalty is the same for all five
   models, on the logit scale. Model rank order across conditions is shown as a table without a
   test (Kendall's tau on 5 objects takes 11 values).

Failing to reject uniformity is not evidence of one ability; it is reported as an interval for the
item:condition variance. Evidence that the image adds something beyond a common shift and slope is
an item:condition variance clearly above 0 after checks 1 and 2, strongest if the items with the
largest penalties are the ones the transcription test (below) shows were misread.

**Item-level penalties.** Mantel-Haenszel DIF (book 5.11, pp. 150-151) compares independent groups
matched on total score; here the same five models appear in every condition, and in our simulation
it detected only 7.7% of the items given a strong extra image penalty. We instead flag items whose
shrunken item:condition deviation from the GLMM has a 95% interval excluding zero, and report the
variance component as the headline number.

**Letter size.** The size curve is the per-model gap at 10, 12 and 14 px, plotted against the
ratio of image tokens to text tokens for that model. The curve is per model because the same size
costs very different amounts: at 12 px images cost 0.14 of the text tokens on Gemma and 0.75 on
Mistral. Size changes token count and legibility together, so this is a letter-size curve, not a
pure compression curve. Since no size is chosen in advance, a claim that one size is best rests on
the paired difference between sizes (same items, same model) with its own interval, not on picking
the highest point estimate.

**Reading vs coding failures.** In a separate transcription test (UFM-12), each model is shown the
same images and asked to read back the identifiers the reference solution needs, including the
target function name. The score R is the fraction read exactly. We report pass rate by R and the
condition x R slope in the GLMM, and classify each failed image answer as "implemented a different
function" (from the extracted function name) or "found the right function but failed". These are
associations: R comes from a separate call and item difficulty drives both reading and passing, so
they do not show that misreading causes failure.

**Contamination.** In calibration many passing answers copied the reference code (24 of 24 exact
copies on DevEval passed). A model that has memorized an item can pass from a partial reading of
the image, which would shrink the gap, so pairing does not cancel contamination (book pp. 22-23).
We report every gap twice: on all items, and without items flagged as possibly contaminated. An
item is flagged for model m when at least one of the other 4 models produces an exact copy of the
reference in a text run, token for token after the tokenization in shared/contamination.py. Near
copies are not flagged. The flag uses text-condition data from other models only,
because conditioning on a model's own passing answers would select on the outcome. The flagged set
can therefore differ by model, and the number of items removed for each model is reported.
Removing flagged items also removes easy or short items, since a canonical function gets copied
without memorization, so the gap without them is a sensitivity check for a different item set, not
a corrected gap. As a control, we remove random item sets of the same size matched on text pass
rate and length, and report how much the gap moves. The item:model estimates from the GLMM give a
second, model-based flag, and the agreement between the two flags is reported.

**Scoring across conditions.** The graders are deterministic, but the step before grading is not:
code extraction, the 2048-token output limit and the context window can treat image answers
differently. Per model and condition we report the share of empty answers, answers cut at 2048
tokens, answers with no extractable code, and answers that define a different function. One model's
failures (30 per condition) are read by hand to estimate false fails. Items that no model passes in
any condition, text included, are listed and 10 to 20 of them are checked for test bugs.

**Context length.** Gap by log text tokens (spline with 3 knots, or the three length buckets), per
size and model, as an exploratory moderator. DevEval is the main evidence; CoderUJB has 32 items in
the longest bucket.

**Reliability.** Run-to-run agreement per condition from the three runs (within-cell variance,
the occasion component), with the single-run and 3-run reliability of the item scores
(Spearman-Brown, p. 147). Variance components for model x item per condition with runs nested in
cells (pp. 119-120, 128), with intervals from MCMC (p. 125). The G coefficient for ranking the five
models is reported per condition as a secondary line, with its interval; its model component rests
on 4 df. Rank stability is shown as each model's rank interval per condition and the probability
that a pair swaps order between text and image, from the joint cluster resample. Omega and a
standard error of measurement are not computed, since with 5 models the score spread they need
is too noisy to use; MTMM is out of scope because the study has one trait.

**Multiple comparisons.** The confirmatory family is the 10 size-averaged gaps delta_mb (5 models x
2 benchmarks), corrected with Holm. The 30 per-size gaps delta_mbs are all reported side by side
with Benjamini-Hochberg adjusted p-values, as are the size differences, the context-length and
contamination analyses and the per-item flags.

**Reporting and freezing.** All estimates are reported with intervals, along with the share of
items passed by all or no models in each condition. This plan is frozen before any image-condition
data is graded, and render parameters, model revisions, seeds and package versions are published
with the code. Updating the power numbers with the first image data changes only the power
discussion: the confirmatory family and the analysis stay as frozen. The run-count rule above is
the one planned change, and any other deviation goes into a dated deviations log, in the spirit of
the book's faithful-execution log (p. 275).

**If compute runs short.** Cuts are applied in this order and logged: (1) fewer DevEval items,
(2) drop 10 px. The text condition is never cut, and
runs go from 3 to 2 only through the D-study rule in 3.1.

---

## Open items

1. Resolved Nov 5: recounted on the final renderer (context only); the image limit is 9 pages per
   request, which keeps every item (3.1).
2. Resolved Nov 5: the contamination flag uses exact copies only, so no similarity threshold is
   needed.
3. The R GLMM (lme4 or glmmTMB) has not been installed or tested on the cluster.
4. The power and coverage numbers come from simulations with assumed variance components. Nothing
   here was run on image data.
5. Resolved Nov 5: the plan was delivered as a presentation, so there is no page limit to cut
   to. The paper's methods section will be a shorter version of this text.
6. Resolved Nov 8, before any block-1 answer was graded: 2 runs are enough for a model and
   benchmark when SE(2 runs) / SE(3 runs) is at most 1.10. The ratio can only fall between 1.00
   (no run noise) and 1.22 (all noise is run noise, sqrt(3/2)), so 1.10 lets the data decide.
7. Resolved Nov 5: the fixed sentence is frozen (3.1) and the renderer and prompt builder are in
   src/codeimg (render.py, prompts.py).
8. A hybrid check was considered and dropped: with the task now in text, the remaining gap is
   about reading the context. A second instruction wording or font, to size prompt and format
   sensitivity, is not budgeted.
