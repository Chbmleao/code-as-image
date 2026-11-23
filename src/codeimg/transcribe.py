"""Transcription requests (UFM-12): the main run's image requests with their text replaced, so the
model copies the rendered code back instead of solving the task.

Each image request keeps its pages in order, as absolute paths to the same PNG files the main run
sent, and gets the [transcription] instruction in front. Where the main prompt has text between two
groups of pages (DevEval's above and below contexts), the separator goes there; every other text
part is dropped. Text-condition rows are skipped. Every PNG is decoded and its pixels checked
against the pixels_sha256 recorded when it was rendered, so the copy is scored against the pages
the model actually saw.
"""
import argparse
import hashlib
import json
import os
import sys

from PIL import Image

from codeimg import config
from codeimg.render import NEWLINE_MARK


class PixelMismatch(ValueError):
    pass


def transcription_parts(parts, base_dir, instruction, separator):
    out = [{"type": "text", "text": instruction}]
    seen_image = gap = False
    for p in parts:
        if p["type"] != "image":
            gap = seen_image
            continue
        if gap:
            out.append({"type": "text", "text": separator})
            gap = False
        out.append({**p, "path": os.path.abspath(os.path.join(base_dir, p["path"]))})
        seen_image = True
    return out


def check_pixels(part):
    with Image.open(part["path"]) as im:
        digest = hashlib.sha256(im.convert("RGB").tobytes()).hexdigest()
    if digest != part["pixels_sha256"]:
        raise PixelMismatch(f"{part['path']}: pixels differ from the main run's render")


def transcription_rows(sources, instruction, separator, ids=None, check=True):
    rows, seen = [], set()
    for path in sources:
        base_dir = os.path.dirname(os.path.abspath(path))
        with open(path, encoding="utf-8") as f:
            for line in f:
                src = json.loads(line)
                if src["condition"] == "text" or (ids is not None and src["id"] not in ids):
                    continue
                k = (src["id"], src["condition"])
                if k in seen:
                    raise ValueError(f"{k} appears in more than one source row")
                seen.add(k)
                parts = transcription_parts(src["parts"], base_dir, instruction, separator)
                if check:
                    for p in parts:
                        if p["type"] == "image":
                            check_pixels(p)
                rows.append({"benchmark": src["benchmark"], "id": src["id"],
                             "condition": src["condition"],
                             "n_images": sum(p["type"] == "image" for p in parts), "parts": parts})
    if ids is not None:
        missing = sorted(set(ids) - {r["id"] for r in rows})
        if missing:
            raise ValueError(f"{len(missing)} listed ids have no image rows, first: {missing[0]}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codeimg transcribe", description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True, action="append",
                    help="main-run requests.jsonl of one benchmark; repeat for block1 and rest")
    ap.add_argument("--out", required=True, help="run dir; writes <out>/<benchmark>/requests.jsonl")
    ap.add_argument("--ids", help="manifest, one item id per line; default: every item")
    args = ap.parse_args(argv)
    cfg = config.load()["transcription"]
    if NEWLINE_MARK not in cfg["instruction"]:
        sys.exit("the instruction must name the newline marker the renderer draws")
    ids = None
    if args.ids:
        with open(args.ids) as f:
            ids = set(f.read().split())
    try:
        rows = transcription_rows(args.source, cfg["instruction"], cfg["separator"], ids)
    except (PixelMismatch, ValueError) as e:
        sys.exit(str(e))
    benchmarks = {r["benchmark"] for r in rows}
    if len(benchmarks) != 1:
        sys.exit(f"expected one benchmark across the sources, got {sorted(benchmarks)}")
    bench = benchmarks.pop()
    os.makedirs(os.path.join(args.out, bench), exist_ok=True)
    final = os.path.join(args.out, bench, "requests.jsonl")
    with open(final + ".tmp", "w", encoding="utf-8") as out:
        out.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    os.replace(final + ".tmp", final)
    print(f"{bench}: {len(rows)} requests, {len({r['id'] for r in rows})} items, "
          f"{sum(r['n_images'] for r in rows)} pages checked", file=sys.stderr)
