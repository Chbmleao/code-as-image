import json
from datetime import datetime, timezone

import anthropic
import httpx2
import pytest
from anthropic.types import MessageTokensCount
from anthropic.types.messages import MessageBatch, MessageBatchIndividualResponse
from conftest import read_jsonl

from codeimg import answers, claude, config
from codeimg.collect import collect

CFG = config.load()
OPUS = config.claude_models(CFG)["opus"]
SONNET = config.claude_models(CFG)["sonnet"]


def message(text="def f():\n    return 1", stop="end_turn", out=40, thinking=None, cache=0,
            stop_details=None):
    usage = {"input_tokens": 1000, "output_tokens": out, "cache_creation_input_tokens": cache,
             "cache_read_input_tokens": 0}
    if thinking is not None:
        usage["output_tokens_details"] = {"thinking_tokens": thinking}
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "thinking", "thinking": "SENTINEL-THOUGHT", "signature": "sig"},
                        {"type": "text", "text": text}],
            "stop_reason": stop, "stop_sequence": None, "stop_details": stop_details,
            "usage": usage}


def ok(**kw):
    return {"type": "succeeded", "message": message(**kw)}


def errored(etype, msg="boom", details=None):
    err = {"type": etype, "message": msg}
    if details:
        err["details"] = details
    return {"type": "errored", "error": {"type": "error", "error": err}}


class FakeBatches:
    def __init__(self, answer):
        self.answer, self.created, self.n = answer, [], 0
        # what the next create call does instead of answering: an exception to raise, or
        # "lost" to make the batch on the server and then time out
        self.fail = None

    def batch(self, bid, status):
        return MessageBatch.model_validate({
            "id": bid, "type": "message_batch", "processing_status": status,
            "request_counts": {"processing": 0, "succeeded": 0, "errored": 0, "canceled": 0,
                               "expired": 0},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": "2026-11-15T00:00:00Z",
            "ended_at": "2026-11-14T01:00:00Z" if status == "ended" else None,
            "archived_at": None, "cancel_initiated_at": None, "results_url": None})

    def create(self, requests):
        fail, self.fail = self.fail, None
        if isinstance(fail, Exception):
            raise fail
        self.n += 1
        self.created.append(list(requests))
        if fail == "lost":
            raise anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.test"))
        return self.batch(f"msgbatch_{self.n}", "in_progress")

    def list(self, limit):
        return type("Page", (), {"data": [self.batch(f"msgbatch_{i + 1}", "in_progress")
                                          for i in range(self.n)]})

    def retrieve(self, bid):
        return self.batch(bid, "ended")

    def results(self, bid):
        reqs = self.created[int(bid.split("_")[1]) - 1]
        return [MessageBatchIndividualResponse.model_validate(
            {"custom_id": r["custom_id"], "result": self.answer(r)}) for r in reqs]


class FakeMessages:
    def __init__(self, answer):
        self.batches, self.counted = FakeBatches(answer), []

    def count_tokens(self, **kw):
        self.counted.append(kw)
        n_images = sum(c["type"] == "image" for c in kw["messages"][0]["content"])
        return MessageTokensCount(input_tokens=500 + 1210 * n_images)


class FakeClient:
    def __init__(self, answer=lambda r: ok()):
        self.default_headers = {"anthropic-version": "2026-10-21"}
        self.messages = FakeMessages(answer)
        self.options = []

    def with_options(self, **kw):
        self.options.append(kw)
        return self


def status_error(status, etype, msg, details=None):
    body = {"type": "error", "error": {"type": etype, "message": msg}}
    if details:
        body["error"]["details"] = details
    response = httpx2.Response(status, json=body,
                               request=httpx2.Request("POST", "https://api.test"))
    return anthropic.APIStatusError(msg, response=response, body=body)


def req(item_id, condition="text", n_images=0):
    parts = [{"type": "text", "text": f"task {item_id}"}]
    parts += [{"type": "image", "path": f"img/{item_id}_{i}.png"} for i in range(n_images)]
    return {"benchmark": "deveval", "id": item_id, "condition": condition, "n_images": n_images,
            "parts": parts}


@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "deveval"
    (d / "img").mkdir(parents=True)
    (d / "img" / "b_0.png").write_bytes(b"one")
    (d / "img" / "b_1.png").write_bytes(b"two")
    (d / "requests.jsonl").write_text("".join(
        json.dumps(q) + "\n" for q in (req("a"), req("b", "image12", 2))))
    return str(tmp_path)


def make(run_dir, short="opus", **cfg_claude):
    cfg = json.loads(json.dumps(CFG))
    cfg["claude"].update(cfg_claude)
    return claude.Run(cfg, short, run_dir)


def go(client, run, balance=100.0, cost_rows=(), run_index=0):
    ceiling = not cost_rows and not run.rows()
    return claude.submit(client, run, run_index, balance, list(cost_rows), yes=True,
                         ceiling=ceiling)


def text_of(r):
    """The item id a fake batch request was built from."""
    return next(c["text"] for c in r["params"]["messages"][0]["content"]
                if c["type"] == "text").split()[-1]


def test_requests_carry_only_the_preregistered_settings(run_dir):
    for short, m in (("sonnet", SONNET), ("opus", OPUS)):
        run = make(run_dir, short)
        q = run.requests["deveval"][1]
        p = claude.params(run.m, q, run.base_dir("deveval"))
        assert set(p) == {"model", "max_tokens", "thinking", "output_config", "messages"}
        assert (p["model"], p["max_tokens"], p["thinking"]) == (m["model"], m["max_tokens"],
                                                                 m["thinking"])
        assert p["output_config"] == {"effort": "low"}
    assert SONNET["thinking"] == {"type": "between_tools"} and SONNET["max_tokens"] == 2048
    assert OPUS["thinking"] == {"type": "adaptive"} and OPUS["max_tokens"] == 16000
    content = p["messages"][0]["content"]
    assert [c["type"] for c in content] == ["text", "image", "image"]
    assert content[1]["source"] == {"type": "base64", "media_type": "image/png", "data": "b25l"}
    assert content[2]["source"]["data"] == "dHdv"


def test_custom_ids_are_valid_and_differ_by_attempt():
    k = ("deveval", "pkg.mod/with spaces.f", "image14", 1)
    ids = {claude.custom_id(k, a) for a in range(4)}
    assert len(ids) == 4
    assert all(len(c) <= 64 and c.replace("_", "").replace("-", "").isalnum() for c in ids)


def test_fail_reasons_in_the_preregistered_order():
    assert claude.fail_reason("refusal", 5000, 0, 2048) == "refusal"
    assert claude.fail_reason("end_turn", 5000, 2900, 2048) == "over_budget"
    assert claude.fail_reason("end_turn", 4000, 2000, 2048) is None
    assert claude.fail_reason("end_turn", 5000, None, None) is None
    assert claude.fail_reason("max_tokens", 2048, 0, None) is None
    assert claude.fail_reason("pause_turn", 10, 0, 2048) == "pause_turn"


def test_account_errors_do_not_use_up_a_resubmission():
    assert claude.account_error("billing_error", None, "card declined")
    assert claude.account_error("invalid_request_error", None,
                                "Your credit balance is too low to access the API.")
    assert claude.account_error("invalid_request_error", None, "You have reached your spend limit")
    assert claude.account_error("rate_limit_error", "enforced_spend_limit_reached", "x")
    assert not claude.account_error("overloaded_error", None, "Overloaded")
    assert not claude.account_error("invalid_request_error", None, "messages: bad block")


def test_count_records_tokens_with_and_without_images(run_dir):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    claude.count(client, run)
    counts = run.counts()
    assert counts[("deveval", "b", "image12")]["input_tokens"] == 500 + 2 * 1210
    assert counts[("deveval", "b", "image12")]["text_part_tokens"] == 500
    assert counts[("deveval", "a", "text")]["text_part_tokens"] == 500
    assert len(client.messages.counted) == 3
    assert all("max_tokens" not in c and c["thinking"] == {"type": "adaptive"}
               for c in client.messages.counted)


def test_dry_run_creates_nothing(run_dir):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    assert claude.submit(client, run, 0, 100.0, [], yes=False, ceiling=True) == "submitted"
    assert client.messages.batches.created == [] and run.state()[1] == []


def test_submit_without_counts_stops(run_dir):
    with pytest.raises(SystemExit, match="run `count` first"):
        go(FakeClient(), make(run_dir))


def test_round_trip_writes_rows_in_the_vllm_schema(run_dir):
    client = FakeClient(lambda r: ok(thinking=10, cache=7))
    run = make(run_dir)
    claude.count(client, run)
    assert go(client, run) == "submitted"
    assert claude.fetch(client, run) == 0
    rows = read_jsonl(run.gen_path("deveval"))
    assert sorted((r["id"], r["condition"], r["run"]) for r in rows) == [
        ("a", "text", 0), ("b", "image12", 0)]
    r = rows[0]
    assert r["seed"] is None and r["reply"] == "def f():\n    return 1"
    assert (r["finish_reason"], r["prompt_tokens"], r["output_tokens"], r["thinking_tokens"]) == (
        "stop", 1007, 40, 10)
    assert r["cost_usd"] == pytest.approx((1007 * 2 + 40 * 10) / 1e6)
    assert r["fail_reason"] is None and r["error"] is None
    log = run.log()
    (batch,) = [x for x in log if x["kind"] == "batch"]
    assert batch["decision"] == "submitted" and batch["purchased_zero"] and batch["auto_reload_off"]
    assert batch["anthropic_version"] == "2026-10-21" and batch["code"]["commit"]
    assert batch["projected_usd"] == pytest.approx(
        1.1 * ((500 * 2 + 16000 * 10) + ((500 + 2420) * 2 + 16000 * 10)) / 1e6)
    result = next(x for x in log if x["kind"] == "result")
    assert result["usage"]["thinking_tokens"] == 10
    assert result["returned_model"] == "claude-opus-5-5" and result["resubmissions"] == 0
    assert client.options == [{"max_retries": 0}]
    assert "SENTINEL-THOUGHT" not in json.dumps(rows) + json.dumps(log)
    assert claude.submit(client, run, 0, 100.0, [], yes=True) is None


def test_refusal_and_max_tokens(run_dir):
    answers_ = {"a": ok(stop="refusal", stop_details={"type": "refusal", "category": "cyber",
                                                      "explanation": "x"}),
                "b": ok(stop="max_tokens", out=16000, thinking=15000)}
    client = FakeClient(lambda r: answers_[text_of(r)])
    run = make(run_dir)
    claude.count(client, run)
    go(client, run)
    claude.fetch(client, run)
    rows = {r["id"]: r for r in read_jsonl(run.gen_path("deveval"))}
    assert rows["a"]["fail_reason"] == "refusal"
    assert rows["b"]["fail_reason"] is None and rows["b"]["finish_reason"] == "length"
    refusal = next(x for x in run.log() if x["kind"] == "result" and x["stop_reason"] == "refusal")
    assert refusal["stop_details"]["category"] == "cyber"


def test_opus_over_budget_is_written_by_fetch(run_dir):
    answers_ = {"a": ok(out=4100, thinking=2000), "b": ok(out=4000, thinking=2000)}
    client = FakeClient(lambda r: answers_[text_of(r)])
    run = make(run_dir)
    claude.count(client, run)
    go(client, run)
    claude.fetch(client, run)
    rows = {r["id"]: r for r in read_jsonl(run.gen_path("deveval"))}
    assert (rows["a"]["fail_reason"], rows["b"]["fail_reason"]) == ("over_budget", None)


def test_opus_without_thinking_tokens_stops_fetch(run_dir):
    client = FakeClient(lambda r: ok(out=3000))
    run = make(run_dir)
    claude.count(client, run)
    go(client, run)
    with pytest.raises(SystemExit, match="no thinking_tokens"):
        claude.fetch(client, run)
    assert run.rows() == [] and not [x for x in run.log() if x["kind"] == "result"]


def test_sonnet_has_no_answer_budget(run_dir):
    client = FakeClient(lambda r: ok(out=3000))
    run = make(run_dir, "sonnet")
    claude.count(client, run)
    go(client, run)
    claude.fetch(client, run)
    assert {r["fail_reason"] for r in read_jsonl(run.gen_path("deveval"))} == {None}


def test_errors_are_resubmitted_then_left_as_request_error(run_dir):
    seen = []

    def answer(r):
        seen.append(r["custom_id"])
        n = len(seen)
        if n in (1, 2):
            return errored("billing_error", "credit")
        return errored("overloaded_error", "Overloaded") if n % 2 else {"type": "expired"}

    client, run = FakeClient(answer), make(run_dir)
    run.requests["deveval"] = run.requests["deveval"][:1]
    claude.count(client, run)
    for _ in range(10):
        if not run.pending(0):
            break
        go(client, run)
        assert run.pending(0) == []
        claude.fetch(client, run)
    assert len(seen) == 2 + 4 and len(set(seen)) == 6
    (row,) = read_jsonl(run.gen_path("deveval"))
    assert row["fail_reason"] == "request_error" and row["reply"] is None
    results = [x for x in run.log() if x["kind"] == "result"]
    assert [x["counts"] for x in results] == [False, False, True, True, True, True]
    assert [x["attempt"] for x in results] == [0, 1, 2, 3, 4, 5]
    assert [x["resubmissions"] for x in results] == [0, 0, 0, 1, 2, 3]


def test_spend_limit_in_results_waits_for_credit(run_dir):
    seen = []

    def answer(r):
        seen.append(r["custom_id"])
        if len(seen) == 1:
            return errored("rate_limit_error", "limit",
                           {"error_code": "enforced_spend_limit_reached"})
        return ok()

    client, run = FakeClient(answer), make(run_dir)
    run.requests["deveval"] = run.requests["deveval"][:1]
    claude.count(client, run)
    go(client, run)
    claude.fetch(client, run)
    (first,) = [x for x in run.log() if x["kind"] == "result"]
    assert first["error_code"] == "enforced_spend_limit_reached" and first["account_error"]
    assert not first["counts"] and run.state()[2] == {}
    go(client, run)
    claude.fetch(client, run)
    assert [r["fail_reason"] for r in read_jsonl(run.gen_path("deveval"))] == [None]


@pytest.mark.parametrize("error, decision", [
    (status_error(400, "invalid_request_error", "You have reached your specified API usage limits"),
     "blocked"),
    (status_error(429, "rate_limit_error", "x", {"error_code": "enforced_spend_limit_reached"}),
     "blocked"),
    (status_error(500, "api_error", "Internal server error"), "create_failed"),
])
def test_refused_create_is_logged(run_dir, error, decision):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    client.messages.batches.fail = error
    with pytest.raises(anthropic.APIStatusError):
        go(client, run)
    (batch,) = [x for x in run.log() if x["kind"] == "batch"]
    assert batch["decision"] == decision and batch["batch_id"] is None
    assert len(run.pending(0)) == 2


def test_lost_create_must_be_adopted_before_more_is_sent(run_dir):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    client.messages.batches.fail = "lost"
    with pytest.raises(anthropic.APITimeoutError):
        go(client, run)
    with pytest.raises(SystemExit, match="msgbatch_1"):
        go(client, run)
    claude.adopt(client, run, "msgbatch_1")
    assert run.pending(0) == []
    claude.fetch(client, run)
    assert len(read_jsonl(run.gen_path("deveval"))) == 2
    assert go(client, run) is None and client.messages.batches.n == 1


def test_timed_out_create_that_made_nothing_does_not_block(run_dir):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    client.messages.batches.fail = anthropic.APITimeoutError(
        request=httpx2.Request("POST", "https://api.test"))
    with pytest.raises(anthropic.APITimeoutError):
        go(client, run)
    assert go(client, run) == "submitted" and client.messages.batches.n == 1


def test_ceiling_is_for_the_smoke_only(run_dir):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    with pytest.raises(SystemExit, match="no measured cost"):
        claude.submit(client, run, 0, 100.0, [], yes=False)
    go(client, run)
    claude.fetch(client, run)
    with pytest.raises(SystemExit, match="ceiling does not apply"):
        claude.submit(client, run, 1, 100.0, [], yes=False, ceiling=True)
    assert claude.submit(client, run, 1, 100.0, [], yes=True) == "submitted"
    batch = [x for x in run.log() if x["kind"] == "batch"][-1]
    assert batch["cost_source"] == "measured"
    assert batch["cost_per_request_usd"] == {"deveval image12": 0.0024, "deveval text": 0.0024}


def test_cut_takes_the_cheapest_and_wait_creates_nothing(run_dir):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    text_cost = 1.1 * (500 * 2 + 16000 * 10) / 1e6
    assert go(client, run, balance=text_cost + 0.0001) == "cut"
    (sent,) = client.messages.batches.created
    assert [run.state()[0][r["custom_id"]]["key"][1] for r in sent] == ["a"]
    assert go(client, run, balance=text_cost + 0.0001) == "waited"
    log = run.log()
    assert [b["decision"] for b in log if b["kind"] == "batch"] == ["cut", "waited"]
    assert len(client.messages.batches.created) == 1


def test_measured_costs_replace_the_ceiling(run_dir):
    client, run = FakeClient(), make(run_dir)
    cell = {"model": OPUS["model"], "benchmark": "deveval"}
    measured = [{**cell, "condition": "text", "cost_usd": 0.01},
                {**cell, "condition": "text", "cost_usd": 0.03},
                {**cell, "condition": "image12", "cost_usd": 0.05}]
    go(client, run, cost_rows=measured)
    (batch,) = [x for x in run.log() if x["kind"] == "batch"]
    assert batch["cost_source"] == "measured"
    assert batch["cost_per_request_usd"] == {"deveval image12": 0.05, "deveval text": 0.02}
    assert batch["projected_usd"] == pytest.approx(1.1 * 0.07)
    with pytest.raises(SystemExit, match="no measured cost"):
        claude.estimates(run, [(req("c", "image14"), ("deveval", "c", "image14", 0))], measured)


def test_open_batches_count_against_the_balance(run_dir):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    run.requests["deveval"] = run.requests["deveval"][:1]
    go(client, run)
    run.requests["deveval"] = read_jsonl(f"{run_dir}/deveval/requests.jsonl")
    open_cost = run.state()[1][0]["projected_usd"]
    assert go(client, run, balance=open_cost + 0.01) == "waited"


def test_batches_split_at_the_byte_cap(run_dir):
    client, run = FakeClient(), make(run_dir, batch_bytes=1)
    claude.count(client, run)
    go(client, run)
    assert [len(b) for b in client.messages.batches.created] == [1, 1]
    assert len({b["batch_id"] for b in run.log() if b["kind"] == "batch"}) == 2


def test_fetch_resumes_without_duplicate_rows(run_dir):
    client, run = FakeClient(), make(run_dir)
    claude.count(client, run)
    go(client, run)
    claude.fetch(client, run)
    log = run.log()
    # a crash after the rows were written but before their result records
    with open(run.log_path, "w") as f:
        f.writelines(json.dumps(x) + "\n" for x in log if x["kind"] not in ("batch_end", "result"))
    claude.fetch(client, run)
    assert len(read_jsonl(run.gen_path("deveval"))) == 2
    assert len([x for x in run.log() if x["kind"] == "result"]) == 2


def test_collect_scores_claude_rows():
    m = OPUS["model"]

    def gen(run, **kw):
        return {"model": m, "id": "i", "condition": "text", "run": run, "seed": None,
                "n_images": 0, "seconds": None, "finish_reason": "stop", "prompt_tokens": 5,
                "output_tokens": 2, "fail_reason": None, "error": None, **kw}

    key = answers.answer_key
    gens = [gen(0), gen(1, fail_reason="refusal"), gen(2, fail_reason="over_budget"),
            gen(3, reply=None, fail_reason="request_error", error="overloaded_error: x")]
    rows, problems = collect("deveval", [m], [{"id": "i", "condition": "text"}], 4, gens,
                             [{"key": key(m, "i", "text", 0), "defines_target": True}], [],
                             [{"key": key(m, "i", "text", 0), "result": "Pass", "seconds": 1}])
    assert problems == []
    assert [(r["passed"], r["reason"]) for r in rows] == [
        (True, "pass"), (False, "refusal"), (False, "over_budget"), (None, "request_error")]


def test_answers_skip_rows_that_fail_before_grading(tmp_path):
    item = {"namespace": "pkg.mod.f", "indent": 4, "project_path": "p", "completion_path": "c",
            "body_position": [1, 2], "tests": []}
    (tmp_path / "data.jsonl").write_text(json.dumps(item) + "\n")
    base = {"model": OPUS["model"], "id": "pkg.mod.f", "condition": "text",
            "reply": "```python\ndef f(x):\n    return x\n```", "error": None}
    gen = [{**base, "run": 0, "fail_reason": None}, {**base, "run": 1, "fail_reason": "refusal"},
           {**base, "run": 2, "reply": None, "fail_reason": "request_error", "error": "x"}]
    (tmp_path / "gen.jsonl").write_text("".join(json.dumps(g) + "\n" for g in gen))
    answers.main(["--benchmark", "deveval", "--items", str(tmp_path / "data.jsonl"),
                  "--gen", str(tmp_path / "gen.jsonl"), "--out", str(tmp_path / "out")])
    assert [a["run"] for a in read_jsonl(tmp_path / "out" / "answers.jsonl")] == [0]
    assert read_jsonl(tmp_path / "out" / "skipped.jsonl") == []


def test_main_needs_the_key_in_the_environment(run_dir, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        claude.main(["count", "--model", "opus", "--run-dir", run_dir])
