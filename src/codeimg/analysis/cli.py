"""Main analysis of the full answer table (methodology 3.3).

  gaps           the paired image-text gap per model (delta_mb, mean over sizes) with the
                 clustered and item-level t intervals and Holm, the pooled gap with its joint
                 cluster resample interval, the per-size gaps and size differences (BH), prompt
                 tokens and the token ratio, leave-one-project-out, context length buckets, floor
                 and ceiling shares, scoring shares and ranks. Writes <out>/gaps.json,
                 <out>/never_passed.csv and <out>/figures/{main_gap,size_curve}.pdf. With
                 --models claude: the Claude models' own gaps (methodology addendum) with their
                 own Holm and BH families and the gaps without contamination-flagged items;
                 writes <out>/gaps.json only.
  replies        Claude only: refusals, stop reasons, over_budget, thinking share, non-thinking
                 output tokens and cache tokens per model and condition, from the Claude run
                 directory. Writes <out>/replies.json.
  prep           writes <scratch>/<b>_answers.csv (model, item, project, condition, run, passed)
                 for analysis/glmm_main.R.
  contamination  flags (model, item) when another model copies the reference in a text run, and
                 compares the gaps with and without the flagged items against a matched random
                 removal. Writes <out>/contamination.json and <out>/contamination_flags.csv.
  report         writes <out>/findings.md from gaps.json, glmm.json and contamination.json. With
                 --models all: <out>/../findings.md, the Claude extension report, and
                 <out>/figures/{claude_gap,size_curve}.pdf.
  ranks          the 7-model line only: rates, ranks with their resample intervals and the text
                 vs image swap probability of each pair. Writes <out>/ranks.json.

usage: uv run python scripts/analysis.py gaps [--models main|claude] [--answers DIR] [--full DIR]
                                         [--claude-full DIR] [--out DIR]
       uv run python scripts/analysis.py replies --run-dir DIR [--claude-full DIR] [--out DIR]
       uv run python scripts/analysis.py prep [--models main|all] [--full DIR] [--claude-full DIR]
                                         [--scratch DIR]
       uv run python scripts/analysis.py contamination --answers DIR [--models main|all]
                                         [--full DIR] [--claude-full DIR] [--out DIR]
       uv run python scripts/analysis.py ranks [--full DIR] [--claude-full DIR] [--out DIR]
       uv run python scripts/analysis.py report [--models main|all] [--out DIR]

The models are those of configs/experiment.toml (CODEIMG_CONFIG overrides the path). `main`, the
default, is the [models] table and writes to results/analysis. `all` is the 7-model line of the
methodology addendum: [models] plus the [claude] models, runs 0 and 1 only for every model; its
results go to results/claude/analysis and its answers CSVs to scratch/analysis_all. In that line
contamination writes the copy flags only. `claude` (gaps only) is the [claude] models alone, and
also writes to results/claude/analysis. Gaps are image minus text, so a loss is negative. Every resample interval is 95%
equal-tailed from type-1 percentiles.
"""
import argparse
import os
import sys

from codeimg import config
from codeimg.analysis import contamination as ctm
from codeimg.analysis import dstudy as ds
from codeimg.analysis import figures as figs
from codeimg.analysis import gaps as gp
from codeimg.analysis import glmm_cells as gc
from codeimg.analysis import inputs as inp
from codeimg.analysis import reliability as rel
from codeimg.analysis import replies as rpl
from codeimg.analysis import report as rpt


def gaps(args):
    cfg = config.load()
    if args.models == "claude":
        inputs = inp.read_claude(cfg, args.claude_full)
        copies = {b: ctm.text_copies(b, args.answers, ("block1", "rest", "claude")) for b in inputs}
        inp.write_json(os.path.join(args.out, "gaps.json"),
                       gp.claude_gaps_report(cfg, inputs, copies))
        return
    rep = gp.gaps_report(cfg, inp.read_inputs(cfg, args.full))
    never = [row for v in rep["benchmarks"].values() for row in v.pop("never_passed")]
    for b, v in rep["benchmarks"].items():
        v["never_passed"] = sum(row[0] == b for row in never)
    inp.write_json(os.path.join(args.out, "gaps.json"), rep)
    path = os.path.join(args.out, "never_passed.csv")
    gc.write_csv(path, inp.NEVER_FIELDS, never)
    print(path)
    figs.figures(inp.rounded(rep), os.path.join(args.out, "figures"))


def prep(args):
    cfg = config.load()
    if args.models == "all":
        inputs = inp.read_line(cfg, args.full, args.claude_full)
    else:
        inputs = {b: data for b, (data, _) in inp.read_inputs(cfg, args.full).items()}
    for b, data in inputs.items():
        out = inp.answer_rows(data)
        path = os.path.join(args.scratch, f"{b}_answers.csv")
        gc.write_csv(path, rel.ANSWER_FIELDS, out)
        print(f"{path}: {len(out)} answers"
              + (f", {len(data['dropped'])} item(s) dropped" if "dropped" in data else ""))


def ranks(args):
    rep = gp.ranks_report(inp.read_line(config.load(), args.full, args.claude_full))
    inp.write_json(os.path.join(args.out, "ranks.json"), rep)


def replies(args):
    collected = {b: ds.read_jsonl(os.path.join(args.claude_full, f"{b}.collected.jsonl"))
                 for b in ds.BENCHES}
    rep = rpl.replies_report(config.load(), args.run_dir, collected)
    inp.write_json(os.path.join(args.out, "replies.json"), rep)


def contamination(args):
    cfg = config.load()
    if args.models == "all":
        line = inp.read_line(cfg, args.full, args.claude_full)
        copies = {b: ctm.text_copies(b, args.answers, ("block1", "rest", "claude")) for b in line}
        rep = ctm.line_flags_report(line, copies)
    else:
        modes = ctm.read_item_modes(os.path.join(args.out, "glmm_item_model.csv"))
        inputs = inp.read_inputs(cfg, args.full)
        copies = {b: ctm.text_copies(b, args.answers) for b in inputs}
        rep = ctm.contamination_report(inputs, copies, modes)
    rows = [r for v in rep["benchmarks"].values() for r in v.pop("flag_rows")]
    inp.write_json(os.path.join(args.out, "contamination.json"), rep)
    path = os.path.join(args.out, "contamination_flags.csv")
    gc.write_csv(path, inp.FLAG_FIELDS, rows)
    print(path)


def report(args):
    if args.models == "all":
        inputs = rpt.read_report_inputs(args.out, rpt.CLAUDE_REPORT_INPUTS)
        main = rpt.read_report_inputs(inp.OUT, {f: rpt.REPORT_INPUTS[f]
                                                for f in ("gaps.json", "glmm.json")})
        cov = rpt.read_cov(os.path.join(args.out, "glmm_contrast_cov.csv"), inputs["glmm"])
        text = rpt.claude_findings(inputs, main, cov, inp.claude_set(config.load()))
        path = os.path.join(os.path.dirname(os.path.abspath(args.out)), "findings.md")
        figs.claude_figures(inputs["gaps"], main["gaps"], os.path.join(args.out, "figures"))
    else:
        text = rpt.findings(rpt.read_report_inputs(args.out))
        path = os.path.join(args.out, "findings.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(path)


COMMANDS = {"gaps": gaps, "prep": prep, "contamination": contamination, "ranks": ranks,
            "report": report, "replies": replies}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Main analysis of the full answer table")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("gaps")
    p.add_argument("--models", choices=("main", "claude"), default="main")
    p.add_argument("--full", default=inp.FULL)
    p.add_argument("--claude-full", default=inp.CLAUDE_FULL)
    p.add_argument("--answers", help="with --models claude: the text answers of every model")
    p.add_argument("--out")
    p = sub.add_parser("replies")
    p.add_argument("--run-dir", required=True, help="the Claude run directory (gen/ and claude/)")
    p.add_argument("--claude-full", default=inp.CLAUDE_FULL)
    p.add_argument("--out")
    for cmd in ("prep", "contamination", "ranks", "report"):
        p = sub.add_parser(cmd)
        if cmd != "ranks":
            p.add_argument("--models", choices=("main", "all"), default="main")
        if cmd != "report":
            p.add_argument("--full", default=inp.FULL)
            p.add_argument("--claude-full", default=inp.CLAUDE_FULL)
        if cmd == "prep":
            p.add_argument("--scratch")
        else:
            p.add_argument("--out")
        if cmd == "contamination":
            p.add_argument("--answers", required=True,
                           help="text answers and references copied from the cluster")
    args = ap.parse_args(argv)
    if args.cmd == "gaps" and (args.models == "claude") != (args.answers is not None):
        ap.error("gaps: --answers goes with --models claude, and only with it")
    line = args.cmd in ("ranks", "replies") or getattr(args, "models", "main") != "main"
    if args.cmd == "prep" and args.scratch is None:
        args.scratch = inp.SCRATCH["all" if line else "main"]
    if args.cmd != "prep" and args.out is None:
        args.out = inp.ALL_OUT if line else inp.OUT
    try:
        COMMANDS[args.cmd](args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
