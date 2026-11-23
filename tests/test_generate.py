import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pytest
from conftest import read_jsonl

from codeimg import config, generate


class Fake(BaseHTTPRequestHandler):
    """Answers like vLLM; the reply to a request is chosen by its first text part."""
    seen: ClassVar[list] = []
    fail_5xx = 0

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Fake.seen.append(body)
        first = body["messages"][0]["content"][0]["text"]
        if "TOO-LONG" in first:
            return self.send(400, {"message": "This model's maximum context length is 16384 tokens."})
        if "BAD" in first:
            return self.send(400, {"message": "unknown field"})
        if "FLAKY" in first and Fake.fail_5xx:
            Fake.fail_5xx -= 1
            return self.send(503, {"message": "busy"})
        finish = "abort" if "ABORT" in first else "stop"
        self.send(200, {"choices": [{"message": {"content": f"reply seed {body['seed']}"},
                                     "finish_reason": finish}],
                        "usage": {"prompt_tokens": 11, "completion_tokens": 3}})

    def send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(generate.time, "sleep", lambda s: None)
    server = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    Fake.seen.clear()
    url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    yield generate.Client(url, "org/model", config.load(), str(tmp_path))
    server.shutdown()


def req(item_id, text, condition="text"):
    return {"benchmark": "deveval", "id": item_id, "condition": condition, "n_images": 0,
            "parts": [{"type": "text", "text": text}]}


def test_every_request_carries_the_sampling_and_the_run_seed(client, tmp_path):
    out = str(tmp_path / "gen.jsonl")
    generate.run_grid(client, [req("a", "hi")], 3, out, 2)
    rows = read_jsonl(out)
    assert sorted((r["run"], r["seed"], r["reply"]) for r in rows) == [
        (0, 0, "reply seed 0"), (1, 1, "reply seed 1"), (2, 2, "reply seed 2")]
    sampling = config.load()["sampling"]
    for body in Fake.seen:
        assert {k: body[k] for k in sampling} == sampling
        assert [m["role"] for m in body["messages"]] == ["user"]
        assert body["chat_template_kwargs"] == {"enable_thinking": False}


def test_resume_skips_rows_already_written(client, tmp_path):
    out = str(tmp_path / "gen.jsonl")
    generate.run_grid(client, [req("a", "hi")], 2, out, 1)
    Fake.seen.clear()
    generate.run_grid(client, [req("a", "hi"), req("b", "hi")], 2, out, 1)
    assert len(Fake.seen) == 2
    assert len(read_jsonl(out)) == 4


def test_context_length_400_is_an_exclusion_row(client, tmp_path):
    out = str(tmp_path / "gen.jsonl")
    generate.run_grid(client, [req("a", "TOO-LONG")], 1, out, 1)
    (row,) = read_jsonl(out)
    assert row["reply"] is None and row["error"].startswith("400")


def test_other_400_stops_the_job_without_a_row(client, tmp_path):
    out = str(tmp_path / "gen.jsonl")
    with pytest.raises(generate.StopJob):
        generate.run_grid(client, [req("a", "BAD")], 1, out, 1)
    assert read_jsonl(out) == []


def test_an_aborted_reply_stops_the_job_without_a_row(client, tmp_path):
    out = str(tmp_path / "gen.jsonl")
    with pytest.raises(generate.StopJob):
        generate.run_grid(client, [req("a", "ABORT")], 1, out, 1)
    assert read_jsonl(out) == []


def test_5xx_is_retried(client, tmp_path):
    Fake.fail_5xx = 2
    out = str(tmp_path / "gen.jsonl")
    generate.run_grid(client, [req("a", "FLAKY")], 1, out, 1)
    assert read_jsonl(out)[0]["reply"] == "reply seed 0"


def test_5xx_that_persists_stops_the_job(client, tmp_path):
    Fake.fail_5xx = 99
    with pytest.raises(generate.StopJob):
        generate.run_grid(client, [req("a", "FLAKY")], 1, str(tmp_path / "gen.jsonl"), 1)
    Fake.fail_5xx = 0


def test_seed_check_writes_its_own_file(client, tmp_path):
    out = str(tmp_path / "gen.jsonl.seedcheck.jsonl")
    generate.run_seed_check(client, [req("a", "hi")], out)
    assert [(r["tag"], r["seed"]) for r in read_jsonl(out)] == [("a", 0), ("b", 0), ("c", 1)]
    assert not (tmp_path / "gen.jsonl").exists()


def test_probe_sends_the_image_message_without_images(client, tmp_path):
    q = req("a", "sentence", "image12")
    q["parts"].append({"type": "image", "path": "missing.png"})
    out = str(tmp_path / "probe.jsonl")
    generate.run_probes(client, [req("a", "hi"), q, {**q, "condition": "image14"}], out)
    assert read_jsonl(out) == [{"model": "org/model", "id": "a", "text_part_tokens": 11}]
    assert Fake.seen[-1]["messages"][0]["content"] == [{"type": "text", "text": "sentence"}]


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    Fake.seen.clear()
    yield srv.server_port
    srv.shutdown()


def run_main(tmp_path, port, dstudy_rows, monkeypatch):
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    reqs, ds = tmp_path / "requests.jsonl", tmp_path / "dstudy.json"
    reqs.write_text(json.dumps(req("a", "hi")) + "\n")
    ds.write_text(json.dumps({"rows": dstudy_rows}))
    out = str(tmp_path / "gen.jsonl")
    generate.main(["--model", "qwen25vl7b", "--requests", str(reqs), "--out", out,
                   "--port", str(port), "--runs-from", str(ds)])
    return out


def test_runs_from_sets_the_runs_and_seeds(tmp_path, server, monkeypatch):
    repo = config.load()["models"]["qwen25vl7b"]["repo"]
    out = run_main(tmp_path, server, [{"benchmark": "deveval", "model": repo, "runs": 2},
                                      {"benchmark": "coderujb", "model": repo, "runs": 3}],
                   monkeypatch)
    assert sorted((r["run"], r["seed"]) for r in read_jsonl(out)) == [(0, 0), (1, 1)]
    with open(out + ".meta.local.json") as f:
        meta = json.load(f)
    assert (meta["runs"], meta["seeds"]) == (2, [0, 1])


def test_runs_from_without_a_row_stops_before_any_request(tmp_path, server, monkeypatch):
    with pytest.raises(SystemExit, match="no deveval row"):
        run_main(tmp_path, server, [{"benchmark": "coderujb", "model": "x", "runs": 2}],
                 monkeypatch)
    assert Fake.seen == []


def test_images_are_sent_as_data_urls_in_message_order(client, tmp_path):
    for name, data in (("p1.png", b"one"), ("p2.png", b"two")):
        (tmp_path / name).write_bytes(data)
    q = req("a", "sentence", "image10")
    q["parts"] += [{"type": "image", "path": "p1.png"}, {"type": "text", "text": "mid"},
                   {"type": "image", "path": "p2.png"}]
    client.reply(q, 0)
    content = Fake.seen[-1]["messages"][0]["content"]
    assert [c["type"] for c in content] == ["text", "image_url", "text", "image_url"]
    assert content[1]["image_url"]["url"] == "data:image/png;base64,b25l"
    assert content[3]["image_url"]["url"] == "data:image/png;base64,dHdv"
