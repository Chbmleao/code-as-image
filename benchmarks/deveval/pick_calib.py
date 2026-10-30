"""Pick the DevEval calibration sample: 10 gold-passing items from each Qwen3.5 token bucket
2k-4k, 4k-8k, 8k-12k, at most one item per repo across the whole sample.

Prompts are the local_infilling ones written by deveval/make_prompts.py. "project" and "bug_id"
are filled so shared/generate.py can run them unchanged.

usage: python3 deveval/pick_calib.py prompts.jsonl counts.jsonl gold_results.jsonl data.jsonl > calib_prompts.jsonl
"""
import json, random, sys

BUCKETS = [(2000, 4000), (4000, 8000), (8000, 12000)]
PER_BUCKET = 10
SEED = 7


def main():
    prompts = {r["id"]: r for r in map(json.loads, open(sys.argv[1]))}
    counts = {r["id"]: r for r in map(json.loads, open(sys.argv[2]))}
    passed = {r["namespace"] for r in map(json.loads, open(sys.argv[3])) if r["result"] == "Pass"}
    data = {r["namespace"]: r for r in map(json.loads, open(sys.argv[4]))}
    rng = random.Random(SEED)
    used = set()
    for lo, hi in BUCKETS:
        ids = sorted(i for i in passed if lo <= counts[i]["qwen35"] < hi)
        rng.shuffle(ids)
        n = 0
        for i in ids:
            repo = data[i]["project_path"]
            if repo in used:
                continue
            used.add(repo)
            print(json.dumps({**prompts[i], "project": repo, "bug_id": i,
                              "qwen35_tokens": counts[i]["qwen35"],
                              "mistral_tokens": counts[i]["mistral24b"]}))
            n += 1
            if n == PER_BUCKET:
                break
        assert n == PER_BUCKET, (lo, hi, n)


if __name__ == "__main__":
    main()
