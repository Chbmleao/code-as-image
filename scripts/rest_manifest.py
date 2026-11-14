"""Rest manifests: every final item not in block 1 (docs/methodology.md 3.1).

The final items are CoderUJB's final_ids.txt and DevEval's inrange_ids.txt, the sets block 1 was
drawn from (src/codeimg/sample.py). Nothing is random: the rest is the set difference. Since the
rest shares no item with block 1, no (model, item, condition, run) key of the rest can repeat one
of block 1's, whatever runs the rest uses.

Writes manifests/rest/{coderujb,deveval}.txt, sorted ids, one per line, like block 1.

usage: uv run python scripts/rest_manifest.py [--out manifests]
"""
import argparse
import os

from codeimg import config
from codeimg.sample import RESULTS, read_lines, write

FINAL = {"coderujb": RESULTS.format("coderujb", "final_ids.txt"),
         "deveval": RESULTS.format("deveval", "inrange_ids.txt")}
EXPECTED = {"coderujb": 96, "deveval": 659}


def rest(final, block):
    final, block = set(final), set(block)
    assert block <= final, f"{len(block - final)} block-1 ids are not final items"
    return sorted(final - block)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(config.ROOT, "manifests"))
    args = ap.parse_args(argv)
    for bench, path in FINAL.items():
        block = read_lines(os.path.join(args.out, "block1", f"{bench}.txt"))
        ids = rest(read_lines(path), block)
        assert len(ids) == EXPECTED[bench], f"{bench}: {len(ids)} rest items, expected {EXPECTED[bench]}"
        write(os.path.join(args.out, "rest", f"{bench}.txt"), ids)
        print(bench, len(ids))


if __name__ == "__main__":
    main()
