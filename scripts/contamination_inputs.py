"""Rebuild scratch/contamination/, the text answers and DevEval references that
`analysis.py contamination` and `analysis.py gaps --models claude` read.

usage: uv run python scripts/contamination_inputs.py [--out scratch/contamination]
           [--open ~/UFMG/ufm9-open] [--claude ~/UFMG/ufm9-claude/full]
           [--coderujb-items scratch/ufm7/coderujb/items.jsonl]
           [--deveval-data scratch/ufm7/deveval/data.jsonl]
           [--deveval-source scratch/ufm7/deveval/Source_Code]

The model replies are not distributed (README, Data), so this runs only where the reply folders
exist. The open-model files are the text rows of the main run's answers; the Claude files are
built from the Claude replies the way `codeimg answers` builds them, text rows only. DevEval goes
through deveval.py as it was in the main run (MAIN_RUN_DEVEVAL): the UFM-33 span and re-indent
fix came later and changes 16 Claude answers and 9 references. Every file is checked against the
sha256 it had when the committed contamination results were computed (docs/decisions.md,
2026-11-26); any mismatch exits 1.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import warnings

from codeimg.answers import answer_key, coderujb, read_jsonl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCHES = ("coderujb", "deveval")
PARTS = ("block1", "rest")
CLAUDE_MODELS = ("sonnet", "opus")
# deveval.py as the main run used it, from the last commit before 59a9c12
MAIN_RUN_DEVEVAL = "bd045fc"
EXPECTED = {
    "block1_coderujb_text.jsonl": "60ada0b9c0badade6f67ef4f8c79e382e6f4ac2f950c9f570ecad000fa97b03a",
    "block1_deveval_text.jsonl": "12174eff5e5f8baeda41c6dd84f3baa7e805f79e4f4b2158f4a8b996f5d1f293",
    "claude_coderujb_text.jsonl": "4ecd89f56340d36e753baf2232b9802092d477d60dce8a98c7f431faef18fc68",
    "claude_deveval_text.jsonl": "afbd08753731a0a1d367394f1d78b97a541220e974606f5476b3b53cc9326484",
    "coderujb_items.jsonl": "46a002dc1b4479eec0c03e8ea569cde602a50eff42ae1a36f4029a8067abee80",
    "deveval_gold.jsonl": "6fbb9a45e8ef9f6ca8ead3e78c7b8c39c2d24f088bc2e20b18e34fdd2ae712c7",
    "rest_coderujb_text.jsonl": "9fae0357adc72388eef9ffb9b73c694cf59c8ea9c2777ec0e3f16ec1d882a35f",
    "rest_deveval_text.jsonl": "7e0af8a33ca542dbfd1511c66d92c6186f87e02e23deb5ce358665e66dc45b0b",
}


def main_run_deveval():
    """src/codeimg/answers/deveval.py at MAIN_RUN_DEVEVAL, as a module."""
    src = subprocess.run(
        ["git", "-C", ROOT, "show", f"{MAIN_RUN_DEVEVAL}:src/codeimg/answers/deveval.py"],
        capture_output=True, text=True, check=True).stdout
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "deveval_main_run.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        spec = importlib.util.spec_from_file_location("deveval_main_run", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def text_lines(path):
    """The lines of an answers.jsonl whose row is a text answer, unchanged."""
    with open(path, encoding="utf-8") as f:
        return [line for line in f if json.loads(line)["condition"] == "text"]


def claude_text(bench, items, gens):
    """Text answer rows of the Claude replies, built as `codeimg answers` does."""
    rows = []
    for path in gens:
        for g in read_jsonl(path):
            if g.get("error") or g.get("fail_reason") or g["condition"] != "text":
                continue
            key = answer_key(g["model"], g["id"], g["condition"], g["run"])
            with warnings.catch_warnings():
                # reply code often holds invalid escapes, which ast.parse warns about
                warnings.simplefilter("ignore", SyntaxWarning)
                ans, _ = bench.answer(g, items[g["id"]], key)
            if ans:
                rows.append(json.dumps(ans) + "\n")
    return rows


def gold_lines(dev, items, ids, source_root):
    return [json.dumps({"id": i, "completion": dev.gold_answer(items[i], source_root)["completion"]})
            + "\n" for i in ids]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(out, expected=EXPECTED):
    """Names of the files in out whose sha256 differs from expected (missing files included)."""
    return [n for n, d in sorted(expected.items())
            if not os.path.exists(os.path.join(out, n)) or sha256(os.path.join(out, n)) != d]


def write(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="contamination_inputs.py")
    ap.add_argument("--out", default=os.path.join(ROOT, "scratch", "contamination"))
    ap.add_argument("--open", default=os.path.expanduser("~/UFMG/ufm9-open"))
    ap.add_argument("--claude", default=os.path.expanduser("~/UFMG/ufm9-claude/full"))
    ap.add_argument("--coderujb-items",
                    default=os.path.join(ROOT, "scratch", "ufm7", "coderujb", "items.jsonl"))
    ap.add_argument("--deveval-data",
                    default=os.path.join(ROOT, "scratch", "ufm7", "deveval", "data.jsonl"))
    ap.add_argument("--deveval-source",
                    default=os.path.join(ROOT, "scratch", "ufm7", "deveval", "Source_Code"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    for part in PARTS:
        for b in BENCHES:
            src = os.path.join(args.open, part, b, "answers", "answers.jsonl")
            write(os.path.join(args.out, f"{part}_{b}_text.jsonl"), text_lines(src))

    dev = main_run_deveval()
    modules = {"coderujb": (coderujb, coderujb.load_items(args.coderujb_items)),
               "deveval": (dev, dev.load_items(args.deveval_data))}
    for b, (mod, items) in modules.items():
        gens = [os.path.join(args.claude, b, "gen", f"claude_{m}.jsonl") for m in CLAUDE_MODELS]
        write(os.path.join(args.out, f"claude_{b}_text.jsonl"), claude_text(mod, items, gens))

    shutil.copyfile(args.coderujb_items, os.path.join(args.out, "coderujb_items.jsonl"))
    with open(os.path.join(ROOT, "benchmarks", "deveval", "results", "inrange_ids.txt")) as f:
        ids = f.read().split()
    write(os.path.join(args.out, "deveval_gold.jsonl"),
          gold_lines(dev, modules["deveval"][1], ids, args.deveval_source))

    bad = check(args.out)
    for n in sorted(EXPECTED):
        print(f"{'MISMATCH' if n in bad else 'ok      '}  {n}")
    if bad:
        sys.exit(f"{len(bad)} of {len(EXPECTED)} files differ from the sha256 the results used")


if __name__ == "__main__":
    main()
