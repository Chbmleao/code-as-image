import importlib.util
import os

import pytest
from conftest import ROOT, read_ids

_spec = importlib.util.spec_from_file_location(
    "rest_manifest", os.path.join(ROOT, "scripts", "rest_manifest.py"))
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


@pytest.mark.parametrize("bench", ["coderujb", "deveval"])
def test_saved_rest_is_every_final_item_not_in_block1(bench):
    saved = read_ids(os.path.join(ROOT, "manifests", "rest", f"{bench}.txt"))
    block = read_ids(os.path.join(ROOT, "manifests", "block1", f"{bench}.txt"))
    assert saved == rm.rest(read_ids(rm.FINAL[bench]), block)
    assert len(saved) == rm.EXPECTED[bench]
    assert not set(saved) & set(block)


def test_block_item_outside_the_final_set_fails():
    with pytest.raises(AssertionError, match="not final items"):
        rm.rest(["a", "b"], ["c"])
