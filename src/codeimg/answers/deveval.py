"""DevEval: extract the function body from a reply.

The extraction functions are benchmarks/deveval/make_answers.py, unchanged. DevEval does not ship
the post-processing it used for chat models, so this one is ours: take the first fenced block that
defines the target function (else the first block, else the whole reply) and keep the function's
statements after its docstring, located with ast. Blocks that do not parse fall back to a line
scan: skip to the end of the signature and stop at the first line indented no deeper than the def.
A reply with no def is taken as a bare body. The body is then re-indented with pass_k.py's
adjust_indent.
"""
import ast
import json
import os
import re
import textwrap

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


FIELDS = ("project_path", "completion_path", "body_position", "tests")


def load_items(path):
    with open(path, encoding="utf-8") as f:
        return {r["namespace"]: r for r in map(json.loads, f)}


def answer(g, it, key):
    """(answer row, None) or (None, skipped row) for one generation row."""
    name = g["id"].split(".")[-1]
    meta = {"key": key, "model": g["model"], "id": g["id"], "condition": g["condition"],
            "run": g["run"]}
    body = extract(g["reply"], name) if g["reply"] else None
    if not body or not body.strip():
        return None, {**meta, "stage": "no_body" if g["reply"] else "no_reply"}
    defines = re.search(r"^\s*(async\s+)?def\s+" + re.escape(name) + r"\s*\(", g["reply"], re.MULTILINE)
    return {**meta, **{k: it[k] for k in FIELDS}, "defines_target": defines is not None,
            "completion": adjust_indent(body, it["indent"]) + "\n"}, None


def gold_answer(it, source_root):
    """The reference body, read from body_position the way grade_answers.py splices answers."""
    with open(os.path.join(source_root, it["completion_path"])) as f:
        lines = f.readlines()
    body = "".join(lines[it["body_position"][0] - 1:it["body_position"][1]])
    return {"key": f"gold__{it['namespace']}", "model": "gold", "id": it["namespace"],
            "condition": "gold", "run": 0, **{k: it[k] for k in FIELDS},
            "defines_target": True, "completion": body}
