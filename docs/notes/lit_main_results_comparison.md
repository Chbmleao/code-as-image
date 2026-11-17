# How the main results compare with related work

Places each finding in `results/analysis/findings.md` against published work on VLMs reading text
or code rendered as images. Compiled 2026-11-16, building on `lit_rendered_text_and_code.md`
(methods of those papers), `lit_llm_eval_variance.md` and `lit_code_eval_statistics.md`.

Tags: [body] = number read in the paper body on its arXiv HTML page, through a fetch tool that
extracts the page (check against the PDF before it goes into a paper table). [abstract] = only the
abstract or a search snippet was read. [ours] = our inference, not a claim of the cited paper.
The search was a handful of broad queries, so "not found" means not found, not "does not exist".

## Summary

| Our finding | Related work | Closest comparators |
|---|---|---|
| Mean gap -28.1 pp (CoderUJB) and -25.8 pp (DevEval), -12.8 to -36.2 per model | Agrees in direction and size for open models on exact-symbol tasks; nothing scores repo-level generation by unit tests | CodeOCR (Qwen-3-VL), ComplexCodeEval study (Qwen2.5-VL 7B) |
| Gemma 4 has the lowest token ratio (0.18 to 0.21) and loses most | Gemma 4 not evaluated anywhere; ratio vs loss trend is compatible but confounded | VTCBench, DeepSeek-OCR, CodeOCR (Gemini-3) |
| Qwen2.5-VL loses least but is weakest in text | Agrees: same floor pattern | SEAM, VISTA-Bench, Reading, Not Thinking |
| Gap differs by model (Wald); item:condition SD 0.91 and 1.39 logit; method-factor pattern | Model heterogeneity agrees qualitatively; no formal test, variance component or MTMM found | SEAM, REST, ReadBench, PromptEval |
| About 1 in 6 DevEval items copied exactly in text; removing them shrinks the gap, which stays negative | No published per-model exact-copy rate; memorization of the source projects is documented; the modality link is untested | Ramos et al. (Defects4J), MM-Detect |

None of the papers found uses CoderUJB or DevEval, and none evaluates Qwen3.5, Gemma 4 or Mistral
Small 3.2 on rendered text or code.

## 1. Size of the gap

- CodeOCR (arXiv 2602.01785, v3 Aug 2026), instruction as text and code or context rendered, 5
  repeats with Wilcoxon tests. Qwen-3-VL 235B at 1x: completion edit similarity 49.7 text vs 35.5
  image (-14.2), code QA 84.0 vs 58.1 (-25.9), both p < 0.01; its image completion score is below
  its no-context score (45.0). GLM-4.6v 108B: QA -5.9, clone detection -12.0. Gemini-3-Pro +1.9
  (completion) and +2.4 (QA), Gemini-3-Flash +2.0 and +1.4; GPT-5.1 QA -10.7, Gemini-2.5-Pro QA
  -11.0. [body]
- ComplexCodeEval compression study (arXiv 2604.13725, Apr 2026), the closest design: repo-level
  generation, Qwen2.5-VL 3B and 7B, same text instruction, only the context compressed. 7B Python
  at about 4x: BLEU 4.52 vs 9.19 with full context (-50.8%), edit similarity -8.2; 3B Java falls
  below the no-context baseline. Scored by BLEU and edit similarity, not tests, and which text
  model serves as the baseline was not confirmed. [body]
- Outside code the gap depends on the task. Short-answer reading: Qwen3-VL-8B -6.8 pp and
  InternVL3.5-8B -9.1 pp on VISTA-Bench (2602.04802). Multi-step reasoning: GSM8K Qwen3-VL-8B 93.6
  to 30.7 and InternVL3-8B 78.0 to 42.5 in Reading, Not Thinking (2603.09095); VTCBench-Wild
  reasoning 11.5 for Qwen3-VL-8B vs 62.3 for text-only Qwen3-8B (2512.15649). [body]
- Two near-zero code results do not contradict ours. Liang et al. (2608.09268, SWE-bench Verified):
  resolve rate 69 to 73% rendered vs 72% text with Qwen3.5, but 100 tasks, one run, and an agent
  that can re-read files and iterate against tests. Reading, Not Thinking HumanEval: image
  sometimes beats text (Qwen2.5-VL-7B 65.2 vs 59.1), but the authors call the 164-item benchmark
  unstable. [body]
- Reading: our gap sits at the severe end but in the range open models without training on
  rendered input show on tasks that need exact identifiers. Papers that report no loss use strong
  closed models or train for rendered input (Glyph, VTC-R1 [abstract], CodeShrink with a
  fine-tuned model). [ours]

## 2. Font size and compression

- Our token ratios (0.18 to 0.70) are not aggressive by the standards of these papers. CodeOCR
  sweeps 1x to 8x (ratios 1.0 to 0.125); completion and QA "degrade beyond 2x to 4x" for most
  models, while Qwen-3-VL already loses 14 to 26 pp at 1x. [body]
- The trend is not monotone. Qwen-3-VL completion rises from 35.5 (1x) to 41.1 (8x), toward its
  no-context score, while GLM-4.6v falls 50.8, 46.3, 44.1, 42.9. The ComplexCodeEval study calls
  its generation gap "ratio-independent" (Python edit similarity 19.20 to 20.35 from 2x to 128x,
  always below full context). [body]
- No paper sweeps font size for code. That fits our 10, 12 and 14 px being nearly equal, but the
  range is narrow: the defensible claim is that size does not explain the loss within it. [ours]
- Layout may explain part of the loss. CodeShrink (2607.29637, Jul 2026): rendering without blank
  space lifts Qwen3-VL completion at 1x from 36.2 to 54.7 edit similarity. The ratio of its
  "CodeOCR" baseline row is unconfirmed, so treat this as a hint. [body] Our packed images are a
  rendering choice a reviewer can question. [ours]

## 3. Gemma 4 and Qwen2.5-VL

- Lower ratios hurt more in VTCBench and DeepSeek-OCR (decoding precision about 97% under 10x,
  about 60% at 20x, on transcription). [body] But CodeOCR's Gemini-3 does not lose at 0.125, so
  Gemma 4's loss is more likely a property of its encoder and training than of compression alone.
  The literature neither confirms nor refutes this. [ours]
- Gemma-3-12B appears in REST (2512.08923): 75.8% equivalence across renderings, 21.3% cross-modal
  failure. [body]
- Floor pattern: SEAM (2508.18179) has Qwen2.5-VL-7B at 0.303 language vs 0.350 vision, and
  Claude-4.1-Opus losing 0.249; Qwen2.5-VL-7B gains on ARC (87.2 to 89.4) in Reading, Not Thinking
  and loses 2.7 pp on VISTA-Bench. [body, but one researcher reports reading only the SEAM
  abstract: check the PDF]

## 4. Heterogeneity across models and items

- Model-specific gaps and rank changes are documented. SEAM: Claude-4.1-Opus first in language
  (0.827) and fourth in vision (0.578). REST: equivalence across renderings from 6.6% to 90.7%,
  with consistency rankings unlike accuracy rankings. IsoBench (2404.01266): mean gaps 18.7, 14.9
  and 28.7 by model. ReadBench (2505.19091): no "universal trigger". [body for REST and ReadBench;
  SEAM and IsoBench to check in the PDF] None reports a test of heterogeneity like our Wald test;
  they give point gaps. [ours]
- Items: ReadBench is the only paper found that looks at which items break. Jaccard overlap of the
  broken sets between model pairs is 20 to 35%, and 3.1% of questions break more than five models,
  read as model-specific rather than item-specific degradation; up to 35 items per subset, 3 runs,
  no intervals. [body] Low overlap across models is compatible with an item by model by modality
  interaction; our GLMM would need an item:condition:model term to speak to it. [ours]
- No GLMM, IRT or variance-component analysis of the same items under text and image input was
  found. M3IRT (2603.02663, ICLR 2026) splits item difficulty by modality for image-plus-question
  items, not rendered text. [abstract]
- PromptEval (2405.17202) models template and example additively on the logit scale; our
  item:condition SD is the interaction that model sets to zero. [body for the model; the framing
  is ours] Sclar et al. (2310.11324): equivalent formats differ by up to 76 points. [body]
- Method factor: Desai et al. (2609.08812, Sep 2026) report that benchmarks sharing a score format
  sometimes correlate more than benchmarks sharing a concept. [abstract] No MTMM with modality as
  the method was found. Higher correlation between image sizes can also come from shared pixels
  and rendering artifacts, so present it as a hypothesis the data are compatible with. [ours]

## 5. Contamination

- DevEval's authors (2405.19856) argue leakage is slight from a mean Pass@1 difference of about
  0.36 between repositories released before and after the models; release date is a weak proxy
  for training inclusion. [body] The v1 body counts 1,874 samples in 117 repositories, the abstract
  1,825 in 115: check before citing the size. [body]
- Defects4J, the source of CoderUJB: Ramos et al. (2411.13323) find 80% membership in TheStack and
  82% 5-gram accuracy for codegen-multi, 64% for CodeLlama 7B and Gemma-2 27B, the highest of the
  bug benchmarks they test. [body] 5-gram continuation is looser than our exact copy of the
  reference function, and our rate is a union over 5 models and several runs. [ours]
- Modality: no study of whether memorized code is recalled as well from images as from text was
  found. MM-Detect (2411.03823) finds multimodal benchmark contamination often enters through text;
  Wen et al. (2506.05198) find limited, asymmetric cross-modal transfer of memorized facts. [body]
  Our reading (memorized code comes back mostly through the text path) is plausible and untested.
  [ours]
- Selection: flags come from text-mode answers, so removing flagged items removes items where text
  succeeds by construction and pulls the remaining gap toward zero. A gap that stays clearly
  negative after removal is the conservative result. The usual practice in this literature is to
  stratify (Riddell et al. 2403.04811 [abstract]; Ramos et al. with post-cutoff control
  repositories) rather than drop. [ours]

## Checks the related work suggests

1. Output length per condition, from the existing logs. Reading, Not Thinking ties much of its gap
   to shorter image-mode answers (Qwen3-VL-8B 618 vs 32 characters; 5 to 19x shorter). [body]
2. Gap on flagged vs unflagged items, with item-clustered intervals.
3. A transcription probe at 10, 12 and 14 px, to separate legibility from token budget. CodeOCR
   sees token errors (1 vs l, 0 vs O) already at 1x; on VISTA-Bench a good OCR front-end recovers
   most of the gap (-25.9 with Tesseract vs -3.1 with PaddleOCR-VL). [body]
4. Whether any model falls below a no-context baseline, as Qwen-3-VL does in CodeOCR.
5. An item:condition:model term, and repeated items to estimate repeatability within a modality.
6. A rendering without blank space as a layout control, or at least a discussion of CodeShrink's
   layout result.
