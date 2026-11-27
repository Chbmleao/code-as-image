"""Pilot: Qwen2.5-VL-7B on 20 HumanEval problems, context as text or as an image.

Each problem is padded to about 12k characters with other HumanEval problems (prompt and
canonical solution) placed before it, so the target function is the last one in the file.
The instruction names the target function, so the task is completing it, not finding it.

Conditions:
  text          code in the prompt
  mono8/10/12   JetBrains Mono at that size, one source line per row, split into pages
  packed8-14    JetBrains Mono, lines flowing across 616 px rows with a newline marker

Every (problem, condition) cell is run RUNS times with a different seed at the sampling
settings from the model's generation_config.json. Results go to results.jsonl (one line per
problem x condition x run, resumable) and images to img/.

Token fields come from Ollama's response. Ollama keeps the KV cache of the previous prompt, so
runs after the first in a cell are mostly cache hits: cached_tokens says how many, and the
prefill time drops with it. instruction_tokens is measured once per cell by sending the
instruction alone, so context_tokens is what the code itself costs as text or as images.
"""
import base64, gzip, json, os, random, re, subprocess, sys, tempfile, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

MODEL = "qwen2.5vl:7b"
N_PROBLEMS = 20
RUNS = 5
TARGET_CHARS = 12000
MAX_COLS = 100
PAGE_H = 2800
PACKED_W = 616
NEWLINE_MARK = "⏎"
CONDITIONS = ["text", "mono8", "mono10", "mono12", "packed8", "packed10", "packed12", "packed14"]
INSTRUCTION = ("Complete the function `{name}`. It is the last function in the code {where} and has only "
               "a signature and a docstring. Reply with only the complete Python code of `{name}`, "
               "including any imports it needs.")
# Qwen/Qwen2.5-VL-7B-Instruct generation_config.json: temperature 1e-6, repetition_penalty 1.05.
OPTIONS = {"temperature": 1e-6, "repeat_penalty": 1.05, "num_predict": 1024, "num_ctx": 16384}
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "JetBrainsMono-Regular.ttf")


def load_problems():
    data = [json.loads(l) for l in gzip.open(os.path.join(HERE, "HumanEval.jsonl.gz"))]
    # Problems whose prompt defines helper functions are dropped: scoring runs only the reply.
    single = [p for p in data if p["prompt"].count("def ") == 1]
    rng = random.Random(0)
    targets = rng.sample(single, N_PROBLEMS)
    return data, targets


def build_context(data, target):
    rng = random.Random(target["task_id"])
    pool = [p for p in data if p["task_id"] != target["task_id"]]
    rng.shuffle(pool)
    parts, size = [], len(target["prompt"])
    for p in pool:
        block = p["prompt"] + p["canonical_solution"] + "\n\n"
        if size + len(block) > TARGET_CHARS:
            break
        parts.append(block)
        size += len(block)
    return "".join(parts) + target["prompt"]


def wrap(line, cols):
    if len(line) <= cols:
        return [line]
    indent = " " * (len(line) - len(line.lstrip()) + 4)
    rows, rest = [line[:cols]], line[cols:]
    while rest:
        rows.append(indent + rest[:cols - len(indent)])
        rest = rest[cols - len(indent):]
    return rows


def render_mono(code, px):
    font = ImageFont.truetype(FONT, px)
    cw, lh, pad = font.getlength("M"), int(round(px * 1.25)), 6
    rows = [r for line in code.expandtabs(4).split("\n") for r in wrap(line, MAX_COLS)]
    width = int(pad * 2 + cw * max(len(r) for r in rows)) + 1
    # Ollama bills every image at least ~1000 tokens, so rows are spread evenly over the pages
    # instead of leaving a short last page.
    n_pages = -(-len(rows) // ((PAGE_H - 2 * pad) // lh))
    per_page = -(-len(rows) // n_pages)
    pages = []
    for start in range(0, len(rows), per_page):
        chunk = rows[start:start + per_page]
        im = Image.new("RGB", (width, lh * len(chunk) + 2 * pad), "white")
        d = ImageDraw.Draw(im)
        for j, r in enumerate(chunk):
            d.text((pad, pad + j * lh), r, font=font, fill="black")
        pages.append(im)
    return pages


def render_packed(code, px):
    # pxpipe-style layout, as in the Sep 28 pilot: lines flow across full-width rows with a
    # visible marker for each newline, so short lines leave no blank area to pay for.
    # JetBrains Mono has no U+21B5 (pxpipe's marker), so U+23CE is used instead.
    font = ImageFont.truetype(FONT, px)
    cw, lh, pad = font.getlength("M"), int(round(px * 1.25)), 6
    flow = NEWLINE_MARK.join(line.rstrip() for line in code.expandtabs(4).split("\n"))
    cols = int((PACKED_W - 2 * pad) // cw)
    rows = [flow[i:i + cols] for i in range(0, len(flow), cols)]
    n_pages = -(-len(rows) // ((PAGE_H - 2 * pad) // lh))
    per_page = -(-len(rows) // n_pages)
    pages = []
    for start in range(0, len(rows), per_page):
        chunk = rows[start:start + per_page]
        im = Image.new("RGB", (PACKED_W, lh * len(chunk) + 2 * pad), "white")
        d = ImageDraw.Draw(im)
        for j, r in enumerate(chunk):
            d.text((pad, pad + j * lh), r, font=font, fill="black")
        pages.append(im)
    return pages


def ollama(content, images, seed, **options):
    msg = {"role": "user", "content": content}
    if images:
        msg["images"] = images
    req = {"model": MODEL, "messages": [msg], "stream": False,
           "options": {**OPTIONS, "seed": seed, **options}}
    r = urllib.request.urlopen(urllib.request.Request("http://localhost:11434/api/chat", json.dumps(req).encode(),
                                                      {"Content-Type": "application/json"}), timeout=1800)
    return json.load(r)


def extract_code(reply):
    blocks = re.findall(r"```(?:python)?\n(.*?)```", reply, re.S)
    return max(blocks, key=len) if blocks else reply


def passes(code, problem):
    prog = code + "\n\n" + problem["test"] + f"\n\ncheck({problem['entry_point']})\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(prog)
    try:
        r = subprocess.run([sys.executable, f.name], capture_output=True, text=True, timeout=20)
        return r.returncode == 0, r.stderr[-400:]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    finally:
        os.unlink(f.name)


def main():
    data, targets = load_problems()
    out_path = os.path.join(HERE, "results.jsonl")
    done = set()
    if os.path.exists(out_path):
        done = {(r["task_id"], r["condition"], r["run"]) for r in map(json.loads, open(out_path))}
    img_dir = os.path.join(HERE, "img")
    os.makedirs(img_dir, exist_ok=True)
    for k, t in enumerate(targets):
        code = build_context(data, t)
        for cond in CONDITIONS:
            pages, images = [], None
            if cond == "text":
                prompt = code + "\n\n" + INSTRUCTION.format(name=t["entry_point"], where="above")
            else:
                if cond.startswith("packed"):
                    pages = render_packed(code, int(cond[6:]))
                    where = f"shown in the images, where {NEWLINE_MARK} marks a line break"
                else:
                    pages = render_mono(code, int(cond[4:]))
                    where = "shown in the images"
                images = []
                for i, im in enumerate(pages):
                    path = os.path.join(img_dir, f"{t['task_id'].replace('/', '_')}_{cond}_{i + 1}.png")
                    im.save(path)
                    images.append(base64.b64encode(open(path, "rb").read()).decode())
                prompt = INSTRUCTION.format(name=t["entry_point"], where=where)
            if all((t["task_id"], cond, run) in done for run in range(RUNS)):
                continue
            instruction = prompt[len(code) + 2:] if cond == "text" else prompt
            instruction_tokens = ollama(instruction, None, seed=0, num_predict=1)["prompt_eval_count"]
            for run in range(RUNS):
                if (t["task_id"], cond, run) in done:
                    continue
                t0 = time.time()
                r = ollama(prompt, images, seed=run)
                reply = r["message"]["content"]
                body = extract_code(reply)
                ok, err = passes(body, t)
                cached = r.get("prompt_eval_cached_count", 0)
                row = {"task_id": t["task_id"], "entry_point": t["entry_point"], "condition": cond, "run": run,
                       "context_chars": len(code), "pages": [list(p.size) for p in pages],
                       "prompt_tokens": r["prompt_eval_count"], "cached_tokens": cached,
                       "uncached_tokens": r["prompt_eval_count"] - cached,
                       "instruction_tokens": instruction_tokens,
                       "context_tokens": r["prompt_eval_count"] - instruction_tokens,
                       "output_tokens": r["eval_count"],
                       "total_tokens": r["prompt_eval_count"] + r["eval_count"],
                       "done_reason": r.get("done_reason"),
                       "load_s": r["load_duration"] / 1e9, "prefill_s": r["prompt_eval_duration"] / 1e9,
                       "generate_s": r["eval_duration"] / 1e9, "total_s": r["total_duration"] / 1e9,
                       "seconds": round(time.time() - t0, 1), "passed": ok,
                       "defines_target": re.search(rf"def\s+{t['entry_point']}\s*\(", body) is not None,
                       "error": err, "reply": reply}
                with open(out_path, "a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(k + 1, t["task_id"], cond, run, row["prompt_tokens"], cached, row["output_tokens"], ok,
                      row["seconds"], flush=True)


if __name__ == "__main__":
    main()
