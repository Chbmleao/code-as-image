# /// script
# requires-python = ">=3.11"
# dependencies = ["tokenizers", "huggingface_hub"]
# ///
"""Per-item text token counts with each panel tokenizer, plus packed pages at 10/12/14 px.

Input: a JSONL file, one object per line with "id" and "text" (the context the model would see,
the part that would be rendered as images). Output: JSONL to stdout, a summary to stderr.

usage: uv run --quiet shared/count_tokens.py items.jsonl > counts.jsonl
"""
import json, math, statistics, sys
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

MODELS = {
    "qwen25vl7b": "Qwen/Qwen2.5-VL-7B-Instruct",
    "qwen35": "Qwen/Qwen3.5-9B",
    "gemma4_12b": "google/gemma-4-12B-it",
    "mistral24b": "jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym",
}
# flow chars per 616x1540 page in the pilot's packed layout (cols x rows, from page_economy.py)
PAGE_CHARS = {10: 100 * 127, 12: 86 * 101, 14: 75 * 84}
MARK = "⏎"

toks = {k: Tokenizer.from_file(hf_hub_download(r, "tokenizer.json")) for k, r in MODELS.items()}

def flow_len(s):
    return len(MARK.join(l.rstrip() for l in s.expandtabs(4).split("\n")))

rows = []
for line in open(sys.argv[1], encoding="utf-8"):
    it = json.loads(line)
    text = it["text"]
    r = {"id": it["id"], "chars": len(text)}
    for k, t in toks.items():
        r[k] = len(t.encode(text, add_special_tokens=False).ids)
    fl = flow_len(text)
    for px, pc in PAGE_CHARS.items():
        r[f"pages{px}"] = math.ceil(fl / pc)
    rows.append(r)
    print(json.dumps(r))

def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]

print(f"n={len(rows)}", file=sys.stderr)
for k in list(MODELS) + ["pages12"]:
    xs = [r[k] for r in rows]
    print(f"{k}: min {min(xs)} q25 {q(xs,.25)} median {statistics.median(xs)} q75 {q(xs,.75)} "
          f"p95 {q(xs,.95)} max {max(xs)}", file=sys.stderr)
xs = [r["qwen35"] for r in rows]
for lo, hi in [(0, 2000), (2000, 4000), (4000, 8000), (8000, 12000), (12000, 16000), (16000, 10**9)]:
    print(f"qwen35 tokens [{lo},{hi}): {sum(lo <= x < hi for x in xs)}", file=sys.stderr)
