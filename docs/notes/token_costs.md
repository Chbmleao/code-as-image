# Token costs of rendered repository context

Pages per item and image-to-text token ratios at 10, 12 and 14 px for the 5-model panel, computed on the 136 CoderUJB and 859 DevEval items.

## Inputs and how the numbers were computed

- Source: `benchmarks/*/results/prompt_counts.jsonl`, written by `benchmarks/shared/count_tokens.py`, filtered to the final item ids (`final_ids.txt`, `inrange_ids.txt`). The file holds text token counts per model and page counts at 10, 12 and 14 px only.
- Layout: the pilot packed layout, 616x1540 pages. Page capacities in `count_tokens.py` are 12700, 8686 and 6300 characters per page at 10, 12 and 14 px.
- Image tokens per item and model = pages x the cost of one full 616x1540 page in `studies/model_panel/README.md`: Mistral 1265, Qwen2.5-VL 1212, Qwen3.5 (9B and 27B) 914, Gemma 4 12B 262.
- This overstates Qwen and Mistral cost when the last page is cropped (their cost scales with area). Gemma also shrinks a tall page to fit its budget of about 256 tokens, so its effective letter size is smaller than the nominal px (not measured).
- Page counts will be rechecked on the final renderer (packed, context only) before the image limit per prompt is set.

## Pages per item

| px | CoderUJB min/med/p95/max | items > 4 pages | DevEval min/med/p95/max | items > 4 pages |
|---|---|---|---|---|
| 10 | 1/2/4/4 | 0 | 1/2/4/4 | 0 |
| 12 | 1/3/5/6 | 23 (17%) | 1/2/5/6 | 91 (11%) |
| 14 | 2/4/7/8 | 43 (32%) | 1/3/7/8 | 224 (26%) |

## Median image-to-text token ratio

Median over items of the item's image tokens divided by its text tokens (1 minus this is the saving). Values are the range across the two benchmarks.

| px | Qwen2.5-VL 7B | Qwen3.5 9B/27B | Mistral 24B | Gemma 4 12B |
|---|---|---|---|---|
| 10 | 0.54-0.55 | 0.37-0.38 | 0.54 | 0.10 |
| 12 | 0.74-0.77 | 0.52-0.53 | 0.74-0.76 | 0.14 |
| 14 | 0.99-1.00 | 0.69-0.70 | 0.99 | 0.18-0.19 |

At 12 px the ratios are about 0.75 (Qwen2.5-VL), 0.75 (Mistral), 0.52 (Qwen3.5) and 0.14 (Gemma). At 14 px Qwen2.5-VL and Mistral save almost nothing.

## Median image tokens per item

Ranges are the two benchmarks (CoderUJB / DevEval where they differ).

| px | Qwen2.5-VL 7B | Qwen3.5 9B/27B | Mistral 24B | Gemma 4 12B |
|---|---|---|---|---|
| 10 | 2424 | 1828 | 2530 | 524 |
| 12 | 2424-3636 | 1828-2742 | 2530-3795 | 524-786 |
| 14 | 3636-4848 | 2742-3656 | 3795-5060 | 786-1048 |

Median text tokens per item are 3.9k to 4.8k depending on model and benchmark.

## Context length

- Prompts must fit 16384 - 2048 = 14336 tokens (context window minus maximum output). In this check no item exceeded that at 10 to 14 px: the worst case of 8 pages is 10120 tokens on Mistral. The check added 300 tokens for instruction and template (860 for Mistral, whose template adds a 560-token system prompt); the 300 is a guess and the task text was not counted separately.
- Context length is therefore not the binding constraint; the image limit per prompt is. The sbatch files set `--limit-mm-per-prompt '{"image": 4}'`, below the 6 pages needed at 12 px and 8 at 14 px, so it has to be raised before those conditions run.
