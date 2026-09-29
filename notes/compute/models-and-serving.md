# Models and serving stack for the image-context coding experiment

Date checked: 2026-09-28. Hardware: RTX 5090 (32 GB, sm_120), CUDA 13.0, PyTorch 2.11.0, 250 GB RAM.
Rule used here: a claim is stated only if I read it in a source whose URL is listed. Everything else is tagged UNVERIFIED. VRAM figures are my own arithmetic from the configs, not measurements.

## 1. Serving stack

### 1.1 vLLM on the 5090

- Latest release when checked: v0.30.0, 2026-09-22 (https://api.github.com/repos/vllm-project/vllm/releases). Its default wheel is CUDA 13.0 (https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).
- Release notes show v0.20.0 as the first release built on torch 2.11 and CUDA 13.0.2. v0.27.0 and later use torch 2.13. So "PyTorch 2.11 on the box" only matches vLLM v0.20 to v0.26. Recommendation: do not try to match the system torch. vLLM pins its own torch, so make a dedicated venv (uv) and let it install its torch. Minimum version I can defend for sm_120 with CUDA 13: v0.20.0. Pin a specific later version (for example v0.30.0) once a smoke test passes.
- Model-specific minimums (from the HF cards and release notes): Qwen3.5 needs v0.17.0 or later; Gemma 4 needs v0.19.0 or later plus transformers 5.5.0 or later.
- Known problem, FP8 block-scaled checkpoints on sm_120: issue #51884 (https://github.com/vllm-project/vllm/issues/51884), DeepGEMM "Unknown SF transformation" assert on RTX 5090 with RedHatAI Muse-Glimmer-30B-FP8-block, a regression seen between v0.26.0 and v0.27.1. This affects the official Qwen3-VL and Qwen3.5 FP8 checkpoints in principle, because they use the same block-scaled format (that link is my inference, not tested). Comments in the issue say the DeepGEMM pin was updated in #52035 (Aug 12) and again in #57218 (Sep 16), and the latest comment says the failure mode changed. Whether v0.30.0 is clean on a single 5090: UNVERIFIED. A candidate workaround is the env var VLLM_USE_DEEP_GEMM=0 (exists, default 1, in https://raw.githubusercontent.com/vllm-project/vllm/main/vllm/envs.py). That it fixes this bug: UNVERIFIED.
- Other issues I read while researching: https://github.com/vllm-project/vllm/issues/47005, https://github.com/vllm-project/vllm/issues/55775, https://github.com/vllm-project/vllm/issues/44209. I did not retain details from them beyond the FP8 finding, so I make no claim about FlashAttention or FlashInfer breakage on consumer Blackwell. Status of FlashAttention and FlashInfer on sm_120: UNVERIFIED. Plan: run a smoke test and, if attention fails, force the backend with VLLM_ATTENTION_BACKEND.
- AWQ and GPTQ 4-bit: expected to run through Marlin kernels, which are not tied to a compute capability. No sm_120-specific bug found, but I did not test. UNVERIFIED in practice.
- FP8 weight-only for models above about 20B does not fit anyway (see section 2), so the FP8 bug matters mostly for the 8B-class FP8 option, which we do not need because BF16 fits.

### 1.2 Per-request image resolution

- Verified in source: chat completion requests accept a per-request `mm_processor_kwargs` field (https://raw.githubusercontent.com/vllm-project/vllm/main/vllm/entrypoints/openai/chat_completion/protocol.py). Engine-level defaults are set with `--mm-processor-kwargs` (https://docs.vllm.ai/en/latest/configuration/conserving_memory/).
- Qwen3-VL code path in vLLM handles `min_pixels`, `max_pixels` and a size dict (https://raw.githubusercontent.com/vllm-project/vllm/main/vllm/model_executor/models/qwen3_vl.py). Qwen2.5-VL uses the same knobs (documented on its HF card, https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct). Visual tokens are about pixels / (28*28) after 14-pixel patches and 2x2 merge.
- InternVL uses `max_dynamic_patch` (default 12) instead of pixel bounds. Not sent through the same key names, check per model. Gemma and Mistral pixel controls: UNVERIFIED.
- Other relevant flags: `--limit-mm-per-prompt` and `--mm-processor-cache-gb` (default 4 GiB) (https://docs.vllm.ai/en/latest/features/multimodal_inputs/). Turn the cache off or note it when timing runs.
- Experiment note: since we render the image ourselves at a fixed size, the safest control is to render to an exact size and set min_pixels = max_pixels so the processor never resizes. Font size then maps directly to tokens.

### 1.3 Counting image tokens

- The OpenAI-compatible server returns a `usage` object with `prompt_tokens`. That the count includes the expanded image placeholder tokens: I did not find it stated in the docs I read, so UNVERIFIED as a documented guarantee. I could not locate the UsageInfo class in the current source layout either.
- Plan that does not depend on the docs: (a) send the request with max_tokens=1 and read usage.prompt_tokens; (b) send the same text-only prompt and diff, giving image tokens directly; (c) cross-check against the grid computed from the image size (h/28 * w/28 for Qwen). Do this once per model at the start and keep the check in the harness.

### 1.4 Alternatives (brief)

Latest releases seen via the GitHub API: SGLang v0.5.20 (2026-09-18), Ollama v0.34.4 (2026-09-23). Their sm_120 and CUDA 13 support: UNVERIFIED, I did not test them. llama.cpp release tag lookup returned an odd value, so I give no version.
- SGLang: same OpenAI-style API, worth trying only if vLLM breaks on a model.
- llama.cpp and Ollama: run GGUF quants (Unsloth and lmstudio-community GGUFs exist for Qwen3.8 and Muse-Glimmer; a Gemma 3 27B QAT q4_0 GGUF exists). Opinion: weaker fit here because pixel bounds and token accounting are less controllable, batching for many sampled runs is slower, and results would mix in a different quantization. Use only as a fallback.

## 2. Candidate models

Params, license and config values come from https://huggingface.co/api/models/<id> and https://huggingface.co/<id>/raw/main/config.json. KV size is 2 * full-attention layers * KV heads * head_dim * 2 bytes per token (bf16), at 32k tokens. Weights: BF16 = 2 bytes/param, 4-bit about 0.55 bytes/param including scales. Vision encoder and activations add roughly 1 to 3 GB (my estimate, UNVERIFIED). Fits = weights + KV + about 3 GB under 32 GB.

| Model | Params | License | Max ctx | BF16 | 4-bit | KV at 32k | Fits 32k on 32 GB |
|---|---|---|---|---|---|---|---|
| Qwen2.5-VL-7B | 8.29B | Apache-2.0 | 128000 | 16.6 GB | 4.6 GB | 1.9 GB | yes, BF16 |
| Qwen2.5-VL-32B | 33.45B | Apache-2.0 | see card | 67 GB | 18.4 GB | 8.6 GB | 4-bit only, about 30 GB, tight |
| Qwen2.5-VL-72B | 73.4B | Qwen license | see card | 147 GB | 40 GB | n/a | no |
| Qwen3-VL-8B | 8.77B | Apache-2.0 | 262144 | 17.5 GB | 4.8 GB | 4.8 GB | yes, BF16 |
| Qwen3-VL-32B | 33.36B | Apache-2.0 | 262144 | 67 GB | 18.3 GB | 8.6 GB | no official 4-bit; FP8 33 GB no |
| Qwen3-VL-30B-A3B | 31.07B | Apache-2.0 | 262144 | 62 GB | 17 GB | 3.1 GB (48 layers, 4 KV heads) | 4-bit only, no official quant seen |
| Qwen3.5-9B | 9.65B | Apache-2.0 | 262144 | 19.3 GB | 5.3 GB | 1.1 GB | yes, BF16 |
| Qwen3.5-27B | 27.78B | Apache-2.0 | 262144 | 55.6 GB | 15.3 GB | 2.1 GB | GPTQ-Int4 yes; FP8 27.8 GB does not |
| Qwen3.5-35B-A3B | 35.95B | Apache-2.0 | 262144 | 72 GB | 19.8 GB | small (10 of 40 layers full, 2 KV heads) | GPTQ-Int4 yes |
| Qwen3.6-27B / Qwen3.8-27B | 27.78B | Apache-2.0 | 262144 | 55.6 GB | 15.3 GB | 2.1 GB | same as Qwen3.5-27B |
| Gemma 4 12B | see card | Apache-2.0 | 262144 | UNVERIFIED | QAT w4a16 exists | UNVERIFIED | probably; UNVERIFIED |
| Gemma 4 31B | 31.27B | Apache-2.0 | 262144 | 62.5 GB | 17.2 GB | 10 full layers plus sliding window 1024, KV heads UNVERIFIED | 4-bit QAT should fit; UNVERIFIED |
| Gemma 3 12B / 27B | 12.19B / 27.43B | Gemma license, gated | see card | 24 / 55 GB | 6.7 / 15 GB | not computed | older; skip |
| Mistral Small 3.2 24B | 24.01B | Apache-2.0 | 131072 | 48 GB | 13.2 GB | 5.4 GB | 4-bit yes (about 19 GB); official quant not seen |
| InternVL3-8B / 38B | 7.94B / 38.39B | Apache-2.0 | see card | 16 / 77 GB | 4.4 / 21 GB | not computed | 8B yes; 38B AWQ tight |
| InternVL3.5-8B / 14B / 38B / 30B-A3B | 8.53B / 15.12B / 38.39B / 30.85B | Apache-2.0 | max positions 40960 | 17 / 30 / 77 / 62 GB | 4.7 / 8.3 / 21 / 17 GB | not computed | context too short for 32k text |
| GLM-4.1V-9B-Thinking | 10.29B | MIT | 65536 | 20.6 GB | 5.7 GB | 2 KV heads, small | yes, but 64k limit |
| Glyph | 10.29B | MIT | 131072 | 20.6 GB | 5.7 GB | small | yes |

Existence and quantization notes (HF listings):
- Qwen2.5-VL: official AWQ for 7B, 32B, 72B.
- Qwen3-VL: 2B, 4B, 8B, 32B, 30B-A3B, 235B-A22B, Instruct and Thinking, official FP8 versions. No AWQ or GPTQ seen from Qwen.
- Qwen3.5 (Feb 2026): natively multimodal, sizes 0.8B, 2B, 4B, 9B, 27B, 35B-A3B, 122B-A10B, 397B-A17B. Official FP8 and GPTQ-Int4 for 27B, 35B-A3B, 122B, 397B. Hybrid design: 9B has 8 full-attention layers out of 32, 27B has 16 of 64, so KV cache is small.
- Qwen3.6 (Apr 2026): 27B and 35B-A3B with FP8. Qwen3.8-27B exists (created 2026-08-05, Apache-2.0, FP8 version Aug 13, same architecture class Qwen3_5ForConditionalGeneration, 262144 ctx, 16 full-attention layers of 64). Official Qwen3.8 GPTQ: not seen, UNVERIFIED.
- Gemma 4: E2B, E4B, 12B (2026-05-23), 26B-A4B, 31B; QAT variants including w4a16 for 31B and 12B.
- Glyph (https://github.com/thu-coai/Glyph, paper https://arxiv.org/abs/2510.17800): GLM-4.1V-9B-based model trained for reading long text rendered as images. Useful as a positive control for the image condition.
- Muse-Glimmer-30B (meta-models, 2026-08-09): 29.78B, Apache-2.0, 131072 ctx, 52 layers (13 full, 39 sliding), 2 KV heads. FP8-block by RedHatAI and NVFP4 (19.8 GB) by nvidia exist. Vision quality and scores: UNVERIFIED, so left out of the lineups.
- Mistral Small 4 is 119B, too large. No InternVL4 found.

vLLM architecture support: Qwen2.5-VL, Qwen3-VL, InternVL, GLM-4.1V, Mistral 3.x: expected, since vLLM has model files for them (I only opened qwen3_vl.py). Qwen3.5 from v0.17.0, Gemma 4 from v0.19.0 (release notes). Glyph loads as GLM-4.1V architecture, UNVERIFIED in vLLM.

### Published scores I could read (vendor-reported, not comparable across cards)

- Qwen2.5-VL-7B: DocVQA test 95.7, OCRBench 864 (https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct, last column of the table, which I read as the 7B column).
- Qwen2.5-VL-32B: DocVQA 96.4, OCRBench-V2 61.5/63.7 in the first column of its table (https://huggingface.co/Qwen/Qwen2.5-VL-32B-Instruct).
- Qwen3.6-27B: OCRBench 89.4, LiveCodeBench v6 83.9, SWE-bench Verified 77.2 (https://huggingface.co/Qwen/Qwen3.6-27B). Same table: Gemma4-31B OCRBench 86.1, LiveCodeBench v6 80.0.
- Qwen3.8-27B: LiveCodeBench v6 90.3 (https://huggingface.co/Qwen/Qwen3.8-27B). OCRBench not extracted.
- Qwen3.5-9B: LiveCodeBench v6 and OCRBench rows exist but I could not map the columns, so no number given. Qwen3-VL, Mistral 3.2, InternVL3.5, GLM-4.1V, Gemma 3: scores UNVERIFIED (not extracted).
- Caveat: LiveCodeBench numbers above are for thinking modes with large budgets, so they say little about a single-pass text-vs-image comparison. We need our own text baseline per model anyway.

## 3. Recommended lineups

Design constraints: one 32 GB card, 32k-token contexts, sampled runs (so throughput matters), and a clean size ladder. Main confound to state in the write-up: the large rung must be 4-bit while the small rung can be BF16. To separate size from quantization, also run the small model in 4-bit for a subset (needs a GPTQ/AWQ small checkpoint; Qwen2.5-VL-7B AWQ exists officially).

### Lineup A: recommended (5 models, two ladders plus a control)
1. Qwen3.5-9B, BF16.
2. Qwen3.5-27B, official GPTQ-Int4.
3. Qwen2.5-VL-7B, BF16.
4. Qwen2.5-VL-32B, official AWQ. About 30 GB at 32k with bf16 KV, so cap context or use fp8 KV cache (support on sm_120: UNVERIFIED), or fall back to 24k.
5. Glyph, BF16, as positive control for image-as-context.
Why: two size ladders from one family each (9B to 27B, 7B to 32B) with official quantized big rungs, plus one older and one newer generation of vision stack. Qwen3.5 has a tiny KV cache, so 32k is comfortable and throughput is good. Cost: one family dominates, so add a second family if time allows (lineup B).

### Lineup B: two families (4 models)
1. Qwen3.5-9B BF16.
2. Qwen3.5-27B GPTQ-Int4.
3. Gemma 4 12B (QAT w4a16 or BF16 if it fits, UNVERIFIED).
4. Gemma 4 31B QAT w4a16.
Why: same ladder logic in two independent families, both Apache-2.0, both 262144 context. Risk: Gemma 4 needs recent vLLM and transformers 5.5.0 or later, which may conflict with Qwen pins, so use separate venvs.

### Lineup C: minimal (3 models, safest to run)
1. Qwen3-VL-8B BF16.
2. Qwen3.5-27B GPTQ-Int4 (or Qwen3.8-27B if an official 4-bit appears).
3. Mistral Small 3.2 24B in 4-bit (community AWQ needed, UNVERIFIED) as the other-family point.
Why: fewest moving parts, but the ladder is across generations, which weakens the size claim. Use only if time runs out.

Avoid: Qwen2.5-VL-72B and the 38B-class models (do not fit well), InternVL3.5 (40960 positions, cannot take 32k text), Qwen3-VL-32B (no official 4-bit, BF16 and FP8 do not fit), and FP8 checkpoints in general until the DeepGEMM issue is retested on v0.30.0.

## 4. First things to run
1. Fresh venv, install vLLM (0.20.0 as floor, 0.30.0 target), serve Qwen3.5-9B, confirm the server starts on sm_120.
2. Measure prompt_tokens for one image and one text prompt (section 1.3).
3. Confirm min_pixels = max_pixels through mm_processor_kwargs changes the token count as predicted.
4. Load the 27B GPTQ and the 32B AWQ at the real context length and record peak VRAM.
