"""Similarity between each model answer and the reference function it replaces.

An answer that reproduces the reference token for token is a sign the model saw the repo in
training. Comments and whitespace are dropped before comparing, so a reformatted copy still
counts. Exact is equality after that; near-exact is a difflib ratio of 0.95 or more.

usage: python3 shared/contamination.py deveval ANSWERS_JSONL GOLD_ANSWERS_JSONL GRADE_JSONL
       python3 shared/contamination.py coderujb ANSWERS_JSONL ITEMS_JSONL GRADE_JSONL
"""
import difflib, io, json, re, statistics, sys, tokenize
from collections import defaultdict

NEAR = 0.95


def python_tokens(code):
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
            tokenize.ENDMARKER}
    try:
        toks = tokenize.generate_tokens(io.StringIO(code).readline)
        return [t.string for t in toks if t.type not in skip]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return re.sub(r"#[^\n]*", "", code).split()


JAVA_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\w+|[^\s\w]')


def java_tokens(code):
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.S)
    code = re.sub(r"//[^\n]*", " ", code)
    return JAVA_TOKEN.findall(code)


def deveval_pairs(ans_path, gold_path):
    gold = {r["id"]: r["completion"] for r in map(json.loads, open(gold_path))}
    for a in map(json.loads, open(ans_path)):
        yield a["key"], a["model"], a["id"], python_tokens(a["completion"]), python_tokens(gold[a["id"]])


def coderujb_pairs(ans_path, items_path):
    items = {r["task_id"]: r for r in map(json.loads, open(items_path))}
    for a in map(json.loads, open(ans_path)):
        it = items[a["id"]]
        src, out = it["source"].split("\n"), a["source"].split("\n")
        n_gold = it["end"] + 1 - it["start"]
        n_ans = n_gold + len(out) - len(src)
        ans = "\n".join(out[it["start"]:it["start"] + n_ans])
        ref = "\n".join(src[it["start"]:it["end"] + 1])
        yield a["task_id"], a["model"], a["id"], java_tokens(ans), java_tokens(ref)


def main():
    bench, ans_path, ref_path, grade_path = sys.argv[1:5]
    if bench == "deveval":
        passed = {r["key"]: r["result"] == "Pass" for r in map(json.loads, open(grade_path))}
        pairs = deveval_pairs(ans_path, ref_path)
    else:
        passed = {r["task_id"]: r["pass_all"] is True for r in map(json.loads, open(grade_path))}
        pairs = coderujb_pairs(ans_path, ref_path)
    rows = []
    for key, model, item, a, g in pairs:
        ratio = difflib.SequenceMatcher(None, a, g, autojunk=False).ratio()
        rows.append({"key": key, "model": model, "id": item, "passed": passed[key],
                     "exact": a == g, "ratio": round(ratio, 3)})
    for r in rows:
        print(json.dumps(r))
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    err = sys.stderr
    print(f"{'model':56} pass exact near exact|pass near|pass", file=err)
    for m, rs in sorted(by_model.items()):
        p = [r for r in rs if r["passed"]]
        print(f"{m:56} {len(p):4} {sum(r['exact'] for r in rs):5} {sum(r['ratio'] >= NEAR for r in rs):4}"
              f" {sum(r['exact'] for r in p):10} {sum(r['ratio'] >= NEAR for r in p):9}", file=err)
    ex = [r for r in rows if r["exact"]]
    print(f"answers {len(rows)}, exact {len(ex)}, near-exact {sum(r['ratio'] >= NEAR for r in rows)},"
          f" exact among passes {sum(r['passed'] for r in ex)} of {sum(r['passed'] for r in rows)}", file=err)
    for flag in (True, False):
        rs = [r["ratio"] for r in rows if r["passed"] is flag]
        if rs:
            print(f"median ratio, {'passing' if flag else 'failing'}: {statistics.median(rs):.2f}", file=err)
    items = defaultdict(int)
    for r in ex:
        items[r["id"]] += 1
    print("items with an exact copy:", dict(sorted(items.items(), key=lambda kv: -kv[1])), file=err)


if __name__ == "__main__":
    main()
