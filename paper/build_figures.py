"""Write the figures of the paper (UFM-14) to paper/figures/ as vector PDFs.

    uv run python paper/build_figures.py [--out DIR]

The plotting helpers are copied and adapted from banner/build.py (which is not imported): Portuguese
labels, decimal comma, true minus sign, DejaVu Sans, widths for a NeurIPS column (5.5 in). A run
changes no byte of the PDFs unless the results change.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

BENCHES = ("coderujb", "deveval")
BENCH_LABEL = {"coderujb": "CoderUJB (Java)", "deveval": "DevEval (Python)"}
COLOR = {"coderujb": "#2468c8", "deveval": "#e0662e"}
GRID = "#dde3ea"
INK = "#2b3440"
SIZES_PX = (10, 12, 14)
WIDTH = 5.5

MINUS = "−"


def num(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace("-", MINUS).replace(".", ",")


def pp(frac: float) -> float:
    return 100 * frac


def short(model: str) -> str:
    return model.replace("Mistral Small 3.2 24B", "Mistral Small 24B")


comma = FuncFormatter(lambda v, _: num(v, 0) if float(v).is_integer() else num(v, 1))


def load(root: Path, rel: str) -> dict:
    return json.loads((root / "results" / rel).read_text(encoding="utf-8"))


def setup_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7,
            "axes.edgecolor": "#8a96a6",
            "axes.linewidth": 0.6,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.major.width": 0.6,
            "ytick.major.size": 0,
            "pdf.fonttype": 42,
        }
    )


def save(fig, path: Path) -> None:
    buf = io.BytesIO()
    fig.savefig(
        buf, format="pdf", metadata={"CreationDate": None}, bbox_inches="tight", pad_inches=0.02
    )
    plt.close(fig)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())


def main_row(gaps: dict, bench: str, model: str) -> dict:
    (r,) = [r for r in gaps["benchmarks"][bench]["main"] if r["model"] == model]
    return r


def fig_gap(gaps: dict):
    """Gap per open model and the mean of models, both benchmarks, cluster interval."""
    names = list(gaps["settings"]["models"])
    rows = [
        (
            short(n),
            {
                b: main_row(gaps, b, n)["cluster"] | {"est": main_row(gaps, b, n)["est"]}
                for b in BENCHES
            },
        )
        for n in names
    ]
    rows.append(("Média dos modelos", {b: gaps["benchmarks"][b]["pooled"] for b in BENCHES}))
    xlim = (-46, 4)
    off = {"coderujb": -0.17, "deveval": 0.17}
    fig, ax = plt.subplots(figsize=(WIDTH, 2.3))
    for y, (_, by_bench) in enumerate(rows):
        for b, r in by_bench.items():
            lo, est, hi = (pp(r[k]) for k in ("lo", "est", "hi"))
            assert xlim[0] < lo and hi < xlim[1], (b, y)
            ax.plot([lo, hi], [y + off[b]] * 2, color=COLOR[b], lw=1.8, solid_capstyle="round")
            ax.plot(est, y + off[b], "o", color=COLOR[b], ms=4.6, mec="white", mew=0.6)
    ax.set_yticks(range(len(rows)), [label for label, _ in rows])
    ax.get_yticklabels()[-1].set_fontweight("bold")
    ax.set_ylim(len(rows) - 0.45, -0.55)
    ax.set_xlim(*xlim)
    ax.axvline(0, color="#4a5563", lw=0.8)
    ax.axhline(len(rows) - 1.5, color=GRID, lw=0.8)
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.xaxis.set_major_formatter(comma)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xlabel(f"Diferença imagem {MINUS} texto (pp); barras: IC 95% agrupado por projeto ou repositório")
    handles = [
        plt.Line2D([], [], color=COLOR[b], marker="o", lw=1.8, ms=4.6, mec="white", mew=0.6)
        for b in BENCHES
    ]
    ax.legend(
        handles,
        [BENCH_LABEL[b] for b in BENCHES],
        frameon=False,
        ncol=2,
        loc="lower center",
        bbox_to_anchor=(0.45, 1.0),
        handlelength=1.6,
        columnspacing=1.4,
    )
    return fig


def fig_size_tokens(gaps: dict):
    """Per-size gap against per-size token ratio, one line per model, one panel per benchmark."""
    names = list(gaps["settings"]["models"])
    markers = dict(zip(names, ("o", "s", "D", "^", "v")))
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.5), sharey=True)
    for ax, b in zip(axes, BENCHES):
        B = gaps["benchmarks"][b]
        for n in names:
            xs = [B["token_ratio"][n][f"image{px}"] for px in SIZES_PX]
            by_size = {r["size"]: r for r in B["sizes"] if r["model"] == n}
            ys = [pp(by_size[f"image{px}"]["est"]) for px in SIZES_PX]
            ax.plot(xs, ys, "-", color=COLOR[b], lw=0.9, alpha=0.6)
            ax.plot(xs, ys, markers[n], color=COLOR[b], ms=4.6, mec="white", mew=0.5)
            if n == names[0]:
                for x, y, px in zip(xs, ys, SIZES_PX):
                    ax.annotate(
                        f"{px} px",
                        (x, y),
                        textcoords="offset points",
                        xytext=(0, 5),
                        ha="center",
                        fontsize=6,
                        color=INK,
                    )
        ax.set_title(BENCH_LABEL[b], fontsize=7.5, color=COLOR[b], loc="left")
        ax.set_xlim(0.1, 0.95)
        ax.set_ylim(-46, 0)
        ax.axhline(0, color="#4a5563", lw=0.8)
        ax.xaxis.set_major_locator(MultipleLocator(0.2))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, 1)))
        ax.yaxis.set_major_locator(MultipleLocator(10))
        ax.yaxis.set_major_formatter(comma)
        ax.tick_params(axis="y", length=2.5, width=0.6)
        ax.grid(color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.set_xlabel("Razão de tokens (imagem / texto)")
    axes[0].set_ylabel(f"Diferença imagem {MINUS} texto (pp)")
    handles = [plt.Line2D([], [], color="#6b7684", marker=markers[n], lw=0, ms=4.6) for n in names]
    fig.legend(
        handles,
        [short(n) for n in names],
        frameon=False,
        ncol=len(names),
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        columnspacing=1.2,
        handletextpad=0.3,
    )
    fig.tight_layout()
    return fig


def fig_item_corr(glmm: dict):
    """Item-logit correlation of text with each image size, against the one-ability reference."""
    xlim = (0.5, 0.9)
    off = {"coderujb": -0.17, "deveval": 0.17}
    fig, ax = plt.subplots(figsize=(WIDTH, 1.6))
    for y, px in enumerate(SIZES_PX):
        for b in BENCHES:
            c = glmm["benchmarks"][b]["correlation"]["pearson"][f"text~image{px}"]
            assert xlim[0] < min(c["observed"], c["lo"]) and c["hi"] < xlim[1], (b, px)
            ax.plot(
                [c["lo"], c["hi"]],
                [y + off[b]] * 2,
                color=COLOR[b],
                alpha=0.28,
                lw=4.6,
                solid_capstyle="butt",
            )
            ax.plot(c["observed"], y + off[b], "o", color=COLOR[b], ms=4.6, mec="white", mew=0.6)
    ax.set_yticks(range(len(SIZES_PX)), [f"texto × {px} px" for px in SIZES_PX])
    ax.set_ylim(len(SIZES_PX) - 0.45, -0.55)
    ax.set_xlim(*xlim)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v, 1)))
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_xlabel("Correlação de Pearson da dificuldade dos itens (logit) entre texto e imagem")
    handles = [
        plt.Line2D([], [], color=COLOR[b], marker="o", lw=0, ms=4.6, mec="white", mew=0.6)
        for b in BENCHES
    ] + [plt.Line2D([], [], color="#c3cad4", lw=4.6, solid_capstyle="butt")]
    ax.legend(
        handles,
        [BENCH_LABEL[b] for b in BENCHES] + ["faixa esperada se a penalidade fosse igual em todo item"],
        frameon=False,
        ncol=3,
        loc="lower center",
        bbox_to_anchor=(0.4, 1.0),
        handlelength=1.6,
        columnspacing=1.4,
        fontsize=6.4,
    )
    return fig


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--root", type=Path, default=ROOT, help="repo root holding results/")
    args = ap.parse_args(argv)
    setup_matplotlib()
    gaps = load(args.root, "analysis/gaps.json")
    glmm = load(args.root, "analysis/glmm.json")
    figs = {
        "fig_gap": fig_gap(gaps),
        "fig_size_tokens": fig_size_tokens(gaps),
        "fig_item_corr": fig_item_corr(glmm),
    }
    for stem, fig in figs.items():
        save(fig, args.out / "figures" / f"{stem}.pdf")
    print("figures: " + " ".join(f"{stem}.pdf" for stem in figs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
