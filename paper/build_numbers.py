"""Write paper/numbers.tex and paper/tables/*.tex from the result files (UFM-14).

    uv run python paper/build_numbers.py [--out DIR]

Every number in the prose is one macro in numbers.tex, declared in MACROS below as (macro, source,
format). Sources, in order of preference: a path in a results JSON, a row count of a results CSV, an
anchored regex that must match a markdown file exactly once, or a simple derived expression
(min, max, count) over those. Nothing is recomputed. A missing source or a prose predicate that no
longer holds stops the run with the macro or the sentence; no default is ever written. The output
holds no dates, so a rerun on the same results is byte-identical.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

MINUS = r"\ensuremath{-}"

OPEN_MODELS = (
    ("Qwen3.5 27B", "QwenTwentySeven"),
    ("Gemma 4 12B", "GemmaTwelve"),
    ("Mistral Small 3.2 24B", "MistralTwentyFour"),
    ("Qwen3.5 9B", "QwenNine"),
    ("Qwen2.5-VL 7B", "QwenVLSeven"),
)
CLAUDE_MODELS = (("Claude Sonnet 5.5", "Sonnet"), ("Claude Opus 5.5", "Opus"))
BENCHES = (("coderujb", "Ujb"), ("deveval", "Dev"))
BENCH_TITLE = {"coderujb": "CoderUJB", "deveval": "DevEval"}
SIZES = (("image10", "Ten", 10), ("image12", "Twelve", 12), ("image14", "Fourteen", 14))
CONDITIONS = (("text", "Text"), *[(c, w) for c, w, _ in SIZES])

OPEN_GAPS = "analysis/gaps.json"
OPEN_GLMM = "analysis/glmm.json"
OPEN_CONTAM = "analysis/contamination.json"
CLAUDE_GAPS = "claude/analysis/gaps.json"
CLAUDE_GLMM = "claude/analysis/glmm.json"
CLAUDE_CONTAM = "claude/analysis/contamination.json"
RELIABILITY = "reliability/reliability.json"
LAYOUT = "layout/layout.json"
DECISIONS = "docs/decisions.md"
EXCLUDED_DEV = "manifests/excluded/deveval.txt"


class SourceError(Exception):
    pass


def plain(x: float, d: int) -> str:
    s = f"{x:.{d}f}"
    neg = s.startswith("-") and float(s) != 0
    return (MINUS if neg else "") + s.lstrip("-").replace(".", ",")


def fmt_pp(x: float) -> str:
    return plain(100 * x, 1)


def fmt_p(p: float) -> str:
    if not 0 < p <= 1:
        raise ValueError(f"p-value out of range: {p}")
    if p < 1e-3:
        mantissa, exp = f"{p:.1e}".split("e")
        return rf"${mantissa.replace('.', '{,}')} \times 10^{{{int(exp)}}}$"
    return plain(p, 1 - math.floor(math.log10(p)))


def fmt_int(x: float) -> str:
    if float(x) != int(x):
        raise ValueError(f"not an integer: {x}")
    return str(int(x))


def fmt_ci(lo: str, hi: str) -> str:
    # semicolon, since the comma is the decimal mark
    return f"[{lo}; {hi}]"


def _bad_version(x: Any) -> str:
    raise ValueError(f"not a version string: {x}")


FORMATS: dict[str, Callable[[Any], str]] = {
    "pp": lambda x: fmt_pp(float(x)),
    "pp_abs": lambda x: fmt_pp(abs(float(x))),
    "dec1": lambda x: plain(float(x), 1),
    "dec2": lambda x: plain(float(x), 2),
    "dec3": lambda x: plain(float(x), 3),
    "int": lambda x: fmt_int(float(x)),
    "p": lambda x: fmt_p(float(x)),
    "version": lambda x: str(x) if re.fullmatch(r"\d+(\.\d+)*", str(x)) else _bad_version(x),
}


@dataclass(frozen=True)
class Sel:
    """Pick the one list element whose `key` equals `value`."""

    key: str
    value: str


ANY = "*"


@dataclass(frozen=True)
class J:
    file: str
    steps: tuple

    def __init__(self, file: str, *steps: Any):
        object.__setattr__(self, "file", file)
        object.__setattr__(self, "steps", steps)

    def describe(self) -> str:
        return (
            self.file
            + ":"
            + ".".join(f"[{s.key}={s.value}]" if isinstance(s, Sel) else str(s) for s in self.steps)
        )


@dataclass(frozen=True)
class Csv:
    """Number of rows of a CSV where every column in `where` has the given value."""

    file: str
    where: tuple = ()

    def describe(self) -> str:
        cond = ", ".join(f"{k}={v}" for k, v in self.where)
        return f"count({self.file}" + (f" where {cond})" if cond else ")")


@dataclass(frozen=True)
class CsvNotIn:
    """Number of rows of a CSV whose `column` is not listed in `manifest` (one id per line)."""

    file: str
    column: str
    manifest: str

    def describe(self) -> str:
        return f"count({self.file} where {self.column} not in {self.manifest})"


@dataclass(frozen=True)
class Md:
    """The one match of `pattern` (one group) in a markdown file, or in the section whose heading
    starts with `section`."""

    file: str
    section: str
    pattern: str

    def describe(self) -> str:
        where = f"{self.file}#{self.section}" if self.section else self.file
        return f"{where}:/{self.pattern}/"


@dataclass(frozen=True)
class Fn:
    label: str
    fn: Callable[..., Any]
    sources: tuple

    def __init__(self, label: str, fn: Callable[..., Any], *sources: Any):
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "fn", fn)
        object.__setattr__(self, "sources", sources)

    def describe(self) -> str:
        return self.label


@dataclass(frozen=True)
class Macro:
    name: str
    source: Any
    fmt: str


def walk(obj: Any, steps: tuple) -> list:
    if not steps:
        return [obj]
    step, rest = steps[0], steps[1:]
    if isinstance(step, Sel):
        if not isinstance(obj, list):
            raise SourceError(f"expected a list for {step.key}={step.value}")
        hits = [x for x in obj if isinstance(x, dict) and str(x.get(step.key)) == step.value]
        if len(hits) != 1:
            raise SourceError(f"{len(hits)} elements with {step.key}={step.value}, expected 1")
        return walk(hits[0], rest)
    if step == ANY:
        items = list(obj.values()) if isinstance(obj, dict) else list(obj)
        return [leaf for item in items for leaf in walk(item, rest)]
    if not isinstance(obj, dict) or step not in obj:
        raise SourceError(f"no key {step!r}")
    return walk(obj[step], rest)


class Sources:
    def __init__(self, root: Path, overrides: dict[str, Any] | None = None):
        self.root = Path(root)
        self.overrides = overrides or {}
        self.cache: dict[str, Any] = {}

    def path(self, rel: str) -> Path:
        # JSON paths are relative to results/, markdown and CSV paths to the repo or results/
        for base in (self.root / "results", self.root):
            if (base / rel).exists():
                return base / rel
        raise SourceError(f"missing file {rel}")

    def json(self, rel: str) -> Any:
        if rel in self.overrides:
            return self.overrides[rel]
        if rel not in self.cache:
            self.cache[rel] = json.loads(self.path(rel).read_text(encoding="utf-8"))
        return self.cache[rel]

    def text(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def rows(self, rel: str) -> list[dict]:
        with self.path(rel).open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def ids(self, rel: str) -> set[str]:
        return set(self.text(rel).split())

    def value(self, src: Any) -> Any:
        if isinstance(src, J):
            leaves = walk(self.json(src.file), src.steps)
            multi = ANY in src.steps
            if multi:
                return leaves
            return leaves[0]
        if isinstance(src, Csv):
            rows = self.rows(src.file)
            for k, _ in src.where:
                if rows and k not in rows[0]:
                    raise SourceError(f"{src.file} has no column {k}")
            return sum(all(r[k] == v for k, v in src.where) for r in rows)
        if isinstance(src, CsvNotIn):
            rows = self.rows(src.file)
            if rows and src.column not in rows[0]:
                raise SourceError(f"{src.file} has no column {src.column}")
            out = self.ids(src.manifest)
            return sum(r[src.column] not in out for r in rows)
        if isinstance(src, Md):
            text = self.text(src.file)
            if src.section:
                m = re.search(
                    rf"^## {re.escape(src.section)}.*?(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
                )
                if not m:
                    raise SourceError(f"no section starting with '## {src.section}'")
                text = m.group(0)
            hits = re.findall(src.pattern, text, re.MULTILINE)
            if len(hits) != 1:
                raise SourceError(f"pattern matched {len(hits)} times, expected exactly 1")
            return hits[0]
        if isinstance(src, Fn):
            return src.fn(*[self.value(s) for s in src.sources])
        raise SourceError(f"unknown source {src!r}")


def repos(src: Sources) -> dict[str, str]:
    """Model name to the repo id that the GLMM files use."""
    out = {}
    for rel in (OPEN_GAPS, CLAUDE_GAPS):
        for row in src.json(rel)["benchmarks"]["coderujb"]["main"]:
            out[row["model"]] = row["repo"]
    return out


def gaps(file: str, bench: str, *steps: Any) -> J:
    return J(file, "benchmarks", bench, *steps)


class Table:
    def __init__(self) -> None:
        self.rows: list[Macro] = []

    def add(self, name: str, source: Any, fmt: str) -> None:
        self.rows.append(Macro(name, source, fmt))

    def interval(self, name: str, source_of: Callable[[str], Any], fmt: str) -> None:
        for suffix, key in (("", "est"), ("Lo", "lo"), ("Hi", "hi")):
            self.add(name + suffix, source_of(key), fmt)


def model_macros(t: Table, repo: dict[str, str]) -> None:
    for bench, B in BENCHES:
        for gaps_file, glmm_file, models in (
            (OPEN_GAPS, OPEN_GLMM, OPEN_MODELS),
            (CLAUDE_GAPS, CLAUDE_GLMM, CLAUDE_MODELS),
        ):
            for name, M in models:
                row = ("main", Sel("model", name))
                t.add(f"gap{M}{B}", gaps(gaps_file, bench, *row, "est"), "pp")
                t.add(f"gap{M}{B}Lo", gaps(gaps_file, bench, *row, "cluster", "lo"), "pp")
                t.add(f"gap{M}{B}Hi", gaps(gaps_file, bench, *row, "cluster", "hi"), "pp")
                t.add(f"gapItem{M}{B}Lo", gaps(gaps_file, bench, *row, "item", "lo"), "pp")
                t.add(f"gapItem{M}{B}Hi", gaps(gaps_file, bench, *row, "item", "hi"), "pp")
                t.add(f"holm{M}{B}", gaps(gaps_file, bench, *row, "holm"), "p")
                t.add(f"textRate{M}{B}", gaps(gaps_file, bench, "rates", "text", name), "pp")
                ratio = gaps(gaps_file, bench, "token_ratio", name, "mean_over_sizes")
                t.add(f"tokenRatio{M}{B}", ratio, "dec2")
                contrast = gaps(glmm_file, bench, "contrast", Sel("model", repo[name]))
                t.interval(f"contrast{M}{B}", lambda k, c=contrast: J(c.file, *c.steps, k), "dec2")


def summary_macros(t: Table) -> None:
    for bench, B in BENCHES:
        t.add(f"nItems{B}", gaps(OPEN_GAPS, bench, "n_items"), "int")
        t.add(f"nClusters{B}", gaps(OPEN_GAPS, bench, "n_clusters"), "int")
        t.interval(f"gapMean{B}", lambda k, b=bench: gaps(OPEN_GAPS, b, "pooled", k), "pp")
        est = gaps(OPEN_GAPS, bench, "main", ANY, "est")
        t.add(f"gapMin{B}", Fn("min(main[].est)", min, est), "pp")
        t.add(f"gapMax{B}", Fn("max(main[].est)", max, est), "pp")
        ratio = gaps(OPEN_GAPS, bench, "token_ratio", ANY, "mean_over_sizes")
        t.add(f"tokenRatioMin{B}", Fn("min(token_ratio[].mean_over_sizes)", min, ratio), "dec2")
        t.add(f"tokenRatioMax{B}", Fn("max(token_ratio[].mean_over_sizes)", max, ratio), "dec2")
        holm = gaps(OPEN_GAPS, bench, "main", ANY, "holm")
        t.add(f"holmMax{B}", Fn("max(main[].holm)", max, holm), "p")
    both = [gaps(OPEN_GAPS, b, "token_ratio", ANY, "mean_over_sizes") for b, _ in BENCHES]
    t.add(
        "tokenRatioMinAll",
        Fn("min(token_ratio[].mean_over_sizes)", lambda *v: min(map(min, v)), *both),
        "dec2",
    )
    t.add(
        "tokenRatioMaxAll",
        Fn("max(token_ratio[].mean_over_sizes)", lambda *v: max(map(max, v)), *both),
        "dec2",
    )
    holms = [gaps(OPEN_GAPS, b, "main", ANY, "holm") for b, _ in BENCHES]
    t.add(
        "holmMaxAll",
        Fn("max(main[].holm), both benchmarks", lambda *v: max(map(max, v)), *holms),
        "p",
    )
    claude = [gaps(CLAUDE_GAPS, b, "main", ANY, "est") for b, _ in BENCHES]
    t.add(
        "claudeLossMinAll",
        Fn("-max(claude main[].est)", lambda *v: -max(map(max, v)), *claude),
        "pp_abs",
    )
    t.add(
        "claudeLossMaxAll",
        Fn("-min(claude main[].est)", lambda *v: -min(map(min, v)), *claude),
        "pp_abs",
    )


def glmm_macros(t: Table) -> None:
    for bench, B in BENCHES:

        def g(*steps: Any, b: str = bench) -> J:
            return gaps(OPEN_GLMM, b, *steps)

        t.interval(
            f"sdItemCondition{B}",
            lambda k, b=bench: gaps(OPEN_GLMM, b, "item_condition_sd", k),
            "dec2",
        )
        t.add(f"sdItem{B}", g("sd", "item"), "dec2")
        t.add(f"sdRatio{B}", g("probit", "ratio_logit"), "dec2")
        t.add(f"sdRatioProbit{B}", g("probit", "ratio_probit"), "dec2")
        t.add(f"waldStat{B}", g("wald", "stat"), "dec1")
        t.add(f"waldDf{B}", g("wald", "df"), "int")
        t.add(f"waldP{B}", g("wald", "p"), "p")
        t.add(f"lrtStat{B}", g("lrt", "stat"), "dec1")
        t.add(f"lrtP{B}", g("lrt", "p"), "p")
        t.add(f"heldoutDiff{B}", g("heldout", "diff"), "dec1")
        t.add(f"heldoutSe{B}", g("heldout", "se"), "dec1")
        folds = (g("heldout", "folds", ANY, "full"), g("heldout", "folds", ANY, "reduced"))
        positive = Fn(
            "count(heldout.folds[].full - reduced > 0)",
            lambda full, red: sum(f > r for f, r in zip(full, red)),
            *folds,
        )
        t.add(f"heldoutPositiveFolds{B}", positive, "int")
        t.add(f"heldoutFolds{B}", Fn("count(heldout.folds[])", len, folds[0]), "int")
        t.add(f"bhFlagged{B}", g("item_flags", "bh_flagged"), "int")
        t.add(f"rawFlagged{B}", g("item_flags", "raw_ci_excludes_zero"), "int")
        t.add(f"nItemFlags{B}", g("item_flags", "n"), "int")
        for size, S, px in SIZES:
            pair = ("correlation", "pearson", f"text~image{px}")
            t.add(f"corr{S}{B}", g(*pair, "observed"), "dec2")
            t.add(f"corr{S}{B}RefLo", g(*pair, "lo"), "dec2")
            t.add(f"corr{S}{B}RefHi", g(*pair, "hi"), "dec2")
            t.add(f"slope{S}{B}", g("common_slope", size, "slope"), "dec2")
            t.add(f"slopeCorrected{S}{B}", g("common_slope", size, "corrected"), "dec2")
        t.add(f"slopeTextRunCorr{B}", g("common_slope", "image10", "text_run_correlation"), "dec2")
        for key, tag in (("observed", ""), ("lo", "RefLo"), ("hi", "RefHi")):
            t.add(f"cPearson{tag}{B}", g("correlation", "pearson", "C", key), "dec2")
        t.add(f"cPearsonPercentile{B}", g("correlation", "pearson", "C", "percentile"), "pp")


def gap_detail_macros(t: Table) -> None:
    for bench, B in BENCHES:
        fc = ("floor_ceiling", "Qwen2.5-VL 7B")
        t.add(f"floorTextQwenVLSeven{B}", gaps(OPEN_GAPS, bench, *fc, "text", "none"), "pp")
        for size, S, _ in SIZES:
            t.add(f"floor{S}QwenVLSeven{B}", gaps(OPEN_GAPS, bench, *fc, size, "none"), "pp")
        t.add(f"noPassText{B}", gaps(OPEN_GAPS, bench, "all_none", "text", "no_model_passes"), "pp")
        t.add(
            f"allPassText{B}", gaps(OPEN_GAPS, bench, "all_none", "text", "all_models_pass"), "pp"
        )
        image = [gaps(OPEN_GAPS, bench, "all_none", s, "no_model_passes") for s, _, _ in SIZES]
        t.add(
            f"noPassImageMin{B}",
            Fn("min(all_none[image*].no_model_passes)", lambda *v: min(v), *image),
            "pp",
        )
        t.add(
            f"noPassImageMax{B}",
            Fn("max(all_none[image*].no_model_passes)", lambda *v: max(v), *image),
            "pp",
        )
        diffs = gaps(OPEN_GAPS, bench, "size_diffs")
        up = "size_diffs[image14-image12, cluster.lo > 0].est"
        t.add(
            f"sizeDiffMin{B}", Fn("min(" + up + ")", lambda rows: min(up_diffs(rows)), diffs), "pp"
        )
        t.add(
            f"sizeDiffMax{B}", Fn("max(" + up + ")", lambda rows: max(up_diffs(rows)), diffs), "pp"
        )
        if bench == "coderujb":
            lopo = gaps(OPEN_GAPS, bench, "lopo", ANY, "est")
            t.add(f"lopoMin{B}", Fn("min(lopo[].est)", min, lopo), "pp")
            t.add(f"lopoMax{B}", Fn("max(lopo[].est)", max, lopo), "pp")


def contamination_macros(t: Table) -> None:
    for bench, B in BENCHES:
        flagged = gaps(OPEN_CONTAM, bench, "flagged_only", ANY, "est")
        t.add(f"flaggedGapMin{B}", Fn("min(flagged_only[].est)", min, flagged), "pp")
        t.add(f"flaggedGapMax{B}", Fn("max(flagged_only[].est)", max, flagged), "pp")
        t.add(f"copiedItems{B}", gaps(OPEN_CONTAM, bench, "copied_items"), "int")
        shares = gaps(OPEN_CONTAM, bench, "control", ANY, "share_at_or_below")
        high = Fn(
            "count(control[].share_at_or_below >= 0.975)",
            lambda v: sum(x >= 0.975 for x in v),
            shares,
        )
        t.add(f"controlHighModels{B}", high, "int")
        both = gaps(OPEN_CONTAM, bench, "flag2", ANY, "both")
        t.add(f"flagBothMin{B}", Fn("min(flag2[].both)", min, both), "int")
        t.add(f"flagBothMax{B}", Fn("max(flag2[].both)", max, both), "int")
        t.add(f"copiedItemsClaude{B}", gaps(CLAUDE_CONTAM, bench, "copied_items"), "int")
        for name, M in CLAUDE_MODELS:
            flagged_n = gaps(CLAUDE_CONTAM, bench, "flagged", name)
            t.add(f"flagged{M}{B}", flagged_n, "int")
            t.add(
                f"unflagged{M}{B}",
                Fn(
                    "n_items - flagged",
                    lambda n, f: n - f,
                    gaps(CLAUDE_GAPS, bench, "n_items"),
                    flagged_n,
                ),
                "int",
            )
    pairs = [
        s
        for b, _ in BENCHES
        for s in (
            gaps(OPEN_CONTAM, b, "gaps", ANY, "est"),
            gaps(OPEN_CONTAM, b, "gaps", ANY, "all_items"),
        )
    ]
    t.add("contamGaps", Fn("count(gaps[])", lambda *v: sum(map(len, v[::2])), *pairs), "int")
    shrink = Fn(
        "count(gaps[].est > gaps[].all_items)",
        lambda *v: sum(e > a for est, full in zip(v[::2], v[1::2]) for e, a in zip(est, full)),
        *pairs,
    )
    t.add("contamShrinking", shrink, "int")


def reliability_macros(t: Table) -> None:
    for bench, B in BENCHES:
        t.add(f"indentShare{B}", J(LAYOUT, "benchmarks", bench, "share", "mean"), "pp")
        for cond, C in CONDITIONS:
            base = ("benchmarks", bench, "conditions", cond)
            t.add(f"relOne{C}{B}", J(RELIABILITY, *base, "reliability", "1", "median"), "dec2")
            t.add(f"relTwo{C}{B}", J(RELIABILITY, *base, "reliability", "2", "median"), "dec2")
            t.interval(
                f"gFinite{C}{B}",
                lambda k, base=base: J(
                    RELIABILITY, *base, "g_finite", "main", "median" if k == "est" else k
                ),
                "dec2",
            )


def file_macros(t: Table) -> None:
    t.add("harnessSuspects", Csv("audit/harness_suspects.csv"), "int")
    t.add(
        "harnessUnpassable", Csv("audit/harness_suspects.csv", (("passed_by_none", "True"),)), "int"
    )
    t.add("handReadAnswers", Csv("audit/hand_read.csv"), "int")
    # the audit samples were drawn from the 859 DevEval items, before the 2026-11-25 exclusion
    t.add("handReadKept", CsvNotIn("audit/hand_read.csv", "id", EXCLUDED_DEV), "int")
    rerun = "2026-11-25: the 13"
    t.add(
        "handReadFalseFailsKept",
        Md(DECISIONS, rerun, r"regraded with their second block:\*\* (\d+) pass"),
        "int",
    )
    t.add("gapGrowthLo", Md(DECISIONS, rerun, r"gaps grow by ([\d.]+)% to [\d.]+% of"), "dec1")
    t.add("gapGrowthHi", Md(DECISIONS, rerun, r"gaps grow by [\d.]+% to ([\d.]+)% of"), "dec1")
    excluded = J(OPEN_GAPS, "benchmarks", "deveval", "excluded", "count")
    t.add("excludedDev", excluded, "int")
    n_dev = J(OPEN_GAPS, "benchmarks", "deveval", "n_items")
    n_ujb = J(OPEN_GAPS, "benchmarks", "coderujb", "n_items")
    t.add(
        "nItemsDevOriginal",
        Fn("deveval n_items + excluded.count", lambda a, b: a + b, n_dev, excluded),
        "int",
    )
    t.add(
        "nItemsAll",
        Fn("coderujb n_items + deveval n_items", lambda a, b: a + b, n_ujb, n_dev),
        "int",
    )
    t.add("relFits", J(RELIABILITY, "gate", "fits"), "int")
    t.add("relFitsPassed", J(RELIABILITY, "gate", "passed"), "int")
    for bench, B in BENCHES:
        floors = [
            J(OPEN_GAPS, "benchmarks", bench, "all_none", c, "no_model_passes") for c, _, _ in SIZES
        ]
        t.add(
            f"floorImageMin{B}",
            Fn("min(all_none[image*].no_model_passes)", lambda *v: min(v), *floors),
            "pp",
        )
        t.add(
            f"floorImageMax{B}",
            Fn("max(all_none[image*].no_model_passes)", lambda *v: max(v), *floors),
            "pp",
        )
    t.add("neverPassedChecked", Csv("audit/never_passed_check.csv"), "int")
    t.add("bootReps", J(OPEN_GAPS, "settings", "n_boot"), "int")
    t.add("glmmTmbVersion", J(OPEN_GLMM, "settings", "glmmTMB"), "version")
    t.add("rVersion", J(OPEN_GLMM, "settings", "R"), "version")
    none_of_seven = [
        Md(
            "audit/summary.md",
            "Items no model passes",
            rf"^\| {b} \| \d+ \| \d+ \| \d+ \| (\d+) \|$",
        )
        for b, _ in BENCHES
    ]
    harness = Csv("audit/harness_suspects.csv", (("passed_by_none", "True"),))
    t.add(
        "neverPassedAllSevenKept",
        Fn(
            "sum(passed by none of the 7) - harness suspects passed by none",
            lambda h, *xs: sum(int(x) for x in xs) - h,
            harness,
            *none_of_seven,
        ),
        "int",
    )
    t.add(
        "neverPassedAllSeven",
        Fn("sum(passed by none of the 7)", lambda *xs: sum(int(x) for x in xs), *none_of_seven),
        "int",
    )
    t.add(
        "neverPassedTestBug", Csv("audit/never_passed_check.csv", (("label", "test_bug"),)), "int"
    )
    summary = "audit/summary.md"
    for name, pattern, fmt in (
        ("handReadFalseFails", r"^False fails: (\d+) of \d+, ", "int"),
        ("handReadOf", r"^False fails: \d+ of (\d+), ", "int"),
        ("handReadPct", r"^False fails: \d+ of \d+, ([\d.]+)% \(exact", "dec1"),
        ("handReadCiLo", r"\(exact 95% CI ([\d.]+)% to ", "dec1"),
        ("handReadCiHi", r"\(exact 95% CI [\d.]+% to ([\d.]+)%\)", "dec1"),
    ):
        t.add(name, Md(summary, "Hand read", pattern), fmt)
    va, checklist, checks = "docs/validity_audit.md", "2. Book 13.5 checklist", "6. New checks"
    for name, pattern in (
        ("checklistYes", r"^Count: Yes (\d+) \("),
        ("checklistPartly", r"\), Partly (\d+) \("),
        ("checklistNo", r"\), No (\d+) \("),
        ("checklistNA", r"\), N/A (\d+) \("),
    ):
        t.add(name, Md(va, checklist, pattern), "int")
    t.add("harnessShrinkPct", Md(va, checks, r"about (\d+\.\d+)% of its size"), "dec1")
    t.add("underspecifiedItems", Md(va, checks, r"^- (\d+) are under-specified"), "int")
    t.add("underspecifiedOf", Md(va, checks, r"Of (\d+) drawn, 9 are labeled"), "int")
    b1, why = "block1/findings.md", "Why image answers fail"
    t.add("nameErrorGrowthPoints", Md(b1, why, r"missing names grow by (\d+) points"), "int")
    t.add("nameErrorNearCopies", Md(b1, why, r"About (\d+) DevEval image answers"), "int")


def corr_pairs(bench: str) -> list[J]:
    """Observed and reference lower limit of the text~image Pearson correlation, by size."""
    out = []
    for _, _, px in SIZES:
        pair = ("correlation", "pearson", f"text~image{px}")
        out += [gaps(OPEN_GLMM, bench, *pair, "observed"), gaps(OPEN_GLMM, bench, *pair, "lo")]
    return out


def count_below(*v: float) -> int:
    return sum(obs < lo for obs, lo in zip(v[::2], v[1::2]))


def missing_name_pattern(i: int) -> str:
    cells = [r"\s*(\d+)%\s*" if j == i else r"\s*\d+%\s*" for j in range(4)]
    return r"^\| Missing name [^|]*\|" + r"\|".join(cells) + r"\|$"


def results_macros(t: Table) -> None:
    """Ranges and one-off numbers that the results prose (section 4) quotes."""
    diffs = [gaps(OPEN_GAPS, b, "size_diffs") for b, _ in BENCHES]
    for name, pick in (("sizeDiffMinAll", min), ("sizeDiffMaxAll", max)):
        label = f"{pick.__name__}(size_diffs[image14-image12, cluster.lo > 0].est), both benchmarks"
        t.add(
            name,
            Fn(label, lambda *v, pick=pick: pick(x for rows in v for x in up_diffs(rows)), *diffs),
            "pp",
        )
    for bench, B in BENCHES:
        base = ("benchmarks", bench, "conditions")
        for k, word in (("1", "One"), ("2", "Two"), ("3", "Three")):
            rel = [J(RELIABILITY, *base, c, "reliability", k, "median") for c, _ in CONDITIONS]
            t.add(
                f"rel{word}Min{B}",
                Fn(f"min(reliability[{k}].median)", lambda *v: min(v), *rel),
                "dec2",
            )
            t.add(
                f"rel{word}Max{B}",
                Fn(f"max(reliability[{k}].median)", lambda *v: max(v), *rel),
                "dec2",
            )
        conds = [c for c, _ in CONDITIONS if not (bench == "coderujb" and c == "image12")]
        g = [J(RELIABILITY, *base, c, "g_finite", "main", "median") for c in conds]
        scope = "all conditions but CoderUJB image12"
        t.add(f"gFiniteMin{B}", Fn(f"min(g_finite.median), {scope}", lambda *v: min(v), *g), "dec2")
        t.add(f"gFiniteMax{B}", Fn(f"max(g_finite.median), {scope}", lambda *v: max(v), *g), "dec2")
        pair = Sel("pair", str(["Gemma 4 12B", "Qwen3.5 9B"]))
        t.add(
            f"swapGemmaQwenNine{B}", J(RELIABILITY, "benchmarks", bench, "swap", pair, "p"), "dec2"
        )
        t.add(
            f"corrBelowRef{B}",
            Fn(
                "count(pearson text~image observed < reference lo)", count_below, *corr_pairs(bench)
            ),
            "int",
        )
        for name, M in CLAUDE_MODELS:
            ceiling = gaps(CLAUDE_GAPS, bench, "floor_ceiling", name, "text", "all")
            t.add(f"ceilingText{M}{B}", ceiling, "pp")
    t.add(
        "claudeTemperature", Md("claude/findings.md", "", r"sample at temperature (\d\.\d)"), "dec1"
    )
    closed, cf = "Open vs closed", "claude/findings.md"
    for title, B in (("CoderUJB", "Ujb"), ("DevEval", "Dev")):
        row = rf"^\| {title} \| "
        skip = r"-?[\d.]+ \| [\d.]+ \| "
        t.add(f"openClosedC{B}", Md(cf, closed, row + r"(-?[\d.]+) \|"), "dec2")
        t.add(f"openClosedC{B}Lo", Md(cf, closed, row + skip + r"\[(-?[\d.]+), "), "dec2")
        t.add(f"openClosedC{B}Hi", Md(cf, closed, row + skip + r"\[-?[\d.]+, (-?[\d.]+)\]"), "dec2")
    b1, why, pilot = "block1/findings.md", "Why image answers fail", "Why the pilot showed no gap"
    head = r"^Block 1 of the main run \(UFM-20\): "
    for name, section, pattern in (
        ("blockOneItemsDev", "", head + r"(\d+) DevEval and \d+ CoderUJB items"),
        ("blockOneItemsUjb", "", head + r"\d+ DevEval and (\d+) CoderUJB items"),
        ("blockOneLossMin", "Pass rates", r"Every model loses (\d+) to \d+ points on images"),
        ("blockOneLossMax", "Pass rates", r"Every model loses \d+ to (\d+) points on images"),
        ("lengthGapShort", why, r"items of 1 to 2 pages lose (\d+) points"),
        ("lengthGapLong", why, r"items of 3 or more pages lose (\d+)\."),
        ("nameErrorTextNearCopies", why, r"only by underscores[\s\S]*?against (\d+) on text"),
        ("pilotProblems", pilot, r"(\d+) HumanEval problems\) passed"),
        ("pilotTextPass", pilot, r"passed (\d+) of \d+ on text and"),
        ("pilotImagePass", pilot, r"on text and (\d+) of \d+ at packed"),
        ("pilotOf", pilot, r"passed \d+ of (\d+) on text and"),
    ):
        t.add(name, Md(b1, section, pattern), "int")
    for i, name in enumerate(("nameDevText", "nameDevImage", "nameUjbText", "nameUjbImage")):
        t.add(name, Md(b1, why, missing_name_pattern(i)), "int")


def macros(src: Sources) -> list[Macro]:
    t = Table()
    model_macros(t, repos(src))
    summary_macros(t)
    glmm_macros(t)
    gap_detail_macros(t)
    contamination_macros(t)
    reliability_macros(t)
    file_macros(t)
    results_macros(t)
    return t.rows


def up_diffs(rows: list[dict]) -> list[float]:
    """The 14 px minus 12 px differences whose cluster interval is above 0."""
    return [r["est"] for r in rows if r["pair"] == "image14-image12" and r["cluster"]["lo"] > 0]


def main_rows(src: Sources) -> list[tuple[str, dict]]:
    return [(b, r) for b, _ in BENCHES for r in src.json(OPEN_GAPS)["benchmarks"][b]["main"]]


def check_main_gaps_negative(src: Sources) -> bool:
    return all(r["cluster"]["hi"] < 0 for _, r in main_rows(src))


def check_deveval_heldout(src: Sources) -> bool:
    folds = src.json(OPEN_GLMM)["benchmarks"]["deveval"]["heldout"]["folds"]
    return len(folds) == 10 and all(f["full"] - f["reduced"] > 0 for f in folds)


def check_coderujb_heldout(src: Sources) -> bool:
    h = src.json(OPEN_GLMM)["benchmarks"]["coderujb"]["heldout"]
    return abs(h["diff"]) < 1.96 * h["se"]


def check_no_bh_flags(src: Sources) -> bool:
    return all(
        src.json(OPEN_GLMM)["benchmarks"][b]["item_flags"]["bh_flagged"] == 0 for b, _ in BENCHES
    )


def contamination_gaps(src: Sources) -> list[dict]:
    return [g for b, _ in BENCHES for g in src.json(OPEN_CONTAM)["benchmarks"][b]["gaps"]]


def check_contamination_shrinks(src: Sources) -> bool:
    gs = contamination_gaps(src)
    return (
        len(gs) == 40
        and all(g["est"] < 0 for g in gs)
        and sum(g["est"] > g["all_items"] for g in gs) == 39
    )


def check_control_share(src: Sources) -> bool:
    return all(
        sum(
            c["share_at_or_below"] >= 0.975
            for c in src.json(OPEN_CONTAM)["benchmarks"][b]["control"].values()
        )
        == 3
        for b, _ in BENCHES
    )


SIZE_UP = {
    ("coderujb", "Qwen3.5 27B"),
    ("deveval", "Qwen3.5 27B"),
    ("deveval", "Mistral Small 3.2 24B"),
    ("deveval", "Qwen3.5 9B"),
}


def check_size_up(src: Sources) -> bool:
    got = {
        (b, d["model"])
        for b, _ in BENCHES
        for d in src.json(OPEN_GAPS)["benchmarks"][b]["size_diffs"]
        if d["pair"] == "image14-image12" and d["cluster"]["lo"] > 0
    }
    return got == SIZE_UP


def check_gemma_tokens(src: Sources) -> bool:
    for b, _ in BENCHES:
        B = src.json(OPEN_GAPS)["benchmarks"][b]
        ratios = {m: t["mean_over_sizes"] for m, t in B["token_ratio"].items()}
        if min(ratios, key=ratios.get) != "Gemma 4 12B":
            return False
        for d in B["size_diffs"]:
            if d["model"] == "Gemma 4 12B" and not d["cluster"]["lo"] < 0 < d["cluster"]["hi"]:
                return False
    return True


def check_floor_smallest(src: Sources) -> bool:
    """Qwen2.5-VL has the smallest gap and the smallest logit contrast of the 5 in both benchmarks."""
    repo = repos(src)
    for b, _ in BENCHES:
        gap = {r["model"]: abs(r["est"]) for r in src.json(OPEN_GAPS)["benchmarks"][b]["main"]}
        con = {c["model"]: abs(c["est"]) for c in src.json(OPEN_GLMM)["benchmarks"][b]["contrast"]}
        vl = "Qwen2.5-VL 7B"
        if min(gap, key=gap.get) != vl or min(con, key=con.get) != repo[vl]:
            return False
    return True


def check_lopo_negative(src: Sources) -> bool:
    rows = src.json(OPEN_GAPS)["benchmarks"]["coderujb"]["lopo"]
    return len(rows) == 20 and all(r["cluster"]["hi"] < 0 for r in rows)


def check_corr_below(src: Sources) -> bool:
    """Observed text~image correlation under the reference band in 5 of 6 pairs; CoderUJB 14 px is not."""
    out = {}
    for b, _ in BENCHES:
        corr = src.json(OPEN_GLMM)["benchmarks"][b]["correlation"]["pearson"]
        for _, _, px in SIZES:
            c = corr[f"text~image{px}"]
            out[(b, px)] = c["observed"] < c["lo"]
    return sum(out.values()) == 5 and not out[("coderujb", 14)]


def check_c_above_reference(src: Sources) -> bool:
    return all(
        src.json(OPEN_GLMM)["benchmarks"][b]["correlation"]["pearson"]["C"]["observed"]
        > src.json(OPEN_GLMM)["benchmarks"][b]["correlation"]["pearson"]["C"]["hi"]
        for b, _ in BENCHES
    )


def check_g_finite(src: Sources) -> bool:
    """CoderUJB 12 px has the lowest G of its benchmark; every DevEval G is above 0.9."""
    cond = src.json(RELIABILITY)["benchmarks"]
    ujb = {c: v["g_finite"]["main"]["median"] for c, v in cond["coderujb"]["conditions"].items()}
    dev = [v["g_finite"]["main"]["median"] for v in cond["deveval"]["conditions"].values()]
    return min(ujb, key=ujb.get) == "image12" and all(x > 0.9 for x in dev)


def check_ranks(src: Sources) -> bool:
    """Qwen3.5 27B is first in every condition; Qwen2.5-VL is last in text; both benchmarks."""
    for b, _ in BENCHES:
        ranks = src.json(RELIABILITY)["benchmarks"][b]["ranks"]
        if any(
            ranks[c]["Qwen3.5 27B"]["rank"] != 1 for c in ("text", "image10", "image12", "image14")
        ):
            return False
        if ranks["text"]["Qwen2.5-VL 7B"]["rank"] != 5:
            return False
    return True


def check_item_variation_evidence(src: Sources) -> bool:
    """The item:condition SD profile interval is above 0 and the LRT p is below 0.05 in both benchmarks."""
    return all(
        g["item_condition_sd"]["lo"] > 0 and g["lrt"]["p"] < 0.05
        for g in (src.json(OPEN_GLMM)["benchmarks"][b] for b, _ in BENCHES)
    )


def check_claude_text_rates_equal(src: Sources) -> bool:
    rates = src.json(CLAUDE_GAPS)["benchmarks"]["coderujb"]["rates"]["text"]
    return fmt_pp(rates["Claude Sonnet 5.5"]) == fmt_pp(rates["Claude Opus 5.5"])


def check_flagged_lose_more(src: Sources) -> bool:
    """On flagged items every model loses more and passes more in text than on the rest."""
    return all(
        f["est"] < f["gap_rest"] and f["text_flagged"] > f["text_rest"]
        for b, _ in BENCHES
        for f in src.json(OPEN_CONTAM)["benchmarks"][b]["flagged_only"]
    ) and all(len(src.json(OPEN_CONTAM)["benchmarks"][b]["flagged_only"]) == 5 for b, _ in BENCHES)


def check_claude_gaps_negative(src: Sources) -> bool:
    rows = [r for b, _ in BENCHES for r in src.json(CLAUDE_GAPS)["benchmarks"][b]["main"]]
    return len(rows) == 4 and all(r["cluster"]["hi"] < 0 for r in rows)


def check_claude_c_positive(src: Sources) -> bool:
    cf, closed = "claude/findings.md", "Open vs closed"
    for title in ("CoderUJB", "DevEval"):
        pattern = rf"^\| {title} \| -?[\d.]+ \| [\d.]+ \| \[(-?[\d.]+), "
        if float(src.value(Md(cf, closed, pattern))) <= 0:
            return False
    return True


def check_harness_suspects_excluded(src: Sources) -> bool:
    flagged = {
        r["item"] for r in src.rows("audit/harness_suspects.csv") if r["passed_by_none"] == "True"
    }
    return bool(flagged) and flagged <= src.ids(EXCLUDED_DEV)


def check_gate_failures_on_model_variance_only(src: Sources) -> bool:
    rows = src.json(RELIABILITY)["gate"]["rows"]
    failed = [r for r in rows if r["gate"] != "pass"]
    off = [
        r
        for r in failed
        if r["component"] != "s2_model" and (float(r["psrf"]) > 1.05 or float(r["ess"]) < 400)
    ]
    return bool(failed) and not off


def check_hand_read_false_fails_excluded(src: Sources) -> bool:
    out = src.ids(EXCLUDED_DEV)
    return all(
        r["id"] in out for r in src.rows("audit/hand_read.csv") if r["label"] == "false_fail"
    )


PREDICATES: tuple[tuple[str, Callable[[Sources], bool]], ...] = (
    (
        "every harness suspect passed by none of the 7 is in the DevEval exclusion list",
        check_harness_suspects_excluded,
    ),
    (
        "the reliability fits that fail the gate fail on s2_model only (PSRF <= 1.05, ESS >= 400 elsewhere)",
        check_gate_failures_on_model_variance_only,
    ),
    (
        "both hand-read false fails are on excluded items, so the 846-item base keeps none",
        check_hand_read_false_fails_excluded,
    ),
    ("all 10 main gaps have a cluster interval entirely below 0", check_main_gaps_negative),
    (
        "DevEval held-out log-likelihood, full minus reduced, is positive in all 10 folds",
        check_deveval_heldout,
    ),
    (
        "CoderUJB held-out difference is indistinguishable from 0 (|diff| < 1.96 se)",
        check_coderujb_heldout,
    ),
    ("no item survives the BH correction in either benchmark", check_no_bh_flags),
    ("39 of 40 contamination gaps shrink and all 40 stay negative", check_contamination_shrinks),
    ("control share at or below >= 0.975 for 3 of 5 models in each benchmark", check_control_share),
    (
        "14 px beats 12 px with cluster lo > 0 for exactly Qwen3.5 27B (both), Mistral and Qwen3.5 9B (DevEval)",
        check_size_up,
    ),
    (
        "Gemma has the lowest token ratio in both benchmarks and no size difference with an interval off 0",
        check_gemma_tokens,
    ),
    (
        "Qwen2.5-VL has the smallest gap and the smallest logit contrast of the 5 in both benchmarks",
        check_floor_smallest,
    ),
    (
        "all 20 CoderUJB leave-one-project-out gaps have a cluster interval entirely below 0",
        check_lopo_negative,
    ),
    (
        "text~image correlation is under the reference band in 5 of 6 pairs, not CoderUJB 14 px",
        check_corr_below,
    ),
    ("C (Pearson) is above its reference band in both benchmarks", check_c_above_reference),
    (
        "G (finite) is lowest at CoderUJB 12 px and above 0.9 in every DevEval condition",
        check_g_finite,
    ),
    (
        "Qwen3.5 27B ranks first in every condition and Qwen2.5-VL last in text, both benchmarks",
        check_ranks,
    ),
    (
        "on flagged items all 10 models-and-benchmarks lose more and pass more in text than the rest",
        check_flagged_lose_more,
    ),
    ("all 4 Claude cluster intervals are entirely below 0", check_claude_gaps_negative),
    (
        "the item:condition SD profile interval is above 0 and the LRT p is below 0.05 in both benchmarks",
        check_item_variation_evidence,
    ),
    (
        "Sonnet and Opus have the same CoderUJB text pass rate at the printed precision",
        check_claude_text_rates_equal,
    ),
    (
        "the open-vs-closed contrast c has a lower limit above 0 in both benchmarks",
        check_claude_c_positive,
    ),
)


def cell(gap: dict) -> str:
    return f"{fmt_pp(gap['est'])} " + fmt_ci(
        fmt_pp(gap["cluster"]["lo"]), fmt_pp(gap["cluster"]["hi"])
    )


TABLE_HEAD = r"""\begin{{tabular}}{{{spec}}}
\toprule
{header} \\
\midrule
"""


def tab_models(src: Sources, gaps_file: str, glmm_file: str, models: tuple, mean: bool) -> str:
    repo = repos(src)
    ncol = 7
    header = (
        r"Modelo & Texto (\%) & Gap (pp) & IC 95\% & Contraste (logit) & IC 95\% & Razão de tokens"
    )
    lines = [TABLE_HEAD.format(spec="lrrcrcr", header=header).rstrip("\n")]
    for i, (bench, _) in enumerate(BENCHES):
        B = src.json(gaps_file)["benchmarks"][bench]
        if i:
            lines.append(r"\midrule")
        lines.append(
            rf"\multicolumn{{{ncol}}}{{l}}{{\emph{{{BENCH_TITLE[bench]}, {B['n_items']} itens}}}} \\"
        )
        contrasts = {c["model"]: c for c in src.json(glmm_file)["benchmarks"][bench]["contrast"]}
        for name, _ in models:
            (row,) = [r for r in B["main"] if r["model"] == name]
            c = contrasts[repo[name]]
            lines.append(
                " & ".join(
                    [
                        name,
                        fmt_pp(B["rates"]["text"][name]),
                        fmt_pp(row["est"]),
                        fmt_ci(fmt_pp(row["cluster"]["lo"]), fmt_pp(row["cluster"]["hi"])),
                        plain(c["est"], 2),
                        fmt_ci(plain(c["lo"], 2), plain(c["hi"], 2)),
                        plain(B["token_ratio"][name]["mean_over_sizes"], 2),
                    ]
                )
                + r" \\"
            )
        if mean:
            p = B["pooled"]
            lines.append(
                " & ".join(
                    [
                        r"\emph{Média dos modelos}",
                        "",
                        fmt_pp(p["est"]),
                        fmt_ci(fmt_pp(p["lo"]), fmt_pp(p["hi"])),
                        "",
                        "",
                        "",
                    ]
                )
                + r" \\"
            )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    return "\n".join(lines)


def tab_sizes(src: Sources) -> str:
    return _tab_by_model(
        src,
        "size",
        "sizes",
        [f"{px} px" for _, _, px in SIZES],
        lambda r: r["size"],
        [s for s, _, _ in SIZES],
    )


def tab_size_diffs(src: Sources) -> str:
    pairs = ["image12-image10", "image14-image10", "image14-image12"]
    labels = [f"{p[5:7]} {MINUS} {p[-2:]} px".replace("image", "") for p in pairs]
    return _tab_by_model(src, "pair", "size_diffs", labels, lambda r: r["pair"], pairs)


def _tab_by_model(src, key, field, labels, get_key, keys) -> str:
    del key
    lines = [TABLE_HEAD.format(spec="lccc", header="Modelo & " + " & ".join(labels)).rstrip("\n")]
    for i, (bench, _) in enumerate(BENCHES):
        B = src.json(OPEN_GAPS)["benchmarks"][bench]
        if i:
            lines.append(r"\midrule")
        lines.append(rf"\multicolumn{{4}}{{l}}{{\emph{{{BENCH_TITLE[bench]}}}}} \\")
        for name, _ in OPEN_MODELS:
            cells = []
            for k in keys:
                (r,) = [x for x in B[field] if x["model"] == name and get_key(x) == k]
                cells.append(cell(r))
            lines.append(" & ".join([name, *cells]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    return "\n".join(lines)


def generate(src: Sources) -> tuple[str, dict[str, str], list[str]]:
    errors: list[str] = []
    for sentence, check in PREDICATES:
        try:
            ok = check(src)
        except (SourceError, KeyError, TypeError, ValueError) as e:
            errors.append(f"predicate: {sentence}: {e!r}")
            continue
        if not ok:
            errors.append(f"predicate no longer holds: {sentence}")

    lines = ["% generated by paper/build_numbers.py, do not edit"]
    names: set[str] = set()
    count = 0
    try:
        declared = macros(src)
    except (SourceError, KeyError) as e:
        return "", {}, errors + [f"macro table: {e!r}"]
    for m in declared:
        if not re.fullmatch(r"[A-Za-z]+", m.name) or m.name in names:
            errors.append(f"macro {m.name}: not letters only or declared twice")
            continue
        names.add(m.name)
        try:
            value = FORMATS[m.fmt](src.value(m.source))
        except (SourceError, KeyError, TypeError, ValueError, IndexError) as e:
            errors.append(f"macro \\{m.name} from {m.source.describe()}: {e!r}")
            continue
        lines.append(rf"\newcommand{{\{m.name}}}{{{value}\xspace}}")
        count += 1

    tables: dict[str, str] = {}
    for name, build in (
        ("tab_gaps", lambda: tab_models(src, OPEN_GAPS, OPEN_GLMM, OPEN_MODELS, True)),
        ("tab_claude", lambda: tab_models(src, CLAUDE_GAPS, CLAUDE_GLMM, CLAUDE_MODELS, False)),
        ("tab_sizes", lambda: tab_sizes(src)),
        ("tab_size_diffs", lambda: tab_size_diffs(src)),
    ):
        try:
            tables[name] = build()
        except (SourceError, KeyError, TypeError, ValueError, IndexError) as e:
            errors.append(f"table {name}: {e!r}")
    return "\n".join(lines) + "\n", tables, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--root", type=Path, default=ROOT, help="repo root holding results/ and docs/")
    args = ap.parse_args(argv)
    numbers, tables, errors = generate(Sources(args.root))
    if errors:
        print("build_numbers failed:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    (args.out / "tables").mkdir(parents=True, exist_ok=True)
    (args.out / "numbers.tex").write_text(numbers, encoding="utf-8")
    for name, body in tables.items():
        (args.out / "tables" / f"{name}.tex").write_text(body, encoding="utf-8")
    n = numbers.count(r"\newcommand")
    print(f"numbers.tex: {n} macros; tables: {' '.join(sorted(tables))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
