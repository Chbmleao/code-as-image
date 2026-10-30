"""Pick the calibration sample: 10 items from each Qwen3.5 token bucket 2k-4k, 4k-8k, 8k-12k.

usage: python3 coderujb/pick_calib.py prompts.jsonl prompt_counts.jsonl > calib_prompts.jsonl
"""
import json, random, sys

BUCKETS = [(2000, 4000), (4000, 8000), (8000, 12000)]
PER_BUCKET = 10
SEED = 7


def main():
    prompts = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[1])}
    counts = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[2])}
    rng = random.Random(SEED)
    for lo, hi in BUCKETS:
        ids = sorted(i for i, c in counts.items() if lo <= c["qwen35"] < hi)
        for i in rng.sample(ids, PER_BUCKET):
            print(json.dumps({**prompts[i], "qwen35_tokens": counts[i]["qwen35"]}))


if __name__ == "__main__":
    main()
