"""DevEval local_infilling prompts as {"id", "text"} rows, for count_tokens.py and pick_calib.

The text is the prompt DevEval ships for gpt-4-1106 in
Experiments/prompt/local_infilling/gpt-4-1106_prompt.jsonl, unchanged.

usage: python3 deveval/make_prompts.py gpt-4-1106_prompt.jsonl > deveval_local_infilling.jsonl
"""
import json, sys

for line in open(sys.argv[1]):
    d = json.loads(line)
    print(json.dumps({"id": d["namespace"], "text": d["prompt"]}))
