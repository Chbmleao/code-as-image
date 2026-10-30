# /// script
# requires-python = ">=3.11"
# dependencies = ["pyarrow"]
# ///
"""Full-file prompts for the CodeUJB complete items that passed the gold check.

CodeUJB's prompt_chat_with_comment is: the abstract class skeleton in a java
block, the instruction, then a java block holding the target's doc comment,
which the model continues. Here the skeleton is replaced by the whole source
file with the target method (lines start..end) and its doc comment cut out.
The instruction and the trailing block are kept as CodeUJB ships them, so
grading still splices the generated method into lines start..end. The target's
signature is appended to the trailing block: CodeUJB's skeleton carries it, and
without it the model guesses the modifiers and CodeUJB's extraction, which
matches the signature verbatim, no longer finds the method.

usage: uv run --quiet coderujb/make_prompts.py complete.parquet gold_pass_ids.txt > prompts.jsonl
"""
import json, re, sys
import pyarrow.parquet as pq

SPLIT = "\n```\n\nYou are a professional Java programmer"


def cut_start(lines, start):
    """First line of the javadoc and annotations directly above the method."""
    i = start
    while i > 0 and (lines[i - 1].strip() == "" or lines[i - 1].strip().startswith("@")):
        i -= 1
    if i > 0 and lines[i - 1].strip().endswith("*/"):
        j = i - 1
        while j >= 0 and not lines[j].lstrip().startswith("/*"):
            j -= 1
        if j >= 0:
            return j
    return start


def main():
    keep = set(open(sys.argv[2]).read().split())
    for r in pq.read_table(sys.argv[1]).to_pylist():
        if r["task_id"] not in keep:
            continue
        p = r["prompt_chat_with_comment"]
        assert p.startswith("```java\n") and p.count(SPLIT) == 1, r["task_id"]
        tail = p[p.index(SPLIT):]
        doc = tail.rsplit("```java\n", 1)[1]
        indent = doc[:len(doc) - len(doc.lstrip(" "))]
        lines = r["source"].split("\n")
        s, e = r["start"], r["end"]
        c = cut_start(lines, s)
        context = "\n".join(lines[:c] + lines[e + 1:]).rstrip()
        body = "\n".join(lines[s:e + 1])
        # a method of a few lines can legitimately repeat elsewhere, so only flag long ones
        leaked = len(body) > 200 and re.sub(r"\s+", "", body) in re.sub(r"\s+", "", context)
        print(json.dumps({
            "id": r["task_id"], "project": r["project"], "bug_id": r["bug_id"],
            "function_name": r["function_name"], "cut_lines": e + 1 - c, "leaked": leaked,
            "text": "```java\n" + context + tail + indent + r["function_signature"].strip(),
        }))


if __name__ == "__main__":
    main()
