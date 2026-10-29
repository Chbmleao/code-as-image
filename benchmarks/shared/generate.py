"""Text condition for the CodeUJB calibration: one reply per prompt from a running vLLM server.

Sampling and request fields match model_panel/text_baseline.py. Resumable: prompt ids already in
the output file are skipped.

usage: python shared/generate.py <model> <port> <prompts.jsonl> <out_dir>
       (writes <out_dir>/gen_<model with / as __>.jsonl)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Qwen3.5-9B explains its approach before the code and hit 1024 on 10 of 30 calibration items
MAX_TOKENS = 2048
SEED = 0
# vLLM fills any field left out from the repo's generation_config, so every field is sent.
SAMPLING = {"temperature": 0.7, "top_p": 0.95, "top_k": -1, "min_p": 0.0, "repetition_penalty": 1.0}


def chat(url, model, prompt):
    body = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "seed": SEED,
        **SAMPLING,
        "messages": [{"role": "user", "content": prompt}],
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)


def main():
    model, port, prompts_path, out_dir = sys.argv[1:5]
    url = f"http://localhost:{port}/v1/chat/completions"
    out_path = os.path.join(out_dir, "gen_" + model.replace("/", "__") + ".jsonl")
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["id"] for l in open(out_path)}
    prompts = [json.loads(l) for l in open(prompts_path)]
    with open(out_path, "a") as out:
        for p in prompts:
            if p["id"] in done:
                continue
            t0 = time.time()
            row = {"model": model, "id": p["id"], "project": p["project"], "bug_id": p["bug_id"]}
            try:
                r = chat(url, model, p["text"])
                row.update(reply=r["choices"][0]["message"]["content"] or "",
                           prompt_tokens=r["usage"]["prompt_tokens"],
                           output_tokens=r["usage"]["completion_tokens"],
                           finish_reason=r["choices"][0]["finish_reason"])
            except urllib.error.HTTPError as e:
                # a prompt over --max-model-len comes back as a 400; record it and go on
                row.update(reply=None, error=f"{e.code} {e.read().decode('utf-8', 'replace')[:500]}")
            row["seconds"] = round(time.time() - t0, 1)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(p["project"], p["bug_id"], row.get("prompt_tokens"), row.get("output_tokens"),
                  row.get("finish_reason", row.get("error", "")[:80]), row["seconds"], flush=True)


if __name__ == "__main__":
    main()
