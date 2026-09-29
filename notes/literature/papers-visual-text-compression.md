# Visual text compression: paper notes

Compiled 2026-09-28 from arXiv abstract and HTML pages. Numbers below were read from the sources. CodeOCR, LongCodeOCR and CodeShrink were read in full from the arXiv HTML (2026-09-28); the "(check)" marks were removed from them. Where a page was summarized by a fetch tool rather than read line by line (VTCBench, Text or Pixels), the numbers should be spot-checked against the PDF before they go into the report; these are marked "(check)". Anything not found in the source is marked "not verified" or UNVERIFIED.

Project reference: pilot with Qwen2.5-VL-7B, text 13/20, image tiny font 5/20 at ~3.4x fewer tokens, mono-12 12/20 at ~1.5x fewer, failures mostly misread identifiers.

---

## 1. DeepSeek-OCR

Citation: Haoran Wei, Yaofeng Sun, Yukun Li (DeepSeek-AI). "DeepSeek-OCR: Contexts Optical Compression". arXiv:2510.18234, submitted 21 Oct 2025. Technical report, no venue found. https://arxiv.org/abs/2510.18234

Claim: long text can be compressed through optical 2D mapping. With text tokens within 10x the vision tokens, OCR decoding precision is about 97%; at about 20x it is about 60%.

Method:
- Model: DeepEncoder (SAM-base window attention, 2-layer conv 16x token downsampler, CLIP-large global attention) plus DeepSeek3B-MoE-A570M decoder (about 570M active parameters).
- Resolution modes (native): Tiny 512x512 = 64 vision tokens, Small 640x640 = 100, Base 1024x1024 = 256, Large 1280x1280 = 400; plus dynamic "Gundam" tiling modes.
- The compression study does not render text itself: it feeds existing Fox benchmark document pages (English part, 100 pages with 600 to 1300 text tokens by the DeepSeek tokenizer) and asks "Free OCR." Text tokens divided by vision tokens gives the ratio.
- Training data: OCR 1.0 (scene and document), OCR 2.0 (charts, chemical formulas, geometry), general vision data.

Key numbers (Fox, Table 2, precision / compression ratio):
- 64 vision tokens: 600-700 text tokens 96.5% / 10.5x; 700-800 93.8% / 11.8x; 800-900 83.8% / 13.2x; 900-1000 85.9% / 15.1x; 1000-1100 79.3% / 16.5x; 1100-1200 76.4% / 17.7x; 1200-1300 59.1% / 19.7x.
- 100 vision tokens: 98.5% / 6.7x at 600-700; 96.8% / 9.7x at 900-1000; 91.5% / 10.6x; 87.1% / 12.6x at 1200-1300.
- OmniDocBench: beats GOT-OCR2.0 (256 tokens per page) with 100 vision tokens, and MinerU2.0 (6000+ tokens per page) with under 800.
- The authors say the metric understates true performance because output format does not match Fox exactly.

Code or prose: documents only (Fox, OmniDocBench). No code, no unit tests. The metric is OCR fidelity, not downstream task accuracy.

Note for us: the paper itself says "OCR alone is insufficient to fully validate true context optical compression" and lists needle-in-a-haystack and interleaved pretraining as future work.

How it relates to us:
- Gives the upper reference for reading fidelity versus ratio (near lossless below about 10x), for a purpose-built OCR model, not a general VLM.
- Ratios are measured in DeepSeek tokenizer tokens on page-sized inputs; our 1.5x to 3.4x is against Qwen2.5-VL token counts, so the numbers are not directly comparable.
- Does not test any reasoning, coding, or unit tests, and does not separate reading from reasoning (it only measures reading).
- Only one model. No cross-model comparison.

---

## 2. Glyph

Citation: Jiale Cheng, Yusen Liu, Xinyu Zhang, Yulin Fei, Wenyi Hong, Ruiliang Lyu, Weihan Wang, Zhe Su, Xiaotao Gu, Xiao Liu, Yushi Bai, Jie Tang, Hongning Wang, Minlie Huang (Zhipu AI; CoAI Group and KEG, Tsinghua University). "Glyph: Scaling Context Windows via Visual-Text Compression". arXiv:2510.17800, submitted 20 Oct 2025, v2 21 Oct 2025. No venue found. https://arxiv.org/abs/2510.17800

Claim: render long text as images and let a VLM read them, giving 3 to 4x token compression with accuracy comparable to text LLMs of similar size (Qwen3-8B), with up to 4.8x faster prefilling, 4.4x faster decoding and about 2x faster SFT.

Method:
- Backbone: GLM-4.1V-9B-Base, continued pretraining on rendered long text (128k context) mixed with OCR and vision-language data.
- Three stages: continual pretraining with diverse rendering styles; LLM-driven genetic search over rendering parameters (font size, layout, resolution) that maximizes accuracy and compression on a validation set; post-training with SFT, RL, and an auxiliary OCR alignment task (Levenshtein reward in RL).
- Test-time rendering resolution is a knob (DPI).
- Baselines: Qwen3-8B, Qwen2.5-7B-Instruct-1M, LLaMA-3.1-8B-Instruct, GLM-4-9B-Chat-1M, and GPT-4.1 on Ruler.
- Benchmarks: LongBench (21 datasets, 6 categories), MRCR, Ruler, MMLongBench-Doc.

Key numbers:
- LongBench average compression 3.3x (some tasks about 5x); MRCR average 3.0x.
- Ruler by rendering DPI (Table 3, average score): DPI 72, compression average 4.0x (up to 7.7x), 72.17; DPI 96, 2.2x (up to 4.4x), 91.23; DPI 120, 1.2x (up to 2.8x), 94.67. Text baselines average 86.08 to 88.61 (GPT-4.1 96.30). This is the closest published analogue to our font-size trade-off: accuracy falls as compression rises.
- Ablation (drop relative to full model): removing OCR alignment in SFT costs 8.12 on LongBench and 8.42 on MRCR.
- Limitations section: performance is sensitive to resolution, font and spacing; UUID recognition is very hard even for Gemini-2.5-Pro (misordered or misclassified characters), and the UUID task was excluded from Ruler.

Code or prose: mainly prose and long-document QA. The abstract mentions "code analysis" as a motivation. Whether the LongBench code subsets were reported separately: not verified. No unit tests. The authors state benchmarks are long-context understanding and do not cover agentic or reasoning tasks.

How it relates to us:
- Confirms our failure mode: rare alphanumeric strings are misread, which is the same as our misread identifiers. Glyph handles this by training with OCR alignment, we cannot (off-the-shelf local VLMs).
- Rendering parameters (DPI 72, 96, 120) move accuracy and compression together, supporting our font-size factor.
- One trained model, prose; no coding accuracy under unit tests, no multi-model psychometric comparison, no explicit reading versus reasoning separation beyond the OCR ablation.

---

## 3. VTCBench

Citation: Hongbo Zhao, Meng Wang, Fei Zhu, Wenzhuo Liu, Bolin Ni, Fanhu Zeng, Gaofeng Meng, Zhaoxiang Zhang (Institute of Automation CAS, UCAS, HKISI CAIR, and an independent researcher). "VTCBench: Can Vision-Language Models Understand Long Context with Vision-Text Compression?" arXiv:2512.15649, Dec 2025 (v2 23 Dec 2025). Preprint. https://arxiv.org/abs/2512.15649 ; code https://github.com/Moenupa/VTCBench (author list and details: check).

Claim: most VLMs decode rendered text well but understand long context poorly when it is delivered as vision-text-compressed input; they fail to capture long associations and dependencies.

Method (check):
- Three tasks: VTC-Retrieval (visual needle-in-a-haystack: single, multi-key, multi-value, multi-query), VTC-Reasoning (associative reasoning with minimal literal overlap between question and needle), VTC-Memory (long dialogue, adapted from LoCoMo).
- Haystack: Paul Graham essays with synthetic key-value needles. Context lengths 1k to 32k text tokens.
- Rendering: fonts Helvetica, Arial, Courier New, Times New Roman; sizes 10 to 20 px; DPI 96; 896x896 images; line height 1.0 to 2.0. VTCBench-Wild uses 99 rendering configurations (11 font sizes x 3 fonts x 3 line heights).
- Compression ratios roughly 2x to 8x depending on model and setting.
- Models: 13 VLMs (Qwen2.5-VL-7B and 72B, Qwen3-VL-8B and 235B-A22B, DeepSeek-OCR, Kimi-VL-A3B, Gemma3-27B, GLM-4.1V-9B-Thinking, InternVL3.5-8B and 38B, Glyph, Gemini-2.5-Pro, GPT-5) plus text baselines Qwen3-8B and Gemini-3-Pro.

Key numbers (check):
- Retrieval at 1k context, ratio 2x: Qwen3-VL-235B 97.16, Qwen3-VL-8B 95.23, Glyph 91.48, text Qwen3-8B 98.86. At 32k Qwen3-VL-235B falls to 81.34 while Qwen3-8B holds 95.57.
- Reasoning at 1k: best VLM (Qwen2.5-VL-72B) 52.79, most under 40, text Qwen3-8B 94.18.
- Wild overall: Gemini-3-Pro as VLM 87.64 (text 89.29), Gemini-2.5-Pro 63.68, GPT-5 61.23, Qwen2.5-VL-72B 57.36, Qwen3-8B text 73.55.
- Lost-in-the-middle pattern for needle depth; sensitivity to font size and layout.

Code or prose: prose (essays, dialogue). No code.

How it relates to us:
- Best example of many-model comparison under rendered context, and it partly separates perception from reasoning by contrasting retrieval with associative reasoning. It does this through task design, not by labeling individual errors as reading or reasoning.
- No unit tests, no code, no psychometric methods (no item response models, reliability, or item-level analysis; not verified in the source, based on the task descriptions).
- Includes Qwen2.5-VL-7B, our pilot model, so its numbers give a direct sanity check for our prose-side behavior.

---

## 4. Extra related work (at most 4, ordered by relevance to code)

### 4a. CodeOCR

Citation: Yuling Shi, Chaoxiang Xie, Zhensu Sun, Yeheng Chen, Chenxu Zhang, Longfei Yun, Chengcheng Wan, Hongyu Zhang, David Lo, Xiaodong Gu. "Seeing Is Coding: On the Effectiveness of Vision Language Models in Code Understanding" (the repo and Hugging Face page use the name CodeOCR). arXiv:2602.01785 (v1 2 Feb 2026, later versions to 14 Aug 2026). Proc. ACM Softw. Eng. vol 3 (ISSTA 2026), DOI 10.1145/3832167. https://arxiv.org/abs/2602.01785 ; code and data https://github.com/YerbaPage/CodeOCR. Read in full from the arXiv HTML.

Models: 7. Open: Qwen-3-VL 235B, GLM-4.6v 108B. Proprietary: GPT-5-mini, GPT-5.1, Gemini-2.5-Pro, Gemini-3-Flash, Gemini-3-Pro. No model under 100B.

Rendering: 2240x2240 canvas, VS Code monospace 40 px, line height 1.0, 1% margin, Pygments plus Pillow. Variants plain, bold, syntax highlighted. Bilinear downsampling to 1x, 2x, 4x, 8x (8x is 12.5% of the text tokens). Ratio is against the text token count.

Tasks and scoring: completion (200 Python and 200 Java, average about 6.1k and 5.7k tokens; EM and ES), summarization (109 examples, LLM judge CompScore by DeepSeek-V3.2), type-4 clone detection (GPTCloneBench, F1), code QA (authors' CodeQA built from repos created after Aug 2025, accuracy). Five repeated runs and Wilcoxon signed-rank tests. No unit tests, no pass@k.

Numbers: clone F1 GPT-5-mini 33.2 to 47.0, GPT-5.1 46.8 to 62.4 (p<0.01), text to image at 1x. Completion ES Gemini-3-Flash 55.1 to 57.1, Gemini-3-Pro 55.8 to 57.7 (p<0.05), Gemini-3-Pro 58.0 at 8x. QA Gemini-3-Pro 74.8 to 77.2 at 1x, 79.5 at 8x. Weak open models suffer: GLM-4.6v QA 72.6% falls to 39.7% at 8x (p<0.01). Highlighting helps a little at low compression. The 58.8 ES at 8x for Gemini-3-Flash in the earlier note was not re-confirmed: UNVERIFIED.

Reading versus reasoning: RQ5 is a reconstruction probe. 100 fresh snippets (average 473.1 tokens), all 7 models, 1x to 8x, prompt "Transcribe the code in the image exactly". Errors are classed token, line, block, growing with compression. It is a separate task, not a per-item label of failed coding answers. No per-item analysis or item-level uncertainty beyond the tests above.

How it relates to us: closest paper. It has the same reading-error story and a transcription probe. Its models are proprietary or over 100B, and its tasks tolerate misread identifiers. No unit tests, no psychometrics (0 hits for unit test, pass@ or psychometric terms in the full text).

### 4b. LongCodeOCR

Citation: Jianping Zhong, Guochang Li, Chen Zhi, Junxiao Han, Zhen Qin, Xinkui Zhao, Nan Wang, Shuiguang Deng, Jianwei Yin (Zhejiang University, Hangzhou City University, Shenzhou Aerospace Software). "Can Vision-Language Models Handle Long-Context Code? An Empirical Study on Visual Compression". arXiv:2602.00746 v1, cs.SE, 31 Jan 2026. Venue: UNVERIFIED (none stated). No code link found. https://arxiv.org/abs/2602.00746. Read in full from the arXiv HTML.

Setup: only the code context is rendered as image sequences, the instruction stays text (our Mixed condition). Models: Qwen3-8B (text baseline), Qwen3-VL-8B, Glyph (9B), all open. Baselines: LongCodeZip, LLMLingua variants, RAG, random line. GPT-4o, Llama 3.1 405B and Gemini 2.5 Pro appear only as published reference numbers, not run.

Tasks and scoring: Long Module Summarization (139 instances over 2k tokens, CompScore), LongCodeQA (443 instances, 98 repos, accuracy), LCC and RepoBench-P (ES, EM). No unit tests, no significance tests, no repeated runs found.

Rendering: single-column layout by default, Verdana; the sensitivity study compares Verdana with JetBrainsMono-Regular and single with two columns. Exact font size and DPI: UNVERIFIED (not extracted). Visual token estimate is H*W/(16*16*4) for Qwen3-VL-8B and H*W/(14*14*4) for Glyph. Average ratios 1.7x, 1.6x, 2.0x, 2.0x (Table 2).

Numbers: summarization CompScore 87.25 versus LongCodeZip 50.40 at about 1.7x (Glyph 72.74; abstract says +36.85). QA 70.46% versus 67.61% (Glyph 64.42%). QA at 64k 80.26 versus GPT-4o 76.3 (published); at 1M Qwen3-VL-8B 72.00 versus Gemini 2.5 Pro 69.8 (published), and Glyph 70.00% at 12.2x versus LongCodeZip 64.00% at 3.0x. Table 10 (4k to 8k, 180 instances each) RepoBench-P ES 49.56, 47.98, 48.48, 51.64, 50.70 at 1x to 5x; LCC ES 42.83, 39.35, 38.95, 35.52, 35.34. Rendering ablation: RepoBench-P ES 51.63 single column versus 49.19 two column; LCC ES 39.35 to 41.75 and EM 11.11 to 12.78 with JetBrainsMono. Discussion frames a coverage-fidelity trade-off: visual is better for global tasks, worse on exactness-critical ones.

Not re-confirmed from the old note, treat as UNVERIFIED: RepoBench-P ES 50.22 versus 39.48 at 2.0x, and LCC Glyph ES 45.90 / EM 13.60.

Reading versus reasoning: no error-type or transcription analysis. Only the fidelity argument in the discussion.

How it relates to us: Mixed-style setup on code with small open VLMs (two, 8B and 9B), compared with pruning baselines. Similarity and QA metrics, no unit tests, no psychometrics (0 hits).

### 4c. CodeShrink

Citation: Wenxin Tang, Jingyu Xiao, Zhenyu Liu, Zipeng Xie, Junliang Liu, Wang Luo, Yuan Jiang, Yintong Huo, Michael Lyu. "CodeShrink: Adaptive Visual Compression for Efficient Multimodal Code Understanding". arXiv:2607.29637 v1, cs.CV, 31 Jul 2026. Venue: UNVERIFIED (none stated). Code https://github.com/vinsontang1/CodeShrink. https://arxiv.org/abs/2607.29637. Read in full from the arXiv HTML.

Method: Blank-Free Rendering (binary search for the largest font under a token budget, adaptive page count, indent markers, patch-grid alignment; example in the paper: font 22 px to 32 px at the same budget, blank coverage 41.9% to 1.2%), Dominant Token Selection to prune visual tokens, and an Adaptive Compression Configuration agent (Qwen3.5-0.8B, SFT then GRPO, 38,400 possible actions). Downstream Qwen3.5-27B with LoRA rank 16. Table III also runs Qwen3-VL-235B-A22B, GPT-5-mini and Gemini-3-Flash at 1x to 8x, 200 samples, 5 runs. Greedy decoding, seed 42.

Tasks and scoring: code QA (300, CodeOCR's set), clone detection (200 balanced type-4, GPTCloneBench), completion (200, LongCodeCompletion), Python and Java. Accuracy, F1, ES, EM. Token reduction R = 1 - n_img^c / n_img, with baselines matched to the text token count. No unit tests, no significance tests found.

Numbers: up to 71.2% token reduction (abstract). Python (Table I): CodeShrink QA 82.3 versus text-only 81.0, R 39.7; clone Acc 68.0, F1 65.9; completion ES 60.3, EM 27.5 versus text-only 55.1 and 27.0. In the same table CodeOCR scores QA 51.7 and ES 46.4 (as run by the CodeShrink authors as a baseline; setup not checked). Ablation without ACC: Python QA 81.5 to 75.0, Java clone accuracy 70.5 to 64.5. The old note said 71.2% was on Java clone detection: UNVERIFIED, the abstract gives no task.

Reading versus reasoning: none. No per-item analysis.

How it relates to us: layout choices (whitespace wastes image area), which touches our characters-per-row factor. Fine-tuned, one main downstream model. No psychometrics (0 hits).

### 4d. Text or Pixels? It Takes Half

Citation: Yanhong Li, Zixuan Lan, Jiawei Zhou. "Text or Pixels? It Takes Half: On the Token Efficiency of Visual Text Inputs in Multimodal LLMs". arXiv:2510.18279, Oct 2025; EMNLP 2025 Findings (check). https://arxiv.org/abs/2510.18279

Method (check): text rendered with LaTeX/pdflatex at 300 DPI to 600x800, 600x1000 or 750x1000 pages with adaptive font size. Models: GPT-4.1-mini, Qwen2.5-VL-72B, and checks on Qwen2.5-VL-7B and Gemini 2.5 Flash. Ruler needle tasks: 97 to 99% (Qwen 72B) and 99 to 100% (GPT-4.1-mini) with 42 to 58% fewer decoder tokens; CNN/DailyMail summarization with 57 to 75% fewer tokens.

Code or prose: prose. The authors list coding as an untested domain.

How it relates to us: earliest clean demonstration of about 2x savings without accuracy loss for prose in general VLMs. Contrasts with our 1.5x (mono-12) at about 12/20, where identifiers matter.

Not covered in depth: PIXEL (Rust et al., pixel-based language model), CLIPPO (Tschannen et al.), VTC-R1 (arXiv:2601.22069, vision-text compression for reasoning traces) and Image Prompt Packaging (arXiv:2604.02492, could not verify tasks). Cited here only by name; their content was not verified for this note.

---

## Gaps relevant to us

- No paper found that scores rendered-context coding with unit tests. Related code work uses edit similarity, exact match, QA accuracy, clone F1 or LLM judges, all of which tolerate a misread identifier that would fail a unit test.
- Code studies use large or proprietary models (CodeOCR: two open models over 100B plus five proprietary) or one or two 8B to 27B open ones (LongCodeOCR: Qwen3-VL-8B and Glyph; CodeShrink: Qwen3.5-27B fine-tuned, plus Qwen3-VL-235B). A multi-model comparison across 3 to 5 local 7B-class VLMs on code is not covered.
- No psychometric treatment (only Wilcoxon tests and 5-run averages in CodeOCR and CodeShrink; item difficulty, reliability, item-level or model-by-item interaction) in any paper read. VTCBench compares many models but reports aggregate scores (not verified beyond the summary).
- Reading versus reasoning: CodeOCR separates reading through a reconstruction task, and VTCBench through retrieval versus associative reasoning. Nobody labels the failures of each coding item as read error (wrong identifier in the code) versus logic error, which is what our failure analysis can add.
- Mixed (context image, instruction text) versus all-image is only partly explored (LongCodeOCR and CodeOCR use mixed; a direct comparison of the two conditions on code was not found).
- Font size and characters per row are treated as tuning knobs (Glyph DPI, CodeOCR downsampling, VTCBench font sizes) but not crossed systematically with model on code.
- Compression ratios are measured against different tokenizers; we should report ratios against each model's own text token count, plus image token counts as reported by Ollama.
