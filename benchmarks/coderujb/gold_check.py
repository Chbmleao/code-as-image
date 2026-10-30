"""Run each CoderUJB complete item's tests against the reference (gold) function.

Mirrors validate_all_patches / run_d4j_test in code_ujb/tasks/code_ujb_complete.py: check out the
fixed version, write the item's source file over the checkout, run `defects4j test -t <method>` for
each test method (120 s each, last line must be "Failing tests: 0"), and only if all pass, the
whole suite (180 s). pass_trigger is the first stage, pass_all the second. The javalang syntax
check is skipped, the reference function is assumed to parse.

Items are independent (each gets its own checkout) and run in parallel. Resumable: task ids
already in the output file are skipped.

usage: python coderujb/gold_check.py ITEMS_JSONL WORK_DIR OUT_JSONL [WORKERS] [LIMIT]
"""
import json, os, shutil, signal, subprocess, sys, time
from multiprocessing import Pool

# CoderUJB uses 120 and 180. Each budget also covers the ant compile, so it depends on the machine;
# both can be raised through the environment.
TEST_BUDGET = int(os.environ.get("UJB_TEST_BUDGET", 120))
SUITE_BUDGET = int(os.environ.get("UJB_SUITE_BUDGET", 180))
WORK = None


def run(cmd, cwd, budget):
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=budget)
        return p.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), False
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
        return None, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), True


def last_line(s):
    lines = s.rstrip("\n").split("\n")
    return lines[-1] if lines else ""


def check(item):
    t0 = time.time()
    wd = os.path.join(WORK, item["task_id"])
    shutil.rmtree(wd, ignore_errors=True)
    r = {"task_id": item["task_id"], "idx": item["idx"], "project": item["project"],
         "bug_id": item["bug_id"], "n_tests": len(item["testmethods"])}
    rc, _, err, _ = run(["defects4j", "checkout", "-p", item["project"],
                         "-v", f"{item['bug_id']}f", "-w", wd], None, 600)
    path = os.path.join(wd, item["location"])
    if rc != 0 or not os.path.exists(path):
        r.update(stage="checkout", pass_trigger=False, pass_all=False, tail=err[-1500:],
                 seconds=round(time.time() - t0, 1))
        shutil.rmtree(wd, ignore_errors=True)
        return r
    with open(path, encoding="utf-8", errors="replace") as f:
        r["file_matches"] = f.read().rstrip() == item["source"].rstrip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(item["source"])
    r["checkout_s"] = round(time.time() - t0, 1)

    stage, tail, compile_fail, timed_out = "pass", "", False, False
    r["test_s"] = []
    for t in item["testmethods"]:
        t1 = time.time()
        rc, out, err, to = run(["defects4j", "test", "-w", wd, "-t", t.strip()], None, TEST_BUDGET)
        r["test_s"].append(round(time.time() - t1, 1))
        if to:
            stage, timed_out = "test_timeout", True
        elif rc != 0:
            stage, compile_fail = "test_error", True
        elif last_line(out) != "Failing tests: 0":
            stage = "test_fail"
        if stage != "pass":
            tail = (out + "\n" + err)[-1500:]
            r["failed_test"] = t.strip()
            break
    r.update(pass_trigger=stage == "pass", compile_fail=compile_fail, timed_out=timed_out)

    r["pass_all"] = False
    if stage == "pass":
        t1 = time.time()
        rc, out, err, to = run(["defects4j", "test", "-w", wd], None, SUITE_BUDGET)
        r["suite_s"] = round(time.time() - t1, 1)
        r["suite_last"] = last_line(out)
        if to:
            stage = "suite_timeout"
        elif rc != 0 or last_line(out) != "Failing tests: 0":
            stage = "suite_fail"
        else:
            r["pass_all"] = True
        if stage != "pass":
            tail = (out + "\n" + err)[-1500:]
    r.update(stage=stage, tail=tail, seconds=round(time.time() - t0, 1))
    shutil.rmtree(wd, ignore_errors=True)
    return r


def init(work):
    global WORK
    WORK = work


def main():
    items_path, work, out_path = sys.argv[1:4]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    limit = int(sys.argv[5]) if len(sys.argv) > 5 else None
    os.makedirs(work, exist_ok=True)
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["task_id"] for l in open(out_path)}
    items = [json.loads(l) for l in open(items_path)]
    todo = [it for it in items if it["task_id"] not in done][:limit]
    print(f"{len(todo)} items to run, {len(done)} already done", flush=True)
    with Pool(workers, initializer=init, initargs=(work,)) as pool, open(out_path, "a") as f:
        for i, r in enumerate(pool.imap_unordered(check, todo), 1):
            f.write(json.dumps(r) + "\n")
            f.flush()
            print(i, r["project"], r["bug_id"], r["stage"], r["seconds"], flush=True)


if __name__ == "__main__":
    main()
