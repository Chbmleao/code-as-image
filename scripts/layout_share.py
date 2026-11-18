"""Leading indentation in the packed layout, and the pages and area the contexts would need
without it (UFM-30, steps 1 and 5; exploratory, outside methods 3.3).

Reads the main run's requests.jsonl per benchmark and splits each item's text prompt into the
context segments its image conditions rendered. First every page is rendered again and checked
against the main run (pixels_sha256 and size in requests.jsonl, page counts in manifests/pages);
any mismatch stops the script before anything is written. Then, per item, it counts the rendered
characters that are leading spaces and lays the segments out again with the leading spaces
removed. Writes items.csv, layout.json and findings.md (the tables and a limitations paragraph,
built from layout.json alone).

usage: uv run python scripts/layout_share.py --requests DIR [--out DIR]
       DIR holds coderujb/requests.jsonl and deveval/requests.jsonl of the main run
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import statistics
import sys
from collections import defaultdict

from codeimg import config
from codeimg.prompts import SPLITTERS, PromptError
from codeimg.render import NEWLINE_MARK, PAD, PAGE_W, capacity, layout, line_height, render

ROOT = config.ROOT
BENCHES = ("coderujb", "deveval")
NAMES = {"coderujb": "CoderUJB", "deveval": "DevEval"}
OUT = os.path.join(ROOT, "results", "layout")
MANIFESTS = os.path.join(ROOT, "manifests", "pages")
ITEM_FIELDS = ["benchmark", "id", "px", "chars", "leading", "pages", "pages2", "area", "area2"]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rel = _load("reliability")


class Mismatch(Exception):
    pass


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def segments(bench, text):
    """The context segments an image condition renders, in page order (prompts.image_parts)."""
    return [s for kind, s, _ in SPLITTERS[bench](text) if kind == "ctx" and s.strip()]


def page_area(pages, px):
    return sum(PAGE_W * (line_height(px) * len(rows) + 2 * PAD) for rows in pages)


def measure(seg, sizes):
    """Characters, leading spaces, and per size the pages and area with and without them."""
    if NEWLINE_MARK in seg:
        # a marker already in the source would read as a line break in the layout
        raise ValueError("the source contains the newline marker")
    lines = seg.expandtabs(4).split("\n")
    leading = sum(len(l.rstrip()) - len(l.rstrip().lstrip(" ")) for l in lines)
    bare = "\n".join(l.lstrip(" ") for l in lines)
    out = {"leading": leading, "sizes": {}}
    for px in sizes:
        pages, pages2 = layout(seg, px), layout(bare, px)
        out["chars"] = sum(len(r) for rows in pages for r in rows)
        out["chars2"] = sum(len(r) for rows in pages2 for r in rows)
        out["sizes"][px] = {"pages": len(pages), "pages2": len(pages2),
                            "area": page_area(pages, px), "area2": page_area(pages2, px)}
    return out


def measure_item(bench, item_id, segs, sizes):
    item = {"benchmark": bench, "id": item_id, "chars": 0, "leading": 0,
            "sizes": {px: {"pages": 0, "pages2": 0, "area": 0, "area2": 0} for px in sizes}}
    chars2 = 0
    for seg in segs:
        try:
            m = measure(seg, sizes)
        except ValueError as e:
            raise Mismatch(f"{bench} {item_id}: {e}") from None
        item["chars"] += m["chars"]
        item["leading"] += m["leading"]
        chars2 += m["chars2"]
        for px in sizes:
            for k, v in m["sizes"][px].items():
                item["sizes"][px][k] += v
    if item["chars"] - chars2 != item["leading"]:
        raise Mismatch(f"{bench} {item_id}: removing the indentation removed "
                       f"{item['chars'] - chars2} characters, not {item['leading']}")
    return item


def verify(bench, rows, manifest, sizes):
    """({item id: segments}, pages compared), after checking that every page renders as in the
    main run."""
    conditions = {"text"} | {f"image{px}" for px in sizes}
    by_id = defaultdict(dict)
    for r in rows:
        if r["condition"] not in conditions or r["condition"] in by_id[r["id"]]:
            raise Mismatch(f"{bench} {r['id']}: unexpected or repeated {r['condition']} row")
        by_id[r["id"]][r["condition"]] = r
    want = {m["id"]: m for m in manifest}
    if set(by_id) != set(want):
        missing, extra = set(want) - set(by_id), set(by_id) - set(want)
        raise Mismatch(f"{bench}: {len(missing)} manifest items missing, {len(extra)} extra; "
                       f"first: {min(missing or extra)}")
    segs, compared = {}, 0
    for item_id, conds in by_id.items():
        for cond in ["text"] + [f"image{px}" for px in sizes]:
            if cond not in conds:
                raise Mismatch(f"{bench} {item_id}: no {cond} row")
        try:
            segs[item_id] = segments(bench, conds["text"]["parts"][0]["text"])
        except PromptError as e:
            raise Mismatch(f"{bench} {item_id}: {e}") from None
        for px in sizes:
            parts = [p for p in conds[f"image{px}"]["parts"] if p["type"] == "image"]
            images = [im for s in segs[item_id] for im in render(s, px)]
            expected = want[item_id][f"image{px}"]
            if not len(images) == len(parts) == expected:
                raise Mismatch(f"{bench} {item_id} {px} px: {len(images)} pages, main run "
                               f"{len(parts)}, manifest {expected}")
            for n, (im, p) in enumerate(zip(images, parts), 1):
                got = hashlib.sha256(im.tobytes()).hexdigest()
                if got != p["pixels_sha256"] or list(im.size) != p["size"]:
                    raise Mismatch(f"{bench} {item_id} {px} px page {n}: {got} {list(im.size)}, "
                                   f"main run {p['pixels_sha256']} {p['size']}")
            compared += len(images)
    return segs, compared


def step(sizes):
    """Smallest relative drop, between adjacent sizes, in the area a character costs."""
    cost = {px: PAGE_W * line_height(px) / capacity(px)[0] for px in sizes}
    s = sorted(sizes)
    return min(1 - cost[a] / cost[b] for a, b in zip(s, s[1:]))


def spread(values):
    v = sorted(values)
    return {"median": rel.quantile(v, 0.5), "p25": rel.quantile(v, 0.25),
            "p75": rel.quantile(v, 0.75)}


def summarize(items, sizes):
    threshold = step(sizes)
    out = {"step": threshold, "benchmarks": {}}
    for b in sorted({i["benchmark"] for i in items}):
        its = [i for i in items if i["benchmark"] == b]
        share = [i["leading"] / i["chars"] for i in its]
        entry = {"n": len(its),
                 "share": {"mean": statistics.mean(share), "sd": statistics.stdev(share),
                           **spread(share),
                           "pooled": sum(i["leading"] for i in its) / sum(i["chars"] for i in its)},
                 "sizes": {}}
        for px in sizes:
            cells = [i["sizes"][px] for i in its]
            entry["sizes"][str(px)] = {
                "area_saved": spread([1 - c["area2"] / c["area"] for c in cells]),
                "pages": sum(c["pages"] for c in cells),
                "pages2": sum(c["pages2"] for c in cells)}
        out["benchmarks"][b] = entry
    small = all(s["area_saved"]["median"] < threshold
                for e in out["benchmarks"].values() for s in e["sizes"].values())
    out["verdict"] = "small" if small else "large"
    return out


def pct(x):
    return f"{100 * x:.1f}%"


def findings(summary):
    """findings.md, from the layout.json dict alone."""
    benches = summary["benchmarks"]
    checked = (f"Exploratory, outside methods 3.3. Generated by `scripts/layout_share.py` from "
               f"`layout.json`; no model was run. Every page of the main run was rendered again "
               f"and matched it ({summary['verified']['pages']} pages, "
               f"{summary['verified']['items']} items).")
    defs = ("Share: leading spaces over all rendered characters (the newline marker counts as "
            "one), per item; the same at every size, since lines flow across rows. Area saved: "
            "1 minus the page area without leading indentation over the page area now, per "
            "item. Quantiles are type 1.")
    lines = ["# Leading indentation in the packed layout (UFM-30)", "", checked, "", defs, ""]
    for b, e in benches.items():
        s = e["share"]
        share = (f"Share: mean {pct(s['mean'])} (SD {pct(s['sd'])}), median {pct(s['median'])} "
                 f"(IQR {pct(s['p25'])} to {pct(s['p75'])}), pooled {pct(s['pooled'])}.")
        lines += [f"## {NAMES.get(b, b)} ({e['n']} items)", "", share, "",
                  "| Size | Pages | Pages without indentation | Area saved, median (IQR) |",
                  "|---|---|---|---|"]
        for px, c in e["sizes"].items():
            a = c["area_saved"]
            lines.append(f"| {px} px | {c['pages']} | {c['pages2']} | {pct(a['median'])} "
                         f"({pct(a['p25'])} to {pct(a['p75'])}) |")
        lines.append("")
    verdict = (f"**Verdict: {summary['verdict']}.** The threshold, fixed before the numbers "
               f"(docs/decisions.md, 2026-11-17), is a median area saving below "
               f"{pct(summary['step'])} in every benchmark and size: the smallest step of the "
               f"font sweep in the area a character costs.")
    lines += [verdict, "", "## Paragraph for the limitations", ""]

    def saved(b):
        m = sorted(c["area_saved"]["median"] for c in benches[b]["sizes"].values())
        lo, hi = pct(m[0]), pct(m[-1])
        return lo if lo == hi else f"{lo} to {hi}"

    shares = " and ".join(f"{pct(benches[b]['share']['mean'])} on {NAMES.get(b, b)}"
                          for b in benches)
    savings = " and ".join(f"{saved(b)} on {NAMES.get(b, b)}" for b in benches)
    paragraph = (
        "One renderer was used. It packs the code: lines run on across each row with a visible "
        "newline marker, so the blank space at line ends is not in our images, but leading "
        "indentation is kept so that the code's structure survives. CodeShrink (Tang et al., "
        "2026) reports that rendering code without blank space raises Qwen3-VL completion at 1x "
        "from 36.2 to 54.7 edit similarity (against a baseline whose compression ratio we could "
        "not confirm), so part of an image penalty can come from the layout rather than the "
        f"modality. Leading spaces make up {shares} of our rendered characters (item means). "
        "Removing them would cut the median item's page area by "
        f"{savings}, depending on the font size. For scale, the smallest step of our font "
        f"sweep changes the area a character costs by {pct(summary['step'])}, and in that sweep "
        "larger fonts raised the pass rate of some models, so area freed from indentation and "
        "spent on a larger font could matter. We did not render the contexts without "
        "indentation or run any model on such images, so a layout effect is not ruled out and "
        "we make no claim about its size for our models.")
    lines += [paragraph, ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="layout_share.py", description=__doc__.split("\n")[0])
    ap.add_argument("--requests", required=True, help="dir with <benchmark>/requests.jsonl")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--manifests", default=MANIFESTS, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    sizes = config.load()["experiment"]["sizes"]

    inputs, items, pages = {}, [], 0
    try:
        for b in BENCHES:
            path = os.path.join(args.requests, b, "requests.jsonl")
            if not os.path.exists(path):
                raise Mismatch(f"no {path}")
            with open(path, "rb") as f:
                # home folded to ~ so the committed file does not carry a local user name
                home = os.path.expanduser("~")
                full = os.path.abspath(path)
                inputs[b] = {"path": "~" + full[len(home):] if full.startswith(home + os.sep) else full,
                             "sha256": hashlib.sha256(f.read()).hexdigest()}
            rows = read_jsonl(path)
            segs, compared = verify(b, rows, read_jsonl(os.path.join(args.manifests, f"{b}.jsonl")),
                                    sizes)
            pages += compared
            items += [measure_item(b, i, segs[i], sizes) for i in sorted(segs)]
            print(f"{b}: {len(segs)} items match the main run", file=sys.stderr)
    except Mismatch as e:
        sys.exit(f"stopped, nothing written: {e}")

    summary = {"inputs": inputs, "verified": {"items": len(items), "pages": pages},
               **summarize(items, sizes)}
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "items.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ITEM_FIELDS)
        w.writeheader()
        for i in items:
            for px in sizes:
                w.writerow({"benchmark": i["benchmark"], "id": i["id"], "px": px,
                            "chars": i["chars"], "leading": i["leading"], **i["sizes"][px]})
    with open(os.path.join(args.out, "layout.json"), "w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")
    with open(os.path.join(args.out, "findings.md"), "w") as f:
        f.write(findings(summary))
    print(f"{args.out}: verdict {summary['verdict']}", file=sys.stderr)


if __name__ == "__main__":
    main()
