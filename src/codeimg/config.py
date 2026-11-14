"""configs/experiment.toml. Only the stages that run on Python 3.11+ import this module."""
import json
import os

import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT = os.path.join(ROOT, "configs", "experiment.toml")


def load(path=None):
    with open(path or os.environ.get("CODEIMG_CONFIG", DEFAULT), "rb") as f:
        return tomllib.load(f)


def runs_from(path, benchmark, models):
    """{model repo: runs} for one benchmark, from the rows of a D-study file
    (results/block1/dstudy.json, keyed by benchmark and raw model repo id)."""
    with open(path) as f:
        table = {(r["benchmark"], r["model"]): r["runs"] for r in json.load(f)["rows"]}
    missing = [m for m in models if (benchmark, m) not in table]
    if missing:
        raise ValueError(f"{path} has no {benchmark} row for {', '.join(missing)}")
    return {m: table[(benchmark, m)] for m in models}
