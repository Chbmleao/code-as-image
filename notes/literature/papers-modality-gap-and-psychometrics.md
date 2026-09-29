# Prior work: modality gap, text-as-image compression, psychometrics of LLM evaluation

Verification note. Every claim below comes from the arXiv abstract page (fetched 2026-09-28) or, where marked "search snippet only", from a web search result summary. I did not read full PDFs, so per-model tables, task counts and methods beyond the abstract are marked "not verified".

## 1. IsoBench

- Citation: Fu, D., Guo, R., Khalighinejad, G., Liu, O., Dhingra, B., Yogatama, D., Jia, R., Neiswanger, W. (2024). IsoBench: Benchmarking Multimodal Foundation Models on Isomorphic Representations. COLM 2024. arXiv:2404.01266. https://arxiv.org/abs/2404.01266
- Claim: multimodal foundation models consistently prefer text over image versions of the same problem.
- Method: benchmark of problems in math, science, algorithms and games, each with multiple isomorphic input representations (visual, textual, mathematical). Search snippet only: 1,887 samples, including discrete and applied math, physics, chemistry and chess. Also proposes IsoCombination and IsoScratchPad prompting to narrow the gap.
- Key numbers (abstract): performance is worse with images than text by 28.7 points for Claude-3 Opus, 18.7 for GPT-4 Turbo, 14.9 for Gemini Pro.
- How it relates to us: it is the closest design to ours (same content, two input modalities, per-model gap). It covers the size of the gap on short, structured problems. It leaves open: long context, coding problems, token savings, item-level analysis (whether the gap is uniform across items or item-specific), and whether the two conditions measure the same latent ability. Whether the paper reports item-level analysis is not verified.

## 2. SEAM

- Citation: Tang, Z., Jiao, D., Yang, B., Anderson, A. (2025). SEAM: Semantically Equivalent Across Modalities Benchmark for Vision-Language Models. COLM 2025. arXiv:2508.18179. https://arxiv.org/abs/2508.18179
- Claim: across 21 models, vision frequently lags language despite semantically equivalent content, and cross-modal agreement is relatively low.
- Method: paired inputs in four domains with standardized textual and visual notations (not OCR-based image-text pairs). Error analysis names two drivers: textual perception failures from tokenization of domain notation, and visual perception failures that produce hallucinations.
- Key numbers: 21 models, four domains (abstract). Accuracy and agreement figures not verified.
- How it relates to us: the low cross-modal agreement is evidence that the two conditions do not rank items or models identically, which is what a paired response matrix and DIF-by-condition would test formally. Its pairing is notation-based, whereas ours is rendering of the same text (closer to OCR-style pairing), so its findings may not transfer. It reports agreement, not IRT or DIF (not verified beyond the abstract).

## 3. Text or Pixels? It Takes Half

- Citation: Li, Y., Lan, Z., Zhou, J. (2025). Text or Pixels? It Takes Half: On the Token Efficiency of Visual Text Inputs in Multimodal LLMs. Findings of EMNLP 2025. arXiv:2510.18279. https://arxiv.org/abs/2510.18279
- Claim: rendering long text as a single image gives substantial decoder token savings, often nearly half, without degrading task performance.
- Method: long text converted to images and fed to multimodal LLMs; evaluated on RULER (long-context retrieval) and CNN/DailyMail (summarization).
- Key numbers: "often nearly half" token reduction (abstract). Models and exact accuracy deltas not verified.
- How it relates to us: it covers the token-savings half of our question, on retrieval and summarization. It leaves open coding tasks, where exact symbols and indentation matter, and any psychometric treatment (a mean accuracy comparison hides item-level or model-level interaction).

## 4. VTCBench

- Citation: Zhao, H., Wang, M., Zhu, F., Liu, W., Ni, B., Zeng, F., Meng, G., Zhang, Z. (2025). VTCBench: Can Vision-Language Models Understand Long Context with Vision-Text Compression? arXiv:2512.15649 (no peer-reviewed venue found). https://arxiv.org/abs/2512.15649
- Claim: most VLMs decode text from vision-text-compressed input but show poor long-context understanding on it.
- Method: benchmark with three scenarios: retrieval, reasoning that needs latent association inference, and memory-based question answering. The abstract cites DeepSeek-OCR and Glyph as systems achieving 3x to 20x compression.
- Key numbers: 3x-20x compression ratios (attributed to those systems in the abstract). Accuracy figures not verified.
- How it relates to us: it shows accuracy loss under compression grows with reasoning demands, which supports expecting a condition effect on harder items. It does not include code tasks or test measurement equivalence. Related: Glyph (arXiv:2510.17800, ACL 2026), which reports 3-4x compression at accuracy comparable to Qwen3-8B (search snippet only, not fetched from the abstract page).

## 5. Sclar et al., prompt formatting sensitivity

- Citation: Sclar, M., Choi, Y., Tsvetkov, Y., Suhr, A. (2024). Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design or: How I learned to start worrying about prompt formatting. ICLR 2024. arXiv:2310.11324. https://arxiv.org/abs/2310.11324
- Claim: widely used open-source LLMs are extremely sensitive to meaning-preserving formatting changes in few-shot prompts, and this persists with model size, more shots and instruction tuning.
- Method: sample plausible formats with FormatSpread (no weight access needed); atomic perturbation analysis; probing of internal representations.
- Key numbers: up to 76 accuracy points difference for LLaMA-2-13B; weak correlation of format performance across models. Recommends reporting performance ranges over formats.
- How it relates to us: it frames input format as construct-irrelevant variance and shows model-by-format interaction (weak cross-model correlation), which parallels a model-by-condition facet. It studies text formats only, not modality, and does not use IRT or DIF. Rendering choices (font, size, resolution) in our images are a similar hidden format facet.

## 6. Messing, hidden measurement error in LLM pipelines (G-theory)

- Citation: Messing, S. (2026). Hidden Measurement Error in LLM Pipelines Distorts Annotation, Evaluation, and Benchmarking. arXiv:2604.11581 (v6, May 2026). https://arxiv.org/abs/2604.11581 (title and G-theory framing from search snippet and page title; the fetched abstract describes "design-study projections", likely decision-study, so wording is not verified.)
- Claim: standard confidence intervals ignore variability from judge choice, temperature and prompt phrasing, so they understate uncertainty.
- Method: decomposes pipeline uncertainty into components and uses projections to choose design changes. Search snippet only: items are the object of measurement and prompt variants, judges and replications are facets.
- Key numbers (abstract): naive SEs are 40-60% smaller than the corrected SE; on Chatbot Arena, naive 95% intervals lose coverage as n grows; halved MMLU estimation error after design changes.
- How it relates to us: it is a template for treating prompt or input variants as a G-theory facet and projecting how many conditions and replications are needed. It is about LLM-as-judge and annotation pipelines, not accuracy on coding items with input modality as a facet, and it does not address whether conditions measure the same ability.

## Searches with no direct hit

- I found no paper applying differential item functioning or measurement invariance to LLM prompt format or input modality. Searches returned general LLM psychometrics work (a systematic review, Ye et al. 2025, arXiv:2505.08245, whose abstract does not mention DIF or invariance) and human-testing DIF papers. Absence in search is not proof of absence.
- No study found of code-from-screenshot versus code-as-text on identical long-context coding problems. Code-Vision (arXiv:2502.11829) and Design2Code surfaced but concern tasks where the image carries information the text lacks; I did not read them.

## Gaps relevant to us

- Modality gap papers (IsoBench, SEAM) report aggregate gaps and agreement, not many-facet Rasch or DIF, so item-level condition effects are untested.
- Token-compression papers (Text or Pixels, VTCBench, Glyph) test retrieval, summarization and QA, not coding problems with long context.
- No prior work found asking whether image-context and text-context coding are the same ability (unidimensionality across conditions, cross-condition latent correlation).
- G-theory has been used for LLM pipelines (judges, prompts) but not with input modality as a facet, and not with a decision study on how many conditions are needed.
- Format sensitivity work treats text format perturbations; rendering parameters (font, resolution, layout) as a facet in image conditions is unexamined in what I found.
- Token savings and accuracy loss are reported separately; a joint per-item view (cost per correct answer by condition) is missing.
