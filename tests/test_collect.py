from codeimg.answers import answer_key
from codeimg.collect import collect

M = "org/m"
REQS = [{"id": "i", "condition": "text"}]


def gen(run, **kw):
    return {"model": M, "id": "i", "condition": "text", "run": run, "seed": run, "n_images": 0,
            "seconds": 1.0, "finish_reason": "stop", "prompt_tokens": 5, "output_tokens": 2, **kw}


def k(run):
    return answer_key(M, "i", "text", run)


def ujb_grade(run, stage, trigger, all_=False):
    return {"task_id": k(run), "stage": stage, "pass_trigger": trigger, "pass_all": all_, "seconds": 2}


def test_coderujb_passes_on_the_trigger_tests_not_the_suite():
    gens = [gen(0), gen(1), gen(2, finish_reason="length")]
    answers = [{"task_id": k(r), "defines_target": True} for r in (0, 1, 2)]
    grades = [ujb_grade(0, "pass", True, True), ujb_grade(1, "suite_fail", True),
              ujb_grade(2, "test_fail", False)]
    rows, problems = collect("coderujb", [M], REQS, 3, gens, answers, [], grades)
    assert problems == []
    got = {r["run"]: (r["passed"], r["reason"], r["suite"], r["truncated"]) for r in rows}
    assert got == {0: (True, "pass", "pass", False), 1: (True, "pass", "suite_fail", False),
                   2: (False, "test_fail", None, True)}


def test_deveval_reasons_and_skips():
    gens = [gen(0), gen(1), gen(2, reply=None, error="400 too long")]
    answers = [{"key": k(0), "defines_target": False}]
    skipped = [{"key": k(1), "stage": "no_body"}]
    grades = [{"key": k(0), "result": "TimeOut", "seconds": 180}]
    rows, problems = collect("deveval", [M], REQS, 3, gens, answers, skipped, grades)
    assert problems == []
    assert [(r["passed"], r["reason"]) for r in rows] == [
        (False, "timeout"), (False, "no_code"), (False, "request_error")]


def test_gaps_and_duplicates_are_problems():
    gens = [gen(0), gen(0)]
    _, problems = collect("deveval", [M], REQS, 2, gens, [{"key": k(0), "defines_target": True}],
                          [], [])
    assert any("duplicate generation" in p for p in problems)
    assert any(f"no generation row for {k(1)}" in p for p in problems)
    assert any("answer with no grade" in p for p in problems)
