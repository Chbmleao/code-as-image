"""CoderUJB: extract the method from a reply and splice it into the source file.

The extraction functions are benchmarks/coderujb/make_answers.py, unchanged, which follows
CodeUJB's postprocess_chat_generation (code_ujb/tasks/code_ujb_complete.py): split the reply on the
signature up to "(", keep that and the text up to the brace that closes the first block. CodeUJB
puts the generation over lines start..end of the source, as here. Replies where the signature is
not found would only fail to compile, so they are skipped and counted as failures.
"""
import json


def remove_line_comment(signature):
    out, in_comment = "", False
    for i, c in enumerate(signature):
        if c == "/" and i < len(signature) - 1 and signature[i + 1] == "/":
            in_comment = True
        if in_comment:
            if c == "\n":
                in_comment = False
            continue
        out += c
    return out


def clean_signature(signature):
    signature = remove_line_comment(signature)
    if signature.startswith("@"):
        idx = 0
        for idx, c in enumerate(signature):
            if c in " \n":
                break
        return signature[:idx] + "\n", signature[idx:].strip().split("(")[0].strip()
    return "", signature.split("(")[0]


def stop_at_function(gen):
    # same scan as CodeUJB's _stop_at_function, including its quote handling
    depth, in_block, in_dq = 0, False, False
    i = 0
    for i, c in enumerate(gen):
        if c == '"':
            in_dq = not in_dq
        if c == "{" and not in_dq:
            depth += 1
            in_block = True
        if c == "}" and not in_dq:
            depth -= 1
        if depth == 0 and in_block:
            break
    return gen[:i + 1] if i else gen


def extract(reply, signature):
    pre, sub = clean_signature(signature.strip())
    if sub not in reply:
        return None
    return pre + sub + stop_at_function(reply.split(sub)[1])


def load_items(path):
    with open(path, encoding="utf-8") as f:
        return {r["task_id"]: r for r in map(json.loads, f)}


def answer(g, it, key):
    """(answer row, None) or (None, skipped row) for one generation row."""
    func = extract(g["reply"], it["function_signature"]) if g["reply"] else None
    meta = {"task_id": key, "model": g["model"], "id": g["id"], "condition": g["condition"],
            "run": g["run"]}
    if func is None:
        return None, {**meta, "project": it["project"], "bug_id": it["bug_id"],
                      "stage": "no_function" if g["reply"] else "no_reply"}
    lines = it["source"].split("\n")
    src = "\n".join(lines[:it["start"]] + func.split("\n") + lines[it["end"] + 1:])
    # extraction keys on the target's signature, so an extracted method is always the target
    return {**it, **meta, "defines_target": True, "source": src}, None


def gold_answer(it, _source_root=None):
    return {**it, "task_id": f"gold__{it['task_id']}", "model": "gold", "id": it["task_id"],
            "condition": "gold", "run": 0, "defines_target": True}
