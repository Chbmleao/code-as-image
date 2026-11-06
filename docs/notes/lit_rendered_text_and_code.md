# Methodology of papers that evaluate VLMs on text or code rendered as images

Covers how published papers evaluate VLMs on text or code rendered as images: conditions, rendering, controls, and statistics. Compiled 2026-10-29.

Tags: [web: URL] = read on the linked arXiv HTML or abstract page, via a fetch tool that summarizes the page (spot-check numbers against the PDF before citing). [ours] = our own inference or design. Papers in section B were summarized from earlier reading and not reopened for this note. Anything seen only as a search snippet is labelled "snippet only". Where a field is absent in the source, the note says "not stated".

---

## A. Papers read via their HTML or abstract pages

### A1. Reading, Not Thinking (Sun et al., 2026)

- Citation: Kaiser Sun, Xiaochuang Yuan, Hongjun Liu, Chen Zhao, Cheng Zhang, Mark Dredze, Fan Bai. "Reading, Not Thinking: Understanding and Bridging the Modality Gap When Text Becomes Pixels in Multimodal LLMs". arXiv:2603.09095 (v1 10 Mar 2026, v3 30 May 2026). [web: https://arxiv.org/abs/2603.09095]
- Claim: the text-to-image gap depends on rendering choices and is small for natural document images; the main cause is reduced reasoning effort under image input (outputs 5 to 19x shorter), and self-distillation on the model's own text-mode traces closes it. [web: https://arxiv.org/abs/2603.09095]
- Conditions: five modes. Pure Text; Pure Image; Instruction as text + content as image; OCR-1P (transcribe then solve in one pass); OCR-2P (transcribe in pass 1, solve the extracted text as plain text in pass 2). [web: https://arxiv.org/html/2603.09095v3]
- Rendering: Pure Image uses a 1280x720 canvas, black on white. Fonts swept: default (NotoSansMath), inverted colors, monospace (DejaVuSans Mono), handwriting; "font choice can swing accuracy by up to 47 percentage points". Resolution scale sweep on ARC and HumanEval with a FLOPs-equivalence marker; a compact 10pt rendering is mentioned. DPI and font-size sweep details: not stated. [web: https://arxiv.org/html/2603.09095v3]
- Models and data: 7 MLLMs (Qwen2.5-VL-7B and 32B, Qwen3-VL-8B, InternVL3-8B, InternVL3.5-8B, Pixtral-12B, GPT-5.2). Items: MMLU 14,042; ARC-C 1,172; GPQA Diamond 198; GSM8K 1,319; HumanEval 164 (pass@1); QASPER 1,445; SQuAD v2 100. [web: https://arxiv.org/html/2603.09095v3]
- Decoding and statistics: zero-shot, temperature 0.1 (0.2 for code), max 1024 tokens, OCR-1P max 4096. Number of runs/seeds: not stated. CIs and significance tests: not stated (the appendix lists "Statistical reporting" as a limitation). One correlation, OCR-2P word error rate vs Pure Image accuracy r = 0.238, without CI. [web: https://arxiv.org/html/2603.09095v3]
- Confound controls: OCR-2P as a recognition check; natural vs synthetic renderings; font and resolution sweeps; an error taxonomy (4,195 errors, grounded theory, kappa 0.57 to 0.69). Inference drawn: image mode does not impair perception or knowledge, because calculation and format errors rise while factual and reasoning errors stay flat. This is inferred from error-category frequencies, not a direct test. [web: https://arxiv.org/html/2603.09095v3]
- Same or different capability: argues the capability is the same and the deficit is behavioral (shorter reasoning). [web: https://arxiv.org/html/2603.09095v3]
- Copy: the five-mode design, in particular the OCR-2P two-pass control and the output-length measurement per condition. Avoid: HumanEval with 164 items and no uncertainty, and the single r with no CI. [ours]
- Relevance to us: it has a mode with the instruction as text and the content as image (like our text task with rendered repository context) and it includes HumanEval, so it is the nearest design on the "same ability" question. Its output-length finding is a confound worth logging (completion tokens per condition), since a shorter answer is a different failure from a misread identifier. [ours]

### A2. VISTA-Bench (Liu et al., 2026)

- Citation: Qing'an Liu, Juntong Feng, Yuhao Wang, Xinzhe Han, Yujie Cheng, Yue Zhu, Haiwen Diao, Yunzhi Zhuge, Huchuan Lu. "VISTA-Bench: Do Vision-Language Models Really Understand Visualized Text as Well as Pure Text?" arXiv:2602.04802 (v3). [web: https://arxiv.org/abs/2602.04802]
- Claim: most of 30+ VLMs score lower on visualized text than on the same text (example Qwen3-VL-8B-Instruct 59.1 text vs 52.3 visualized); harder rendering widens the gap. [web: https://arxiv.org/html/2602.04802v3]
- Conditions: pure text vs visualized text for the same instance (dual-format items). 1,500 items (1,462 multiple choice, 38 open), drawn from MMBench, SEED-Bench, MMMU, MMLU after manual review of about 4,000 candidates. [web: https://arxiv.org/html/2602.04802v3]
- Rendering: LaTeX. Defaults Arial 16pt, width 800 px, DPI 72.27, margins 60/40 px, adaptive height. Font sweep over Arial, Times New Roman, Cambria, Brush Script MT at 9, 16, 32, 48 pt (preliminary sweep also 64 pt, on two 8B models). Layout ablation one parameter at a time on two models: width 512/800/1024, margin 20/60/100. Analysis is a table/figure of point accuracies per setting. [web: https://arxiv.org/html/2602.04802v3]
- Quality and OCR controls: a VLM judge scored render fidelity 0 to 2 with manual review below 2 (judge agreed with humans 75% on 200 samples); Tesseract, DeepSeek-OCR and PaddleOCR-VL-1.5 used to convert images to text for two models. The OCR result itself was not in the part of the page I could read. Subset-size check at 500/1,000/1,500 items. [web: https://arxiv.org/html/2602.04802v3]
- Evaluation and statistics: VLMEvalKit default decoding; one wrapper uses sampling at temperature 0.7 with no seed given; runs, CIs, significance tests: not stated. [web: https://arxiv.org/html/2602.04802v3]
- Same or different: the authors call the gap a non-equivalence and say large gaps persist under clean settings, pointing to limits beyond readability, without a definitive verdict. [web: https://arxiv.org/html/2602.04802v3]
- Copy: a render-fidelity check before scoring, and one-factor-at-a-time layout ablations. Avoid: mixed decoding settings across models, which makes the gap partly a harness effect. [ours]

### A3. ReadBench (Clavie and Brand, 2025)

- Citation: Benjamin Clavie, Florian Brand. "ReadBench: Measuring the Dense Text Visual Reading Ability of Vision-Language Models". arXiv:2505.19091. [web: https://arxiv.org/html/2505.19091v1]
- Claim: all VLMs degrade from text to image input, more on multi-page contexts; degradation is mostly model-specific. [web: https://arxiv.org/html/2505.19091v1]
- Conditions: text-only vs multimodal, where the context (or answer options for short-context sets) is an image and the question stays text. MMLU-Redux, MMLU-Pro, GPQA-Diamond; BABILong and LongBench subsets capped at 8k tokens (about 12 pages). [web: https://arxiv.org/html/2505.19091v1]
- Rendering: A4 pages, Arial 12 pt, 92.9 PPI, continued onto new pages, last page cropped. Margins, spacing, pixel size: not stated. Resolution sweep 72 to 300 PPI on Gemini 2.0 Flash only; "little variation"; no statistics. [web: https://arxiv.org/html/2505.19091v1]
- Models and sample: 9 VLMs (Pixtral 12B, Qwen2.5-VL 7B and 32B, GPT-4o, Gemini 1.5 Pro and 2.0 Flash named). Up to 35 examples per benchmark subset, justified by a claimed high correlation with full-dataset results (value not reported). Average of 3 runs. CIs and tests: not stated. [web: https://arxiv.org/html/2505.19091v1]
- Item-level analysis: yes, partly. Jaccard overlap of 20 to 35% between models' mismatch sets and 3.1% of questions affecting more than five models. This is the only paper here that looks at which items break, by overlap counts rather than a model. [web: https://arxiv.org/html/2505.19091v1]
- Copy: the mismatch-set overlap idea (it argues for item-level analysis). Avoid: 35 items per subset, and a resolution sweep on one model. [ours]

### A4. PixelWorld (Lyu, Ma, Chen, 2025)

- Citation: Zhiheng Lyu, Xueguang Ma, Wenhu Chen. "PixelWorld: How Far Are We from Perceiving Everything as Pixels?" arXiv:2501.19339. [web: https://arxiv.org/html/2501.19339]
- Claim: pixel input (PEAP) matches token input on sentence and paragraph tasks but drops on reasoning and code; smaller models drop more. [web: https://arxiv.org/html/2501.19339]
- Conditions: text-only; PEAP (text rendered, with an added instruction "follow the instruction in the image", i.e. all-image); semi (tables as image, question as text); multimodal. [web: https://arxiv.org/html/2501.19339]
- Rendering: adaptive width 512 to 1024 px, fixed height 256 px, font 15 to 25 pt, padding 5 to 30 px, plus several noise augmentations; DPI and systematic font sweeps: not stated. [web: https://arxiv.org/html/2501.19339]
- Models: 5 (Qwen2-VL-2B and 7B, Phi-3.5-vision, Gemini-1.5-flash-002, GPT-4o). Test sizes include MBPP 757 (pass@1, CoT), GSM8K 1,319, MMLU-Pro 12,032. Zero-shot. Runs, seeds, temperature, CIs, tests: not stated. The authors' own limitations include single-run results and no render-parameter sweeps. [web: https://arxiv.org/html/2501.19339]
- Confound handling: identical prompts plus the image instruction; no controlled OCR-vs-PEAP comparison for text tasks; MMMU-Pro numbers taken from the original paper, not rerun. [web: https://arxiv.org/html/2501.19339]
- Same or different: "partial transfer", not equivalence. [web: https://arxiv.org/html/2501.19339]
- Copy: running a code benchmark with pass@1 in the image condition. Avoid: random font size and noise per item (render variance is then confounded with item), and borrowing numbers from other papers. [ours]

### A5. VisInContext (Wang et al., NeurIPS 2024)

- Citation: Alex Jinpeng Wang, Linjie Li, Yiqi Lin, Min Li, Lijuan Wang, Mike Zheng Shou. "Leveraging Visual Tokens for Extended Text Contexts in Multi-Modal Learning". arXiv:2406.02547, NeurIPS 2024. [web: https://arxiv.org/abs/2406.02547]
- Claim: rendering long text as images extends in-context length from 256 to 2048 tokens at nearly the same FLOPs. [web: https://arxiv.org/abs/2406.02547]
- Method: training-side work (Open-Flamingo 9B, a 56B MoE), not an evaluation of off-the-shelf VLMs. Font HERSHEY 10 px default; font-size sweep 4, 6, 8, 10, 12 px reported as accuracy per setting (TextVQA 15.4 / 17.2 / 18.5 / 21.8 / 20.3; DocVQA 39.8 / 42.5 / 45.6 / 44.3 / 36.2); about 1.5 text tokens per 16x16 patch; interval-threshold sweep. Runs, seeds, CIs, tests: not stated. [web: https://arxiv.org/html/2406.02547v1]
- Copy: a font-size sweep reported as a table is the only place here where the sweep shows a non-monotone optimum (accuracy peaks mid-range and falls at the largest size), which is a reason not to assume accuracy is monotone in font size. Avoid: training the model to the render. [ours]

### A6. VIST (Xing et al., NeurIPS 2025 spotlight)

- Citation: Ling Xing, Alex Jinpeng Wang, Rui Yan, Xiangbo Shu, Jinhui Tang. "Vision-centric Token Compression in Large Language Model". arXiv:2502.00791, NeurIPS 2025. [web: https://arxiv.org/html/2502.00791v5]
- Claim: a frozen vision encoder plus a trained resampler reads distant context as images, giving 2.3x fewer tokens at matched in-context-learning accuracy. [web: https://arxiv.org/html/2502.00791v5]
- Method: Noto Sans 10 px; 14x3584 strip equal in pixels to 224x224; 4,096 text tokens become 28 images x 64 = 1,792 visual tokens; visual tokens per image swept 32/64/96/128. TinyLlama base, Mistral 7B check. In-context learning on 11 datasets with 250 examples each, averaged over three seeds (42, 43, 44), variance not reported. No CIs or tests. Compression-rate-matched baselines (ToMe, FastV) are used as controls. [web: https://arxiv.org/html/2502.00791v5]
- Copy: baselines matched on compression rate, so a gain cannot be explained by fewer tokens alone. Avoid: training-based design, not our setting. [ours]

---

## B. Papers summarized from earlier reading, methodology only

Summarized by the same fields as section A.

| Paper | Link | Conditions | Rendering and sweep | Controls | N and stats |
| -- | -- | -- | -- | -- | -- |
| DeepSeek-OCR (Wei et al., 2025) | [web: https://arxiv.org/abs/2510.18234] | image only, OCR decode | native modes 64/100/256/400 vision tokens; pages not rendered by authors (Fox, 100 English pages) | none; authors say OCR alone does not validate compression | precision by text-token bin (97% under 10x, about 60% at 20x); one model; no CI |
| Glyph (Cheng et al., 2025) | [web: https://arxiv.org/abs/2510.17800] | text LLM vs image-trained VLM | DPI 72/96/120 sweep on Ruler: 4.0x/72.17, 2.2x/91.23, 1.2x/94.67 | OCR alignment ablation (8.12 on LongBench) | benchmark scores, single runs, no CI |
| VTCBench (Zhao et al., 2025) | [web: https://arxiv.org/abs/2512.15649] | text vs image | fonts 4, sizes 10 to 20 px, 96 DPI, 896x896, line height 1.0 to 2.0; Wild set = 99 configs | retrieval vs reasoning task contrast | 13 VLMs; point scores, no CI |
| Text or Pixels (Li et al., 2025) | [web: https://arxiv.org/abs/2510.18279] | text vs image | LaTeX, 300 DPI, 600x800 to 750x1000 pages, adaptive font | none found | few models, point scores |
| CodeOCR (Shi et al., 2026) | [web: https://arxiv.org/abs/2602.01785] | text vs image at 1x/2x/4x/8x | 2240x2240, 40 px monospace, downsampled 1/2/4/8x; plain/bold/highlight | transcription probe on 100 snippets (token, line, block errors) | 7 models, 5 repeated runs, Wilcoxon signed-rank; no unit tests, no psychometrics |
| LongCodeOCR (Zhong et al., 2026) | [web: https://arxiv.org/abs/2602.00746] | Mixed-style (code image, instruction text) vs pruning baselines | Verdana vs JetBrains Mono, 1 vs 2 columns; size/DPI not extracted | none | 3 open models; no repeats or tests found |
| CodeShrink (Tang et al., 2026) | [web: https://arxiv.org/abs/2607.29637] | text vs image with adaptive render | binary search on font size under token budget | baselines matched to text token count | one main model; no tests found |
| Liang et al., 2026 | [web: https://arxiv.org/abs/2608.09268] | text vs rendered code in SWE-bench Verified agent | renderer picks resolution/font/pages; sizes not reported | none per-font | 100 tasks, one run per cell, no CI |
| IsoBench (Fu et al., 2024) | [web: https://arxiv.org/abs/2404.01266] | isomorphic text vs image | not rendering-focused | multiple representations per item | gap 28.7 / 18.7 / 14.9 points (abstract); item analysis not verified |
| SEAM (Tang et al., 2025) | [web: https://arxiv.org/abs/2508.18179] | notation-matched text vs image | notation, not rendered text | agreement metric | 21 models; abstract level only |

---

## C. Candidates checked but not used or not opened

- ScreenCoder, VisualWebBench: not opened. They concern screenshot-to-code and web UI tasks where the image carries information the text does not, so they are out of scope for a same-content comparison. [ours]
- "Can VLMs read code from screenshots": the search returned no dedicated paper. Closest hits were CodeOCR (section B) and Nagaonkar et al., arXiv:2502.06445, OCR on video frames including a code editor with WER/CER; snippet only, not opened. [web: https://arxiv.org/abs/2502.06445v1]
- OCRVerse (arXiv:2601.21639) and Vision2Code: snippet only; image-to-code, out of scope. [web: https://arxiv.org/pdf/2601.21639]
- "Seeing is believing" style long-context-via-images papers: not found under a clear title; not used.
- PDF fetches of VISTA-Bench, ReadBench and VisInContext failed (binary); the HTML pages were used instead.

---

## D. Synthesis

Standard practice in this literature (as read above):

1. Condition set: text vs image, usually with the question kept as text (ReadBench, LongCodeOCR) or all-image with an added instruction (PixelWorld). Only Reading, Not Thinking has a full ladder including a text-instruction-plus-image-content mode and OCR-then-solve. [web: https://arxiv.org/html/2603.09095v3]
2. Rendering is mostly a single default (Arial 12 or 16 pt, 800 px or A4, 72 to 96 PPI). Sweeps exist but are small: VisInContext 5 font sizes, VISTA-Bench 4 to 5 sizes on 2 models, ReadBench resolution on 1 model, Glyph 3 DPIs, VTCBench 99 configs. The analysis is a table or line of point accuracies against the setting or compression ratio; none fits a model of accuracy against px per character. [web: https://arxiv.org/html/2406.02547v1] [web: https://arxiv.org/html/2602.04802v3] [web: https://arxiv.org/html/2505.19091v1]
3. Confound control is thin: same content is assumed from the render, with an OCR or transcription check in only some papers (Reading, Not Thinking OCR-2P; VISTA-Bench OCR tools; CodeOCR probe). Matching compression rate across methods is done in VIST and CodeShrink. [web: https://arxiv.org/html/2502.00791v5]
4. Rigor: the dominant pattern is one run, point accuracy, no CI, no test. Exceptions: CodeOCR (5 runs, Wilcoxon), ReadBench (3 runs, no CI), VIST (3 seeds, no variance reported). Samples are often small (35 per subset; HumanEval 164; 100 SWE tasks). [web: https://arxiv.org/html/2505.19091v1] [web: https://arxiv.org/html/2603.09095v3]
5. Same-ability claims are made from aggregate gaps or error-category counts. Reading, Not Thinking says the ability is shared and only behavior differs; PixelWorld says partial transfer; VISTA-Bench says non-equivalence. No paper tests equivalence at the item level (a paired response matrix, item correlations across conditions). ReadBench's mismatch-set overlap is the nearest. [web: https://arxiv.org/html/2505.19091v1]
6. Code with unit tests under rendering is rare: HumanEval 164 and MBPP 757 (pass@1) in the above, and the SWE-bench agent study. Small open VLMs of 7B to 27B on repo-level code with only the context rendered are not covered. [web: https://arxiv.org/html/2501.19339]

Where our design adds something [ours]:

- Five models, two benchmarks (CoderUJB Java, DevEval Python), four conditions (text, and image at 10, 12 and 14 px) and 3 runs at T 0.7, with the task always in text and only the repository context rendered, so variance from model, item, render size and sampling can be separated.
- A per-model paired gap with a project-clustered interval and a binomial GLMM with condition as a facet, instead of point accuracies.
- A separate transcription test on the rendered pages, so reading failures can be told apart from coding failures (CodeOCR has a probe, but not per item against execution-scored tasks).
- Completion length per condition is worth logging: Reading, Not Thinking shows it differs 5 to 19x.
- Several small open models under one harness (vLLM) and one decoding setting, with render fidelity checked before scoring (VISTA-Bench style).

Caveats [ours]: the fetch tool summarizes pages with a small model, so figures above should be spot-checked against the PDF; the OCR-control outcome in VISTA-Bench was not readable in the source used; the ReadBench model list is incomplete in the source used.
