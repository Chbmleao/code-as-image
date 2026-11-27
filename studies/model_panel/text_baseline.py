"""Text-only floor check: the pilot's 20 HumanEval problems in the text condition, 3 runs each.

Reuses the pilot's problem sample, padded context, instruction and grader, so a model's score here
is comparable with the pilot's text row (Qwen2.5-VL-7B: 60/100).

Usage: python text_baseline.py <model> <port>   (appends rows to text_baseline_<model>.jsonl)
"""
import json
import os
import sys
import time
import urllib.request

from run_pilot import INSTRUCTION, build_context, extract_code, load_problems, passes

RUNS = 3
MAX_TOKENS = 1024
# Same sampling for every model. vLLM fills any field left out from the repo's generation_config,
# so top_k and repetition_penalty are set too, or Gemma keeps top_k 64 and Qwen2.5-VL keeps 1.05.
SAMPLING = {"temperature": 0.7, "top_p": 0.95, "top_k": -1, "min_p": 0.0, "repetition_penalty": 1.0}
HERE = os.path.dirname(os.path.abspath(__file__))


def chat(url, model, prompt, seed):
    body = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "seed": seed,
        **SAMPLING,
        "messages": [{"role": "user", "content": prompt}],
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)


def main():
    model, port = sys.argv[1], sys.argv[2]
    url = f"http://localhost:{port}/v1/chat/completions"
    data, targets = load_problems()
    passed = 0
    # One file per model: jobs on different nodes appending to one file over NFS lost a row.
    name = "text_baseline_" + model.replace("/", "__") + ".jsonl"
    with open(os.path.join(HERE, name), "a") as out:
        for t in targets:
            code = build_context(data, t)
            prompt = code + "\n\n" + INSTRUCTION.format(name=t["entry_point"], where="above")
            for run in range(RUNS):
                t0 = time.time()
                r = chat(url, model, prompt, seed=run)
                reply = r["choices"][0]["message"]["content"] or ""
                ok, err = passes(extract_code(reply), t)
                passed += ok
                row = {"model": model, "task_id": t["task_id"], "run": run, "passed": ok,
                       "prompt_tokens": r["usage"]["prompt_tokens"],
                       "output_tokens": r["usage"]["completion_tokens"],
                       "finish_reason": r["choices"][0]["finish_reason"],
                       "seconds": round(time.time() - t0, 1), "error": err, "reply": reply}
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                print(t["task_id"], run, ok, row["output_tokens"], row["seconds"], flush=True)
    print(json.dumps({"model": model, "passed": passed, "of": len(targets) * RUNS}), flush=True)


if __name__ == "__main__":
    main()
