# Notes: validity and response matrices (course book)

Reference: Truong, Sang T. and Koyejo, Sanmi. AI Measurement Science, 2026.
Sections covered: 1.2 A Taxonomy of Validity Evidence, 1.3 Threats to Validity in AI Evaluation, 2.1 The Response Matrix, 2.5 Paired Response Matrices.

Page numbers are the printed page numbers in the page headers (they match the PDF page index in the file at docs/AI-Measurement-Science.pdf). Notation is written in ASCII: theta_i for model ability, lambda_j and gamma_j for loadings, z_ij for item-specific variance, Y_ij for the response of subject i on item j.

The project pilot numbers used below (Qwen2.5-VL-7B, 20 HumanEval problems padded to ~12k chars: Text 13/20 at ~3,870 tokens, image tiny font 5/20 at ~1,124, mono-12 12/20 at ~2,580) come from our own work, not from the book.

---

## 1.2 A Taxonomy of Validity Evidence (pp. 16-20)

### Why validity is treated as evidence accumulation (pp. 16-17)

- The nomological network (Section 1.1) is not identifiable from observational data alone. Different networks can produce the same observed data (p. 16).
- Figure 1.2 (p. 17): four items Y1..Y4 load on two abilities theta (Y1, Y2) and theta' (Y3, Y4). Panel (a) is a correlated-factors model. Panel (b) is a bifactor model with a general factor g loading on all four items plus orthogonal specific factors s1, s2. For suitable parameters both give the same Cov(Y1, ..., Y4). A proportionally constrained bifactor is mathematically the correlated two-factor model.
- Consequence: covariance can show that theta and theta' covary, not why. The same holds for the meaning of a single construct: shared variance in a benchmark may reflect the intended ability or a construct-irrelevant cause such as memorized text (pp. 16-17). Committing to one network means choosing among structures the data cannot separate.
- So validation is a process of accumulating evidence (Cronbach, Messick, Kane, claim-centered view), answering "how do we come to know that a test supports its intended interpretation?" (p. 17).
- Modern view (Messick 1995, the Standards for Educational and Psychological Testing): validity is unitary, defined as the degree to which evidence supports the intended interpretation of test scores. The evidence comes in five distinguishable forms, following Salaudeen et al. (2025) and the classical framework (p. 17).

### The five forms

**Content validity (pp. 17-18).** Does the benchmark adequately represent the construct domain? Key questions: does it cover the full range of the construct, are the items relevant, are important aspects missing? Established by expert judgment, not statistics: experts review the construct definition, the item pool, and coverage. Frequently skipped in AI evaluation because benchmarks come from convenience samples. Book examples: a "coding ability" benchmark that tests only Python function completion and neglects debugging, design, documentation, review (p. 17); a "scientific reasoning" benchmark that tests only factual recall has poor content validity "regardless of how reliable the scores are" (pp. 17-18).

**Criterion validity (p. 18).** Do scores predict or correlate with an external criterion that independently captures the construct? Two subtypes:
- Concurrent: correlation with a currently available gold standard (an automated coding benchmark should correlate with expert human evaluation of the same code).
- Predictive: predicts future outcomes (a coding-assistant benchmark should predict usefulness in real developer workflows).
Limitation: needs a trustworthy external criterion, which is often the fundamental problem. The circularity of criterion validation (Cronbach and Meehl 1955) is acute in AI. Example: correlation with Chatbot Arena Elo, where Arena itself rests on validity assumptions.

**Construct validity (pp. 18-19).** The central and most encompassing form: does the benchmark measure the theoretical construct? It concerns internal structure. Two kinds of evidence:
- Convergent: scores correlate positively with other measures of the same or closely related constructs.
- Discriminant: scores do not correlate strongly with measures of different constructs.
Formalized by Campbell and Fiske (1959) as the Multitrait-Multimethod (MTMM) matrix, developed in Section 5.11.5 (p. 19). Under Borsboom's causal framework, construct validity is the causal claim that variation in the latent construct produces variation in scores. It is testable by intervention (raise the ability, hold all else fixed, scores should rise), but clean interventions are rare (p. 19).

**External validity (p. 19).** Generalizability beyond the specific evaluation conditions: other contexts, populations, times. AI questions the book lists: English benchmarks vs multilingual performance, clean curated items vs noisy real inputs, scores today vs after a model update, research setting vs production. Linked to distribution shift (Chapter 9).

**Consequential validity (pp. 19-20).** Introduced by Messick (1995): are the social consequences of using the scores appropriate? The most controversial form. Listed issues: Goodhart's law, development distortion (easy-to-optimize benchmarks attract disproportionate effort), misuse of rankings. Negative consequences do not make a benchmark invalid by themselves; they count as evidence about whether the measurement system serves its purpose (p. 20).

**Summary (Table 1.1, p. 20).** Typical evidence per form: content = expert review, domain specification; criterion = correlation with gold standard; construct = MTMM matrix, factor analysis; external = cross-context replication; consequential = impact analysis, misuse audit.

### How it applies to our project

The question we ask is "does moving long context from text to a rendered image change coding accuracy?" The design supports these evidence types:

- **Construct validity (main one, and the one we can test directly).** The intended construct is "coding ability given the context". The book's causal framing (p. 19) is close to what we do: the rendering condition is an intervention on how the context reaches the model, with the code task held fixed. The transcription probe is a discriminant-style check. It separates a reading construct (can the model recover identifiers from pixels) from a coding construct (can it write correct code from correct information). If accuracy in the image conditions drops because of misread identifiers, the score is no longer measuring coding ability, which matches the pilot observation that most image failures are misread identifiers. Convergent evidence: Text, Mixed and All-image conditions should rank the models similarly when reading is not the bottleneck; disagreement in rankings is evidence that the image conditions measure something else. If we use several models (3 to 5), a small MTMM-like layout is possible: traits = {coding, reading}, methods = {text, image}. We should say clearly that with 3 to 5 models this is illustrative, not a full factor analysis.
- **Criterion validity (concurrent).** Unit tests are the criterion for correctness. The Text condition can serve as the gold standard for "what the model can do with the same information", so image-condition scores can be reported as agreement with Text scores per item. This is a concurrent-criterion argument, with the caveat (p. 18) that Text is itself an imperfect criterion.
- **Content validity.** HumanEval-style function completion padded with distractor context covers a narrow slice of "coding with long context" (no multi-file editing, no debugging, no real repo history). We should state this as a limit, per pp. 17 and 22. The padding (~12k chars) is synthetic, so we should describe how it was built.
- **External validity.** Factors we vary (font size, characters per row) give within-study generalization across rendering choices. Generalization to other tools, real repositories, other model families, and other rendering pipelines is not tested and should be listed as a limit. One model in the pilot means no generalization claim across VLMs yet.
- **Consequential validity.** Token savings are a cost claim. The consequence to discuss is that a reported token saving is only meaningful if accuracy holds; a lower token count with lower accuracy should not be presented as an unqualified efficiency gain. We do not have consequential evidence beyond that argument.

---

## 1.3 Threats to Validity in AI Evaluation (pp. 21-23)

The book names four categories (p. 21).

### 1.3.1 Construct-irrelevant variance, CIV (p. 21)

- Definition: systematic factors other than the target construct influence scores. Unlike random noise, which lowers reliability, CIV is systematic and can inflate or deflate scores predictably.
- Sources listed: prompt formatting sensitivity (Mizrahi et al. 2024), multiple-choice position bias, tokenization artifacts (performance depends on how text is tokenized, an artifact of vocabulary, not ability), language and cultural bias.
- CIV does not average out with more items. A benchmark with position bias has high reliability but poor validity.
- Model (p. 21), for model i on item j:

  Y_ij = lambda_j * theta_i + gamma_j * N_i + z_ij

  with the terms labeled construct, construct-irrelevant, and item-specific. The nuisance cause N (formatting sensitivity, position preference) loads on several items through gamma_j. A cause confined to one item collapses into z_ij and only adds noise; a cause shared across items acts as a second common factor and biases the construct estimate. Figure 1.3 (p. 22) shows this graphically.
- Practical rule (p. 21): if N is observed (answer position, prompt length, language), control for it or randomize it (counterbalancing position decorrelates it from the score). If N is latent, it is confounded with theta and a single benchmark cannot separate them; the multitrait-multimethod design of Section 5.11.5 is the tool.

### 1.3.2 Construct underrepresentation (p. 22)

The benchmark is too narrow and samples only part of the construct. It is the content-validity threat seen from another side. Examples: coding tested only by function completion; language understanding only with formal text; safety only with English adversarial prompts. Often a result of convenience sampling.

### 1.3.3 Benchmark contamination (pp. 22-23)

Evaluation items appear in training data so the model retrieves memorized answers. Can be direct (exact match) or indirect (paraphrases, derivatives, same-source items with structural patterns). Detection methods listed (p. 23): canary strings (Jacovi et al. 2023), membership inference, chronological splits (before vs after training cutoff), public/private splits (the gap estimates contamination), performance discontinuities between seen and matched unseen items. In Borsboom's framing it adds an alternative causal path: memory, not ability, causes the response (p. 23).

### 1.3.4 Differential item functioning, DIF (p. 23)

An item is systematically easier or harder for one subgroup after controlling for overall ability. In AI evaluation the groups are model families, architectures, or training paradigms. A DIF item rewards a construct-irrelevant feature (a formatting convention, a tokenization quirk). It is a group-structured special case of CIV. A DIF term is an item-by-group interaction, tested with Mantel-Haenszel, logistic regression, and IRT-based tests (developed in Section 5.11.1; not read for these notes).

### How it applies to our project

- **CIV is the main threat, and rendering is a source of it.** The image pipeline adds nuisance causes that are unrelated to coding ability: font size, characters per row, font face, image resolution, and the vision encoder's downscaling. In the book's model these are N variables that load on many items at once (every item that contains small identifiers is affected), so they behave as a second common factor, not as noise. This fits the pilot: tiny font gave 5/20 against 12/20 at mono-12 and 13/20 as text, with most failures being misread identifiers. Reading errors are CIV relative to a "coding" construct.
- **Handling.** Font size and characters per row are observed nuisance variables, so the book's rule (p. 21) says to control or randomize them. Our factorial design does this: they are explicit factors, crossed with condition and model, so their effect is estimated and not confounded. The transcription probe measures the reading component directly on the same rendered inputs, which lets us report coding accuracy conditional on correct transcription, or at least report the two error types separately. Latent nuisance causes (for example encoder-specific behavior we cannot observe) are confounded with ability per p. 21; comparing several VLMs (different methods) is our version of the multimethod remedy, and we should say it only partly separates them.
- **Tokenization artifacts (p. 21).** Text token counts and image token counts come from different tokenizers and encoders. The token-saving figures (3,870 vs 1,124 vs 2,580 in the pilot) are model-specific and should be reported per model, not pooled.
- **Order and layout effects.** Position of the context vs instruction, and which item is placed where in the image, are observed variables; randomize or counterbalance them (p. 21).
- **Construct underrepresentation.** HumanEval problems with synthetic padding sample only single-function completion with filler context. Say so; do not claim the result covers repository-scale context. Padding that is not semantically related to the task may also make the task easier or harder than real context.
- **Contamination.** HumanEval is widely public and likely in training data. This affects Text and image conditions differently: a model may complete a memorized solution from the function signature alone, which would hide reading errors in the image conditions. Ways to check with the book's tools: a performance discontinuity test between original and modified/renamed problems, or an ablation with the context removed. If the no-context baseline solves many items, the accuracy drop from images is underestimated. This is worth checking before interpreting the drop.
- **DIF.** Treat model as the group. An item (for example one with long or look-alike identifiers such as l/1/I or O/0) may be hard only in image conditions and only for some VLMs. That is an item-by-model-by-condition interaction and should be examined item by item, not only in aggregate. The methods are in Section 5.11.1, which has not been read for these notes.

---

## 2.1 The Response Matrix (pp. 25-27)

### Definition (pp. 25-26)

- Every AI evaluation produces a table: rows are systems being evaluated (models, agents, model-scaffold combinations), columns are evaluation items, entries record performance (p. 25).
- Definition (pp. 25-26): a response matrix Y in R^(N x M) records the performance of N subjects (models) on M items (tasks). Y_ij can be binary in {0, 1} (correct/incorrect, pass/fail), continuous in [0, 1] (pass@1 rate, partial credit, token probability), or missing (NaN, subject not evaluated on the item).
- It is the fundamental data structure: IRT, factor models, and Bradley-Terry all operate on response matrices or transformations of them (p. 26).
- The same N x M structure covers different paradigms (table on pp. 26-27). Examples with (subjects x items): MMLU-Pro (48 x 12,257), BigCodeBench code generation (153 x 1,140, binary or pass@1), SWE-bench (134 x 500), BFCL (93 x 4,751), WebArena (14 x 812), Terminal-Bench (128 x 89, continuous), CRUXEval (38 x 800, continuous).

### What counts as a subject (p. 27)

The key design decision is what a subject is. For knowledge benchmarks it is usually one LLM. For agentic benchmarks it is a model-scaffold combination (for example SWE-Agent + Claude Sonnet 4), because scaffold search strategy, tool use, and error recovery add to performance. If the scaffold contributes variance, an IRT ability estimate partly reflects the scaffold and not the model alone.

### 2.1.1 Shape and sparsity (p. 27)

- Matrices can be dense (SWE-bench Verified, 500 items x 134 combinations) or sparse when models are evaluated on different item subsets.
- LiveCodeBench: 72 models x 1,055 problems, 88.8% filled, because older models were evaluated on earlier problem sets (713 or 880 problems). This is missing-by-design, not at random, and the pattern carries information (newer models tend to be more capable).
- Dense rectangular matrices support standard IRT and factor models. Sparse or systematically incomplete ones need models that handle missing data explicitly, or imputation that accounts for the missingness mechanism.

### How it applies to our project

Our results form a response matrix in which a subject is not just a model. By the book's own point about subjects (p. 27), the subject should be defined as a model plus its input condition, since the rendering pipeline contributes variance the same way a scaffold does. Two workable layouts:

1. One matrix per model, subjects = conditions/factor cells (Text, Mixed, All image, crossed with font size and characters per row), items = the HumanEval problems. Y_ij is binary (unit tests pass or fail), or continuous if we use pass rate over several samples.
2. A larger matrix with subjects = (model, condition, font size, chars per row) cells. With 3 to 5 models and the factor grid, this gives roughly a few dozen to a few hundred rows against about 20 to a few hundred items. The exact size depends on the final design and is not fixed yet.

The pilot is a 20-item, few-row matrix (Text 13/20, tiny font 5/20, mono-12 12/20 for one model). That is very small, and item-level responses are what allow us to do paired or item-level analysis later. We should store item-level Y_ij, not only totals. Sparsity: if we run some conditions on fewer items or drop items because of budget, we would create missing-by-design cells, and the book warns that the pattern then carries information (p. 27). Prefer a complete matrix (every cell run on every item), which allows standard models. The transcription probe gives a second matrix of the same shape (item by cell, correct transcription or not), which can be aligned with the coding matrix.

---

## 2.5 Paired Response Matrices (pp. 44-47)

### Definition and model (p. 44)

- Some evaluations produce paired matrices: the same or comparable subjects respond to items under multiple conditions, typically with and without AI assistance (deployment RCTs, uplift studies, human-AI collaboration experiments) (p. 44).
- The standard matrix Y_ij in {0, 1} (subject i on item j) is extended to Y_ij^(t) in {0, 1} (subject i on item j under condition t), with t in {control, treatment} or several treatment arms (p. 44).
- In the book's datasets the subjects are humans (radiologists, developers, students) and the target is the causal effect of AI on human performance, not the AI system's capability alone (p. 44).
- Link to many-facet Rasch measurement (p. 44): treatment is another facet next to person ability and item difficulty:

  log [ P(Y_ij^(t) = 1) / P(Y_ij^(t) = 0) ] = theta_i - beta_j + tau_t

  where tau_t is the treatment-effect facet. The interaction theta_i x tau_t captures heterogeneous treatment effects, the degree to which the treatment helps some subjects more than others.

### Inventory of datasets (pp. 44-46)

Five public intervention datasets, the first in torch_measure with human subjects (p. 44). Table on p. 45:
- Collab-CXR: 336 radiologists (text also says 227 read subsets), 324 chest X-ray cases, four conditions (image only, +history, +AI, +AI+history). Within-subject crossed design, "ideal for many-facet analysis". Mean accuracy 96.5% to 97.1% with AI, heterogeneous across radiologists and pathologies (p. 45).
- METR Early-2025 (16 developers, 246 issues) and Late-2025 (57 developers, 1,134 issues): within-subject RCT, each developer's issues randomly assigned to AI allowed or disallowed; outcome is completion time. Early: AI-allowed took longer (119.5 vs 90.9 min). Late: 151 vs 169 min, with severe selection effects. Limitation for IRT: items are developer-specific, so the matrix is block-diagonal (p. 45).
- HAIID: 1,125 participants, 152 items, five domains, pre/post advice labeled as from AI or from a human. Label has minimal effect; advice content drives the effect (pp. 45-46). Figure 2.1 (p. 46) shows the HAIID art domain matrices under three conditions (pre-advice 558 participants x 32 items, mean accuracy 0.658; post-advice AI label 0.746; human label 0.735).
- GenAI Learning: 943 students, GPT-4 vanilla and guardrailed tutor. Practice score 0.69 with ChatGPT vs 0.34 controls, but exam without AI 0.36 vs 0.36 (guardrailed tutor 0.35). The book calls this a measurement paradox: AI inflates apparent performance without durable learning (p. 46). Figures 2.2 and 2.3 (pp. 47-48) show the arms in practice and exam phases.

### 2.5.3 What paired matrices enable (p. 46)

The section opens the list with heterogeneous treatment effects (does AI help all users equally, or preferentially experts, novices, subgroups), analyzed with many-facet Rasch models and DIF analysis. The text extracted from the PDF for this subsection ends after the first item on p. 46, and p. 47 contains only a figure, so the remaining items in the list were not in the extracted text and are not reported here.

### How it applies to our project

Our design is a paired response matrix in the book's sense, with the roles changed: the subjects are models (not humans) and the "treatment" is the way context is delivered.

- Y_ij^(t) in {0, 1}: model i (or model-by-setting) on HumanEval item j under condition t, where t in {Text (control), Mixed, All image}, with font size and characters per row as additional treatment factors. The same items appear in every condition, so the data are paired at the item level, and we can use paired tests such as McNemar for two conditions, or a many-facet logistic model. Text is the control arm; Mixed and All image are treatment arms.
- Following the book's many-facet form (p. 44), a model for our data is
  log [ P(Y_ij^(t)=1) / P(Y_ij^(t)=0) ] = theta_i - beta_j + tau_t,
  with theta_i the model ability, beta_j the item difficulty, tau_t the effect of rendering condition t (extended with font size and characters-per-row terms). This is our reading of how to apply the book's model; the book does not apply it to rendered context. With 20 items and 3 to 5 models the estimates will be imprecise, so we should report intervals and treat the model as descriptive.
- The theta_i x tau_t interaction is the heterogeneous-effect term: does image context hurt some models more than others. That is also where DIF (Section 1.3.4) enters, because we care about item-by-condition interactions such as identifier-heavy items failing only in images.
- Same-item pairing removes item difficulty from the comparison, which is why the pilot gap (13/20 vs 5/20 vs 12/20) is more informative when broken down per item. The pilot data should be kept at item level.
- Contrast with the book's datasets: in the METR data items are subject-specific, producing a block-diagonal matrix (p. 45). Ours is fully crossed (every model sees every item under every condition), which is the favorable case the book attributes to Collab-CXR.
- The GenAI Learning result (p. 46) is a caution about what a score measures: performance under one condition (with AI help) need not transfer to another condition. For us the analogue is that a high score under the Mixed condition is a statement about that condition. The token-saving claim and the accuracy claim should both be reported per condition.

---

## Caveats on these notes

- Only the four sections were read (PDF pages 16-23, 25-27, 44-47). Cross-references to Sections 5.11.1 (DIF tests), 5.11.5 (MTMM), and Chapter 9 were not read.
- The mappings to our project are my proposals, not statements from the book.
- I did not check the book's reference list for the cited papers (Salaudeen et al. 2025, Mizrahi et al. 2024, and others), only their mention in the text.
