# Long-context code benchmarks: notes for the text vs image context study

Compiled 2026-09-28 from the arXiv abstract and HTML pages, the GitHub READMEs and APIs, and the Hugging Face dataset cards. "Verified" means I read it on those pages or computed it from the released files. Anything marked UNVERIFIED comes from search snippets, memory, or was not found. No benchmark was run.

Project constraint to keep in mind: 3 to 5 open VLMs from 7B to about 32B served with vLLM on one Linux machine (Rocky Linux 9.8, Threadripper 7970X 32 cores, 250 GB RAM, one RTX 5090 32 GB, Docker or Podman available), execution-based scoring (unit tests), and a context that is naturally long and multi-file or multi-turn. The context is the thing we render as an image, so what matters per item is how much of the prompt is "context" that can be moved into an image, and whether the target question can be scored by running tests. The psychometric analysis (Rasch, G-theory, DIF) needs items whose pass rates for the stronger models sit away from 0 and 1, with several runs per item.

Second pass (same date) resolved several UNVERIFIED marks below and added sections 4e to 4j, a run-cost estimate and a new recommendation table. Sections 1 to 3 and 4a to 4d were edited in place where a mark was resolved.

---

## 1. CodeFlowBench

**Citation.** Sizhe Wang, Zhengren Wang, Dongsheng Ma, Yongan Yu, Rui Ling, Zhiyu Li, Feiyu Xiong, Wentao Zhang. "CodeFlowBench: A Multi-turn, Iterative Benchmark for Complex Code Generation." arXiv:2504.21751 (v1 30 Apr 2025, v4 15 Apr 2026). Venue: ACL 2026 Main Conference (stated in the GitHub README and listed at ACL Anthology, https://aclanthology.org/2026.acl-long.201/). Paper: https://arxiv.org/abs/2504.21751. Code: https://github.com/Rise-1210/codeflow (MIT). Data: https://huggingface.co/datasets/WaterWang-001/CodeFlowBench-2505 (the HF card lists license MIT; 5,258 rows, 2.2 GB; the Codeforces material inside stays under a non-commercial academic license).

Note: the arXiv id 2504.20434 is a different paper (ARCS). Use 2504.21751.

**What it measures.** "Codeflow": implementing new functionality by reusing functions written in earlier turns. Each problem is decomposed into a dependency tree of subproblems (functions). In the multi-turn setting the model writes the subfunctions one turn at a time, bottom up, and later turns can call earlier ones. In the single-turn setting the model writes the whole solution at once. The gap between the two is the headline finding.

**Item format.**
- Two subsets. CodeFlowBench-Comp: 5,258 Codeforces problems in the paper (v4); the released test file has 986 problems (the paper evaluates "the most recent 1,000"; the 14-item difference is not explained in what I read). CodeFlowBench-Repo: built from DomainEval; 70 multi-turn problems plus 12 single-turn problems per domain over five domains (the released file has 129 items).
- Single file, function-level. Multi-turn: each turn adds the previous turns' code and a subproblem statement to the conversation, so the history is the "long context".
- Context length: the paper gives no per-item prompt token count that I found. In the released JSON, the median record is about 6.3k characters (Repo) and 6.9k characters (Comp), but a record also holds solutions and tests, so the actual prompt is smaller. In practice prompts are a few thousand tokens at most. Not naturally long. UNVERIFIED as a token figure.

**Scoring.** Execution. Comp: test cases (Codeforces-official tests verified the reference solutions; subproblem tests are generated). Repo: test code derived from the DomainEval tests, run in Docker containers because of package dependencies. Metrics: Pass@1, plus Average Pass Depth (APD@k) and Average Pass Turn (APT@k).

**Size, license, setup.** Comp test 986 (file), Repo 129 (file). Repo code MIT. Setup: pure Python with conda (Python 3.10) and `pip install -r requirements.txt`; Repo subset needs `requirements_repo.txt` and, per the paper, Docker for execution. Inference scripts assume HF weights or an API model. Codeforces materials are used under the academic, non-commercial license (per the paper).

**Models and headline numbers (v4 Table 1, Comp, Pass@1 multi-turn vs single-turn).** GPT-5 26.5 vs 37.6; o1-mini 20.8 vs 37.8; Claude-4.5-Sonnet 31.6 vs 47.9; Gemini-3-flash-thinking 48.4 vs 65.5. Open 7B-8B: Llama-3.1-8B-Instruct 0.9 vs 3.5; Qwen2.5-Coder-7B-Instruct 2.3 vs 15.0; Qwen3-8B 9.1 vs 18.3. Larger open: Qwen2.5-Coder-32B 8.6 vs 19.8; Llama-3.3-70B 15.0 vs 27.6.

**How it relates to our project.**
- Fit as item source: partial. It is execution-scored and genuinely multi-turn, which is what we want. But the "context" is a few short function turns, not thousands of tokens, so an image-vs-text contrast would need us to render the conversation history as an image, and the savings would be small per item.
- 7B floor problem: 7B models score 0.9 to 9.1 percent on Comp multi-turn, which cannot show a text-to-image drop. The Repo subset has headroom (v4 Table 1, Pass@1 multi-turn / single-turn): Llama-3.1-8B 17.3 / 39.6; Qwen2.5-Coder-7B 19.7 / 39.1; Qwen3-8B 18.1 / 36.2; Qwen2.5-Coder-32B 25.2 / 45.7; Qwen3-Coder-30B-A3B 23.6 / 42.5; Qwen2.5-72B 25.2 / 43.3; Llama-3.3-70B 22.1 / 39.6. Comp at 14B to 34B: Qwen2.5-Coder-32B 8.6 / 19.8, Qwen3-Coder-30B-A3B 11.6 / 26.0. So use Repo, or Comp single-turn.
- Contamination: Comp uses Codeforces problems and the authors report a chronological slice check (no clear degradation on newer slices; the check was on Gemini-3 and Claude-4.5, not on 7B models). Codeforces editorial and problem text is likely in 7B pretraining data. Repo comes from public GitHub repos via DomainEval, also likely seen.
- Feasible items: several hundred (Comp subset filtered to depth 1 to 3, plus 129 Repo). Compute per item is small. Repo needs Docker or matching packages on a Mac.

---

## 2. RepoBench

**Citation.** Tianyang Liu, Canwen Xu, Julian McAuley. "RepoBench: Benchmarking Repository-Level Code Auto-Completion Systems." arXiv:2306.03091 (5 Jun 2023, v2 4 Oct 2023). Venue: ICLR 2024 (stated in the GitHub README). https://arxiv.org/abs/2306.03091. Code: https://github.com/Leolty/repobench (repo license CC-BY-4.0 per the GitHub API). Data: https://huggingface.co/datasets/tianyang/repobench_python_v1.1 (and the Java twin). The older sets `tianyang/repobench-c` and `repobench-p` list cc-by-nc-nd-4.0 on their cards; the v1.1 card license was not checked (UNVERIFIED). Treat the license as needing a check before redistribution.

**What it measures.** Next-line completion given cross-file context, in three tasks: RepoBench-R (retrieve the right cross-file snippet), RepoBench-C (complete the next line given a prepared context), RepoBench-P (retrieve then complete, full pipeline). Python and Java. Settings: cross_file_first (first use of an imported module masked), cross_file_random, in_file.

**Item format.** One target line per item. Context = code snippets from other files in the same repo (imports resolved) plus the in-file prefix. Multi-file, single-turn. Lengths (Table 1, Python): RepoBench-C 2k subset mean 1,035 tokens, 8k subset mean 3,967 tokens; RepoBench-P mean 44,028 tokens (Java 139,406). In v1.1 the record carries a `token_num` field and a `created_at` date; v1.1 splits have 8,033 (cross_file_first), 7,618 (cross_file_random) and 7,910 (in_file) examples for Python.

**Scoring.** Not execution. Exact Match and Edit Similarity on the predicted line; Acc@k for retrieval. No tests.

**Size, setup.** Paper test sets for Python RepoBench-C: the 2k subset lists 12,000, 5,000 and 7,000 examples across settings and the 8k subset lists 18,000, 7,500 and 10,500 (Table 1 column labels were ambiguous when read, so treat the per-setting mapping as UNVERIFIED). Setup is pure Python; `load_dataset` from Hugging Face plus a simple `run.py`. No repo checkouts, no Docker (the snippets are pre-extracted).

**Models and headline numbers (paper Table 3, RepoBench-C Python, EM / ES, "All").** CodeGen 350M 20.71 / 64.22; CodeGen 6.1B 31.67 / 70.68; StarCoder 15.5B 31.67 / 71.28; CodeGen 16.1B 33.41 / 71.22; Codex 175B 31.31 / 72.22. All are code-completion models from 2023; no VLMs.

**How it relates to our project.**
- Fit: good on the "naturally long, multi-file" criterion (2k to 8k-token contexts are within reach of 7B VLMs at image resolution), bad on the scoring criterion. Exact match on one line is not execution-based; the project asked for unit tests.
- One could run a smaller EM-based side study, but EM on a single line is noisy and sensitive to formatting, which a VLM reading an image of the code might change in ways unrelated to comprehension.
- Contamination: v1.1 was rebuilt with newer GitHub data and has per-item dates, so we can select items created after a model's cutoff. Original sets predate most 7B model training and are likely seen.
- Feasible items: thousands available; 200 to 500 is easy. Cost per item is low.

---

## 3. LongCodeBench (LCB)

**Citation.** Stefano Rando, Luca Romani, Alessio Sampieri, Luca Franco, John Yang, Yuta Kyuragi, Fabio Galasso, Tatsunori Hashimoto. "LongCodeBench: Evaluating Coding LLMs at 1M Context Windows." arXiv:2505.07897 (12 May 2025, v3 22 Oct 2025). Venue: an OpenReview forum exists (https://openreview.net/forum?id=GFPoM8Ylp8); a search summary said COLM 2025 but I could not confirm it on the page, so the venue is UNVERIFIED. https://arxiv.org/abs/2505.07897. Code: https://github.com/Zteefano/long-code-bench (the GitHub API reports no license, so the code license is unknown; default branch is master; uses Pixi and Hydra). Data: https://huggingface.co/datasets/Steefano/LCB (card license apache-2.0; files LongCodeQA.zip and LongSWE_Bench.zip). The arXiv paper is CC0.

**What it measures.** Long-context comprehension and repair on real GitHub repositories, at six context brackets: 32K, 64K, 128K, 256K, 512K, 1M tokens. Two tasks:
- LongCodeQA: multiple-choice question derived from a real GitHub issue discussion, with the repository as context. 443 questions from 98 repositories. Scored by accuracy (not execution).
- LongSWE-Bench: bug fixing, SWE-bench style. The model gets a subset of the repo files sized to the bracket plus the issue, and outputs a patch. 600 instances from 61 repositories, 100 per bracket. Scored by running unit tests in a per-instance Docker image.

Whole benchmark: 1,043 instances from 108 repositories (from the paper's intro).

**Item format.** Single-turn, multi-file, repo-scale. Table 2 (LongSWE-Bench): mean files per repo grows from 8 (32K) to 203 (1M); about 3.2k to 5.2k tokens per file. Python repositories.

**Scoring.** LongSWE-Bench is execution-based (unit tests, Docker). LongCodeQA is multiple choice.

**Setup cost.** High for LongSWE-Bench: Docker image per instance and evaluation of patches. Also, the authors filtered QA questions with GPT-4 (questions answerable without the repo were removed). Self-hosted Qwen2.5-14B inference in the paper (Table 6, read from the table layout) used 8 A100 80GB for 12 h on LongCodeQA and 4 A100 64GB for 35 h on LongSWE-Bench. This corrects the earlier note, which had the two tasks swapped.

**Per-bracket detail (Table 2, verified).** LongCodeQA items per bracket (32K, 64K, 128K, 256K, 512K, 1M): 113, 76, 92, 65, 47, 50. LongSWE-Bench: 100 per bracket; repos per bracket 12, 11, 11, 10, 10, 7; files per repo 8, 17, 27, 62, 135, 203; tokens per file 5200, 3668, 4646, 4219, 3211, 4372. LongCodeQA files per repo 26, 56, 88, 93, 209, 202; tokens per file 690, 862, 1047, 1840, 1782, 3419.

**Open-model results.** Qwen2.5-14B-Instruct, LongCodeQA accuracy by bracket: 61.9, 65.8, 68.5, 63.1, 70.2, 40.0. Qwen2.5-14B-Instruct on LongSWE-Bench: 0 at every bracket. Llama 4 Scout: 0 at every bracket. Claude 3.5 Sonnet: 29, 19, 15, 3 (32K to 256K). No model under 14B was tested.

**Tunable SWE-Bench.** The README describes a builder that repeats each SWE-bench problem with a chosen number of context files (bm25 or random retrieval). That would let us build our own 8K to 24K variants, but the resulting pass rates for 7B to 32B models are unmeasured.

**Models and headline numbers.** GPT-4o, GPT-4.1, Claude 3.5 Sonnet, Gemini 2 Flash / 1.5 Pro / 2.5 Pro, Qwen2.5-14B-Instruct, Jamba 1.5 Large, Llama 3.1 405B, Llama 4 Scout. Claude 3.5 Sonnet solves 29% of LongSWE-Bench issues at 32K and 3% at 256K; Qwen2.5 on LongCodeQA goes from 70.2% at 512K to 40.0% at 1M. Gemini 2.5 Pro gets 23% at 32K and 7% at 1M. No model below 14B and no VLM was evaluated (from the model list I read).

**How it relates to our project.**
- Fit: it is the only one of the three that is natively long, multi-file and (for the SWE part) execution-scored. But the shortest bracket is 32K tokens of text. A 7B VLM on 24 GB in Ollama will struggle with 32K text tokens (memory and speed), and rendering 32K tokens (roughly 100k+ characters) as images means many pages at legible resolution. The only open model tested (Qwen2.5-14B) scores 0 on LongSWE-Bench at every bracket, so a 7B to 32B model gives no headroom at the reported settings; a 32B coder model was not tested and its score is unknown.
- LongCodeQA is more usable for weaker models (multiple-choice gives a nonzero floor by design) but is not execution-scored, which conflicts with the project goal. Could serve as a secondary, accuracy-scored task.
- Contamination: repos are public GitHub, so likely seen, but QA questions were filtered against no-context GPT-4 answers. The LongSWE-Bench issues follow SWE-bench, which has known leakage into recent models (UNVERIFIED for these specific instances).
- Feasible items: 100 per bracket; only the 32K bracket is plausible for us, so 100 SWE items and 113 QA items. On the Linux x86 machine Docker images run natively.

---

## 4. Other candidates

### 4a. CrossCodeEval

Yangruibo Ding, Zijian Wang, Wasi Uddin Ahmad, Hantian Ding, Ming Tan, Nihal Jain, Murali Krishna Ramanathan, Ramesh Nallapati, Parminder Bhatia, Dan Roth, Bing Xiang. "CrossCodeEval: A Diverse and Multilingual Benchmark for Cross-File Code Completion." arXiv:2310.11248 (17 Oct 2023). NeurIPS 2023 Datasets and Benchmarks track. https://arxiv.org/abs/2310.11248. Code and data: https://github.com/amazon-science/cceval (Apache-2.0 for the repo; the data license is UNVERIFIED; the README says raw data is available by email).

- Task: complete a statement where at least one cross-file entity is used. Python, Java, TypeScript, C#. Examples: Python 2,665 (471 repos), Java 2,139, TypeScript 3,356, C# 1,768. Average prompt 584 to 995 tokens (StarCoder tokenizer).
- Scoring: exact match, edit similarity, identifier match. No execution.
- Headline (Python EM): StarCoder-15.5B 8.82 with in-file context only, 15.72 with retrieved cross-file context; GPT-3.5-turbo 4.88 and 10.77.
- Setup: pure Python, tree-sitter build, vLLM script. Repos were chosen to not overlap with The Stack, and the paper discusses memorization as a limitation.
- Relation: context is small (short prompts plus retrieved cross-file context), so there is little to save with images, and the scoring is not execution. Low fit; mention only as a sibling of RepoBench.

### 4b. EvoCodeBench

Jia Li, Ge Li, Xuanming Zhang, Yihong Dong, Zhi Jin. "EvoCodeBench: An Evolving Code Generation Benchmark Aligned with Real-World Code Repositories." arXiv:2404.00599 (31 Mar 2024). Venue not stated on the arXiv page (still UNVERIFIED whether published). HF data: https://huggingface.co/datasets/LJ0815/EvoCodeBench (card lists no license). https://arxiv.org/abs/2404.00599. Code and data: https://github.com/seketeam/EvoCodeBench (Apache-2.0).

- Task: repository-level function generation from a requirement, with local repo context (the README's prompt script takes a context window up to 16,384 tokens). EvoCodeBench-2403 has 275 samples from 25 repositories.
- Scoring: execution, Pass@k (unit tests), plus Recall@k of reference dependencies.
- Headline: the best Pass@1 is 20.73% for gpt-4 across 10 LLMs.
- Version 2403: 275 items, 25 repos. Model windows in the paper are 16,384 tokens. No per-item context token count is reported (UNVERIFIED as a per-item figure); the average repo is 1.1M tokens, so the prompt is a truncated local file or infilling context.
- Setup (README, verified): Ubuntu with conda and pip packages, then `bash setup_env.sh`, which the README says takes a few hours. No Docker. Do not run parallel evaluations in the same repo. On Rocky Linux 9.8 this needs adaptation or an Ubuntu container (untested). Per-test runtime is not reported.
- Pass@1 (paper Table 4, Local File Completion): DeepSeek Coder 33B 14.18, 6.7B 13.45; StarCoder2 15B 13.45, 7B 13.82; CodeLlama 13B 12.73, 7B 12.73; Gemma 7B 10.55; Qwen1.5 7B 5.45; gpt-4 17.45. Infilling: DeepSeek 33B 19.64, 6.7B 17.82; StarCoder2 15B 14.91, 7B 15.27; gpt-4 20.73. No context: 5.45 to 7.27. So open models land at 5 to 20%, and per-item pass rates for many items will be at the floor.
- Relation: execution-scored and multi-file, but only 275 items and low pass rates. Weak for Rasch since most items will sit near 0 for 7B models.

### 4c. MINT

Xingyao Wang, Zihan Wang, Jiateng Liu, Yangyi Chen, Lifan Yuan, Hao Peng, Heng Ji. "MINT: Evaluating LLMs in Multi-turn Interaction with Tools and Language Feedback." arXiv:2309.10691 (19 Sep 2023). ICLR 2024. https://arxiv.org/abs/2309.10691. Code: https://github.com/xingyaoww/mint-bench (Apache-2.0).

- Task: multi-turn problem solving with Python tool use and simulated natural-language feedback (GPT-4 plays the user). Repurposes reasoning, coding and decision-making datasets into a compact subset. Twenty open and closed LLMs evaluated. Reported: each turn of tool use adds 1 to 8 points, and language feedback adds 2 to 17 points.
- Coding items come from established code sets (I did not verify which and how many; HumanEval and MBPP are the usual ones, UNVERIFIED). Scoring by executing tests on the final code.
- Setup: Docker recommended by the README. The feedback simulator uses GPT-4 (API cost, and a dependency on a proprietary model; a local judge would change the protocol).
- Relation: it gives real multi-turn histories, but the contexts are short (same problem sizes as HumanEval-like tasks), so it repeats the weakness of the pilot (padding needed). Low fit unless we accept a local feedback simulator.

### 4d. SWE-bench Lite (brief)

Carlos E. Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, Karthik Narasimhan. "SWE-bench: Can Language Models Resolve Real-world GitHub Issues?" arXiv:2310.06770. ICLR 2024. https://www.swebench.com, code https://github.com/SWE-bench/SWE-bench (MIT). SWE-bench Lite on Hugging Face (princeton-nlp/SWE-bench_Lite): 300 test and 23 dev instances. Execution-scored, per-instance Docker images, heavy setup, and 7B models typically resolve very few instances (general knowledge, not measured here; UNVERIFIED). Prompt context per instance is long (the LongCodeBench paper lists SWE-Bench max context as 50K). It is the ancestor of LongSWE-Bench; use LongSWE-Bench's 32K bracket instead if we go this route.

### 4e. DevEval

Jia Li et al. "DevEval: A Manually-Annotated Code Generation Benchmark Aligned with Real-World Code Repositories." https://arxiv.org/abs/2405.19856. Code and data: https://github.com/seketeam/DevEval (the GitHub API returned no license; venue not verified).

- 1,874 items from 117 repositories, 73% non-standalone functions. Requirements average 91.5 tokens; repos average 243 files and 45,941 lines. Model windows in the paper are 16k; no per-item context token count is reported (UNVERIFIED).
- Scoring: execution, Pass@k with unit tests. Setup: conda `environment.txt`, pip requirements, NLTK_DATA, checked with `python pass_k.py`. No Docker mentioned in the README.
- Pass@1, Local File Completion: DeepSeek Coder 33B 41.78, 6.7B 36.13; StarCoder2 15B 37.78, 7B 32.82; CodeLlama 13B 41.94, 7B 39.75; gpt-4 47.44. Infilling: DeepSeek 33B 46.32, 6.7B 40.82; gpt-4 53.04. No context: gpt-4 17.40. These are 2024 code models; newer Qwen coder models were not in the paper.
- Relation: the best headroom found among multi-file, unit-tested, repo-derived sets (open models roughly 33 to 46%), and the context that matters (repo files) is what would go into an image. The cost is size (1,874 items would need subsampling).

### 4f. RepoExec

https://arxiv.org/abs/2406.11927. 355 items, 22.8% requiring cross-file context, average line coverage 96.25%. Average prompt tokens 362.92 (full), 253.05 (medium), 179.66 (small). Execution-scored, but prompts are short, so little to render as an image. Open-model Pass@1 table not captured (UNVERIFIED). Setup and license not checked.

### 4g. BigCodeBench

https://arxiv.org/abs/2406.15877, https://github.com/bigcode-project/bigcodebench (Apache-2.0). 1,140 tasks, 5.6 tests per task on average, 99% branch coverage. Prompt length in the paper's statistics table: 1112.5 (Complete) and 663.2 (Instruct), read as characters (unit not confirmed); short, not naturally long. The paper reports Instruct 8.5 points lower than Complete on average, and Qwen2.5-Coder-32B-Instruct at 27.7 on the Hard Instruct subset. Per-model scores for 7B to 34B open models were not captured (UNVERIFIED). Useful as a short-context control with good headroom, not as a long-context set.

### 4h. ClassEval, LiveCodeBench, Long Code Arena

- ClassEval (https://arxiv.org/abs/2308.01861): 100 class-level Python tasks, execution-scored. Prompt lengths and open-model pass rates not captured (UNVERIFIED). Only 100 items.
- LiveCodeBench: not researched, UNVERIFIED. It is competitive-programming style with short prompts, so it does not fit the long-context premise.
- Long Code Arena (https://arxiv.org/abs/2406.11612): six project-level tasks (library-based code generation, CI builds repair, project-level code completion, commit message generation, bug localization, module summarization). Which are execution-scored, sizes and setup were not checked (UNVERIFIED).

### 4i. SWE-bench Lite / Verified with small and open models

SWE-smith (https://arxiv.org/abs/2504.21798): SWE-agent-LM-32B reaches 40.2% on SWE-bench Verified. SWE-Gym (https://arxiv.org/abs/2412.21139, ICML 2025): 32.0% on Verified and 26.0% on Lite for the best open-weight agents with verifiers. These are multi-turn agents with a Docker image per instance and long trajectories, so cost is very high, and the 7B to 32B single-shot patch setting used in LongCodeBench gives 0 for a 14B model. Not a fit.

### 4j. Other execution-scored long-context sets seen only in search results

From a search summary (not opened, all UNVERIFIED beyond the numbers quoted there): ReCUBE, repository-level, up to 111K tokens, 10,785 unit tests (https://arxiv.org/html/2603.25770); FEA-Bench, BM25 prompts capped at 27K tokens, ACL 2025 (https://aclanthology.org/2025.acl-long.839.pdf); NL2Repo-Bench, 104 tasks, input documents near 19k tokens, pytest-scored (https://arxiv.org/html/2512.12730v1). Worth a look if the shortlist below does not work out.

---

## Run-cost estimate

Formula from the project spec: runs = items x 3 conditions x 3 font sizes x 5 runs x 4 models = 180 x items. If the text condition has no font size, the real count is lower; confirm the design before budgeting. Numbers below are inference calls before test execution.

| Benchmark | Items | Runs |
|---|---|---|
| EvoCodeBench | 275 | 49,500 |
| DevEval | 1,874 | 337,320 |
| LongSWE-Bench 32K bracket | 100 | 18,000 |
| CodeFlowBench-Repo | 129 | 23,220 (multi-turn adds one call per turn) |
| CodeFlowBench-Comp | 1,000 | 180,000 |
| RepoExec | 355 | 63,900 |
| BigCodeBench | 1,140 | 205,200 |

No source reports per-item test execution time. Only the EvoCodeBench environment build ("a few hours") and the LongCodeBench self-hosted inference times above are reported. Tests run on CPU and can be parallelised across 32 cores (except within one EvoCodeBench repo), so GPU inference on the single 5090 is likely the bottleneck, but this was not measured. Sets of 1,000 or more items need subsampling to about 200 to 300 items (36,000 to 54,000 runs).

## Recommendation table

Pass rate ranges are the published numbers for open models near 7B to 34B and older code models; none was measured with VLMs or images.

| Benchmark | Execution-scored | Context tokens | Items | Setup | Expected pass rate, 7B to 32B | Fit |
|---|---|---|---|---|---|---|
| DevEval | Yes (unit tests) | Up to 16k window; per-item count not reported | 1,874 (117 repos) | conda plus pip, no Docker in README | About 33 to 46% (Pass@1, 2024 code models) | High for headroom; subsample; check per-item lengths |
| CodeFlowBench-Repo | Yes (unit tests) | Few k at most; not verified in tokens (UNVERIFIED) | 129 | conda, pip, Docker | About 17 to 46% (multi vs single turn) | Medium to high; small context to save |
| EvoCodeBench | Yes (unit tests) | Up to 16k window; per-item count not reported | 275 (25 repos) | Ubuntu conda, setup_env.sh takes hours, no Docker | About 5 to 20% | Medium; floor risk |
| LongSWE-Bench (32K) | Yes (Docker) | 32K and up | 100 per bracket | Docker per instance, Pixi | 0 for Qwen2.5-14B, others untested | Low at reported settings |
| CodeFlowBench-Comp | Yes | Few k; not verified | 1,000 evaluated | conda, pip | About 1 to 28% (multi-turn near floor) | Low to medium |
| LongCodeQA | No (multiple choice) | 32K to 1M | 113 at 32K | Files only | 40 to 70% (Qwen2.5-14B) | Side task only |
| RepoExec | Yes | About 180 to 363 per prompt | 355 | Not checked | Not captured | Low (short) |
| BigCodeBench | Yes | Short (about 0.7k to 1.1k characters) | 1,140 | pip, Docker optional (not checked) | Mean about 41% Instruct; 27.7 (32B, Hard) | Short-context control |
| RepoBench-C | No (EM, ES) | 1k to 4k | Thousands | HF download | EM about 21 to 33 (2023 models) | Wrong metric |

## Gaps relevant to us

- No benchmark checked combines all three of: execution scoring, contexts of 4k to 20k tokens, and per-item context length reported. DevEval and EvoCodeBench are the closest, and both report only a 16k window, so we must measure the tokens per item ourselves with the models' tokenizers.
- Nothing here has been run with VLMs or with text-as-image context. All reported model results are text-only LLMs; the smallest are 7B to 8B (CodeFlowBench, EvoCodeBench, DevEval) or 14B (LongCodeBench).
- Floor effects: EvoCodeBench (5 to 20%) and CodeFlowBench-Comp multi-turn (1 to 12%) will leave many items at 0 for 7B models; LongSWE-Bench gave 0 for a 14B model. DevEval and CodeFlowBench-Repo have the most headroom. Whether per-item pass rates are spread away from 0 and 1 can only be known after a pilot run.
- Option, not verified: build mid-length items with the LongCodeBench "Tunable SWE-Bench" builder, or attach real repo files to CodeFlowBench-Repo items.
- Tokens saved: no benchmark reports image-token counts, so savings must be measured by us. Rendered images of 12k to 32k text tokens may need many tiles per item, which could cancel savings on some VLMs (UNVERIFIED for the chosen models).
- Contamination cannot be excluded for any of them; EvoCodeBench (refreshable) and RepoBench v1.1 (per-item dates) give a way to pick post-cutoff items.
