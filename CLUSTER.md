# Running on the DCC cluster

No model runs on the Mac. Generation, gold checks and grading all go through Slurm on the DCC
cluster. Edit the code in this repo, copy it over, then submit from the login node.

## Machines

| Node | What it is for |
|---|---|
| `phocus4` | Login node. Has internet, no GPU. Download models and datasets here, submit jobs here. Never start vLLM here. |
| `medusa3` to `medusa6` | GPU nodes, one RTX 5090 (32 GB) each. Partitions `medusas_dev,medusas_shr`. No internet. |
| `gorgonas` | CPU partition, used for gold checks and grading. |

From the Mac, `ssh phocus4` works (add `-o BatchMode=yes` in scripts).

## Directories

The cluster directories are not git checkouts.

| Path | Holds |
|---|---|
| `/sonic_home/carlosleao/ufm8` | Model panel code (flat copy of `model_panel/` plus `run_pilot.py`, `HumanEval.jsonl.gz`, `fonts/` from `pilot/`) and its `logs/` |
| `/sonic_home/carlosleao/ufm7` | Benchmark code, same layout as `benchmarks/` |
| `/snfs2/carlosleao/ufm8` | `venv/` (vLLM 0.32.0, torch 2.13, transformers 5.19), `hf/` (HF_HOME), `home/` and `cache/` for the GPU jobs |
| `/snfs2/carlosleao/ufm7` | Benchmark data and outputs (`coderujb`, `deveval`, `deveval_calib`, `d4j`) and `logs/` |
| `/sonic_home/carlosleao/ufm9/<date>-<sha>` | One read-only copy of the pipeline code per sync (`scripts/sync_cluster.sh`); jobs name the copy they run |
| `/snfs2/carlosleao/ufm9` | `inputs/` (benchmark prompt files with sha256), `smoke/` and `block1/` run dirs, `logs/` |

Big files (models, datasets, outputs) go on `/snfs2`, code on `/sonic_home`.

## Workflow

1. Copy the edited files over, for example:
   ```
   scp model_panel/text_baseline.py phocus4:/sonic_home/carlosleao/ufm8/
   scp benchmarks/shared/generate.py phocus4:/sonic_home/carlosleao/ufm7/shared/
   ```
2. On `phocus4`, download what the job needs. The GPU nodes run with `HF_HUB_OFFLINE=1`, so a
   model or dataset that is not already on disk makes the job fail. `queue_one.sh` downloads the
   model and then submits the job for you:
   ```
   bash queue_one.sh <hf-repo> [extra vllm serve args]
   ```
   Benchmark jobs are submitted directly, from `/sonic_home/carlosleao/ufm7`:
   ```
   sbatch deveval/generate.sbatch <hf-repo> [extra vllm serve args]
   ```
3. Watch the job with `squeue -u carlosleao`. When it ends, read the job log and the vLLM log
   (`logs/vllm_<job>.log` for the model panel).
4. Copy the results back with `scp phocus4:<path> <local path>`.

A GPU job starts `vllm serve` on port `8000 + (job id mod 1000)`, so two jobs on one node do not
collide. It waits for `/health`, runs the Python client against
`http://localhost:<port>/v1/chat/completions`, then stops the server. Loading the model takes
most of a short job's time, so expect about 15 minutes even for 60 short generations.

### Main study (ufm9)

1. `scripts/sync_cluster.sh` copies the pipeline code to a new dated dir and prints its path.
2. On `phocus4`, with the ufm8 venv active and `PYTHONPATH=<code>/src`, build the requests:
   `python -m codeimg prompts --benchmark <b> --source /snfs2/carlosleao/ufm9/inputs/<file>
   --ids <code>/manifests/<sample>/<b>.txt --out /snfs2/carlosleao/ufm9/<sample>/<b>`.
3. `<code>/slurm/submit_generate.sh <code> /snfs2/carlosleao/ufm9/<sample> [generate args]`
   prints one job per model and asks before submitting.
4. `python -m codeimg answers`, then `sbatch <code>/slurm/grade_<b>.sbatch <code> ANSWERS OUT`,
   then `python -m codeimg collect`.

### Transcription test (UFM-12)

1. `scripts/sync_cluster.sh`, as above.
2. Build the requests from the main run's, for each benchmark (add `--ids <manifest>` for a subset,
   such as `manifests/transcribe_check/<b>.txt` for the startup check):
   `python -m codeimg transcribe --source /snfs2/carlosleao/ufm9/block1/<b>/requests.jsonl
   --source /snfs2/carlosleao/ufm9/rest/<b>/requests.jsonl --out /snfs2/carlosleao/ufm9/transcribe`.
   It checks the pixels of every page against the main run's render.
3. `SBATCH_TIME=<limit> <code>/slurm/submit_generate.sh <code> /snfs2/carlosleao/ufm9/transcribe
   --transcription --runs 2`. With `--transcription` the job starts vLLM with
   `[transcription].max_model_len` (32768); medusas_dev allows 8 h and medusas_shr 2 days.
4. `python <code>/scripts/transcription_score.py --benchmark <b> --source <block1 requests>
   --source <rest requests> --requests /snfs2/carlosleao/ufm9/transcribe/<b>/requests.jsonl
   --gen /snfs2/carlosleao/ufm9/transcribe/<b>/gen/*.jsonl --runs 2
   --out /snfs2/carlosleao/ufm9/transcribe/<b>/scores.jsonl`, then copy `scores.jsonl` to
   `results/transcription/<b>.jsonl`.

## Things that have already broken

- Slurm copies the `.sbatch` file when you submit, but reads the `.py` files when the job
  starts. Editing a `.py` file changes jobs that are already queued.
- Never have two jobs append to the same file. Over NFS, two nodes appending to one JSONL lost a
  row. Write one output file per model.
- The Qwen3.5 27B AWQ runs out of memory at startup unless it gets
  `--max-num-batched-tokens 4096 --max-num-seqs 16 --mm-processor-kwargs '{"max_pixels": 1048576}'`.
- The cluster's CUDA toolkit is older than 12.9, so quantizations that compile kernels at load
  time (NVFP4) fail on the 5090.
- `$HOME` is not writable on the GPU nodes. The sbatch files point `HOME` and `XDG_CACHE_HOME`
  at `/snfs2/carlosleao/ufm8`.
- The venv was built on `phocus4` against `/opt/python/3-12-1/bin/python3`. It only works on a
  node where that path exists, and `run_checks.sbatch` checks for it first.
- Grading has no Docker and no network on the compute nodes. Defects4J and the DevEval venv were
  installed on `phocus4` without root (`benchmarks/coderujb/setup_d4j.sh`,
  `benchmarks/deveval/setup_env.sh`).
- `squeue` and `sbatch` fail over a plain `ssh phocus4 '...'` (the Slurm config is found through
  the login profile). Use `ssh phocus4 'bash -lc "..."'`.
- The cluster's Pillow has libraqm, which gives fractional glyph advances and so more pages than a
  laptop without it. The renderer pins Pillow's basic layout engine. PNG bytes still differ (zlib
  1.2.11 there, zlib-ng on the Mac) with identical pixels, so compare renders by `pixels_sha256`.
- /snfs2 can stop taking writes for everyone. On Nov 12 jobs crashed with `No space left on
  device` at 96% used, then creating any file gave `Remote I/O error` for about 4 hours while
  reads still worked. Test with a one-line write before resubmitting; `/sonic_home` (160G quota)
  and the node's `/tmp` kept working, so grades and logs can go there.
- Until Nov 14 the grading sbatch files ended with `echo end`, so Slurm reported COMPLETED even
  when the grader crashed. They now exit with the grader's status, but still check the row count
  and the log for a Traceback before trusting a job.
- The 3 gorgonas nodes can be held for days by other users' jobs with no time limit, and
  medusas_shr can have free CPUs but no free memory. A chain of 1:30 jobs on gorgonas_dev
  (`--dependency=afterany` on the one before) keeps a resumable grader going. `afterany` treats a
  cancelled job as done, so to shorten a chain cancel from the last job back.
- DevEval tests ran 3 to 5 times slower than in block 1 while the shared disks were busy (pytest
  waiting on NFS reads, CPU nearly idle). The last job, on Nov 13, ran about 4 times faster than
  the chain before it.
- `sbatch` can print `Batch job submission failed: Unexpected message received` and still create
  the job. Run `squeue` before submitting again.
- A job that ends in NODE_FAIL can sit in CG for a long time, and a `--dependency=singleton` job
  with the same name waits for it. If the failed job never ran, submit under another name.
