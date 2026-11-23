"""Items for the transcription startup check (UFM-12): the requests closest to the 32k limit.

Per model, the 3 items with the largest image14 + text prompt tokens in run 0 of the main run (the
image pages plus a copy about as long as the text prompt), ties broken by id; the check runs the
union over the models, so each model also sees the other models' largest items.

Writes manifests/transcribe_check/{coderujb,deveval}.txt, sorted ids, one per line.

usage: uv run python scripts/transcription_check_ids.py [--results results/full] [--out manifests]
"""
import argparse
import json
import os
from collections import defaultdict

from codeimg import config
from codeimg.sample import write

TOP = 3


def largest(rows, top=TOP):
    tokens = defaultdict(dict)
    for r in rows:
        if r["run"] == 0 and r["condition"] in ("text", "image14") and r["prompt_tokens"] is not None:
            tokens[(r["model"], r["id"])][r["condition"]] = r["prompt_tokens"]
    by_model = defaultdict(list)
    for (model, item), t in tokens.items():
        if len(t) == 2:
            by_model[model].append((-(t["text"] + t["image14"]), item))
    return sorted({item for ranked in by_model.values() for _, item in sorted(ranked)[:top]})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default=os.path.join(config.ROOT, "results", "full"))
    ap.add_argument("--out", default=os.path.join(config.ROOT, "manifests"))
    args = ap.parse_args(argv)
    for bench in ("coderujb", "deveval"):
        with open(os.path.join(args.results, f"{bench}.collected.jsonl")) as f:
            ids = largest(json.loads(line) for line in f)
        write(os.path.join(args.out, "transcribe_check", f"{bench}.txt"), ids)
        print(bench, len(ids))


if __name__ == "__main__":
    main()
