"""Requests for every condition of every item: the text prompt and one image prompt per size.

The text condition is the benchmark prompt unchanged. In the image conditions the task part stays
text, word for word, and each code context block is replaced by its rendered pages, in place:

  CoderUJB  SENTENCE, [file pages], the instruction and the target's doc comment and signature
  DevEval   SENTENCE, "Please complete ...", "The contexts above ...", [pages],
            "The contexts below ...", [pages], "The code to be completed is: ..."

An empty context block (DevEval items whose target is the last function in the file) has nothing
to render, so it stays as the empty fenced block of the text prompt.

CoderUJB prompts come from benchmarks/coderujb/make_prompts.py. DevEval's is the file DevEval
ships in Experiments/prompt/local_infilling/gpt-4-1106_prompt.jsonl.
"""
import argparse
import contextlib
import hashlib
import json
import os
import re
import sys

from codeimg import config
from codeimg.render import NEWLINE_MARK, layout, render

UJB_SPLIT = "\n```\n\nYou are a professional Java programmer"
DEV_PROMPT = re.compile(
    r"\APlease complete the (?P<name>\S+) function in the middle of a (?P<where>\w+)\.\n\n"
    r"The contexts above the function are:\n```Python\n(?P<above>.*?)\n```\n\n"
    r"The contexts below the function are:\n```Python\n(?P<below>.*?)\n```\n\n"
    r"The code to be completed is:\n```Python\n(?P<code>.*?)\n```\n\nCompleted code:\Z", re.DOTALL)


class PromptError(ValueError):
    pass


def segments_coderujb(text):
    """(kind, text, fence language) pieces; "ctx" pieces are the code that becomes pages."""
    if not text.startswith("```java\n") or text.count(UJB_SPLIT) != 1:
        raise PromptError("not a make_prompts.py CoderUJB prompt")
    i = text.index(UJB_SPLIT)
    context, task = text[len("```java\n"):i], text[i + len("\n```\n\n"):]
    if "```java\n" + context + "\n```\n\n" + task != text:
        raise PromptError("split is not lossless")
    return [("ctx", context, "java"), ("text", task, None)]


def segments_deveval(text):
    m = DEV_PROMPT.match(text)
    if not m:
        raise PromptError("prompt does not follow the local_infilling template")
    head = f"Please complete the {m['name']} function in the middle of a {m['where']}.\n\n"
    tail = "The code to be completed is:\n```Python\n" + m["code"] + "\n```\n\nCompleted code:"
    rebuilt = (head + "The contexts above the function are:\n```Python\n" + m["above"]
               + "\n```\n\nThe contexts below the function are:\n```Python\n" + m["below"]
               + "\n```\n\n" + tail)
    if rebuilt != text:
        raise PromptError("split is not lossless")
    return [("text", head + "The contexts above the function are:", None),
            ("ctx", m["above"], "Python"),
            ("text", "The contexts below the function are:", None),
            ("ctx", m["below"], "Python"),
            ("text", tail, None)]


SPLITTERS = {"coderujb": segments_coderujb, "deveval": segments_deveval}


def image_parts(segs, px, sentence, item_id, out_dir=None):
    """Message parts for one image condition; pages are written only when out_dir is given."""
    parts = [{"type": "text", "text": sentence}]

    def add_text(s):
        if parts[-1]["type"] == "text":
            parts[-1]["text"] += "\n\n" + s
        else:
            parts.append({"type": "text", "text": s})

    for k, (kind, s, lang) in enumerate(segs):
        if kind == "text":
            add_text(s)
        elif not s.strip():
            add_text(f"```{lang}\n{s}\n```")
        else:
            pages = render(s, px) if out_dir else [None] * len(layout(s, px))
            for n, im in enumerate(pages, 1):
                part = {"type": "image", "path": os.path.join("img", str(px), f"{item_id}_{k}_{n}.png")}
                if out_dir:
                    path = os.path.join(out_dir, part["path"])
                    im.save(path)
                    with open(path, "rb") as f:
                        part["sha256"] = hashlib.sha256(f.read()).hexdigest()
                    # PNG bytes depend on the zlib build (the cluster's differs from a laptop's),
                    # so the pixels get their own hash for comparing renders across machines
                    part["pixels_sha256"] = hashlib.sha256(im.tobytes()).hexdigest()
                    part["size"] = list(im.size)
                parts.append(part)
    return parts


def item_requests(bench, item, sizes, sentence, out_dir=None):
    try:
        segs = SPLITTERS[bench](item["text"])
    except PromptError as e:
        raise PromptError(f"{item['id']}: {e}") from None
    base = {"benchmark": bench, "id": item["id"],
            "context_chars": sum(len(s) for kind, s, _ in segs if kind == "ctx")}
    rows = [{**base, "condition": "text", "n_images": 0,
             "parts": [{"type": "text", "text": item["text"]}]}]
    for px in sizes:
        parts = image_parts(segs, px, sentence, item["id"], out_dir)
        rows.append({**base, "condition": f"image{px}",
                     "n_images": sum(p["type"] == "image" for p in parts), "parts": parts})
    return rows


def load_prompts(bench, path):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    if bench == "deveval":
        return {r["namespace"]: {"id": r["namespace"], "text": r["prompt"]} for r in rows}
    return {r["id"]: {"id": r["id"], "text": r["text"]} for r in rows}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codeimg prompts", description=__doc__.split("\n")[0])
    ap.add_argument("--benchmark", required=True, choices=sorted(SPLITTERS))
    ap.add_argument("--source", required=True, help="benchmark prompt file")
    ap.add_argument("--ids", required=True, help="manifest, one item id per line")
    ap.add_argument("--out", required=True, help="output dir (requests.jsonl, img/)")
    ap.add_argument("--count-only", action="store_true",
                    help="print pages per item and condition to stdout, write nothing")
    args = ap.parse_args(argv)
    cfg = config.load()["experiment"]
    if NEWLINE_MARK not in cfg["sentence"]:
        sys.exit("the sentence must name the newline marker the renderer draws")
    prompts = load_prompts(args.benchmark, args.source)
    with open(args.ids) as f:
        ids = f.read().split()
    missing = [i for i in ids if i not in prompts]
    if missing:
        sys.exit(f"{len(missing)} ids have no prompt, first: {missing[0]}")

    out_dir = None if args.count_only else args.out
    if out_dir:
        for px in cfg["sizes"]:
            os.makedirs(os.path.join(out_dir, "img", str(px)), exist_ok=True)
    final = os.path.join(args.out, "requests.jsonl")
    most = {px: 0 for px in cfg["sizes"]}
    # written to a temp file and renamed, so a killed run never leaves a partial requests.jsonl
    with open(final + ".tmp", "w", encoding="utf-8") if out_dir else contextlib.nullcontext() as out:
        for item_id in ids:
            rows = item_requests(args.benchmark, prompts[item_id], cfg["sizes"], cfg["sentence"], out_dir)
            for px, r in zip(cfg["sizes"], rows[1:]):
                most[px] = max(most[px], r["n_images"])
            if out_dir:
                for r in rows:
                    out.write(json.dumps(r, ensure_ascii=False) + "\n")
            else:
                print(json.dumps({"id": item_id, **{r["condition"]: r["n_images"] for r in rows[1:]}}))
    if out_dir:
        os.replace(final + ".tmp", final)
    print(f"{args.benchmark}: {len(ids)} items, most images per request: "
          + ", ".join(f"{px} px {n}" for px, n in most.items()), file=sys.stderr)
    if max(most.values()) > cfg["image_limit"]:
        print(f"warning: above the image limit of {cfg['image_limit']}", file=sys.stderr)
