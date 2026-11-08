"""Grade DevEval completions: splice each into body_position the way pass_k.py's
SetUp_evaluation does, run the item's tests, then put the file back.

run_item is benchmarks/deveval/gold_check.py's and the rest is benchmarks/deveval/grade_answers.py,
both unchanged: `python setup.py pytest --addopts <test>` in the repo directory, each test id once,
180 s budget for the whole item, first non-zero exit fails it. The file is always restored from the
pristine tree, never from a copy taken before the splice, so an answer left in place by a killed
job is overwritten on the next start. Answers for one repo run one at a time; repos run in
parallel. Resumable: keys already in the output are skipped.

usage: python -I slurm/launch.py codeimg.grade.deveval ANSWERS_JSONL PRISTINE_ROOT WORK_ROOT OUT_JSONL [WORKERS]
"""
import json, os, shutil, signal, subprocess, sys, time
from collections import defaultdict
from multiprocessing import Pool

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


def grade_repo(args):
    pristine, work, answers = args
    rows = []
    for a in answers:
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
        rows.append({"key": a["key"], "model": a["model"], "id": a["id"], "result": r["result"],
                     "seconds": r["seconds"], "tail": r["tail"]})
    return rows


def main():
    ans_path, pristine, work, out_path = sys.argv[1:5]
    workers = int(sys.argv[5]) if len(sys.argv) > 5 else 8
    answers = [json.loads(l) for l in open(ans_path)]
    for a in answers:
        shutil.copy2(os.path.join(pristine, a["completion_path"]),
                     os.path.join(work, a["completion_path"]))
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["key"] for l in open(out_path)}
    by_repo = defaultdict(list)
    for a in answers:
        if a["key"] not in done:
            by_repo[a["project_path"]].append(a)
    print(f"{sum(map(len, by_repo.values()))} answers in {len(by_repo)} repos, "
          f"{len(done)} already done", flush=True)
    with Pool(workers) as pool, open(out_path, "a") as f:
        for rows in pool.imap_unordered(grade_repo, [(pristine, work, v) for v in by_repo.values()]):
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.flush()
            print(rows[0]["id"], len(rows), sum(r["result"] == "Pass" for r in rows), flush=True)


if __name__ == "__main__":
    main()
