"""Turn model replies into gold_check.py items: extract the method, splice it into the source.

Extraction follows CodeUJB's postprocess_chat_generation (code_ujb/tasks/code_ujb_complete.py):
split the reply on the signature up to "(", keep that and the text up to the brace that closes
the first block. CodeUJB puts the generation over lines start..end of the source, as here.
Replies where the signature is not found would only fail to compile, so they are written to the
skipped file and counted as failures instead of being graded.

usage: python3 coderujb/make_answers.py items.jsonl gen_dir answers.jsonl skipped.jsonl
"""
import glob, json, os, sys


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


def main():
    items_path, gen_dir, ans_path, skip_path = sys.argv[1:5]
    items = {json.loads(l)["task_id"]: json.loads(l) for l in open(items_path)}
    n_ans = n_skip = 0
    with open(ans_path, "w") as ans, open(skip_path, "w") as skip:
        for path in sorted(glob.glob(os.path.join(gen_dir, "gen_*.jsonl"))):
            for l in open(path):
                g = json.loads(l)
                it = items[g["id"]]
                func = extract(g["reply"], it["function_signature"]) if g["reply"] else None
                key = g["model"].replace("/", "__") + "__" + g["id"]
                if func is None:
                    skip.write(json.dumps({"task_id": key, "model": g["model"], "id": g["id"],
                                           "project": it["project"], "bug_id": it["bug_id"],
                                           "stage": "no_function" if g["reply"] else "no_reply"}) + "\n")
                    n_skip += 1
                    continue
                lines = it["source"].split("\n")
                src = "\n".join(lines[:it["start"]] + func.split("\n") + lines[it["end"] + 1:])
                ans.write(json.dumps({**it, "task_id": key, "model": g["model"], "id": g["id"],
                                      "source": src}) + "\n")
                n_ans += 1
    print(f"{n_ans} to grade, {n_skip} skipped", file=sys.stderr)


if __name__ == "__main__":
    main()
