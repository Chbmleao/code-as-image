"""configs/experiment.toml. Only the stages that run on Python 3.11+ import this module."""
import os

import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT = os.path.join(ROOT, "configs", "experiment.toml")


def load(path=None):
    with open(path or os.environ.get("CODEIMG_CONFIG", DEFAULT), "rb") as f:
        return tomllib.load(f)
