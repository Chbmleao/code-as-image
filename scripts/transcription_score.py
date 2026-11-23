"""Scores for the transcription replies (UFM-12): how much of the rendered code each reply copies.

Per reply, against the item's context blocks as the renderer drew them:
  names  each distinct identifier of the code (comments, strings and keywords left out) is exact,
         underscore-only (equal once underscores are removed), near (Levenshtein 1 or 2, names of
         4+ characters) or missing; R = exact / names
  text   longest common subsequence of the code tokens (comments and strings included), over the
         source tokens (text_match) and over the copy tokens (copy_match, low when a reply adds
         code or loops)
  lines  stripped non-blank lines matched by difflib; indent_match is the share of matched lines
         with the same leading spaces, leaving out lines whose leading spaces cross a row end in
         the rendering (drawn as trailing blanks of the previous row, so the page itself loses
         them; counted in indent_lost_rows)

The source text is the text-condition prompt of the main run's requests.jsonl, split with
prompts.SPLITTERS. The grid must be complete: every (model, item, image condition, run) has exactly
one generation row, or the exit code is nonzero. No reply text is written.

usage: python scripts/transcription_score.py --benchmark B --source MAIN_REQUESTS [--source ...]
           --requests TRANSCRIBE_REQUESTS --gen GEN... --runs 2 --out scores.jsonl [--workers N]
"""
import argparse
import difflib
import json
import keyword
import multiprocessing
import os
import re
import sys
from collections import Counter

from codeimg import config
from codeimg.answers import answer_key, read_jsonl
from codeimg.prompts import SPLITTERS
from codeimg.render import NEWLINE_MARK, capacity

NUMBER = (r"(?:0[xX][0-9a-fA-F_]+[lL]?|0[bB][01_]+[lL]?|0[oO][0-7_]+"
          r"|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d[\d_]*)?[jJlLfFdD]?)")
# Python allows non-ASCII letters in names and Java also allows $
IDENT = r"(?:[^\W\d]|\$)[\w$]*"
TOKEN = re.compile(rf"(?P<num>{NUMBER})|(?P<id>{IDENT})|\S")
# a backslash before a newline continues a Python short string, so the escape takes any character
PY_SKIP = (r"#[^\n]*"
           r"|(?<![\w$])[rRbBuUfF]{0,2}(?:'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\""
           r"|'(?:\\[\s\S]|[^'\\\n])*'|\"(?:\\[\s\S]|[^\"\\\n])*\")")
JAVA_SKIP = (r"//[^\n]*|/\*[\s\S]*?\*/|\"\"\"[\s\S]*?\"\"\""
             r"|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])+'")
CODE = {b: re.compile(rf"(?P<skip>{skip})|(?P<num>{NUMBER})|(?P<id>{IDENT})|\S")
        for b, skip in (("deveval", PY_SKIP), ("coderujb", JAVA_SKIP))}
JAVA_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const",
    "continue", "default", "do", "double", "else", "enum", "extends", "final", "finally", "float",
    "for", "goto", "if", "implements", "import", "instanceof", "int", "interface", "long",
    "native", "new", "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws", "transient", "try",
    "void", "volatile", "while", "true", "false", "null"}
KEYWORDS = {"deveval": set(keyword.kwlist), "coderujb": JAVA_KEYWORDS}
FENCE_OPEN = re.compile(r"```[A-Za-z0-9_+-]*[ \t]*")

COLUMNS = ["key", "model", "benchmark", "id", "condition", "run", "seed", "n_names", "n_exact",
           "n_underscore", "n_near", "R", "mean_edit_distance", "src_tokens", "copy_tokens",
           "text_match", "copy_match", "n_marks", "src_lines", "line_match", "indent_match",
           "indent_lost_rows", "finish_reason", "truncated", "prompt_tokens", "output_tokens",
           "error"]
SCORES = COLUMNS[7:22]


def tokens(text):
    return [m.group() for m in TOKEN.finditer(text)]


def identifiers(text):
    return {m.group() for m in TOKEN.finditer(text) if m.lastgroup == "id"}


def names(bench, code):
    found = {m.group() for m in CODE[bench].finditer(code) if m.lastgroup == "id"}
    return found - KEYWORDS[bench]


def blocks(bench, prompt):
    """Context blocks as the renderer drew them: tabs expanded, trailing whitespace cut
    (render.layout), empty blocks skipped (prompts.image_parts renders nothing for them)."""
    return [[line.rstrip() for line in s.expandtabs(4).split("\n")]
            for kind, s, _ in SPLITTERS[bench](prompt) if kind == "ctx" and s.strip()]


def lost_indent(block_lines, cols):
    """Per line: do its leading spaces cross a row end of the packed rendering?"""
    out, start = [], 0
    for line in block_lines:
        k = len(line) - len(line.lstrip(" "))
        first_break = (start // cols + 1) * cols
        out.append(bool(line.strip()) and start < first_break <= start + k)
        start += len(line) + len(NEWLINE_MARK)
    return out


def source(bench, prompt, sizes):
    bl = blocks(bench, prompt)
    lines = [line for b in bl for line in b]
    text = "\n".join(lines)
    lost = {px: [f for b in bl for f in lost_indent(b, capacity(px)[0])] for px in sizes}
    keep = [i for i, line in enumerate(lines) if line.strip()]
    return {"names": sorted(names(bench, text)), "tokens": tokens(text),
            "lines": [(lines[i].strip(), indent(lines[i])) for i in keep],
            "lost": {px: [f[i] for i in keep] for px, f in lost.items()}}


def indent(line):
    return len(line) - len(line.lstrip(" "))


def copy_of(reply):
    """The reply's code: from the first opening fence to the last closing fence line, so a reply
    split into two blocks, or code that itself contains ```, stays whole."""
    lines = reply.split("\n")
    start = next((i for i, line in enumerate(lines) if FENCE_OPEN.fullmatch(line)), None)
    if start is None:
        return reply
    ends = [i for i in range(start + 1, len(lines)) if lines[i].rstrip() == "```"]
    return "\n".join(lines[start + 1:ends[-1] if ends else len(lines)])


def lcs_len(a, b):
    """Length of the longest common subsequence, bit-parallel (Hyyroe 2004), so 20k-token
    sequences take well under a second."""
    if not a or not b:
        return 0
    masks = {}
    for i, x in enumerate(a):
        masks[x] = masks.get(x, 0) | (1 << i)
    full = (1 << len(a)) - 1
    v = full
    for y in b:
        u = v & masks.get(y, 0)
        v = ((v + u) | (v - u)) & full
    return len(a) - bin(v).count("1")


def levenshtein(a, b, cutoff):
    """Edit distance, or cutoff + 1 once it is known to exceed cutoff."""
    if abs(len(a) - len(b)) > cutoff:
        return cutoff + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cutoff:
            return cutoff + 1
        prev = cur
    return prev[-1]


def nearest(name, by_len):
    """Smallest edit distance from name to a copy token; tokens are tried by length difference,
    which bounds the distance from below."""
    best = None
    for diff in range(max(by_len) + len(name) + 1):
        if best is not None and diff >= best:
            break
        for n in {len(name) - diff, len(name) + diff}:
            for t in by_len.get(n, ()):
                d = levenshtein(name, t, best - 1 if best is not None else len(name) + len(t))
                if best is None or d < best:
                    best = d
    return best


def score(src, px, reply):
    copy = copy_of(reply)
    n_marks = copy.count(NEWLINE_MARK)
    copy = copy.replace(NEWLINE_MARK, "\n").expandtabs(4)
    found = identifiers(copy) | identifiers(copy.replace("\n", ""))
    no_us = {t.replace("_", "") for t in found}
    by_len = {}
    for t in found:
        by_len.setdefault(len(t), []).append(t)
    counts, dists = Counter(), []
    for name in src["names"]:
        if name in found:
            counts["exact"] += 1
            dists.append(0)
            continue
        d = nearest(name, by_len) if found else None
        dists.append(d)
        if "_" in name and name.replace("_", "") in no_us:
            counts["underscore"] += 1
        elif len(name) >= 4 and d is not None and d <= 2:
            counts["near"] += 1
    n_names = len(src["names"])
    copy_tokens = tokens(copy)
    common = lcs_len(src["tokens"], copy_tokens)
    out_lines = [(line.strip(), indent(line)) for line in copy.split("\n") if line.strip()]
    sm = difflib.SequenceMatcher(None, [s for s, _ in src["lines"]], [s for s, _ in out_lines],
                                 autojunk=False)
    pairs = [(blk.a + k, blk.b + k) for blk in sm.get_matching_blocks() for k in range(blk.size)]
    lost = src["lost"][px]
    judged = [(i, j) for i, j in pairs if not lost[i]]
    same_indent = sum(src["lines"][i][1] == out_lines[j][1] for i, j in judged)
    return {"n_names": n_names, "n_exact": counts["exact"], "n_underscore": counts["underscore"],
            "n_near": counts["near"], "R": ratio(counts["exact"], n_names),
            "mean_edit_distance": ratio(sum(dists), n_names) if found else None,
            "src_tokens": len(src["tokens"]), "copy_tokens": len(copy_tokens),
            "text_match": ratio(common, len(src["tokens"])),
            "copy_match": ratio(common, len(copy_tokens)), "n_marks": n_marks,
            "src_lines": len(src["lines"]), "line_match": ratio(len(pairs), len(src["lines"])),
            "indent_match": ratio(same_indent, len(judged)), "indent_lost_rows": sum(lost)}


def ratio(a, b):
    return a / b if b else None


SOURCES = {}


def score_row(g):
    row = {"key": "tr__" + answer_key(g["model"], g["id"], g["condition"], g["run"]),
           "model": g["model"], "benchmark": g["benchmark"], "id": g["id"],
           "condition": g["condition"], "run": g["run"], "seed": g["seed"],
           "finish_reason": g.get("finish_reason"), "truncated": g.get("finish_reason") == "length",
           "prompt_tokens": g.get("prompt_tokens"), "output_tokens": g.get("output_tokens"),
           "error": g.get("error")}
    if g.get("error") or g.get("reply") is None:
        row.update(dict.fromkeys(SCORES))
    else:
        px = int(g["condition"].removeprefix("image"))
        row.update(score(SOURCES[g["id"]], px, g["reply"]))
    return {c: row[c] for c in COLUMNS}


def grid(models, requests, runs, gen_rows):
    """(generation rows in grid order, problems)."""
    expected = {(m, q["id"], q["condition"], r) for m in models for q in requests
                for r in range(runs)}
    gen, problems = {}, []
    for g in gen_rows:
        k = (g["model"], g["id"], g["condition"], g["run"])
        if k in gen:
            problems.append(f"duplicate generation row {k}")
        gen[k] = g
    problems += [f"no generation row for {k}" for k in sorted(expected - gen.keys())]
    problems += [f"generation row outside the grid: {k}" for k in sorted(gen.keys() - expected)]
    return [gen[k] for k in sorted(gen.keys() & expected)], problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--benchmark", required=True, choices=sorted(SPLITTERS))
    ap.add_argument("--source", required=True, action="append",
                    help="main-run requests.jsonl, for the text prompts; repeat for block1 and rest")
    ap.add_argument("--requests", required=True, help="requests.jsonl from codeimg transcribe")
    ap.add_argument("--gen", nargs="+", required=True)
    ap.add_argument("--runs", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args(argv)
    cfg = config.load()
    models = [m["repo"] for m in cfg["models"].values()]
    requests = read_jsonl(args.requests)
    wanted = {q["id"] for q in requests}
    for path in args.source:
        for r in read_jsonl(path):
            if r["condition"] == "text" and r["id"] in wanted:
                SOURCES[r["id"]] = source(args.benchmark, r["parts"][0]["text"],
                                          cfg["experiment"]["sizes"])
    missing = sorted(wanted - SOURCES.keys())
    if missing:
        sys.exit(f"{len(missing)} items have no text prompt in the sources, first: {missing[0]}")
    gen_rows, problems = grid(models, requests, args.runs,
                              [r for p in args.gen for r in read_jsonl(p)])
    with open(args.out + ".tmp", "w") as f:
        if args.workers > 1:
            # fork, so the workers share SOURCES instead of each rebuilding it
            ctx = multiprocessing.get_context("fork")
            with ctx.Pool(args.workers) as pool:
                rows = pool.imap(score_row, gen_rows, chunksize=16)
                f.writelines(json.dumps(r) + "\n" for r in rows)
        else:
            f.writelines(json.dumps(score_row(g)) + "\n" for g in gen_rows)
    os.replace(args.out + ".tmp", args.out)
    print(f"{len(gen_rows)} rows scored")
    for p in problems[:50]:
        print("problem:", p, file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} problems")


if __name__ == "__main__":
    main()
