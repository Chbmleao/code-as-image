full transcription run, submitted 2026-11-15 01:56 -03
code /sonic_home/carlosleao/ufm9/20261114-2248-4b2321e-dirty head 4b2321e files_sha256 f587db11390c7210147ae10f12b21b3cc7a2b5bec35e9a491ed1bbf4f7ebf77f
run dir /snfs2/carlosleao/ufm9/transcribe (408 coderujb + 2577 deveval requests, 9722 pages pixel-checked)
args --transcription --runs 2, --time=08:00:00 --dependency=singleton, 6 jobs per model
qwen25vl7b 89710-89715; qwen35_9b 89716-89721; gemma4_12b 89722-89727; qwen35_27b 89728-89733; mistral24b 89734-89739
check run: /snfs2/carlosleao/ufm9/transcribe_check, jobs 89671 89679 89680 89681 89682, all gate ok
scorer lexer fix after the generation sync (2026-11-15): re-sync before scoring and log that dir's files_sha256
2026-11-15 12:30 chain extended: gemma4_12b 89769-89772, mistral24b 89773 (same args)
2026-11-15 ~15:52 GPU0 (PCI 0000:41:00.0) on medusa3 and medusa4 fails: "Unable to determine the device handle for GPU0: 0000:41:00.0: Unknown Error" / NVMLError_Unknown / CUDA unknown error.
  failed on it: qwen25vl7b 89712 (spare, model already complete), gemma4_12b 89722-89724, qwen35_27b 89728-89733 (whole chain).
  fix 16:05: scancel qwen25vl7b spares 89713-89715; ExcNodeList=medusa3,medusa4 on all pending gen jobs; new qwen35_27b chain 89785-89790 with --exclude=medusa3,medusa4.
  qwen25vl7b complete: 816 + 5154 rows (89711 COMPLETED).
2026-11-15 16:02 GPU1 on medusa3 and medusa4 also fails ("CUDA unknown error"): gemma4_12b 89725, mistral24b 89734 FAILED at startup, no rows lost.
2026-11-15 16:40 pending jobs showed BadConstraints (medusas_shr has no node left after the exclusion): set Partition=medusas_dev on all pending gen jobs.
2026-11-16 08:00 medusa3/4 back (igor jobs COMPLETED there since 15/11 20:00): 89785 (qwen35_27b chain head) un-excluded as a probe; rest of chains still medusa6-only
2026-11-16 13:00 all pending gen jobs un-excluded (medusas_dev,medusas_shr): medusa3/4 have run other users' GPU jobs to COMPLETED since 15/11 20:00
2026-11-16 13:20 un-exclude done (try 4 of flaky ssh); gemma chain extended 90176-90178
2026-11-16 ~15:30 medusa6 GPU0 (0000:41:00.0) fails mid-run: mistral24b 89736 "CUDA error: unspecified launch failure", generate stopped (gave up after 3 retries, connection refused); 89737-89739, 89773 FAILED at startup (NVML Unknown Error). Rows on disk intact (files end in newline, 0 error rows).
2026-11-16 14:12 medusa5 back in service; 89719 (qwen35_9b) and 89727 (gemma4_12b) printed "vllm not ready after 20 min" and hung in the exit trap; scancel at ~15:50, no rows written by them.
2026-11-16 15:50 all pending gen jobs: ExcNodeList=medusa5,medusa6 Partition=medusas_shr. New mistral24b chain 90240-90244.
2026-11-16 16:50 medusa3/4 busy with other users at higher priority; medusa6 GPU1 idle. Wrapper /snfs2/carlosleao/ufm9/ops/healthy_gpu.sh (sha256 fa3843393de943f601bcfce3832b5d1b26a67059955a5ba8ecb6d6827c4e6ee0): sbatch --gres=gpu:2 --nodelist=medusa6, tests each allocated device with torch, sets CUDA_VISIBLE_DEVICES to the working one, execs the same generate.sbatch.
  gemma4_12b: old chain 89769-89772, 90176-90178 cancelled (singleton made 90275 wait on them); medusa6 chain 90275, 90288-90294.
2026-11-16 17:00 90275 on medusa6: both devices fail CUDA init ("CUDA unknown error"), so a broken GPU0 blocks new CUDA contexts on the whole node (as on medusa3/4 on 15/11). Wrapper not used further. Cancelled 90288-90294; gemma4_12b chain 90295-90302 on medusas_shr excluding medusa5,medusa6.
2026-11-16 18:35 probe 90347 on medusa6 (gpu:2): both devices "CUDA unknown error". Cancelled spares 89721, 89790, 90244.
2026-11-16 19:14 medusa4 GPU0 (0000:41:00.0) NVML Unknown Error again: 89720 (qwen35_9b), 89786-89788 (qwen35_27b) FAILED at startup, no rows lost. Pending gen jobs: ExcNodeList=medusa4,medusa5,medusa6 Partition=medusas_shr. New: qwen35_9b 90374, qwen35_27b 90375-90378.

## 2026-11-16 ~20:44 medusa3 GPU0 fails too
- 90240 (mistral) on medusa3: "Unable to determine the device handle for GPU0: 0000:41:00.0: Unknown Error"; vLLM "CUDA unknown error". Cancelled.
- 90295 (gemma) on medusa3 GPU1: vllm log empty after 8 min.
- Held all pending gen jobs (90241-90243, 90296-90302, 90374, 90375-90378) so the chains do not burn on startup failures. Release after a node passes cuda_probe.sh.
- 90295 (gemma, medusa3 GPU1) FAILED after 19:23: vllm_90295.log line 50 "RuntimeError: CUDA unknown error". Whole node without CUDA, same as medusa6. Queue stays held; nothing resubmitted.

## 2026-11-17 ~07:25 probes
- 90348 medusa5: "device ok NVIDIA GeForce RTX 5090".
- 90437 medusa3, 90438 medusa4, 90439 medusa6: "CUDA unknown error" on both devices.
- Pending gen jobs moved to Partition=medusas_dev, ExcNodeList=medusa3,medusa4,medusa6 (medusa5 only) and released.

## 2026-11-17 10:22 to 10:38 medusa5 fails under our jobs
- 90374 (9b) and 90375 (27b) started 10:22 on medusa5, wrote 15 and 3 rows, then vLLM died: 90374 "torch.AcceleratorError: CUDA error: unknown error" (10:30:26), 90375 "CUDA error: unspecified launch failure" (10:29:47). generate stopped with "gave up after 3 retries: ConnectionRefusedError".
- Chains then burned on startup failures ("NVMLError_Unknown", "CUDA unknown error"): 90241-90243, 90296, 90297, 90376-90378.
- Cancelled 90298, held 90299-90302. No 9b, 27b or mistral jobs left in the queue.
- Rows 14507 (9b +15, 27b +3).

## 2026-11-17 ~10:45 aborted rows
- check_gen found finish_reason "abort" rows with error None: deveval qwen35_9b 24, qwen35_27b 8. vLLM answers in-flight requests with "abort" when its engine dies, and run_grid counted them as done.
- Fix: Client.reply raises StopJob on finish_reason "abort" (test_an_aborted_reply_stops_the_job_without_a_row). pytest 142 passed, 1 skipped.
- Backed up to /snfs2/carlosleao/ufm9/ops/backup_20261117/ and dropped the rows: 9b 4163 -> 4139 (backup sha256 96e1f775..., new 30bceca9...), 27b 651 -> 643 (backup 99b9fab7..., new bf00a6e5...).
- Synced code: /sonic_home/carlosleao/ufm9/20261117-1044-4b2321e-dirty, files_sha256 22fc0d16dc7326b62bba58869de1e2d5880070eaefda0b32f0851bc680b9211d. Rows before this point came from 20261114-2248-4b2321e-dirty (f587db11...).
- Cancelled held gemma 90299-90302 (old code dir). Queue empty until a node passes cuda_probe.sh.

## 2026-11-17 ~14:10 resubmitted
- Probes 10:48 and 11:52: no device ok on any medusa. 12:57 and 14:01 probes never got a node (all GPUs busy with other users) and were cancelled by the loop.
- Admin (group chat): GPU0 of every medusa and gorgona3 went down; checking on site. Since 11:00 other users completed 144 jobs on medusa3-6, so the GPUs look back.
- Submitted from 20261117-1044-4b2321e-dirty (sha256 -c ok, files_sha256 22fc0d16...), partition medusas_dev,medusas_shr, 8 h, singleton:
  qwen35_9b 90847-90848; qwen35_27b 90849-90853; mistral24b 90854-90858; gemma4_12b 90859-90867.
- 90847 (9b) on medusa6 FAILED after 1 min: "vllm.third_party.pynvml.NVMLError_Unknown: Unknown Error". medusa6 GPU0 still down; other users' jobs evidently do not need it. Held the 19 pending jobs; probes now ask for 1 GPU (a dead GPU0 takes CUDA down on the whole node, so one working device means the node is back).

## 2026-11-17 17:32 medusa3 and medusa5 back
- Probes 91199 medusa3 and 91201 medusa5: "device ok NVIDIA GeForce RTX 5090". 91200 medusa4: "/snfs2/carlosleao/ufm8/venv/bin/activate: Communication error on send" (snfs2 mount problem on medusa4). 91202 medusa6 did not run.
- Pending jobs moved to Partition=medusas_dev,medusas_shr ExcNodeList=medusa4,medusa6 and released. New qwen35_9b chain 91203-91204 with the same exclusion.
- Started: 90849 (27b) and 90854 (mistral) on medusa5, 90859 (gemma) on medusa3.
- 91203 (9b) on medusa3 wrote 40 rows, then vLLM died at 17:52:33 ("AsyncLLM output_handler failed", c10::Error); generate stopped with "gave up after 3 retries: ConnectionRefusedError". 91204 failed at startup with "NVMLError_Unknown: Unknown Error". medusa3 lost a GPU again ~20 min into our load; gemma 90859 on its other GPU kept running.
- Pending jobs moved to Partition=medusas_dev ExcNodeList=medusa3,medusa4,medusa6 (medusa5 only). New qwen35_9b chain with the same exclusion.

## 2026-11-17 evening: every GPU fails under load
- 90859 gemma medusa3 died at ~18:02 (29 min): "CUDA error: unknown error".
- 90854 mistral medusa5 died at ~18:13 (41 min): "CUDA error: unspecified launch failure".
- 90849 27b medusa5 died at ~18:52 (79 min): "CUDA error: unknown error".
- From 19:32 every remaining chain job failed at startup on medusa5 ("NVMLError_Unknown", "CUDA unknown error"): 90850-90853, 90855-90858, 90860-90867, 91299-91300. Queue empty.
- The 15-min monitor printed nothing for 6 h: every ssh poll failed silently (2>/dev/null, no retry); the poll works when run by hand at 00:20.
- Rows 14882. Not resubmitted: GPUs fail 20 to 80 min into our vLLM load, and other users' jobs fail on those nodes afterwards.

## 2026-11-18 00:25 resubmitted
- Admin: Slurm normalized at 17:28 on 17/11. Resumed as before.
- Probes: 91442 medusa3 and 91444 medusa5 "CUDA unknown error"; 91443 medusa4 and 91445 medusa6 "device ok".
- Chains from 20261117-1044-4b2321e-dirty, medusas_dev,medusas_shr, --exclude=medusa3,medusa5, 8 h, singleton (IDs below).
- qwen35_9b 91447-91448; qwen35_27b 91449-91453; mistral24b 91454-91458; gemma4_12b 91459-91468.
- 91454 mistral medusa4 died at ~00:34 (10 min): "CUDA error: unspecified launch failure". Then 91455-91458, 91459-91463 failed at startup ("NVMLError_Unknown"). Cancelled 91464, held the rest, pending jobs now medusa6 only (medusas_dev, ExcNodeList=medusa3,medusa4,medusa5). 91447 (9b) and 91449 (27b) keep running on medusa6.

## 2026-11-18 08:35
- 91447 qwen35_9b COMPLETED on medusa6 after 4:45:24 (deveval 5154 rows): qwen35_9b done, 5970 rows.
- 91449 qwen35_27b TIMEOUT at 8 h on medusa6 with no GPU fault (deveval 2242). medusa6 held up 8 h under two vLLM jobs.
- The laptop slept from ~00:40 to 08:30, so the local monitor did not poll in that window.
- Cancelled 91448 (9b spare). Released 27b 91450-91453 and gemma 91465-91468 (medusa6 only). New mistral chain 91493-91497 on medusa6 only.
- 08:40 probes: 91498 medusa3, 91499 medusa4, 91500 medusa5 "CUDA unknown error"; 91501 medusa6 did not run (busy). Queue stays medusa6 only.
- 08:48 probes: 91502 medusa3, 91503 medusa4, 91504 medusa5 "CUDA unknown error"; 91505 medusa6 did not run.
- 11:38 probe 91710 medusa5 (gpu:2): "CUDA unknown error". medusa6 held by another user's two 1-GPU jobs; 27b 91450, gemma 91465 and mistral 91493 pending.
- ~11:36 the local temporary dir was cleared: these notes were rebuilt from the command history into results/transcription/run_notes.md, and the monitor's poll script was lost (monitor reported "ssh failed" 11:55 to 12:47 because the script was missing, not because of ssh).
- 2026-11-18 13:26: gemma 91465 started on medusa6 (second GPU). By 15:08: gemma coderujb 816/816, deveval 24; 27b deveval 2731; total 17858.
- 2026-11-18 15:10: probes 91777-91779 on medusa3, medusa4, medusa5 all still "CUDA unknown error". Mistral 91493 stays pending for medusa6.
- 2026-11-18 evening: admin announced a GPU health check that drains a failing node and requeues the job. Probes 91794-91796 right after still got "CUDA unknown error" on medusa3, medusa4, medusa5, and sinfo kept all three idle (not drained). Exclusion kept; the 3 nodes reported to the admin.
- 2026-11-18 19:57: 27b 91450 and (21:26) gemma 91465 hit the 8 h limit (TIMEOUT) as planned. Mistral 91493 took the free GPU at 19:57; 27b 91451 started 21:27 and gemma waited.
- 2026-11-19 00:07: medusa6 GPU0 (0000:41:00.0) died under 27b 91451, 2h40 into the job: vllm_91451.log "torch.AcceleratorError: CUDA error: unspecified launch failure", then "gave up after 3 retries: ConnectionRefused". No abort rows written (abort fix held; grep finds 0 abort rows in all files).
- 2026-11-19 00:09-00:16: 91452, 91453, 91466-91468 failed at start with "NVMLError_Unknown" for GPU0 0000:41:00.0. Chains for 27b and gemma burned.
- 2026-11-19 03:57: mistral 91493 on GPU1 survived until its 8 h TIMEOUT (deveval 715 to 1770). 91494-91497 then failed at start with "CUDA unknown error"; chain burned.
- The admin's new GPU check did not drain medusa6: sinfo shows it idle at 08:16. Local monitor had stopped printing at 22:26 (Mac asleep), so the failures were not caught overnight.
- 2026-11-19 08:20: probes 91886-91889: GPU0 dead on all four medusas (3, 4, 5, 6). No queued ufm9 jobs. Rows: 20925 / 29850 (27b deveval 4179, mistral 1770, gemma 588).
- 2026-11-19 ~09:10: two-GPU probes 91901-91904 (--gres=gpu:2, each device tested alone). On all four medusas nvidia-smi fails on GPU0 0000:41:00.0 ("Unable to determine the device handle ... Unknown Error") and lists GPU1 0000:83:00.0 as healthy, but CUDA init fails on both devices ("CUDA unknown error"). sinfo -a lists only medusa3-6 with GPUs for us; no usable node.
- 2026-11-19 08:23-13:16: 30-min probes, all four medusas dead every time.
- 2026-11-19 13:16: admin reservations gpu_falling_test (gorgona3) and gpu_falling_test2 (medusa6), 13:16 to 23:16. 13:30 probes 92005-92007: medusa3, 4, 5 still dead; medusa6 probe could not run (reserved).
- 2026-11-19 13:48 to 22/11: local watcher stalled (Mac asleep); no ufm9 jobs ran. 19/11 16:50: medusa3 down* (Not responding), medusa6 reservation gone.
- 2026-11-22 09:25: medusa3 down* (Not responding); medusa4, 5, 6 drained by root since 20/11 09:53 ("Job step not running"). No usable node.
- 2026-11-22 09:30: queued one job per model, no chain, to start as soon as a medusa is released: gemma 92131, mistral 92132, 27b 92133 (--partition=medusas_dev,medusas_shr, no exclusions, code dir 20261117-1044). Chains to be added once a job is seen running.
- 2026-11-22 11:01: admin reported at least one GPU per medusa down again and bus tests that may take snfs2 down. snfs2 partly broken: reading the venv gives "Communication error on send" (timeout), data files still readable. Medusas unchanged (3 down*, 4-6 drained). 92131-92133 left pending.
- 2026-11-22 17:00: no change (medusa3 down*, 4-6 drained, jobs pending). snfs2 (beegfs) reads fail on some files only: ufm8/venv/bin/activate and the Qwen3.5-27B-AWQ snapshot config.json time out ("Communication error on send"); venv python3, pyvenv.cfg, ops scripts and the gen jsonl files read fine.
- 2026-11-23 07:37: no change on medusas (3 down*, 4-6 drained), 92131-92133 pending. snfs2 read failures spread to coderujb/gen/qwen25vl7b.jsonl (816 rows, 30 MB, listed fine but reads give "Communication error on send"). Copied the 9 readable gen files (and their meta files) to /sonic_home/carlosleao/ufm9/backup_gen_20261123/ (720 MB). If the qwen25vl7b coderujb file does not come back, its 816 rows must be regenerated.
- 2026-11-23 09:20: transcription work moved to branch transcription-tests. Files hash recomputed locally with the sync_cluster.sh listing (46 files): 22fc0d16dc7326b62bba58869de1e2d5880070eaefda0b32f0851bc680b9211d, equal to the CODE_VERSION of 20261117-1044-4b2321e-dirty.
- 2026-11-23 09:40: ops scripts copied to /sonic_home/carlosleao/ufm9/ops/ (check_gen.py, cuda_probe.sh, cuda_probe2.sh, healthy_gpu.sh sha256 fa384339..., probe_all.sh, run_notes.md). Reads under /snfs2/carlosleao/ufm9/ops/ now hang; backup_20261117/ (the abort-row backups) is still only on snfs2.
