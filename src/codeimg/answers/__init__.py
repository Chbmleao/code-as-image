"""Grader inputs from model replies. Every reply gets either an answer row or a skipped row.

usage: python -m codeimg answers --benchmark B --items ITEMS --gen GEN... --out DIR
       python -m codeimg answers --benchmark B --items ITEMS --gold --ids MANIFEST --out DIR
                                 [--source-root DEVEVAL_SOURCE]   (reference solutions)

Writes DIR/answers.jsonl and DIR/skipped.jsonl.
"""
import argparse
import importlib
import json
import os


def answer_key(model, item_id, condition, run):
    return f"{model.replace('/', '__')}__{item_id}__{condition}__r{run}"


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codeimg answers")
    ap.add_argument("--benchmark", required=True, choices=["coderujb", "deveval"])
    ap.add_argument("--items", required=True,
                    help="CoderUJB items.jsonl (make_items.py) or DevEval data.jsonl")
    ap.add_argument("--gen", nargs="*", default=[], help="generation files")
    ap.add_argument("--gold", action="store_true", help="reference solutions instead of replies")
    ap.add_argument("--ids", help="manifest, with --gold")
    ap.add_argument("--source-root", help="DevEval Source_Code, with --gold")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    bench = importlib.import_module(f"codeimg.answers.{args.benchmark}")
    items = bench.load_items(args.items)
    if args.gold:
        with open(args.ids) as f:
            ids = f.read().split()
        answers, skipped = [bench.gold_answer(items[i], args.source_root) for i in ids], []
    else:
        answers, skipped = [], []
        for path in args.gen:
            for g in read_jsonl(path):
                if g.get("error") or g.get("fail_reason"):
                    # refused by the server, or a Claude reply that fails before grading; collect
                    # records the reason
                    continue
                k = answer_key(g["model"], g["id"], g["condition"], g["run"])
                ans, skip = bench.answer(g, items[g["id"]], k)
                (answers if ans else skipped).append(ans or skip)
    os.makedirs(args.out, exist_ok=True)
    for name, rows in (("answers", answers), ("skipped", skipped)):
        with open(os.path.join(args.out, f"{name}.jsonl"), "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
    print(f"{len(answers)} to grade, {len(skipped)} skipped")
