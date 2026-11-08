import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
# full benchmark data, kept out of git (scratch/ is ignored); tests that need it skip without it
SCRATCH = os.path.join(ROOT, "scratch", "ufm7")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def read_ids(path):
    with open(path) as f:
        return f.read().split()


def need(path):
    if not os.path.exists(path):
        pytest.skip(f"needs {os.path.relpath(path, ROOT)}")
    return path
