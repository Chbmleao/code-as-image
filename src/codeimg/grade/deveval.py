"""Grade DevEval completions: splice each into body_position the way pass_k.py's
SetUp_evaluation does, run the item's tests, then put the file back.

run_item is benchmarks/deveval/gold_check.py's, unchanged: `python setup.py pytest --addopts <test>`
in the repo directory, each test id once, 180 s budget for the whole item, first non-zero exit
fails it. The splice and restore in grade_one are benchmarks/deveval/grade_answers.py's. The file
is always restored from the pristine tree, never from a copy taken before the splice, so an answer
left in place by a killed job is overwritten on the next start.

Answers for one repo run one at a time, in one thread per repo, largest repo first. Unlike
grade_answers.py, which wrote a repo's rows only when the whole repo was done (a job that hit its
time limit lost every unfinished repo, UFM-11), each row is written and flushed as soon as its
answer is graded. Resumable: keys already in the output are skipped, and a last line torn by a
killed job is cut off and its answer graded again. If one answer raises, the other threads finish
the answer they are on, start no new one, and the job exits with the error.

usage: python -I slurm/launch.py codeimg.grade.deveval ANSWERS_JSONL PRISTINE_ROOT WORK_ROOT OUT_JSONL [WORKERS]
"""
import json, os, shutil, signal, subprocess, sys, threading, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

ITEM_BUDGET = 180


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


def grade_one(pristine, work, a):
    src = os.path.join(pristine, a["completion_path"])
    dst = os.path.join(work, a["completion_path"])
    lines = open(src).readlines()
    sos, eos = a["body_position"][0] - 1, a["body_position"][1]
    with open(dst, "w") as f:
        f.write("".join(lines[:sos] + ["\n", a["completion"], "\n"] + lines[eos:]))
    try:
        r = run_item(work, {**a, "namespace": a["key"]})
    finally:
        shutil.copy2(src, dst)
    return {"key": a["key"], "model": a["model"], "id": a["id"], "result": r["result"],
            "seconds": r["seconds"], "tail": r["tail"]}


def read_done(out_path):
    """Keys already in the output. Every row is written with its newline in one write, so bytes
    after the last newline are a row torn by a killed job: they are cut off and the key regraded."""
    if not os.path.exists(out_path):
        return set()
    with open(out_path, "rb") as f:
        data = f.read()
    end = data.rfind(b"\n") + 1
    if end < len(data):
        with open(out_path, "r+b") as f:
            f.truncate(end)
        print(f"cut a torn last line ({len(data) - end} bytes)", flush=True)
    return {json.loads(l)["key"] for l in data[:end].decode("utf-8").splitlines()}


def grade(ans_path, pristine, work, out_path, workers):
    answers = [json.loads(l) for l in open(ans_path)]
    for a in answers:
        shutil.copy2(os.path.join(pristine, a["completion_path"]),
                     os.path.join(work, a["completion_path"]))
    done = read_done(out_path)
    by_repo = defaultdict(list)
    for a in answers:
        if a["key"] not in done:
            by_repo[a["project_path"]].append(a)
    print(f"{sum(map(len, by_repo.values()))} answers in {len(by_repo)} repos, "
          f"{len(done)} already done", flush=True)
    # the executor starts tasks in submission order, so the repo that takes longest starts first
    repos = sorted(by_repo.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    lock, stop = threading.Lock(), threading.Event()

    def grade_repo(answers):
        for a in answers:
            if stop.is_set():
                return
            try:
                r = grade_one(pristine, work, a)
            except BaseException:
                stop.set()
                raise
            with lock:
                f.write(json.dumps(r) + "\n")
                f.flush()
                print(r["key"][:70], r["result"], r["seconds"], flush=True)

    with open(out_path, "a") as f, ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(grade_repo, v) for _, v in repos]
    for fut in futures:
        fut.result()


def main():
    ans_path, pristine, work, out_path = sys.argv[1:5]
    workers = int(sys.argv[5]) if len(sys.argv) > 5 else 8
    grade(ans_path, pristine, work, out_path, workers)


if __name__ == "__main__":
    main()
