# /// script
# requires-python = ">=3.11"
# dependencies = ["pyarrow"]
# ///
"""Turn the CoderUJB complete parquet into the JSONL that gold_check.py reads.

usage: uv run --quiet coderujb/make_items.py complete.parquet > items.jsonl
"""
import json, sys
import pyarrow.parquet as pq

KEEP = ["task_id", "project", "bug_id", "testmethods", "location", "start", "end", "source",
        "function_signature"]

for idx, r in enumerate(pq.read_table(sys.argv[1]).to_pylist()):
    print(json.dumps({"idx": idx, **{k: r[k] for k in KEEP}}))
