# pxpipe: notes on the README and evals

Retrieved 2026-09-28. Main repo: https://github.com/teamchong/pxpipe (MIT, TypeScript, created 2026-05-20, about 7.4k stars, npm package `pxpipe-proxy`). Many forks exist (searched GitHub for "pxpipe": 32 repos, mostly forks and wrappers). I read the README on `main`, plus `docs/MODEL_RENDER_PROFILES.md`, `docs/RENDER_SIZING.md`, `docs/LEGIBILITY-AUDIT-2026-07-01.md`, `eval/qwen-profile/QUALITY_RESULTS.md`, `eval/swe-bench/README.md`, `eval/swe-bench-pro/README.md`, `eval/gist-recall/README.md`. I did not read the eval scripts or raw result JSON, so anything below about how a run was scored comes from the prose docs only. Third-party blog posts (Medium, Wavect, explainx, ai-tldr) showed up in search but I did not read them; nothing here is taken from them.

Search log: WebSearch "pxpipe render LLM context into images save tokens", WebSearch "pxpipe github vision tokens Claude Code context images", GitHub repository search "pxpipe", then raw fetches from the teamchong repo. PyPI was not searched separately (the tool is npm/TypeScript).

## What pxpipe does

A local proxy (`npx pxpipe-proxy`, default 127.0.0.1:47821) that sits between an agent client (Claude Code, also Codex, cursor-agent) and the model API. It rewrites the bulky, older parts of each request into PNG pages and forwards the request. Only the request is changed; model output is untouched. Supported wire formats: Anthropic Messages, OpenAI Responses and Chat Completions, Google generateContent. There is also an offline `export` command and a library API (`renderTextToImages`, `transformAnthropicMessages`).

Three kinds of input blocks get imaged, each behind a profitability gate:
1. Large `tool_result` bodies above about 6k characters of token-dense content.
2. Older collapsed history (recent turns always stay text).
3. The static cacheable system prompt plus tool docs.

Everything else passes through byte-identical. Alongside the images, a bounded "factsheet" (up to 96 recognized precision-critical tokens such as SHAs and numbers) is sent as text, and a banner tells the model how to read the page. Newlines are marked with a return arrow glyph in the render.

Cost claim: image tokens depend on pixel dimensions, not on text content, so dense code packs about 3.1 characters per image token versus about 1 per text token (README, "real Claude Code traffic"). Headline: 59 to 70 percent lower end-to-end bill at the authors' Fable 5 list prices.

## How it renders

Depends on the model profile (selected by exact model id). Page formula from `docs/RENDER_SIZING.md`: width = 2*PAD_X + columns*cellWidth, height = 2*PAD_Y + usedRows*cellHeight. Pages are fixed-width, variable height, never padded to a square; overflow becomes another page.

- Claude "dense" profile: Spleen 5x8 bitmap font, 312 columns, page 1568 x 728 px (about 1.14 MP, chosen to stay under Anthropic's resize limits of 1568 px long edge and about 1.15 MP). Cost is billed by 28 px patches, ceil(w/28)*ceil(h/28), so 1568x728 is 56x26 = 1456 tokens per page.
- Claude/anthropic "legible" profile in `MODEL_RENDER_PROFILES.md`: JetBrains Mono 14 px, 9x16 cell, 172 columns, max height 728 px. The README table says Fable 5 ships the dense Spleen 5x8 profile. The two documents do not obviously agree on which one is the Claude default; treat as unresolved. `claude-opus-5-5` uses Spleen 5x8 with 2 px extra row height (about 25 percent more image tokens).
- GPT 5.6 Sol and Grok (opt-in): JetBrains Mono 14 px, 9x16 cell, 84 columns, 764 px wide strip, max height 1954 px (Sol) or 512 px (Grok).
- Other OpenAI-shaped models (generic fallback): Spleen 5x8, 152 columns, 768 px wide, up to 1932 px tall.
- Example from the README: about 48k characters of system prompt and tools, about 25k tokens as text, about 2.7k image tokens as one page (1573x1248 in one search summary; not verified in the README text I read).
- Older design: 1928x1928 pages (about 92k characters, about 4.7k tokens). The 2026-07-01 audit found Anthropic silently downscaled these by 0.555x, so the "16x" compression claim was partly illusory; true legible rate is about 5x versus text.
- Font atlases are prebuilt: JetBrains Mono, Spleen 5x8, Unifont fallback. Anti-aliasing, grid, color cycle, and marker style are per-profile settings.
- Real image budget caps: 100 images per request, and an empirical 18 MiB decoded-bytes cap.

## Which models and profiles

Default scope: `PXPIPE_MODELS=claude-fable-5,claude-opus-5-5,gemini`. Opt-in: claude-opus-5, gpt-5.6-sol, GPT 5.5, Grok 4.5/4.6. Non-listed models pass through as text. An unknown model behind an OpenAI-compatible gateway (Kimi K3, Qwen, GLM) falls back to the generic GPT profile and OpenAI tile math for the cost gate, which the docs call an approximation.

**The "Qwen 3.8 profile"**: this is the model id `qwen-3.8`, specifically `@cf/qwen/qwen3.8-27b` (also written `workers-ai/@cf/qwen/qwen3.8-27b`), a 27B Qwen model served through Cloudflare Workers AI via a local gateway. It is a text-and-vision model reached through the OpenAI-compatible transport. The README says it ships the measured "JetBrains Mono 14px, 84 columns" geometry, but its broad-suite numbers were taken earlier with Spleen 5x8, 152 columns. The `MODEL_RENDER_PROFILES.md` table does not list a qwen row (unverified how the profile is wired in code; I did not read the source). Results are in `eval/qwen-profile/QUALITY_RESULTS.md`. Note it is Qwen3.8, not Qwen2.5-VL, so it is a different model from our pilot's.

## What the evals measure and the reported numbers

The README frames it as model-specific reading quality, not a cross-model comparison ("every unlisted model is not run"). Probes, with the number of items in parentheses:
- Arithmetic (N=100): novel random-number word problems read from the image. GSM8K was dropped because of contamination.
- Gist (N=98): recall of decisions, numbers, paths, names, negations from imaged session transcripts.
- State (N=18): a value mutated three times through a session.
- Never-stated (N=16): unanswerable probes; counts confabulations (lower is better).
- Dense hex (N=15): verbatim recall of 12-char hex strings.

Selected rows from the README matrix (arith / gist / state / never-stated / hex):

| model | geometry | arith | gist | state | never | hex |
|---|---|---|---|---|---|---|
| claude-fable-5 | Spleen 5x8, 312 cols | 100 | 98 | 18 | 0/16 | 13/15 |
| claude-opus-5 | same | 100 | 94 | 17 | 0/16 | 2/15 |
| claude-opus-5-5 (default) | +2px rows | 100 | 94 | 17 | 0/16 | 3/15 |
| gemini-3.6/3.7-flash | same | 100 | 98 | 18 | 0/16 | 14/15 |
| gpt-5.6-sol | Spleen 152 cols (ships 14px/84) | 98 | 83 | 17 | 4/16 | 0/15 |
| claude-opus-4-8 (historical) | same | 93 | 77 | 18 | 0/16 | 0/15 |
| grok-4.5 | 14px, 84 cols | 100 | 97 | 17 | 0/16 | 0/15 |
| kimi-k3 | Spleen 152 cols | 79 | 84 | 15 | 1/16 | 0/15 |
| qwen-3.8 | Spleen 152 cols | 98 | 72 | 11 | 0/16 | 0/15 |
| glm-5.3-flash | Spleen 152 cols | 36 | 57 | 6 | 0/16 | 0/15 |

**Qwen 3.8 detail** (`eval/qwen-profile/QUALITY_RESULTS.md`): at Spleen 5x8 (152 cols): arithmetic 98/100, gist 72/98, state 11/18, never-stated 0/16, dense hex 0/15, and 0/8 exact on a paired synthetic pilot (raw output empty on one fixture, confabulated path and port on the other). At JetBrains Mono 14 px (84 cols): dense hex 11/15 (README summary line says 11/15; its table cell says 11/15 in the row, another README cell says 8/8 exact on the pilot), pilot 8/8 exact, 2/2 gist, 2/2 guard. The 14 px run only re-ran hex and the 8-fact pilot, not arithmetic, gist or state, so the "fixed" profile has not been measured on the broad suite. The docs' own sentence: 5x8 glyphs are too dense for Qwen 3.8's vision encoder. GLM shows the same pattern (5x8 illegible, 14 px pilot 10/15 hex).

Cost figures:
- Per-request token cut on real traffic: about 59 to 70 percent end to end (13,709-request snapshot: 59 percent, $100 to about $41; a later 8,904-request trace: about 70 percent). Measured by a free `count_tokens` call on the original body versus the billed usage on the same request, logged to `~/.pxpipe/events.jsonl`.
- Offline export of a 454,045-char dense corpus: Claude Spleen 5x8 gives 17 pages, 23,856 image tokens versus 122,715 text estimate (80.6 percent saving); Sol 14 px gives 45 pages, 65,424 tokens (46.7 percent). Text estimate uses 3.7 chars per token.
- Density: about 18.9 chars per vision token for Fable 5, about 4.7x more context than text at 4 chars/token.
- The docs warn that native 14 px profiles are a legibility profile, not a cost win on warm-cache traffic; one measured turn cost 43,444 tokens versus 8,964 as text.

Task-level evals (Fable 5 only, Claude Code as the agent):
- SWE-bench Lite: 10 paired instances, resolved 10/10 ON vs 10/10 OFF, official swebench 4.1.0 Docker harness, request size -65 percent.
- SWE-bench Pro: 19 pairs (10 attempted, 9 completed, then +10 with 9 completed and one dropped again; the docs' "19 pairs" should be checked), ON 14/19 vs OFF 15/19, verdicts agree 18/19, request size -60 percent. The one split (navidrome, ON failed) was re-run 3 times on the ON arm and resolved 3/3, so the authors attribute it to agentic variance.
- Gist-recall A/B on Fable 5 (text arm versus image arm, same questions): 98/98 vs 98/98 and 0/16 confabulations both arms; authors call this a ceiling effect.
- Gemini production-history retrieval: row localization text 17/30 vs image 18/30; exact row 3/30 vs 3/30.

Legibility audit (2026-07-01, Spleen 5x8, blind read of 24 tokens): 15/24 = 63 percent exact (camelCase 6/8, numbers 6/8, hex 3/8). Misses match a glyph-confusability matrix: 45 of 94 ASCII glyphs have a neighbor within Hamming distance 3 of 40 pixels (H/K, 0/O, 3/8, 5/S, 6/8...). Misses are case flips and single-glyph substitutions, which fits our pilot's "misread identifiers" finding. A later K-glyph repaint cut Fable's H/K error from 47.2 to 18.7 percent but did not improve exact control IDs.

Other reported points: on Opus 5, dense render 3/26 exact on a 26-value battery (10/26 silently wrong), versus 100/100 exact at JetBrains Mono 14 px 172 cols, at cost of 1.47x cheaper than text instead of 5.28x. That is the clearest published size-versus-accuracy tradeoff in the repo.

## How the evals were run

- Two arms through separate proxies, ON (compressing) and OFF (passthrough), Claude Code CLI with claude-fable-5, official SWE harness Docker images, patches graded by the harness's own tests (execution-based).
- Gist, arithmetic and hex probes: synthetic transcripts with seeded random values, deterministic string matching, no LLM grader, answers or the exact word UNKNOWN. The gist evals were pre-registered (per the README of that folder). Rendered PNGs supplied through the Read tool.
- Sample sizes are as listed above: N=15 to 100 per probe, 10 and 19 tasks for SWE-bench, one seed, mostly one day per experiment, one run per item.
- Runs on the Qwen/GLM/Kimi profiles use Cloudflare Workers AI through a local gateway; different models used different transports and profile generations, which the README says makes the rows not comparable.

## Weaknesses from a measurement point of view

- No confidence intervals or significance tests anywhere I read. SWE-bench Pro 14/19 vs 15/19 is reported as "variance, not compression" with no test; a paired 19-item comparison cannot detect a moderate drop. For scale, an exact binomial 95 percent interval on 14/19 is roughly 49 to 91 percent (my calculation, not in the repo).
- Ceiling effects: SWE-bench Lite 10/10 and gist 98/98 do not discriminate. The authors say so themselves for Lite and gist.
- Small N and single runs per item; the navidrome case shows the authors already know one agentic run is noisy, but they did not repeat every item.
- The task evals are Fable-5-specific. Smaller open models (Qwen, GLM, Kimi) got only probe suites, never a code-task ON/OFF run. "Every unlisted model is not run."
- Probes are synthetic (random hex, paths, novel arithmetic) and not code-problem solving from imaged content.
- Compared arms are not always the same setup (different transports, geometry generations, historical vs shipped profiles). Qwen's 14 px numbers cover only hex and an 8-fact pilot.
- Savings figure is a ratio of the tool's own token accounting, on the author's own traffic, priced at list rates; the "16x" claim was later found inflated by API downscaling, so the compression numbers have needed revision.
- Confounds: total tokens per arm differ because runs take different numbers of turns; the authors correctly use per-request counterfactual counts instead.
- Data leakage/contamination is acknowledged for GSM8K and dropped, which is good practice.
- The factsheet passes exact identifiers as text next to the image, so the "image-only" accuracy is not what the production system measures; most reported numbers mix both, except where stated as "pure image".
- No per-item error analysis in the READMEs beyond the glyph-confusability audit, which is per-glyph on 24 tokens.
- Repo authors state most commits and docs were written by AI agents running behind pxpipe; the numbers are self-reported and I did not reproduce any of them.

## How it relates to our project

- Same mechanism, different setup. pxpipe compresses request context to images for frontier Claude/Gemini/Grok models; we test whether a small open VLM (Qwen2.5-VL-7B via Ollama) keeps coding accuracy when the problem context is an image. The repo itself shows model dependence: the same tiny 5x8 font reads at 100 percent arithmetic for Fable 5 and gives 0/15 exact hex for most other models, including Qwen 3.8 (which reads 5x8 badly and 14 px well).
- Our pilot (text 13/20, tiny-font image 5/20, failures mostly misread identifiers) is consistent with pxpipe's own audit: identifiers and hex are the failure mode, misses are confident substitutions, and 5x8 is below the legibility floor for weaker vision encoders. This supports a font-size sweep as our main experimental factor, with 14 px monospace (pxpipe's shipped legible setting for non-Claude models) as the obvious comparison arm.
- pxpipe's token accounting gives us a template: per-request counterfactual (count what text would cost versus what was sent), chars per image token, page counts and image tokens per page. With Ollama we can read image token counts from the API and compute the same ratios.
- pxpipe's Qwen 3.8 result (0/15 to 11/15 hex by changing only geometry) is a direct precedent for our resolution-versus-accuracy curve.
- Their offline export (`pxpipe export`) can produce PNG pages from files and diffs, so it could be used to generate our image conditions, with its Spleen and JetBrains Mono atlas (a reproducible baseline for our font settings) instead of a custom renderer. Not tested by me.

## Gaps relevant to us

- No published code-generation accuracy for any open-weight or small VLM, with images versus text. No HumanEval/MBPP-style or execution-scored ON/OFF run for Qwen, and nothing for Qwen2.5-VL.
- Only 10 and 19 tasks for the execution-based evals, ceiling on Lite, no repeats per item, no intervals. We can add paired analysis (McNemar or exact sign test) on a larger set, multiple seeds, and Wilson/bootstrap intervals.
- Nothing on the accuracy-versus-compression frontier as a curve (font size, columns, page count versus pass rate and tokens); the repo only has point profiles and a single Opus 5 dense-versus-legible comparison.
- No per-item failure taxonomy on code tasks (which identifiers, which tokens, which lines were misread). We can classify errors from image-arm outputs against gold identifiers, and relate them to glyph confusability (0/O, l/1/I, 6/8, H/K).
- Their factsheet (identifiers as text next to the image) is a mitigation whose effect is not isolated in the published results. An image-only versus image-plus-factsheet ablation on code problems would be new.
- Execution-based scoring of the code the model writes given imaged context (unit tests) is absent outside SWE-bench with Fable 5.
- Sample-size caveat for us too: 20 items in our pilot gives very wide intervals (13/20 vs 5/20 is a large gap, but per-condition estimates are imprecise); a larger item count is needed for the finer factors.
- Unverified by me: whether the Qwen profile code path is really 14 px/84 columns in the shipped code, the exact page dimensions for the 14 px profiles, and whether the README's 11/15 versus 8/8 Qwen figures refer to the same run.
