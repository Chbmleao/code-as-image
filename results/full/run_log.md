# Run log: the rest of the main run (UFM-11)

Times are local (UTC-3). Run dir `/snfs2/carlosleao/ufm9/rest`.

## Code

| Code dir | Head | files_sha256 |
|---|---|---|
| `/sonic_home/carlosleao/ufm9/20261110-1339-f64d32a-dirty` | 8e6aee516de8bf7ceff0e6aa95eac1388e5e8751 plus uncommitted changes | 1bca9a46d0224ea610aa3e2e18b44e349d5cb930c6234ad6e9629ca5b124371b |

`files_sha256` is the sha256 of `CODE_FILES.sha256`, the sorted sha256 listing of every synced
file (`scripts/sync_cluster.sh`). `sha256sum -c CODE_FILES.sha256` passed on the cluster copy, and
the hash of the listing matched `CODE_VERSION`.

On Nov 14 the history was rewritten to change the author email, which changed every commit
hash but no file. The head was f64d32a8720fd786e4371592830ac4c0e8385729 when the code was
synced, and that is the hash in the dir name and in the cluster's `CODE_VERSION`.

## Software

Read on the cluster on Nov 14; nothing was reinstalled during the run.

- Generation: `/snfs2/carlosleao/ufm8/venv`, Python 3.12.1, vLLM 0.32.0, torch 2.13.0,
  transformers 5.19.0, openai 3.36.1, Pillow 13.0.0.
- CoderUJB grading: Defects4J at commit a83e479 (Aug 25 2023), `/snfs2/carlosleao/ufm7/d4j`.
- DevEval grading: `/snfs2/carlosleao/ufm7/deveval/venv`, Python 3.9.18.

Model snapshots (each the only one in `/snfs2/carlosleao/ufm8/hf`; the GPU jobs run with
`HF_HUB_OFFLINE=1`):

| Model | Snapshot |
|---|---|
| `Qwen/Qwen2.5-VL-7B-Instruct` | cc594898137f460bfe9f0759e9844b3ce807cfb5 |
| `Qwen/Qwen3.5-9B` | c202236235762e1c871ad0ccb60c8ee5ba337b9a |
| `google/gemma-4-12B-it` | 707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7 |
| `cyankiwi/Qwen3.5-27B-AWQ-4bit` | 9d8d63632afafe90bdfcb70164d3e2a0955619f7 |
| `jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym` | 49ec31ec0975e46a1aeef24186a45f11be3042b8 |

## Inputs

Prompt sources in `/snfs2/carlosleao/ufm9/inputs`, both matching their `.sha256` files:
`coderujb_prompts.jsonl` (35a539f0...), `deveval_gpt-4-1106_prompt.jsonl` (cc3b88ed...).

Manifests: `manifests/rest/coderujb.txt` (96 items) and `manifests/rest/deveval.txt` (659), drawn
by `scripts/rest_manifest.py` before any generation. No item is in block 1.

Runs and seeds: 2 runs for every model and benchmark (`results/block1/dstudy.json`), run r sent
with seed r, as in block 1. Nothing was cut: every item, condition and run in the plan was
generated and graded.

## Steps

| When (about) | Step | Result |
|---|---|---|
| 11-10 13:39 | sync | code dir above |
| 11-10 13:40 to 13:51 | `codeimg prompts` CoderUJB (login node) | 96 items, at most 4/6/8 images at 10/12/14 px |
| 11-10 13:52 | render check CoderUJB | 384 requests, page counts equal to `manifests/pages`, 44 pages of 5 items pixel-identical to laptop renders |
| 11-10 13:52 to 14:59 | `codeimg prompts` DevEval (login node) | 2,636 requests (659 items x 4 conditions). The ssh session dropped at about 14:06; the process kept running and finished the file |
| 11-10 15:01 | render check DevEval | page counts equal to `manifests/pages`, 54 pages of 5 items pixel-identical to laptop renders |
| 11-10 15:55 | generation submitted | jobs 85745 (qwen25vl7b), 85746 (qwen35_9b), 85747 (gemma4_12b), 85748 (qwen35_27b), 85749 (mistral24b) |
| 11-10 15:55 to 20:17 | generation | all 5 COMPLETED, exit 0, on medusa6 (two at a time). Elapsed 1:04:19, 2:06:05, 1:36:48, 1:58:21, 1:41:03 (8.45 GPU hours, model load included) |
| 11-10 22:05 | generation check | every gen file has its full grid (768 CoderUJB, 5,272 DevEval rows per model), no duplicate key, 0 request errors, seed equal to run on every row |
| 11-10 22:10 | `codeimg answers` (login node) | CoderUJB per model into `answers_<model>/` (739, 759, 763, 766, 760 to grade) and all models into `answers/` (3,787 to grade, 53 skipped); DevEval into `answers/` (26,342 to grade, 18 skipped) |
| 11-11 09:01 | grading submitted | DevEval 85876 (gorgonas, 12 h); CoderUJB per model 85877 (qwen25vl7b), 85878 (qwen35_9b), 85879 (gemma4_12b), 85880 (qwen35_27b), 85881 (mistral24b), gorgonas, 12 h each, into `coderujb/grades_<model>.jsonl` |
| 11-11 09:02 | DevEval moved | 85876 cancelled before it started: all 3 gorgonas nodes held by another user's jobs with no time limit since 04:41. Resubmitted as 85882 on medusas_shr |
| 11-11 09:07 | DevEval moved again | 85882 cancelled before it started: medusas_shr had free CPUs but no free memory (252 of 252 GB allocated), expected start 11-12 14:52. Resubmitted as a chain of 7 jobs on gorgonas_dev (1:30 limit), each `--dependency=afterany` on the one before, all resuming the same `deveval/grades.jsonl`: 85883 to 85889. 85883 started 09:07 on gorgona3 |
| 11-11 09:25 | DevEval speed | about 16 answers a minute, per-answer test time 3 to 5 times block 1's (mean 43 s once a repo's files are cached, 66 s for its first answers). The pytest processes wait on NFS reads (`wait_on_page_bit_common`), CPU load about 3 on 32 cores. At this speed the 26,342 answers need about 28 h |
| 11-11 09:31 | queue widened | CoderUJB 85877 to 85881 moved to `gorgonas,medusas_shr` (`scontrol update`). DevEval 85893 queued on `gorgonas,medusas_shr` (1-12:00:00) after the chain (`afterany:85889`), resuming the same file. Slurm's start estimate for the CoderUJB jobs: 11-13 08:21 |
| 11-11 10:38 | first chain hand-off | 85883 TIMEOUT at 1:30:25 (expected, the 1:30 limit) with 1,371 rows written; 85884 started on gorgona3 and read `24971 answers in 77 repos, 1371 already done`. No torn last line |
| 11-11 16:15 | DevEval queue reworked | 85893 cancelled. Chain extended to about 11-12 09:00 with 86129 to 86137 (`afterany`, 1:30 each). 86138 submitted from `/snfs2/carlosleao/ufm9/rest/dev_takeover.sbatch` (sha256 57429b41...): queued on `gorgonas,medusas_shr` for 1-12:00:00; when it starts it cancels every `ufm9-dev-grade` job, waits until none is left, then runs `grade_deveval.sbatch` on the same answers and grades file |
| 11-11 22:40 | CoderUJB grading started | 85877 (qwen25vl7b) started on gorgona7 (gorgonas); first rows written. 85878 to 85881 and 86138 still pending (Priority). DevEval at 10,512 of 26,342 rows, chain job 86131 on gorgona3 |
| 11-11 23:08 | CoderUJB grading | 85878 (qwen35_9b) started on gorgona6. At 23:16: 85877 had 45 rows after 36 min; DevEval 10,755 rows |
| 11-12 08:11 | CoderUJB qwen25vl7b done | 85877 COMPLETED in 9:31:35, 739 rows, 739 unique keys, last line complete. 85879 (gemma4_12b) started on gorgona7 |
| 11-12 10:50 | CoderUJB qwen35_9b done | 85878 COMPLETED in 11:42:00, 759 rows, 759 unique keys, last line complete. 85880 (qwen35_27b) started on gorgona6 |
| 11-12 12:30 | DevEval chain ended | last chain job 86137 TIMEOUT on gorgona10 as planned; 16,175 of 26,342 rows, all unique, last line complete. 86138 still pending |
| 11-12 13:23 to 14:02 | /snfs2 stopped taking writes | 85880 crashed with `OSError: [Errno 28] No space left on device` from the grader (`coderujb.py` line 116) after 132 rows, leaving a torn last line; Slurm shows it COMPLETED because `grade_coderujb.sbatch` ends with `echo`, so the grader's exit status is lost. 85881 and 86138 started on gorgona6 at 13:23:59 and died at once (batch step CANCELLED, exit 0:53) with no log file. 85879 FAILED (exit 1) at 14:02 after 404 rows; its log is cut mid-line. At 14:25 `df` showed /snfs2 (BeeGFS) 96% used with 882G free, but creating any file under /snfs2/carlosleao failed with `Remote I/O error`; reads still worked, and /sonic_home and /tmp took writes |
| 11-12 14:30 | CoderUJB partial grades moved | complete lines of `grades_{gemma4_12b,qwen35_27b,mistral24b}.jsonl` copied to `/sonic_home/carlosleao/ufm9/rest_coderujb/` (404, 132, 0 rows; the one torn line of qwen35_27b dropped), each read back with the same count |
| 11-12 17:02 | /snfs2 still failing | creating a file under /snfs2/carlosleao still gave `Remote I/O error`; no file under /snfs2 (depth 3, any user) was modified after 13:04 |
| 11-12 17:43 | /snfs2 writes back | a test write under /snfs2/carlosleao succeeded; `df` 914G free (96%). `/snfs2/carlosleao` uses 1.8T in all, of which `ufm7` 14G and `ufm9` 1.8G |
| 11-12 18:04 | grading resubmitted | CoderUJB into `/sonic_home/carlosleao/ufm9/rest_coderujb/grades_<model>.jsonl`, logs in `/sonic_home/carlosleao/ufm9/logs`: 87824 (gemma4_12b), 87825 (qwen35_27b), 87826 (mistral24b), `gorgonas,medusas_shr`, 12 h. DevEval 87827 from `dev_takeover.sbatch` (no chain left to cancel). 87824 started on gorgona7 and read `359 items to run, 404 already done` |
| 11-12 18:04 to 11-13 09:19 | CoderUJB grading done | 87824 COMPLETED 2:18:43 (gorgona7, resumed at 404), 87825 COMPLETED 6:37:15 (gorgona7, `634 items to run, 132 already done`), 87826 COMPLETED 6:26:52 (gorgona5, 760 to run). No Traceback or OSError in any log. Rows per model, all unique keys and complete last lines: qwen25vl7b 739, qwen35_9b 759 (on /snfs2), gemma4_12b 763, qwen35_27b 766, mistral24b 760 (on /sonic_home): 3,787 in all, the number `answers` wrote |
| 11-13 09:19 | DevEval long job started | 87827 on gorgona5. Log: `takeover start`, `chain gone` the same second (nothing to cancel), then `10167 answers in 77 repos, 16175 already done`. At 10:20: 19,907 rows (about 61 a minute in the first hour, against 12 to 16 a minute in the gorgonas_dev chain) |
| 11-13 12:09 | DevEval grading done | 87827 COMPLETED in 2:50:00; 26,342 rows, all unique, last line complete |
| 11-13 12:22 | `codeimg collect` (login node) | CoderUJB 3,840 rows (`test_error` 2,213, `pass` 780, `test_fail` 785, `no_code` 53, `test_timeout` 9); DevEval 26,360 rows (`error` 19,238, `pass` 6,407, `timeout` 697, `no_code` 18); no problems reported, exit 0 both. sha256 1b7e2909... (CoderUJB), a1c74322... (DevEval); the copies on the laptop match |
| 11-13 12:23 | full table | `scripts/full_table.py build`: CoderUJB 6,240 of 6,240 rows, DevEval 38,360 of 38,360; 0 missing, extra, duplicate, null `passed` or `seed != run` rows |
| 11-13 12:25 | re-score sample | `full_table.py sample`, seed 20261111: 20 CoderUJB and 50 DevEval keys in `rescore_keys.json`. Their gen rows (block 1 and rest) filtered into `/snfs2/carlosleao/ufm9/rescore/<b>/gen_sample.jsonl` (20 and 50 found) and `codeimg answers` rerun on them: 20 and 50 to grade, 0 skipped. Every re-extracted answer equals the original one (row index aside): 0 differ |
| 11-13 16:36 | re-score submitted | CoderUJB: `sbatch` printed `Batch job submission failed: Unexpected message received`, but the job had been created: 88708 (`ufm9-ujb-rescore`) running on gorgona5 at 16:39. DevEval: 88709 (`ufm9-dev-grade`, singleton), pending (Resources). Both 2 h, `gorgonas,medusas_shr`, grades into `/snfs2/carlosleao/ufm9/rescore/<b>/grades.jsonl` |
| 11-13 about 16:45 to 16:57 | phocus4 refused logins | ssh to phocus4 failed with `Permission denied (publickey,password)` for both key and password, while the `dcc` jump host still took the key. Working again at 16:57 |
| 11-13 16:46 | CoderUJB re-score done | 88708 COMPLETED in 8:38; 20 rows, no Traceback or OSError. `full_table.py rescore`: 20 of 20 regraded, 0 verdicts differ |
| 11-13 16:57 | DevEval re-score lost | 88709 NODE_FAIL on gorgona5 at start (elapsed 0:00), no rows written |
| 11-13 about 17:00 | DevEval re-score resubmitted | 88709 stayed in CG on gorgona5 and held the singleton name, so the same job went in as 88710 with `--job-name=ufm9-dev-rescore --exclude=gorgona5` |
| 11-13 18:21 to 18:22 | DevEval re-score done | 88710 COMPLETED on gorgona7 in 1:11; log `50 answers in 23 repos, 0 already done`, 50 rows (10 Pass, 40 Error), no Traceback. `full_table.py rescore` with both grade files: CoderUJB 20 of 20 and DevEval 50 of 50 regraded, 0 verdicts differ, 0 extractions differ |

Truncated replies (`finish_reason` length), CoderUJB / DevEval: Qwen2.5-VL 7B 12 / 92, Qwen3.5 9B
68 / 565, Gemma 4 12B 4 / 77, Qwen3.5 27B 31 / 87, Mistral Small 3.2 24B 0 / 7. As in block 1,
Qwen3.5 9B is the outlier (8.9% and 10.7% here, 8.1% and 9.9% in block 1).

Items for `answers`: `/snfs2/carlosleao/ufm7/coderujb/items.jsonl` and
`/snfs2/carlosleao/ufm7/deveval/data.jsonl`, as in block 1.

Generation command (one `sbatch` per model, printed by the script and confirmed):

```
SBATCH_TIME=04:00:00 <code>/slurm/submit_generate.sh <code> /snfs2/carlosleao/ufm9/rest \
  --runs-from <code>/results/block1/dstudy.json
sbatch --job-name=ufm9-gen-<model> --time=04:00:00 <code>/slurm/generate.sbatch <code> <model> \
  /snfs2/carlosleao/ufm9/rest --runs-from <code>/results/block1/dstudy.json
```
