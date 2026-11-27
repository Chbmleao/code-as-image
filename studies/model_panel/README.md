# Model panel

UFM-8: picks the VLMs for the study (fit on an RTX 5090, floor screen on text, image token cost,
license, speed) and records the limits of a 5-model panel.

Oct 26, 2026. Checks run on the DCC cluster (medusa3 and medusa4, one RTX 5090 32 GB per job,
vLLM 0.32.0, torch 2.13, transformers 5.19). Thinking turned off for every model.

## Panel

Five models, all fit on one 5090 and all run under vLLM without custom kernels.

| Model | Hugging Face repo | Precision | Weights | License |
|---|---|---|---|---|
| Qwen2.5-VL 7B | Qwen/Qwen2.5-VL-7B-Instruct | 16-bit | about 16 GB | Apache 2.0 |
| Qwen3.5 9B | Qwen/Qwen3.5-9B | 16-bit | about 19 GB | Apache 2.0 |
| Gemma 4 12B | google/gemma-4-12B-it | 16-bit | about 24 GB | Apache 2.0 |
| Qwen3.5 27B | cyankiwi/Qwen3.5-27B-AWQ-4bit | 4-bit AWQ | about 19 GB | Apache 2.0 |
| Mistral Small 3.2 24B | jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym | 4-bit W4A16 | 15 GB | Apache 2.0 (base model; the quant repo states none) |

Size and precision are confounded: the two largest models are the only 4-bit ones. This was
already planned and will be reported as such.

Weight sizes other than Mistral's are from memory of the download logs, not re-measured. Worth
checking with `du -sh` on the HF cache before quoting them.

## Floor screen (text only)

The pilot's 20 HumanEval problems in the text condition, same padded context, instruction and
grader as the pilot, 3 runs per problem (seeds 0 to 2), up to 1024 output tokens, model's default
sampling settings.

| Model | Passed | Rate |
|---|---|---|
| Qwen2.5-VL 7B | 38/60 | 63% |
| Mistral Small 3.2 24B | 51/60 | 85% |
| Qwen3.5 9B | 50/60 | 83% |
| Qwen3.5 27B | 55/60 | 92% |
| Gemma 4 12B | 58/60 | 97% |

No model is floored. Qwen2.5-VL's 63% matches its pilot text score (60/100), so the harness
reproduces the pilot. Gemma (97%) and the 27B (92%) are near the ceiling on these 20 problems.
That is not a problem for the panel choice: the main study will use harder benchmarks with longer
contexts, which pulls scores down from the ceiling and gives a better measure of token usage. This
screen only answers whether each model can do the task at all.

Longer contexts mean more pages per prompt, so two things need checking before the main runs.
The servers here ran with `--max-model-len 16384`, and the 27B already needed its startup limits
lowered to fit, so its KV cache at longer lengths is the tightest on the panel. Gemma's fixed
budget of about 256 tokens per image also makes it much cheaper per page as contexts grow, which
widens the token gap between models.

## Image token cost

Measured as the difference in `prompt_tokens` between the same request with and without one image.

| Model | 616x1540 page | 616x770 page | How it counts |
|---|---|---|---|
| Mistral Small 3.2 24B | 1265 | 644 | 28 px cells plus one break token per row (1210 + 55) |
| Qwen2.5-VL 7B | 1212 | 618 | 28 px cells plus 2 |
| Qwen3.5 9B | 914 | 458 | close to 32 px cells |
| Qwen3.5 27B | 914 | 458 | same vision encoder as the 9B |
| Gemma 4 12B | 262 | 254 | fixed budget of about 256 per image |

Qwen and Mistral scale with page area, so a page costs about the same per pixel whatever its
shape. Gemma does not: it spends about 256 tokens on any image and downscales to fit. A
616x1540 page costs Gemma about a fifth of what it costs Mistral, but the 10 px text is shrunk
more on a tall page than on a short one.

This corrects the Oct 22 note, which said Gemma uses one token per 48 px. That number came from
the model card's patch size, not from a measurement.

## Speed

Mean seconds per text generation over the 60 runs above.

| Model | Seconds |
|---|---|
| Qwen2.5-VL 7B | 2.4 |
| Mistral Small 3.2 24B | 2.7 |
| Qwen3.5 9B | 3.2 |
| Qwen3.5 27B | 4.1 |
| Gemma 4 12B | 5.0 |

One requests at a time, so these are latency numbers, not throughput under load. Each full check
job (server start, token check, 60 generations) took about 15 minutes, most of it model loading.

## Things that came up

- **Mistral NVFP4 does not run on this cluster.** RedHatAI's NVFP4 build compiles its kernel when
  the model loads, and the cluster's CUDA toolkit is older than 12.9, the minimum for the 5090
  (SM 12). Error: `No supported CUDA architectures found for major versions [12]`. Replaced with
  a W4A16 build, whose kernels ship prebuilt with vLLM. Installing a newer CUDA toolkit in the
  venv would probably also fix it, but was not tried.
- **Qwen3.5 27B needs lower startup limits.** With defaults it ran out of memory right after
  loading the weights (a 12.25 GiB allocation, most likely vLLM's profiling pass with a
  maximum-size dummy image). It runs with
  `--max-num-batched-tokens 4096 --max-num-seqs 16 --mm-processor-kwargs '{"max_pixels": 1048576}'`.
  Our pages are under that pixel cap, so token counts are not affected. These flags have to be
  used in every run of this model.
- **Qwen's own 4-bit 27B does not fit.** Qwen's GPTQ-Int4 release keeps attention in 16-bit and
  needs about 30 GB of weights, which leaves nothing for the KV cache on a 32 GB card.
- **Mistral adds a long default system prompt.** Its chat template inserts a system prompt of
  about 560 tokens. It is present in both the text and image conditions, so the comparison
  holds, but it inflates Mistral's absolute prompt sizes.
- **Qwen2.5-VL is close to deterministic.** Its three seeds gave nearly identical replies (same
  output token counts), because its `generation_config.json` sets temperature to 0.000001 (see
  the sampling table below). Left as is, the run facet in G-theory has almost no variance for
  this model, which would make it look more reliable than the others for the wrong reason.
- **Results are now written one file per model.** Two jobs on different nodes appended to the same
  JSONL file over NFS and one row was lost (Qwen3.5 9B has 59 of 60 rows; its pass count was
  counted in memory and is correct).

## Limitation: 3 to 5 models

In the Rasch model the models are the respondents, so there are only 5 ability estimates. Each
will have a wide interval, and item fit statistics rest on very few respondents. Repeated runs
add observations per cell but are not new models, so they do not fix this.

In G-theory the model facet has at most 4 degrees of freedom, so its variance component will be
unstable. The plan is to treat the model facet as fixed and to describe results as properties of
this panel, not of VLMs in general. Adding the hosted reference (Claude) gives a sixth respondent
but on a different serving stack, so it should be reported separately.

## Sampling settings used in the screen

`text_baseline.py` sends no sampling parameters, so vLLM used each repo's
`generation_config.json`, or its own defaults when the repo has none.

| Model | Temperature | top_p | top_k | Other | Source |
|---|---|---|---|---|---|
| Qwen2.5-VL 7B | 0.000001 | 1.0 | none | repetition_penalty 1.05 | repo config |
| Mistral Small 3.2 24B | 0.15 | 1.0 | none | | repo config |
| Qwen3.5 27B (AWQ) | 0.6 | 0.95 | 20 | | quant repo config |
| Gemma 4 12B | 1.0 | 0.95 | 64 | | repo config |
| Qwen3.5 9B | 1.0 | 1.0 | none | | vLLM default, repo has no generation_config.json |

This confirms that Qwen2.5-VL ran as effectively greedy, which explains its identical runs. It
also means the 9B and 27B Qwen3.5 scores (50 vs 55) are not a clean size comparison: they ran
with different settings. The 27B quant's 0.6 is Qwen's recommendation for thinking mode on coding
tasks, not for non-thinking mode (Qwen's model card gives 0.7, top_p 0.8, top_k 20, presence
penalty 1.5 for that).

## Decisions

1. Sampling: one setting for every model, temperature 0.7, top_p 0.95, seeds 0 to 2.
   `text_baseline.py` also sends top_k -1, min_p 0 and repetition_penalty 1.0, because vLLM fills
   any field the request leaves out from the repo's config (otherwise Gemma would keep top_k 64,
   the 27B top_k 20 and Qwen2.5-VL repetition_penalty 1.05). The screen scores above were run with
   each model's defaults and are kept as they are.
2. Page height: same images for every model. Gemma's downscaling is reported as a result
   (compression vs readability), not corrected. A shorter-page check for Gemma alone may be run
   later and reported separately.
3. System prompt: empty for every model, which removes Mistral's default prompt of about 560
   tokens. The methods section notes that this departs from Mistral's intended use.
4. Context length: handled in the benchmark selection issue. Before the main runs, the 27B needs
   one test job at the chosen benchmark's longest context, since it is the tightest on memory.

## Files

- `queue_one.sh`: run on the login node. Downloads one model and submits its check job.
- `run_checks.sbatch`: starts vLLM on a GPU node, then runs the two checks below.
- `token_check.py`: image tokens per page, by diffing `prompt_tokens` with and without an image.
- `text_baseline.py`: the text-only floor screen.
- `results/token_check.jsonl`: two rows per model, one per page size.
- `results/text_baseline_<model>.jsonl`: one row per problem and run, with the reply.

`text_baseline.py` now sends the shared sampling setting from decision 1. The results in
`results/` were run before that change, with each model's defaults. The first three models wrote
to one shared file, which was split per model here. Its one corrupt line was a Qwen3.5 9B row
that passed, so that file has 59 rows and 49 passes, while the job's own count was 50/60.

## Reproducing

See `../../CLUSTER.md` for how to use the cluster. The cluster runs from a flat directory, `/sonic_home/carlosleao/ufm8`, holding the four files
above plus `run_pilot.py`, `HumanEval.jsonl.gz` and `fonts/` from `studies/pilot/`, which
`text_baseline.py` imports. The venv and HF cache live in `/snfs2/carlosleao/ufm8`. On the login
node:

```
bash queue_one.sh Qwen/Qwen2.5-VL-7B-Instruct
bash queue_one.sh Qwen/Qwen3.5-9B
bash queue_one.sh google/gemma-4-12B-it
bash queue_one.sh cyankiwi/Qwen3.5-27B-AWQ-4bit --max-num-batched-tokens 4096 --max-num-seqs 16 --mm-processor-kwargs '{"max_pixels": 1048576}'
bash queue_one.sh jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym
```

Each job writes `token_check.jsonl`, `text_baseline_<model>.jsonl` and `logs/checks_<job>.out`.
