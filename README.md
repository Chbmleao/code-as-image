# Code as Image

Final project for the UFMG course "Medição e Caracterização de IA" (AI Measurement Science).

Coding agents carry a lot of repository context, and tools such as pxpipe render that context as
images because an image token holds more characters than a text token. This project measures what
that saving costs: how much pass rate open vision-language models lose when the repository context
of a coding task arrives as an image instead of text, and how many input tokens the image saves.

## Design in one paragraph

995 items from two repository-level benchmarks, CoderUJB (136 Java methods from Defects4J) and
DevEval (859 Python functions from 79 repositories), each with a reference solution that passes
its tests and a prompt of 2k to 12k tokens. Five open models served with vLLM: Qwen2.5-VL 7B,
Qwen3.5 9B and 27B, Gemma 4 12B and Mistral Small 3.2 24B. Four conditions: text, and the context
rendered as packed images at 10, 12 and 14 px, with the task itself always in text. Three runs per
item, model and condition at temperature 0.7, scored pass/fail by the unit tests. The main result
is the paired text-minus-image gap per model with a project-clustered interval. Full plan in
[`docs/methodology.md`](docs/methodology.md).

## Layout

| Path | What it holds |
|---|---|
| `docs/methodology.md` | The written plan: design, construct, analysis, open items |
| `docs/decisions.md` | Dated log of design decisions and what was dropped |
| `docs/notes/` | Reading notes on the course book and the literature behind the plan |
| `presentations/` | Proposal and methodology slides (in Portuguese, as presented) |
| `pilot/` | First pilot: Qwen2.5-VL 7B on 20 HumanEval problems, text vs image |
| `model_panel/` | Model choice: fit on one RTX 5090, text floor screen, image token cost |
| `benchmarks/` | Benchmark choice, item filters, gold checks, token counts, contamination check |
| `CLUSTER.md` | How to run jobs on the DCC cluster (Slurm) |

## Status

- Done: proposal, model panel, benchmark selection, pilot, methodology presentation.
- Next: the experiment pipeline (render, generate, grade) and a first block of 240 items that
  decides between 2 and 3 runs for the rest. Then the main run, the analysis and the paper.

## Running

Nothing runs locally except the first pilot. Generation, gold checks and grading go through Slurm
on the DCC cluster; see [`CLUSTER.md`](CLUSTER.md) and the README in each folder.
