"""Pass rates per model and per item; skipped answers count as failures.

usage: python3 deveval/report.py calib_prompts.jsonl grade_results.jsonl skipped.jsonl
"""
import json, sys
from collections import defaultdict

prompts = [json.loads(l) for l in open(sys.argv[1])]
res = {}
for path in sys.argv[2:4]:
    for r in map(json.loads, open(path)):
        res[(r["model"], r["id"])] = r.get("result", "Skipped:" + r.get("stage", ""))
models = sorted({m for m, _ in res})
print("model".ljust(56), "pass / graded")
for m in models:
    rs = [v for (mm, _), v in res.items() if mm == m]
    print(m.ljust(56), f"{sum(v == 'Pass' for v in rs)} / {len(rs)}")
by_item = defaultdict(int)
for (m, i), v in res.items():
    by_item[i] += v == "Pass"
print("\nmodels passing, per item (qwen35 tokens, id)")
for p in prompts:
    print(by_item[p["id"]], p["qwen35_tokens"], p["id"])
hist = defaultdict(int)
for p in prompts:
    hist[by_item[p["id"]]] += 1
print("\nitems by number of models passing:", dict(sorted(hist.items())))
mean = sum(v == "Pass" for v in res.values()) / max(len(res), 1)
print(f"panel mean pass rate {mean:.1%} over {len(res)} answers")
