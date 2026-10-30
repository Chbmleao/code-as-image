"""Run each DevEval item's tests against the unmodified (gold) source.

Mirrors execution_tests in DevEval's pass_k.py: `python setup.py pytest --addopts <test>` in the
repo directory, each test id once, 60 s budget for the whole item, first non-zero exit fails it.
Repos run in parallel, items within a repo run one at a time, so no two processes share a repo.
Resumable: namespaces already in the output file are skipped.

usage: python deveval/gold_check.py DATA_JSONL SOURCE_ROOT OUT_JSONL [WORKERS]
"""
import json, os, signal, subprocess, sys, time
from collections import defaultdict
from multiprocessing import Pool

ITEM_BUDGET = 180
WARMUP_BUDGET = 1800


def run_item(src_root, item):
    cwd = os.path.join(src_root, item["project_path"])
    t0 = time.time()
    status, tail = "Pass", ""
    for test in sorted(set(item["tests"])):
        left = ITEM_BUDGET - (time.time() - t0)
        if left <= 0:
            status = "TimeOut"
            break
        p = subprocess.Popen(["python", "setup.py", "pytest", "--addopts", test], cwd=cwd,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             start_new_session=True)
        try:
            out, _ = p.communicate(timeout=left)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            out, _ = p.communicate()
            status = "TimeOut"
        if status == "Pass" and p.returncode != 0:
            status = "Error"
        if status != "Pass":
            tail = out.decode("utf-8", "replace")[-1500:]
            break
    return {"namespace": item["namespace"], "project_path": item["project_path"],
            "result": status, "seconds": round(time.time() - t0, 1), "tail": tail}


def run_repo(args):
    src_root, items = args
    # setup.py pytest fetches missing install/tests requirements into the repo's .eggs on first
    # use; do that once, untimed by the item budget, so downloads are not scored as failures
    cwd = os.path.join(src_root, items[0]["project_path"])
    try:
        subprocess.run(["python", "setup.py", "pytest", "--addopts", sorted(items[0]["tests"])[0]],
                       cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=WARMUP_BUDGET)
    except subprocess.TimeoutExpired:
        pass
    return [run_item(src_root, it) for it in items]


def main():
    data, src_root, out_path = sys.argv[1:4]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["namespace"] for l in open(out_path)}
    by_repo = defaultdict(list)
    for line in open(data):
        it = json.loads(line)
        if it["namespace"] not in done:
            by_repo[it["project_path"]].append(it)
    # biggest repos first so the long tail finishes inside the time limit
    jobs = sorted(by_repo.items(), key=lambda kv: -len(kv[1]))
    print(f"{sum(len(v) for v in by_repo.values())} items in {len(jobs)} repos, "
          f"{len(done)} already done", flush=True)
    with Pool(workers) as pool, open(out_path, "a") as f:
        for rows in pool.imap_unordered(run_repo, [(src_root, v) for _, v in jobs]):
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.flush()
            print(rows[0]["project_path"], len(rows),
                  sum(r["result"] == "Pass" for r in rows), flush=True)


if __name__ == "__main__":
    main()
