import importlib.util
import os

import pytest
from conftest import ROOT

_spec = importlib.util.spec_from_file_location("audit_sample",
                                               os.path.join(ROOT, "scripts", "audit_sample.py"))
au = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(au)

CONDS = au.CONDITIONS


def answer(model, item, cond, run, passed, reason="error"):
    return {"key": f"{model}__{item}__{cond}__r{run}", "model": model, "benchmark": "deveval",
            "id": item, "condition": cond, "run": run, "passed": passed,
            "reason": "pass" if passed else reason}


def answers(model="claude-sonnet-5-5", n_items=30):
    return [answer(model, f"pkg.f{i:02d}", c, run, passed=(i % 3 == 0))
            for i in range(n_items) for c in CONDS for run in (0, 1)]


def test_hand_read_draws_n_failures_of_the_model_per_condition():
    rows = answers() + answers(model="claude-opus-5-5")
    out = au.draw_hand_read(rows, n=4, seed=1)
    assert [r["condition"] for r in out] == [c for c in CONDS for _ in range(4)]
    assert {r["model"] for r in out} == {"claude-sonnet-5-5"}
    passed = {(r["id"], r["condition"], r["run"]) for r in rows if r["passed"]}
    assert not any((r["id"], r["condition"], r["run"]) in passed for r in out)
    assert all(r["label"] == "" and r["note"] == "" for r in out)


def test_hand_read_is_fixed_by_the_seed_and_ignores_row_order():
    rows = answers()
    a = au.draw_hand_read(rows, n=4, seed=1)
    assert a == au.draw_hand_read(list(reversed(rows)), n=4, seed=1)
    assert a != au.draw_hand_read(rows, n=4, seed=2)


def test_hand_read_stops_when_a_condition_is_short():
    rows = [r for r in answers(n_items=3) if not (r["condition"] == "image12" and r["run"] == 1)]
    with pytest.raises(au.AuditError, match="image12"):
        au.draw_hand_read(rows, n=4)


def never_rows():
    return [{"benchmark": b, "item": f"{b}-{i}", "project": "p"} for b in au.BENCHES
            for i in range(6)]


def test_pool_drops_items_a_claude_model_passes_and_counts():
    claude = {b: [answer("claude-opus-5-5", f"{b}-0", "text", 0, True),
                  answer("claude-sonnet-5-5", f"{b}-1", "image10", 1, False)] for b in au.BENCHES}
    gold = {b: {f"{b}-{i}": (i != 5, 10.0) for i in range(6)} for b in au.BENCHES}
    pool, counts = au.never_passed_pool(never_rows(), claude, gold)
    assert [r["item"] for r in pool if r["benchmark"] == "deveval"] == [f"deveval-{i}"
                                                                        for i in range(1, 6)]
    assert counts["coderujb"] == {"never_passed_open": 6, "gold_passed": 5, "claude_passed": 1,
                                  "passed_by_none": 5}


def test_gold_records_by_benchmark():
    dev = au.gold_by_item("deveval", [{"namespace": "a.b", "result": "Pass", "seconds": 3.0},
                                      {"namespace": "a.c", "result": "TimeOut", "seconds": 180.0}])
    assert dev == {"a.b": (True, 3.0), "a.c": (False, 180.0)}
    ujb = au.gold_by_item("coderujb", [{"task_id": "x", "pass_trigger": True, "test_s": [4.0, 9.5]}])
    assert ujb == {"x": (True, 9.5)}


def test_never_passed_draw_carries_reasons_and_gold():
    pool = never_rows()
    collected = {b: [{"id": r["item"], "reason": reason} for r in pool if r["benchmark"] == b
                     for reason in ("error", "error", "timeout")] for b in au.BENCHES}
    gold = {b: {r["item"]: (True, 12.34) for r in pool if r["benchmark"] == b} for b in au.BENCHES}
    out = au.draw_never_passed(pool, collected, gold, n=4, seed=3)
    assert out == au.draw_never_passed(pool, collected, gold, n=4, seed=3)
    assert len(out) == 4 and len({(r["benchmark"], r["item"]) for r in out}) == 4
    r = out[0]
    assert (r["rows"], r["reasons"], r["gold_passed"], r["gold_seconds"]) == (3, "error:2;timeout:1",
                                                                             True, 12.3)
    assert r["budget_seconds"] == au.BUDGET[r["benchmark"]]


def test_never_passed_stops_on_a_short_pool_or_a_missing_record():
    pool = never_rows()[:3]
    with pytest.raises(au.AuditError, match="3 items"):
        au.draw_never_passed(pool, {}, {}, n=4)
    collected = {b: [] for b in au.BENCHES}
    with pytest.raises(au.AuditError, match="no collected rows"):
        au.draw_never_passed(pool, collected, {}, n=1)
    collected = {b: [{"id": r["item"], "reason": "error"} for r in pool] for b in au.BENCHES}
    with pytest.raises(au.AuditError, match="no gold record"):
        au.draw_never_passed(pool, collected, {b: {} for b in au.BENCHES}, n=1)


def test_pool_counts_an_item_missing_from_gold_as_not_passed():
    gold = {b: {f"{b}-{i}": (True, 1.0) for i in range(5)} for b in au.BENCHES}
    _, counts = au.never_passed_pool(never_rows(), {b: [] for b in au.BENCHES}, gold)
    assert counts["deveval"]["gold_passed"] == 5


def test_existing_output_is_never_overwritten(tmp_path):
    path = tmp_path / "hand_read.csv"
    path.write_text("benchmark,label\ndeveval,wrong_name\n")
    with pytest.raises(au.AuditError, match="exists"):
        au.write_new_csv(str(path), ["benchmark", "label"], [])
    assert "wrong_name" in path.read_text()


COUNTS = {b: {"never_passed_open": 6, "gold_passed": 6, "claude_passed": 1, "passed_by_none": 5}
          for b in au.BENCHES}


def test_summary_counts_labels_and_pools_the_false_fail_share():
    hand = [{"condition": c, "label": lab} for c in CONDS
            for lab in ("false_fail", "wrong_name", "wrong_name", "unclear")]
    check = [{"label": "no_bug"}, {"label": "no_bug"}, {"label": "test_bug"}]
    md = au.summary(hand, check, COUNTS)
    assert "| wrong_name | 2 | 2 | 2 | 2 | 8 |" in md
    assert "False fails: 4 of 16, 25.0% (exact 95% CI 7.3% to 52.4%)." in md
    assert "| no_bug | 2 |" in md and "| test_bug | 1 |" in md
    assert "| deveval | 6 | 6 | 1 | 5 |" in md


@pytest.mark.parametrize("label", ["", "misread", "no_bug"])
def test_summary_rejects_an_empty_or_unknown_hand_label(label):
    with pytest.raises(au.AuditError, match="hand_read.csv line 2"):
        au.summary([{"condition": "text", "label": label}], [], COUNTS)


def test_summary_rejects_an_unknown_bug_label():
    with pytest.raises(au.AuditError, match="never_passed_check.csv line 3"):
        au.summary([], [{"label": "no_bug"}, {"label": "false_fail"}], COUNTS)


def test_harness_flags_offset_spans_and_a_shifted_column_zero_string():
    gold = {"m.A.f": "    @classmethod\n    def f(cls):\n        return 1\n",
            "m.g": "    async def g():\n        pass\n",
            "m.h": '    s = """\nkey = 1\n"""\n    return s\n',
            "m.ok": "    x = 1\n    return x\n",
            "m.doc": "    return 2\n",
            "m.tail": '        x="lax",\n    ):\n        return x\n',
            "m.deep": "        x = 1\n        return x\n"}
    items = {k: {"indent": "4"} for k in gold}
    assert au.harness_suspects(gold, items) == {"m.A.f": "offset", "m.g": "offset",
                                                "m.h": "reindent", "m.tail": "offset"}


def test_harness_ignores_a_body_that_calls_another_def_named_alike():
    gold = {"m.f": "    def helper():\n        pass\n    return helper()\n"}
    assert au.harness_suspects(gold, {"m.f": {"indent": "4"}}) == {}


def test_summary_adds_the_harness_counts():
    harness = [{"pattern": "offset", "passed_by_none": "True"},
               {"pattern": "reindent", "passed_by_none": "False"}]
    md = au.summary([], [], COUNTS, harness)
    assert "| offset | 1 | 1 |" in md and "| reindent | 1 | 0 |" in md
