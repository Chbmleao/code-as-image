# Last-block sensitivity (DevEval)

A post hoc sensitivity analysis, added on 2026-11-26 after the main gaps were seen (docs/decisions.md 2026-11-26, UFM-35); it changes nothing in methodology 3.3. The main analysis grades the first fenced block in which the target function is found. Here a reply with 2 or more such blocks is graded on the last one, with the same re-indent. Fences only match closed blocks, so in a truncated reply the last block is the last closed one.

1693 replies on the kept items are in scope (647 truncated). In 297 the last block gives the same answer and the main-run verdict stands. An empty last body is scored as a fail (1). The other 1395 were graded on the cluster in one job, last block and first block both, so a flip compares two grades of the same job. Drift is the job's first-block verdict against the main run's, a measure of grading noise between the two runs.

## Gaps (image minus text, percentage points)

The main gap of each model, item-weighted with every run, and the same gap with the last-block verdicts; 95% project-clustered t intervals, no Holm adjustment.

| Model | First block (main) | Last block | Change |
|---|---|---|---|
| Qwen3.5 27B | -28.2 [-32.3, -24.1] | -28.2 [-32.3, -24.1] | -0.03 |
| Gemma 4 12B | -30.6 [-35.5, -25.7] | -30.7 [-35.6, -25.8] | -0.03 |
| Mistral Small 3.2 24B | -31.5 [-36.1, -26.9] | -31.5 [-36.1, -26.9] | +0.00 |
| Qwen3.5 9B | -23.8 [-28.0, -19.5] | -22.9 [-27.1, -18.7] | +0.87 |
| Qwen2.5-VL 7B | -16.5 [-20.2, -12.8] | -16.5 [-20.2, -12.8] | +0.00 |
| Claude Sonnet 5.5 | -6.1 [-8.1, -4.2] | -6.1 [-8.1, -4.2] | +0.02 |
| Claude Opus 5.5 | -1.8 [-3.2, -0.3] | -1.8 [-3.3, -0.4] | -0.06 |

## Replies

Graded replies, flips within the job and drift from the main run, by condition type.

| Model | Condition | In scope | Graded | Fail to pass | Pass to fail | Drift |
|---|---|---|---|---|---|---|
| Qwen3.5 27B | text | 15 | 11 | 1 | 1 | 0 |
| Qwen3.5 27B | image | 14 | 8 | 0 | 1 | 0 |
| Gemma 4 12B | text | 23 | 23 | 4 | 1 | 0 |
| Gemma 4 12B | image | 106 | 94 | 6 | 1 | 0 |
| Mistral Small 3.2 24B | text | 0 | 0 | 0 | 0 | 0 |
| Mistral Small 3.2 24B | image | 0 | 0 | 0 | 0 | 0 |
| Qwen3.5 9B | text | 6 | 6 | 2 | 0 | 0 |
| Qwen3.5 9B | image | 1362 | 1103 | 66 | 12 | 1 |
| Qwen2.5-VL 7B | text | 9 | 1 | 0 | 0 | 0 |
| Qwen2.5-VL 7B | image | 1 | 1 | 0 | 0 | 0 |
| Claude Sonnet 5.5 | text | 31 | 26 | 7 | 1 | 0 |
| Claude Sonnet 5.5 | image | 120 | 116 | 26 | 7 | 0 |
| Claude Opus 5.5 | text | 1 | 1 | 1 | 0 | 0 |
| Claude Opus 5.5 | image | 5 | 5 | 0 | 0 | 0 |
