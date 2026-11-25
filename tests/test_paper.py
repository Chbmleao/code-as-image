import copy
import csv
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import pytest
from conftest import ROOT, need

PAPER = os.path.join(ROOT, "paper")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(PAPER, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bn = load("build_numbers")
bld = load("build")

MINUS = bn.MINUS
EM_DASH = "\u2014"
SOURCE_FILES = [
    "analysis/gaps.json", "analysis/glmm.json", "analysis/contamination.json",
    "claude/analysis/gaps.json", "claude/analysis/glmm.json", "claude/analysis/contamination.json",
    "reliability/reliability.json", "layout/layout.json", "block1/findings.md",
    "audit/summary.md", "audit/harness_suspects.csv", "audit/hand_read.csv",
    "audit/never_passed_check.csv",
]


def need_results():
    for rel in SOURCE_FILES + ["../docs/validity_audit.md"]:
        need(os.path.join(ROOT, "results", rel))


@pytest.fixture(scope="module")
def values():
    need_results()
    src = bn.Sources(ROOT)
    return {m.name: bn.FORMATS[m.fmt](src.value(m.source)) for m in bn.macros(src)}


@pytest.fixture
def tree(tmp_path):
    """A repo root with just the files build_numbers reads, free to edit."""
    need_results()
    for rel in SOURCE_FILES:
        dst = tmp_path / "results" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(ROOT, "results", rel), dst)
    (tmp_path / "docs").mkdir()
    shutil.copy(os.path.join(ROOT, "docs", "validity_audit.md"), tmp_path / "docs")
    return tmp_path


def run_script(name, *args):
    return subprocess.run(
        [sys.executable, os.path.join(PAPER, name), *args], check=False, capture_output=True, text=True
    )


# formatting

def test_pp_uses_one_decimal_decimal_comma_and_math_minus():
    assert bn.fmt_pp(-0.316585) == MINUS + "31,7"
    assert bn.fmt_pp(0.54) == "54,0"
    assert bn.fmt_pp(-0.0004) == "0,0"
    assert bn.fmt_ci(bn.fmt_pp(-0.320448), bn.fmt_pp(-0.237048)) == f"[{MINUS}32,0; {MINUS}23,7]"


def test_two_and_three_decimals():
    assert bn.FORMATS["dec2"](-4.04727) == MINUS + "4,05"
    assert bn.FORMATS["dec2"](0.46) == "0,46"
    assert bn.FORMATS["dec3"](0.997) == "0,997"
    assert bn.FORMATS["dec3"](1) == "1,000"


def test_p_values_two_significant_figures_and_scientific_below_a_thousandth():
    assert bn.fmt_p(0.00439) == "0,0044"
    assert bn.fmt_p(0.0323) == "0,032"
    assert bn.fmt_p(0.5) == "0,50"
    assert bn.fmt_p(9.14e-21) == r"$9{,}1 \times 10^{-21}$"
    assert bn.fmt_p(1.01e-05) == r"$1{,}0 \times 10^{-5}$"
    with pytest.raises(ValueError):
        bn.fmt_p(0)


def test_integers_must_be_whole():
    assert bn.FORMATS["int"](12) == "12"
    with pytest.raises(ValueError):
        bn.FORMATS["int"](12.5)


# determinism

def test_generators_are_byte_identical_across_runs(tmp_path):
    need_results()
    outs = [tmp_path / "a", tmp_path / "b"]
    for out in outs:
        for script in ("build_numbers.py", "build_figures.py"):
            res = run_script(script, "--out", str(out))
            assert res.returncode == 0, res.stderr
    files = sorted(p.relative_to(outs[0]) for p in outs[0].rglob("*") if p.is_file())
    assert [f.name for f in files if f.suffix == ".pdf"] == [
        "fig_gap.pdf", "fig_item_corr.pdf", "fig_size_tokens.pdf"
    ]
    assert "numbers.tex" in [f.name for f in files]
    for f in files:
        assert (outs[0] / f).read_bytes() == (outs[1] / f).read_bytes(), f


# cross-check against the findings tables

def findings_rows(path, section, subsection, first_cell=""):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    flags = re.MULTILINE | re.DOTALL
    sec = re.search(rf"^## {re.escape(section)}\n.*?(?=^## |\Z)", text, flags).group(0)
    sub = re.search(rf"^### {re.escape(subsection)}\n.*?(?=^### |\Z)", sec, flags).group(0)
    rows, in_gap_table = [], False
    for ln in sub.splitlines():
        if not ln.startswith("|"):
            in_gap_table = False
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if cells[:4] == ["Model", "Text %", "Gap pp", "Cluster 95% CI"]:
            in_gap_table = True
        elif in_gap_table and not set(cells[0]) <= set("-") and cells[0].startswith(first_cell):
            rows.append(cells)
    return rows


def as_paper(cells):
    """Text %, gap and interval of a findings row, through the paper's formatter."""
    pct = bn.FORMATS["pp"](float(cells[1]) / 100) if cells[1] else None
    gap = bn.FORMATS["pp"](float(cells[2]) / 100)
    lo, hi = (bn.FORMATS["pp"](float(x) / 100) for x in cells[3].strip("[]").split(","))
    return pct, gap, lo, hi


def test_main_gaps_match_the_findings_table(values):
    path = os.path.join(ROOT, "results", "analysis", "findings.md")
    short = dict(bn.OPEN_MODELS)
    for bench, B in bn.BENCHES:
        rows = findings_rows(path, "Gaps", bn.BENCH_TITLE[bench])
        seen = 0
        for cells in rows:
            if cells[0] == "Mean of models":
                _, gap, lo, hi = as_paper(cells)
                assert (gap, lo, hi) == tuple(values[f"gapMean{B}{k}"] for k in ("", "Lo", "Hi"))
                continue
            if cells[0] not in short:
                continue
            M = short[cells[0]]
            pct, gap, lo, hi = as_paper(cells)
            assert pct == values[f"textRate{M}{B}"], (bench, cells[0])
            assert (gap, lo, hi) == tuple(values[f"gap{M}{B}{k}"] for k in ("", "Lo", "Hi"))
            seen += 1
        assert seen == 5


def test_claude_gaps_match_the_claude_findings(values):
    path = os.path.join(ROOT, "results", "claude", "findings.md")
    short = dict(bn.CLAUDE_MODELS)
    seen = 0
    for bench, B in bn.BENCHES:
        for cells in findings_rows(path, "Claude gaps", bn.BENCH_TITLE[bench], "Claude "):
            M = short[cells[0]]
            pct, gap, lo, hi = as_paper(cells)
            assert pct == values[f"textRate{M}{B}"]
            assert (gap, lo, hi) == tuple(values[f"gap{M}{B}{k}"] for k in ("", "Lo", "Hi"))
            seen += 1
    assert seen == 4


# derived macros, recomputed from the JSON

def test_derived_macros_are_recomputed_from_the_json(values):
    def results(rel):
        with open(os.path.join(ROOT, "results", rel), encoding="utf-8") as f:
            return json.load(f)

    gaps, contam = results(bn.OPEN_GAPS), results(bn.OPEN_CONTAM)
    glmm, claude = results(bn.OPEN_GLMM), results(bn.CLAUDE_GAPS)
    for bench, B in bn.BENCHES:
        est = [r["est"] for r in gaps["benchmarks"][bench]["main"]]
        assert values[f"gapMin{B}"] == bn.fmt_pp(min(est))
        assert values[f"gapMax{B}"] == bn.fmt_pp(max(est))
        shares = [c["share_at_or_below"] for c in contam["benchmarks"][bench]["control"].values()]
        assert values[f"controlHighModels{B}"] == str(sum(s >= 0.975 for s in shares)) == "3"
    gs = [g for b in contam["benchmarks"].values() for g in b["gaps"]]
    assert values["contamGaps"] == "40"
    assert values["contamShrinking"] == str(sum(g["est"] > g["all_items"] for g in gs)) == "39"
    folds = glmm["benchmarks"]["deveval"]["heldout"]["folds"]
    assert values["heldoutPositiveFoldsDev"] == str(sum(f["full"] > f["reduced"] for f in folds))
    loss = [r["est"] for b in claude["benchmarks"].values() for r in b["main"]]
    assert values["claudeLossMinAll"] == bn.fmt_pp(-max(loss))
    assert values["claudeLossMaxAll"] == bn.fmt_pp(-min(loss))
    path = os.path.join(ROOT, "results", "audit", "harness_suspects.csv")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert values["harnessUnpassable"] == str(sum(r["passed_by_none"] == "True" for r in rows))
    assert values["harnessUnpassable"] == "12"
    assert values["sizeDiffMinDev"] == "4,1" and values["sizeDiffMaxUjb"] == "8,8"


def test_macro_names_are_letters_only_and_unique():
    need_results()
    names = [m.name for m in bn.macros(bn.Sources(ROOT))]
    assert len(names) == len(set(names))
    assert all(re.fullmatch("[A-Za-z]+", n) for n in names)
    assert {"gapQwenTwentySevenDev", "gapQwenTwentySevenDevLo", "textRateGemmaTwelveUjb"} <= set(
        names
    )


# prose predicates and missing sources

def test_a_violated_predicate_stops_the_build_and_names_the_sentence(tree):
    path = tree / "results" / "analysis" / "gaps.json"
    data = json.loads(path.read_text())
    data["benchmarks"]["deveval"]["main"][0]["cluster"]["hi"] = 0.01
    path.write_text(json.dumps(data))
    res = run_script("build_numbers.py", "--root", str(tree), "--out", str(tree / "out"))
    assert res.returncode != 0
    assert "all 10 main gaps have a cluster interval entirely below 0" in res.stderr
    assert not (tree / "out" / "numbers.tex").exists()


def test_each_predicate_fails_on_its_own_violation():
    need_results()
    src = bn.Sources(ROOT)
    assert bn.generate(src)[2] == []
    gaps = copy.deepcopy(src.json(bn.OPEN_GAPS))
    glmm = copy.deepcopy(src.json(bn.OPEN_GLMM))
    contam = copy.deepcopy(src.json(bn.OPEN_CONTAM))
    glmm["benchmarks"]["deveval"]["heldout"]["folds"][3]["full"] = -1e9
    glmm["benchmarks"]["coderujb"]["item_flags"]["bh_flagged"] = 1
    contam["benchmarks"]["deveval"]["gaps"][0]["est"] = -9
    contam["benchmarks"]["coderujb"]["control"]["Gemma 4 12B"]["share_at_or_below"] = 0.1
    gaps["benchmarks"]["coderujb"]["size_diffs"][5]["cluster"]["lo"] = 0.01
    broken = bn.Sources(
        ROOT, {bn.OPEN_GAPS: gaps, bn.OPEN_GLMM: glmm, bn.OPEN_CONTAM: contam}
    )
    errors = " ".join(bn.generate(broken)[2])
    for sentence in (
        "positive in all 10 folds",
        "no item survives the BH correction",
        "39 of 40 contamination gaps",
        "3 of 5 models",
        "14 px beats 12 px",
    ):
        assert sentence in errors, sentence


def test_a_missing_source_names_the_macro_and_writes_nothing(tree):
    (tree / "results" / "audit" / "harness_suspects.csv").unlink()
    res = run_script("build_numbers.py", "--root", str(tree), "--out", str(tree / "out"))
    assert res.returncode != 0
    assert "harnessUnpassable" in res.stderr
    assert not (tree / "out").exists()


def test_a_regex_must_match_exactly_once(tree):
    md = tree / "docs" / "validity_audit.md"
    md.write_text(md.read_text().replace("Count: Yes 6 (", "Count: Yes 7 (1)\nCount: Yes 6 (", 1))
    res = run_script("build_numbers.py", "--root", str(tree), "--out", str(tree / "out"))
    assert res.returncode != 0
    assert "checklistYes" in res.stderr


def test_markdown_section_and_pattern_anchoring(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "a.md").write_text("## One\n\nn = 3\n\n## Two\n\nn = 4\nn = 5\n")
    src = bn.Sources(tmp_path)
    assert src.value(bn.Md("a.md", "One", r"^n = (\d+)$")) == "3"
    with pytest.raises(bn.SourceError):
        src.value(bn.Md("a.md", "Two", r"^n = (\d+)$"))
    with pytest.raises(bn.SourceError):
        src.value(bn.Md("a.md", "Three", r"^n = (\d+)$"))


# build helpers

TEX = "intro \\todo{explain the gap}\n% \\todo{commented out}\nA word " + EM_DASH + " here\n"


def test_todos_are_listed_with_file_and_line_and_comments_are_skipped():
    assert bld.list_todos(TEX, "sections/x.tex") == [("sections/x.tex", 1, "explain the gap")]
    nested = "\\caption{\\todo{legenda com {chaves}}}\n"
    assert bld.list_todos(nested, "f.tex") == [("f.tex", 1, "legenda com {chaves}")]


def test_typography_hits_flag_dashes_ellipsis_and_curly_quotes():
    assert bld.typography_hits(TEX, "x.tex") == ["x.tex:3: em dash"]
    assert bld.typography_hits("a -- b\n", "x.tex") == ["x.tex:1: double hyphen"]
    assert bld.typography_hits("a --- b\n", "x.tex") == ["x.tex:1: triple hyphen"]
    for ch in ("\u2013", "\u2026", "\u2018", "\u2019", "\u201c", "\u201d"):
        assert bld.typography_hits(f"a{ch}b", "x.tex")
    assert bld.typography_hits("pages 3-5, 1{,}5 \\ensuremath{-}3\n", "x.tex") == []


def test_log_problems_read_undefined_references_citations_and_control_sequences():
    log = (
        "LaTeX Warning: Reference `fig:gap' on page 3 undefined on input line 12.\n"
        "Package natbib Warning: Citation `miller2024errorbars' on page 2 undefined on input line 4.\n"
        "! Undefined control sequence.\n"
    )
    refs, cites, fatal = bld.log_problems(log)
    assert refs == ["fig:gap"] and cites == ["miller2024errorbars"]
    assert fatal == ["! Undefined control sequence."]


AUX = "\\newlabel{body-end}{{7}{%d}{Conclusão e trabalhos futuros}{section.7}{}}\n"


def test_body_end_page_is_read_from_the_aux():
    assert bld.body_end_page(AUX % 9) == 9
    assert bld.body_end_page("\\newlabel{other}{{1}{2}}\n") is None


def test_final_fails_on_page_9_and_passes_on_page_8():
    assert bld.final_failures([], [], [], 9) == ["body ends on page 9, limit is 8"]
    assert bld.final_failures([], [], [], 8) == []
    assert bld.final_failures([("f", 1, "x")], ["a"], [], 8)


@pytest.mark.parametrize(("page", "code"), [(9, 1), (8, 0)])
def test_final_exit_code_follows_the_body_end_page(tmp_path, monkeypatch, page, code):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"")
    monkeypatch.setattr(bld, "run_generator", lambda script: None)
    monkeypatch.setattr(bld, "compile_pdf", lambda: ("", AUX % page, pdf))
    monkeypatch.setattr(bld, "count_pages", lambda p: 12)
    monkeypatch.setattr(bld, "sources", list)
    assert bld.main(["--final"]) == code
    assert bld.main([]) == 0
