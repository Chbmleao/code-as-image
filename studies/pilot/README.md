# Pilot

Laptop pilot for UFM-19: Qwen2.5-VL 7B via Ollama on 20 HumanEval problems, with the code given
either as text or as images. It replaces the pilot numbers in the proposal and the deck, which come
from a run whose script was lost.

## Running it

Needs Ollama (0.34.3 was used) with `qwen2.5vl:7b` pulled, and Pillow.

```
python3 run_pilot.py
```

Results are appended to `results.jsonl`, one line per (problem, condition, run). The script skips
cells already in that file, so it can be stopped and restarted. Rendered pages go to `img/`.

## Setup

- 20 HumanEval problems whose prompt defines a single function, sampled with seed 0.
- Each problem is padded to about 12k characters with other HumanEval problems (prompt plus
  canonical solution) placed before it, so the target function is the last one.
- The instruction names the target function: "Complete the function `name`. It is the last
  function in the code ...".
- Sampling settings from the model's `generation_config.json`: temperature 1e-6, repeat penalty
  1.05, `num_predict` 1024, `num_ctx` 16384. 5 runs per cell, seeds 0 to 4.
- Font: JetBrains Mono (`fonts/`, OFL license).

Conditions:

| Condition | Layout |
|---|---|
| `text` | code in the prompt |
| `mono8`, `mono10`, `mono12` | one source line per row (wrapped at 100 columns), pages up to 2800 px tall |
| `packed8` to `packed14` | lines flow across 616 px wide rows, with `⏎` marking each line break |

## Results

800 calls: 20 problems x 8 conditions x 5 runs. Token columns are means per call.

| Condition | Passed (of 100) | Pages | Prompt | Cached | Uncached | Instruction | Code | Code vs text | Output | Total |
|---|---|---|---|---|---|---|---|---|---|---|
| text | 60 | 0 | 3,503 | 2,838 | 665 | 65 | 3,438 | 100% | 234 | 3,737 |
| mono8 | 55 | 2.0 | 2,750 | 2,202 | 548 | 68 | 2,682 | 78% | 192 | 2,941 |
| mono10 | 60 | 2.05 | 3,995 | 3,237 | 757 | 68 | 3,927 | 114% | 208 | 4,203 |
| mono12 | 55 | 3.0 | 5,654 | 4,525 | 1,129 | 68 | 5,586 | 162% | 150 | 5,804 |
| packed8 | 20 | 1.0 | 1,141 | 915 | 226 | 77 | 1,064 | 31% | 145 | 1,286 |
| packed10 | 30 | 1.0 | 1,184 | 950 | 235 | 77 | 1,108 | 32% | 145 | 1,330 |
| packed12 | 50 | 1.0 | 1,681 | 1,346 | 334 | 77 | 1,604 | 47% | 136 | 1,817 |
| packed14 | 60 | 1.6 | 2,289 | 1,833 | 456 | 77 | 2,212 | 64% | 146 | 2,435 |

Sum of total tokens over all 800 calls: 2,355,287.

What the columns mean (all from Ollama's `/api/chat` response):

- **Prompt**: `prompt_eval_count`, every input token including image tokens.
- **Cached**: `prompt_eval_cached_count`, input tokens served from the KV cache of the previous
  call. Cached + uncached = prompt.
- **Instruction**: the instruction sent alone, once per (problem, condition). It is a few tokens
  longer for packed conditions because it explains the `⏎` marker.
- **Code**: prompt minus instruction, so what the code costs as text or as images.
- **Output**: `eval_count`, generated tokens.
- **Total**: prompt + output.

There are no reasoning tokens: Qwen2.5-VL 7B is not a reasoning model, and Ollama reports only
the three counts above.

The cache split depends on run order, not on the condition. Run 0 of each cell is almost fully
uncached (14 cached tokens in most cells). Runs 1 to 4 repeat the same prompt, so all but one input
token is cached. The 20% uncached mean is that 1-in-5 pattern.

## Findings

- **Naming the function fixed the wrong-function failures** of the earlier rebuild. All 800 replies
  define the target function.
- **Line-per-row images match text accuracy but do not save tokens.** Only mono8 is cheaper than
  text. Most of each row is blank, and Qwen bills every 28x28 patch, blank or not.
- **Packing cuts image tokens by about 3x, and accuracy drops at small sizes.** packed14 matches
  text (60 of 100) with 64% of the code tokens. packed12 passes 50 with 47%.
- **packed10 costs about 1,108 tokens**, close to the ~1,190 reported for 10 px in the proposal.
  The original pilot almost certainly used continuous packing, which explains its low image cost.
- **The 5 runs added almost no information.** In 158 of 160 cells every run gave the same
  pass/fail and output length. At the recommended temperature this is close to greedy decoding,
  so UFM-17 cannot estimate run-to-run variance from repeats at this setting.

Caveats:

- 20 problems, so 5 passed runs is one problem. Differences of 5 to 10 are not meaningful.
- 10 rows (5 mono8, 5 mono10) hit the 1,024-token output limit and were cut off.
- Timing fields (`prefill_s`, `generate_s`, `seconds`) are not usable: the laptop slept during part
  of the run and shared the CPU with other work.

## Relation to the proposal numbers

The proposal and deck cite a run from around Sep 28 (text 13/20, mono12 12/20, 10 px ~1,190
tokens). Its script is gone, and an Oct 5 rebuild (`scratch/pilot/`) did not reproduce it, mainly
because the model completed the wrong function. This pilot replaces both. Its numbers come from
`results.jsonl` in this folder.
