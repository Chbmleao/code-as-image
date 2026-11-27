"""The Claude reply measures: refusals, stop reasons, thinking share, output and cache tokens per
model and condition, from the Claude run directory."""
import os
from collections import Counter, defaultdict

from codeimg import config
from codeimg.analysis import dstudy as ds
from codeimg.analysis import inputs as inp
from codeimg.analysis import stats as st


def reply_cell():
    return {"replies": 0, "request_errors": 0, "refusals": Counter(), "max_tokens": 0,
            "over_budget": 0, "other_stops": Counter(), "thinking": 0, "output": 0,
            "with_thinking": 0, "plain": [], "cache_creation_tokens": 0, "cache_read_tokens": 0}


def replies_report(cfg, run_dir, collected, benches=ds.BENCHES):
    """Per Claude model, benchmark and condition, from the run directory: each gen row joined on
    (benchmark, id, condition, run) to its one succeeded result in the run log, which holds the
    stop reason and the usage. collected[b] is the Claude collected table, which the gen rows must
    match key for key. Output tokens here leave thinking out."""
    conds = inp.conditions(cfg)
    rep = {"settings": {"models": [inp.name(m) for m in inp.claude_set(cfg)],
                        "output_tokens": "output_tokens minus thinking_tokens, per reply",
                        "thinking_share": "thinking tokens over output tokens, summed"},
           "benchmarks": {b: {} for b in benches}}
    for short, settings in config.claude_models(cfg).items():
        model = settings["model"]
        results = defaultdict(list)
        for r in ds.read_jsonl(os.path.join(run_dir, "claude", f"{short}.log.jsonl")):
            if r["kind"] == "result":
                results[tuple(r["key"])].append(r)
        for b in benches:
            gen = ds.read_jsonl(os.path.join(run_dir, b, "gen", f"claude_{short}.jsonl"))
            col = {(r["id"], r["condition"], r["run"]): r for r in collected[b]
                   if r["model"] == model}
            keys = Counter((g["id"], g["condition"], g["run"]) for g in gen)
            if keys != Counter(col.keys()):
                raise ValueError(f"{b}: the gen rows of {inp.name(model)} ({len(gen)}) do not "
                                 f"match its collected rows ({len(col)}) key for key")
            cells = defaultdict(reply_cell)
            for g in gen:
                k = (b, g["id"], g["condition"], g["run"])
                reason = col[k[1:]]["reason"]
                if g["fail_reason"] is not None and g["fail_reason"] != reason:
                    raise ValueError(f"{b}: {k}: gen fail_reason {g['fail_reason']} but the "
                                     f"collected reason is {reason}")
                done = [r for r in results[k] if r["type"] == "succeeded"]
                cell = cells[g["condition"]]
                cell["replies"] += 1
                if g["fail_reason"] == "request_error":
                    if done:
                        raise ValueError(f"{b}: {k} is a request_error with a succeeded result")
                    cell["request_errors"] += 1
                    continue
                if len(done) != 1:
                    raise ValueError(f"{b}: {k} has {len(done)} succeeded results in the run log")
                res = done[0]
                u, stop = res["usage"], res["stop_reason"]
                if u["thinking_tokens"] is None:
                    raise ValueError(f"{b}: {k}: no thinking_tokens in the usage")
                if stop == "refusal":
                    cell["refusals"][(res["stop_details"] or {}).get("category") or "none"] += 1
                elif stop == "max_tokens":
                    cell["max_tokens"] += 1
                elif stop != "end_turn":
                    cell["other_stops"][stop] += 1
                cell["over_budget"] += g["fail_reason"] == "over_budget"
                cell["thinking"] += u["thinking_tokens"]
                cell["output"] += u["output_tokens"]
                cell["with_thinking"] += u["thinking_tokens"] > 0
                cell["plain"].append(u["output_tokens"] - u["thinking_tokens"])
                cell["cache_creation_tokens"] += u["cache_creation_input_tokens"] or 0
                cell["cache_read_tokens"] += u["cache_read_input_tokens"] or 0
            stopped = sum(c["max_tokens"] for c in cells.values())
            truncated = sum(bool(r["truncated"]) for r in col.values())
            if stopped != truncated:
                raise ValueError(f"{b}: {inp.name(model)} has {stopped} replies at max_tokens but "
                                 f"{truncated} truncated collected rows")
            out = {}
            for c in conds:
                x = cells[c]
                plain = x.pop("plain")
                thinking, output = x.pop("thinking"), x.pop("output")
                out[c] = {**x, "refusals": dict(x["refusals"]),
                          "other_stops": dict(x["other_stops"]),
                          "thinking_share": thinking / output if output else None,
                          "output_tokens": {**st.spread(plain), "mean": st.mean(plain)}}
            rep["benchmarks"][b][inp.name(model)] = out
    return rep
