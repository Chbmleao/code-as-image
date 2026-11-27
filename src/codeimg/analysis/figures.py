"""The analysis figures: the gap per model and the size curve, for the open models and for the
Claude extension."""
import os

from codeimg.analysis import dstudy as ds

# slots 1 to 5 of the dataviz reference palette (light), and its text inks
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")
INK, INK2, GRID, MUTED = "#0b0b0b", "#52514e", "#d9d8d4", "#a8a7a2"
WIDTH = 5.5


def _pyplot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "pdf.fonttype": 42,
                         "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                         "ytick.color": INK2, "text.color": INK, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.hashsalt": "analysis"})
    return plt


def _save(fig, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, metadata={"CreationDate": None, "ModDate": None, "Producer": None,
                                "Creator": None})
    print(path)


def figures(rep, out_dir, files=("main_gap.pdf", "size_curve.pdf"), muted=()):
    """The gap per model with its interval and per-size dots, and the size curve. Muted models
    are drawn in grey without intervals on the size curve, with one legend entry."""
    plt = _pyplot()
    benches = list(rep["benchmarks"])
    models = rep["settings"]["models"]
    scale = 100

    fig, axes = plt.subplots(1, len(benches), figsize=(WIDTH, 0.45 * len(models) + 1.1),
                             sharey=True)
    for ax, b in zip(axes, benches):
        v = rep["benchmarks"][b]
        sizes = sorted({r["size"] for r in v["sizes"]}, key=lambda s: int(s[5:]))
        for k, r in enumerate(v["main"]):
            yk = len(models) - 1 - k
            c = r["cluster"]
            ax.plot([c["lo"] * scale, c["hi"] * scale], [yk, yk], color=INK, lw=1.5,
                    solid_capstyle="round")
            ax.plot(r["est"] * scale, yk, "o", color=INK, ms=6)
            for q, s in enumerate(sizes):
                g = next(x for x in v["sizes"] if x["model"] == r["model"] and x["size"] == s)
                ax.plot(g["est"] * scale, yk + 0.22, "o", color=SERIES[q], ms=4,
                        label=f"{s[5:]} px" if k == 0 else None)
        ax.axvline(0, color=GRID, lw=1, zorder=0)
        ax.set_title(ds.TITLES.get(b, b), fontsize=9)
        ax.set_xlabel("Image minus text (points)")
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels(list(reversed(models)))
        ax.tick_params(axis="y", length=0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, loc="lower center", ncol=len(labels),
               handletextpad=0.2)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    _save(fig, os.path.join(out_dir, files[0]))
    plt.close(fig)

    fig, axes = plt.subplots(1, len(benches), figsize=(WIDTH, 2.6), sharey=True)
    for ax, b in zip(axes, benches):
        v = rep["benchmarks"][b]
        first_muted = next((m for m in models if m in muted), None)
        for k, m in enumerate(models):
            rows = [r for r in v["sizes"] if r["model"] == m]
            rows.sort(key=lambda r: int(r["size"][5:]))
            xs = [v["token_ratio"][m][r["size"]] for r in rows]
            if m in muted:
                ax.plot(xs, [r["est"] * scale for r in rows], "-o", color=MUTED, lw=1, ms=3,
                        label="Open models, every run" if m == first_muted else None)
                continue
            ax.plot(xs, [r["est"] * scale for r in rows], "-o", color=SERIES[k % len(SERIES)],
                    lw=2, ms=4, label=m)
            for x, r in zip(xs, rows):
                ax.plot([x, x], [r["cluster"]["lo"] * scale, r["cluster"]["hi"] * scale],
                        color=SERIES[k % len(SERIES)], lw=1, alpha=0.6)
        ax.axhline(0, color=GRID, lw=1, zorder=0)
        ax.set_title(ds.TITLES.get(b, b), fontsize=9)
        ax.set_xlabel("Image / text prompt tokens (median)")
    axes[0].set_ylabel("Image minus text (points)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, loc="lower center",
               ncol=min(len(labels), 3))
    fig.tight_layout(rect=(0, 0.16, 1, 1))
    _save(fig, os.path.join(out_dir, files[1]))
    plt.close(fig)


def claude_figures(g, g5, out_dir):
    """claude_gap.pdf and size_curve.pdf: the Claude models, then the open models of the 5-model
    run, which are grey on the size curve."""
    benches = {}
    for b, v in g["benchmarks"].items():
        w = g5["benchmarks"][b]
        benches[b] = {"main": v["main"] + w["main"], "sizes": v["sizes"] + w["sizes"],
                      "token_ratio": {**v["token_ratio"], **w["token_ratio"]}}
    rep = {"settings": {"models": g["settings"]["models"] + g5["settings"]["models"]},
           "benchmarks": benches}
    figures(rep, out_dir, ("claude_gap.pdf", "size_curve.pdf"), muted=set(g5["settings"]["models"]))
