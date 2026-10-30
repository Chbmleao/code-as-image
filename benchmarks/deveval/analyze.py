"""Summarise gold_results.jsonl against the token counts.

usage: python deveval/analyze.py gold_results.jsonl counts_infilling.jsonl counts_completion.jsonl
"""
import json, re, sys
from collections import Counter, defaultdict

res = [json.loads(l) for l in open(sys.argv[1])]
cnt_inf = {r["id"]: r for r in map(json.loads, open(sys.argv[2]))}
cnt_com = {r["id"]: r for r in map(json.loads, open(sys.argv[3]))}
print("items", len(res), Counter(r["result"] for r in res))
secs = sorted(r["seconds"] for r in res)
print("seconds median", secs[len(secs) // 2], "p95", secs[int(.95 * len(secs))])

def cause(t):
    for pat, name in [(r"ModuleNotFoundError|ImportError", "import"),
                      (r"Couldn't find index page|No matching distribution|DistutilsError", "fetch"),
                      (r"ConnectionRefused|ConnectionError|Connection refused", "connection"),
                      (r"no tests ran|not found:|ERROR: not found", "test id not found"),
                      (r"\bFAILED\b|AssertionError", "test failed")]:
        if re.search(pat, t):
            return name
    return "other"
print("non-pass causes", Counter(cause(r["tail"]) for r in res if r["result"] != "Pass"))

by_repo = defaultdict(Counter)
for r in res:
    by_repo[r["project_path"]][r["result"] == "Pass"] += 1
full = sum(1 for c in by_repo.values() if not c[False])
none = sum(1 for c in by_repo.values() if not c[True])
print(f"repos {len(by_repo)}: all pass {full}, none pass {none}")

ok = [r["namespace"] for r in res if r["result"] == "Pass"]
for name, cnt in [("infilling", cnt_inf), ("completion", cnt_com)]:
    toks = [cnt[n]["qwen35"] for n in ok if n in cnt]
    b = Counter()
    for t in toks:
        b["0-2k" if t < 2000 else "2-4k" if t < 4000 else "4-8k" if t < 8000
          else "8-12k" if t < 12000 else ">12k"] += 1
    mid = [n for n in ok if n in cnt and 2000 <= cnt[n]["qwen35"] < 12000]
    print(f"{name}: passing gold {len(toks)}, buckets {dict(sorted(b.items()))}, "
          f"2k-12k {len(mid)} items in {len({n for n in mid})} / "
          f"{len({r['project_path'] for r in res if r['namespace'] in set(mid)})} repos")
