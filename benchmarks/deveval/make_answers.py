"""Turn model replies into DevEval completions (the function body only).

DevEval does not ship the post-processing it used for chat models, so this one is ours: take the
first fenced block that defines the target function (else the first block, else the whole
reply) and keep the function's statements after its docstring, located with ast. Blocks that do
not parse fall back to a line scan: skip to the end of the signature and stop at the first line
indented no deeper than the def. A reply with no def is taken as a bare body. The body is then
re-indented with pass_k.py's adjust_indent.

usage: python3 deveval/make_answers.py data.jsonl gen_dir answers.jsonl skipped.jsonl
"""
import ast, glob, json, os, re, sys, textwrap

FENCE = re.compile(r"```[A-Za-z0-9_+-]*[ \t]*\n(.*?)```", re.S)


def adjust_indent(code, new_indent):
    return textwrap.indent(textwrap.dedent(code), " " * new_indent)


def drop_docstring(body):
    # body_position starts after the original docstring, which stays in the file
    code = textwrap.dedent(body)
    try:
        first = ast.parse(code).body[0]
    except (SyntaxError, IndexError):
        return body
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
            and isinstance(first.value.value, str):
        return "\n".join(body.split("\n")[first.end_lineno:]).strip("\n")
    return body


def body_after_def(code, name):
    lines = code.split("\n")
    head = re.compile(r"^(\s*)(async\s+)?def\s+" + re.escape(name) + r"\s*\(")
    for i, line in enumerate(lines):
        m = head.match(line)
        if not m:
            continue
        indent, depth, j = len(m.group(1)), 0, i
        # the signature can span lines; it ends at the ":" that closes it at paren depth 0
        while j < len(lines):
            depth += lines[j].count("(") + lines[j].count("[") - lines[j].count(")") - lines[j].count("]")
            if depth <= 0 and lines[j].split("#")[0].rstrip().endswith(":"):
                break
            j += 1
        body = []
        for line in lines[j + 1:]:
            if line.strip() and len(line) - len(line.lstrip()) <= indent:
                break
            body.append(line)
        return drop_docstring("\n".join(body).strip("\n"))
    return None


def body_via_ast(code, name):
    lines = textwrap.dedent(code).split("\n")
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            stmts = node.body
            if isinstance(stmts[0], ast.Expr) and isinstance(stmts[0].value, ast.Constant) \
                    and isinstance(stmts[0].value.value, str):
                stmts = stmts[1:]
            if not stmts:
                return ""
            first = stmts[0]
            start = min([first.lineno] + [d.lineno for d in getattr(first, "decorator_list", [])])
            if start == node.lineno:
                # one-line def such as "def f(): return 1"
                return " " * 4 + lines[start - 1][first.col_offset:]
            return "\n".join(lines[start - 1:node.end_lineno]).strip("\n")
    return None


def extract(reply, name):
    blocks = FENCE.findall(reply)
    for b in blocks:
        body = body_via_ast(b, name)
        if body is not None:
            return body
    for b in blocks:
        body = body_after_def(b, name)
        if body is not None:
            return body
    body = body_after_def(reply, name)
    if body is not None:
        return body
    return (blocks[0] if blocks else reply).strip("\n")


def main():
    data_path, gen_dir, ans_path, skip_path = sys.argv[1:5]
    data = {r["namespace"]: r for r in map(json.loads, open(data_path))}
    n_ans = n_skip = 0
    with open(ans_path, "w") as ans, open(skip_path, "w") as skip:
        for path in sorted(glob.glob(os.path.join(gen_dir, "gen_*.jsonl"))):
            for g in map(json.loads, open(path)):
                it = data[g["id"]]
                key = g["model"].replace("/", "__") + "__" + g["id"]
                body = extract(g["reply"], g["id"].split(".")[-1]) if g["reply"] else None
                if not body or not body.strip():
                    skip.write(json.dumps({"key": key, "model": g["model"], "id": g["id"],
                                           "stage": "no_body" if g["reply"] else "no_reply"}) + "\n")
                    n_skip += 1
                    continue
                ans.write(json.dumps({
                    "key": key, "model": g["model"], "id": g["id"],
                    **{k: it[k] for k in ("project_path", "completion_path", "body_position", "tests")},
                    "completion": adjust_indent(body, it["indent"]) + "\n",
                }) + "\n")
                n_ans += 1
    print(f"{n_ans} to grade, {n_skip} skipped", file=sys.stderr)


if __name__ == "__main__":
    main()
