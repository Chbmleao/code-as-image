"""Build the presentation banner (UFM-16) from the result files on main.

    uv run python banner/build.py

Writes banner/out/banner.pdf (A4, vector, scales to A1/A0) and banner/out/banner.png. Every number
on the page is read from results/ here; the template only holds wording. Needs Google Chrome (or
CHROME=/path/to/chrome) and pdftoppm.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter, MultipleLocator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT / "results"
FONTS = HERE / "fonts"
ASSETS = HERE / "assets"
OUT = HERE / "out"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

BENCHES = ("coderujb", "deveval")
BENCH_LABEL = {"coderujb": "CoderUJB (Java)", "deveval": "DevEval (Python)"}
COLOR = {"coderujb": "#2468c8", "deveval": "#e0662e"}
GRID = "#dde3ea"

# Design facts that no result file holds as a number, with where they are stated.
SIZES_PX = (10, 12, 14)  # docs/methodology.md 3.1, Conditions
OPEN_TEMPERATURE = 0.7  # docs/decisions.md, Claude addendum (open models at 0.7)
LINE_RUNS = 2  # scripts/analysis.py: the 7-model line uses runs 0 and 1 of every model
GLMM_FORMULA = (
    "cbind(k, n - k) ~ model * condition + (1 | item) + (1 | item:model) + (1 | item:condition)"
    " + (1 | project) + (1 | project:condition) + (1 | cell)"
)

AUTHORS = "Carlos Henrique Brito Malta Leão"

MINUS = "\u2212"


def load(rel: str) -> dict:
    return json.loads((RESULTS / rel).read_text())


OPEN = load("analysis/gaps.json")
CLAUDE = load("claude/analysis/gaps.json")
CLAUDE_CONTAM = load("claude/analysis/contamination.json")
GLMM = load("analysis/glmm.json")
CONTAM = load("analysis/contamination.json")


def num(x: float, d: int = 1, sign: bool = False) -> str:
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    return s.replace("-", MINUS).replace(".", ",")


def pp(frac: float, d: int = 1, sign: bool = False) -> str:
    return num(100 * frac, d, sign)


def ci(lo: float, hi: float) -> str:
    # semicolon, since the comma is the decimal mark
    return f"[{pp(lo)}; {pp(hi)}]"


def row(data: dict, bench: str, model: str) -> dict:
    (r,) = [r for r in data["benchmarks"][bench]["main"] if r["model"] == model]
    return r


def model_names(data: dict) -> list[str]:
    return list(data["settings"]["models"])


def short(model: str) -> str:
    return model.replace("Mistral Small 3.2 24B", "Mistral Small 24B").replace("Claude ", "")


def setup_matplotlib() -> None:
    for f in sorted(FONTS.glob("*.ttf")):
        font_manager.fontManager.addfont(str(f))
    plt.rcParams.update(
        {
            "svg.fonttype": "none",
            "svg.hashsalt": "ufm16-banner",
            "font.family": "Source Sans 3",
            "font.size": 7,
            "axes.edgecolor": "#8a96a6",
            "axes.linewidth": 0.6,
            "axes.labelcolor": "#2b3440",
            "xtick.color": "#2b3440",
            "ytick.color": "#2b3440",
            "xtick.major.width": 0.6,
            "ytick.major.size": 0,
        }
    )


def svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", metadata={"Date": None}, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    text = buf.getvalue()
    return text[text.index("<svg") :]


comma = FuncFormatter(lambda v, _: num(v, 0) if float(v).is_integer() else num(v, 1))


def dot_rows(ax, rows: list[tuple[str, dict]], xlim: tuple[float, float]) -> None:
    """One row per label, CoderUJB above DevEval, point and cluster CI in points."""
    off = {"coderujb": -0.17, "deveval": 0.17}
    for y, (_, by_bench) in enumerate(rows):
        for b, r in by_bench.items():
            lo, est, hi = (100 * r[k] for k in ("lo", "est", "hi"))
            ax.plot([lo, hi], [y + off[b]] * 2, color=COLOR[b], lw=1.6, solid_capstyle="round")
            ax.plot(est, y + off[b], "o", color=COLOR[b], ms=4.2, mec="white", mew=0.6)
    assert all(
        xlim[0] < 100 * r["lo"] and 100 * r["hi"] < xlim[1] for _, br in rows for r in br.values()
    )
    ax.set_yticks(range(len(rows)), [label for label, _ in rows])
    ax.set_ylim(len(rows) - 0.45, -0.55)
    ax.set_xlim(*xlim)
    ax.axvline(0, color="#4a5563", lw=0.8)
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.xaxis.set_major_formatter(comma)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xlabel(f"Diferença imagem {MINUS} texto (pp); barras: IC 95% agrupado por projeto")


def legend(ax, **kw) -> None:
    handles = [
        plt.Line2D([], [], color=COLOR[b], marker="o", lw=1.6, ms=4.2, mec="white", mew=0.6)
        for b in BENCHES
    ]
    ax.legend(
        handles,
        [BENCH_LABEL[b] for b in BENCHES],
        frameon=False,
        ncol=2,
        handlelength=1.6,
        columnspacing=1.4,
        **kw,
    )


XLIM = (-46, 4)
TOKEN_XLIM = (0.1, 0.8)


def fig_main() -> str:
    def rows_of(data: dict) -> list[tuple[str, dict]]:
        return [
            (
                short(n),
                {b: row(data, b, n)["cluster"] | {"est": row(data, b, n)["est"]} for b in BENCHES},
            )
            for n in model_names(data)
        ]

    rows = rows_of(OPEN)
    rows.append(("Média dos abertos", {b: OPEN["benchmarks"][b]["pooled"] for b in BENCHES}))
    n_open = len(rows)
    rows += rows_of(CLAUDE)
    fig, ax = plt.subplots(figsize=(4.1, 1.55))
    dot_rows(ax, rows, XLIM)
    ax.axhline(n_open - 1.5, color=GRID, lw=0.8)
    ax.axhline(n_open - 0.5, color="#8a96a6", lw=0.8, ls=(0, (3, 2)))
    labels = ax.get_yticklabels()
    labels[n_open - 1].set_fontweight("bold")
    for label in labels[n_open:]:
        label.set_fontstyle("italic")
    ax.text(
        XLIM[0] + 1,
        n_open - 0.5 + 0.08,
        "Claude (exploratório)",
        va="top",
        fontsize=6.4,
        color="#8a4b00",
        style="italic",
    )
    legend(ax, loc="lower center", bbox_to_anchor=(0.45, 1.0))
    return svg(fig)


CORR_XLIM = (0.5, 0.9)


def fig_items() -> str:
    """Item-logit correlation of text with each image size, against the one-ability reference."""
    off = {"coderujb": -0.17, "deveval": 0.17}
    fig, ax = plt.subplots(figsize=(4.1, 0.78))
    for y, px in enumerate(SIZES_PX):
        for b in BENCHES:
            c = GLMM["benchmarks"][b]["correlation"]["pearson"][f"text~image{px}"]
            assert CORR_XLIM[0] < min(c["observed"], c["lo"]) and c["hi"] < CORR_XLIM[1]
            ax.plot(
                [c["lo"], c["hi"]],
                [y + off[b]] * 2,
                color=COLOR[b],
                alpha=0.28,
                lw=4.2,
                solid_capstyle="butt",
            )
            ax.plot(c["observed"], y + off[b], "o", color=COLOR[b], ms=4.2, mec="white", mew=0.6)
    ax.set_yticks(range(len(SIZES_PX)), [f"texto × {px} px" for px in SIZES_PX])
    ax.set_ylim(len(SIZES_PX) - 0.45, -0.55)
    ax.set_xlim(*CORR_XLIM)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, 1)))
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_xlabel("Correlação da dificuldade dos itens entre texto e imagem")
    handles = [
        plt.Line2D([], [], color=COLOR[b], marker="o", lw=0, ms=4.2, mec="white", mew=0.6)
        for b in BENCHES
    ] + [plt.Line2D([], [], color="#c3cad4", lw=4.2, solid_capstyle="butt")]
    ax.legend(
        handles,
        [BENCH_LABEL[b] for b in BENCHES] + ["esperada se a dificuldade não mudasse"],
        frameon=False,
        ncol=3,
        loc="lower center",
        bbox_to_anchor=(0.45, 1.0),
        handlelength=1.6,
        columnspacing=1.4,
    )
    return svg(fig)


def fig_tokens() -> str:
    names = model_names(OPEN)
    markers = dict(zip(names, ("o", "s", "D", "^", "v")))
    fig, ax = plt.subplots(figsize=(3.3, 1.1))
    for b in BENCHES:
        tr = OPEN["benchmarks"][b]["token_ratio"]
        # Qwen3.5 27B and 9B share a tokenizer, so their ratios tie; spread tied points sideways
        # so neither hides the other
        ties: dict[float, list[str]] = {}
        for n in names:
            ties.setdefault(round(tr[n]["mean_over_sizes"], 4), []).append(n)
        for n in names:
            r = row(OPEN, b, n)
            group = ties[round(tr[n]["mean_over_sizes"], 4)]
            x = tr[n]["mean_over_sizes"] + 0.014 * (group.index(n) - (len(group) - 1) / 2)
            assert TOKEN_XLIM[0] < x < TOKEN_XLIM[1] and XLIM[0] < 100 * r["cluster"]["lo"], (b, n)
            ax.plot(
                [x, x],
                [100 * r["cluster"]["lo"], 100 * r["cluster"]["hi"]],
                color=COLOR[b],
                lw=1.2,
                alpha=0.55,
            )
            ax.plot(x, 100 * r["est"], markers[n], color=COLOR[b], ms=5, mec="white", mew=0.6)
    ax.set_xlim(*TOKEN_XLIM)
    ax.set_ylim(XLIM[0], 0)
    ax.axhline(0, color="#4a5563", lw=0.8)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, 1)))
    ax.yaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_major_formatter(comma)
    ax.tick_params(axis="y", length=2.5, width=0.6)
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_xlabel("Tokens do prompt: imagem / texto (mediana por item, média dos tamanhos)")
    ax.set_ylabel(f"Diferença imagem {MINUS} texto (pp)")
    model_handles = [
        plt.Line2D([], [], color="#6b7684", marker=markers[n], lw=0, ms=4.6) for n in names
    ]
    bench_handles = [plt.Line2D([], [], color=COLOR[b], lw=5) for b in BENCHES]
    ax.legend(
        bench_handles + model_handles,
        [BENCH_LABEL[b] for b in BENCHES] + [short(n) for n in names],
        frameon=False,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        handletextpad=0.7,
        handlelength=1.2,
        labelspacing=0.35,
        fontsize=6.8,
    )
    return svg(fig)


def values() -> dict[str, str]:
    v: dict[str, str] = {}
    names = model_names(OPEN)
    cnames = model_names(CLAUDE)
    sonnet, opus = (next(n for n in cnames if k in n) for k in ("Sonnet", "Opus"))

    for b in BENCHES:
        B = OPEN["benchmarks"][b]
        v[f"{b}_items"] = f"{B['n_items']:,}".replace(",", ".")
        v[f"{b}_projects"] = str(B["n_clusters"])
        pooled = B["pooled"]
        v[f"{b}_mean"] = pp(pooled["est"])
        v[f"{b}_mean_ci"] = ci(pooled["lo"], pooled["hi"])

    sizes = [int(re.search(r"(\d+)B", n).group(1)) for n in names]
    v["n_open"] = str(len(names))
    v["size_min"], v["size_max"] = str(min(sizes)), str(max(sizes))
    v["temp_open"] = num(OPEN_TEMPERATURE, 1)
    assert len(CLAUDE["settings"]["runs"]) == LINE_RUNS
    v["runs"] = str(LINE_RUNS)
    v["claude_models"] = " e ".join(cnames)
    for k, px in zip(("px1", "px2", "px3"), SIZES_PX):
        v[k] = str(px)
    conds = set(OPEN["benchmarks"]["coderujb"]["rates"])
    assert {f"image{px}" for px in SIZES_PX} | {"text"} <= conds, conds

    mains = [r for b in BENCHES for r in OPEN["benchmarks"][b]["main"]]
    assert all(r["cluster"]["hi"] < 0 and r["holm"] < 0.05 for r in mains)
    v["n_gaps"] = str(len(mains))
    v["holm_max"] = f"{max(r['holm'] for r in mains):.2g}".replace(".", ",")

    # result 2: what the image saves against what it loses
    ratios, rel = {}, {}
    for b in BENCHES:
        B = OPEN["benchmarks"][b]
        for n in names:
            ratios[b, n] = B["token_ratio"][n]["mean_over_sizes"]
            rel[b, n] = -row(OPEN, b, n)["est"] / B["rates"]["text"][n]
    v["ratio_min"] = num(100 * min(ratios.values()), 0)
    v["ratio_max"] = num(100 * max(ratios.values()), 0)
    v["rel_min"] = num(100 * min(rel.values()), 0)
    v["rel_max"] = num(100 * max(rel.values()), 0)
    # result 1, Claude rows (exploratory)
    text_c = {CLAUDE["benchmarks"]["coderujb"]["rates"]["text"][n] for n in (sonnet, opus)}
    assert len(text_c) == 1, text_c
    v["claude_text_c"] = pp(text_c.pop())
    # the text says the Opus CoderUJB item CI includes zero
    opus_item = row(CLAUDE, "coderujb", opus)["item"]
    assert opus_item["lo"] < 0 < opus_item["hi"]
    flagged = CLAUDE_CONTAM["benchmarks"]["coderujb"]["flagged"]
    v["flag_sonnet"], v["flag_opus"] = str(flagged[sonnet]), str(flagged[opus])
    cg = [row(CLAUDE, b, n)["est"] for b in BENCHES for n in (sonnet, opus)]
    v["claude_gap_min"], v["claude_gap_max"] = pp(max(cg)), pp(min(cg))

    # result 3: the sentence names the sizes whose correlation falls below the reference
    below = {
        b: [
            px
            for px in SIZES_PX
            if (c := GLMM["benchmarks"][b]["correlation"]["pearson"][f"text~image{px}"])["observed"]
            < c["lo"]
        ]
        for b in BENCHES
    }
    assert below == {"coderujb": [10, 12], "deveval": [10, 12, 14]}, below
    v["sims"] = f"{GLMM['settings']['sims']:,}".replace(",", ".")

    # limitations
    for b in BENCHES:
        v[f"{b}_copied"] = str(CONTAM["benchmarks"][b]["copied_items"])
    assert all(g["est"] < 0 for b in BENCHES for g in CONTAM["benchmarks"][b]["gaps"])

    g = GLMM["settings"]
    assert g["formula"] == GLMM_FORMULA, g["formula"]
    v["glmmtmb"] = g["glmmTMB"]

    v["authors"] = AUTHORS
    v["logo_left"] = logo("ufmg", "Logo UFMG")
    v["logo_right"] = logo("ppgcc", "Logo PPGCC")
    return v


def logo(stem: str, label: str) -> str:
    for ext, mime in ((".svg", "image/svg+xml"), (".png", "image/png")):
        p = ASSETS / f"{stem}{ext}"
        if p.exists():
            data = base64.b64encode(p.read_bytes()).decode()
            return f'<img alt="{label}" src="data:{mime};base64,{data}">'
    return f'<div class="placeholder">{label}<br>(pendente)</div>'


def font_faces() -> str:
    faces = []
    for family, stem in (("Source Sans 3", "SourceSans3"), ("Source Serif 4", "SourceSerif4")):
        for style, weight, suffix in (
            ("normal", 400, "Regular"),
            ("italic", 400, "It"),
            ("normal", 600, "Semibold"),
            ("normal", 700, "Bold"),
        ):
            data = base64.b64encode((FONTS / f"{stem}-{suffix}.ttf").read_bytes()).decode()
            faces.append(
                f"@font-face {{ font-family: '{family}'; font-style: {style}; "
                f"font-weight: {weight}; src: url(data:font/ttf;base64,{data}) format('truetype'); }}"
            )
    mono = base64.b64encode((ROOT / "src/codeimg/assets/JetBrainsMono-Regular.ttf").read_bytes())
    faces.append(
        "@font-face { font-family: 'JetBrains Mono'; "
        f"src: url(data:font/ttf;base64,{mono.decode()}) format('truetype'); }}"
    )
    return "\n".join(faces)


def chrome(*args: str) -> str:
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-scrollbars",
        "--virtual-time-budget=10000",
        *args,
    ]
    with tempfile.TemporaryDirectory() as profile:
        res = subprocess.run(
            [*cmd, f"--user-data-dir={profile}"], capture_output=True, text=True, check=True
        )
    return res.stdout


def check_layout(html: Path) -> None:
    """Fail on any box whose content overflows it; report the slack in the stretched cards."""
    dom = chrome("--dump-dom", html.as_uri())
    m = re.search(r'<pre id="layout-report"[^>]*>(.*?)</pre>', dom, re.DOTALL)
    if not m:
        sys.exit("layout check did not run")
    report = json.loads(m.group(1))
    for line in report["slack"]:
        print(f"  slack {line}")
    if report["overflow"]:
        sys.exit("overflow: " + "; ".join(report["overflow"]))


def fix_pdf_dates(pdf: Path) -> None:
    # Chrome stamps the print time; a fixed stamp of the same length keeps the xref offsets valid
    data = pdf.read_bytes()
    data = re.sub(
        rb"\(D:\d{14}[^)]*\)",
        lambda m: b"(D:20261124000000" + b" " * (len(m.group(0)) - 18) + b")",
        data,
    )
    pdf.write_bytes(data)


def main() -> None:
    setup_matplotlib()
    v = values()
    v |= {
        "fig_main": fig_main(),
        "fig_tokens": fig_tokens(),
        "fig_items": fig_items(),
        "font_faces": font_faces(),
        "css": (HERE / "banner.css").read_text(),
    }
    html = Template((HERE / "banner.html").read_text()).substitute(v)
    OUT.mkdir(exist_ok=True)
    page = OUT / "banner.html"
    page.write_text(html)
    pdf = OUT / "banner.pdf"
    # tagged PDFs carry DOM node ids that change between runs
    chrome(
        "--no-pdf-header-footer", "--disable-pdf-tagging", f"--print-to-pdf={pdf}", page.as_uri()
    )
    fix_pdf_dates(pdf)
    subprocess.run(
        ["pdftoppm", "-r", "150", "-png", "-singlefile", str(pdf), str(OUT / "banner")], check=True
    )
    # after printing, so a failed check still leaves the page to look at
    check_layout(page)
    print(f"wrote {pdf.relative_to(ROOT)} and banner.png")


if __name__ == "__main__":
    main()
