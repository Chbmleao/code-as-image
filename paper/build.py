"""Build the paper PDF (UFM-14): numbers, figures, tectonic, then the checks on the result.

    uv run python paper/build.py [--final]

Runs build_numbers.py and build_figures.py, compiles main.tex with tectonic into paper/out/ and
prints the build summary. The typography check and "Undefined control sequence" always fail the
build. --final also fails on any \\todo, any undefined reference or citation, and a body that ends
after page 8 (the references and the appendix do not count). --overleaf also fills
out/overleaf/ with the sources plus the generated numbers, tables and figures.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TECTONIC = "/opt/homebrew/bin/tectonic"
MAX_BODY_PAGES = 8

# written as escapes so that this file passes its own check
TYPOGRAPHY = {
    "---": "triple hyphen",
    "--": "double hyphen",
    "\u2013": "en dash",
    "\u2014": "em dash",
    "\u2026": "ellipsis character",
    "\u2018": "curly quote",
    "\u2019": "curly quote",
    "\u201c": "curly quote",
    "\u201d": "curly quote",
}


def sources() -> list[Path]:
    return [
        HERE / "main.tex",
        *sorted((HERE / "sections").glob("*.tex")),
        *sorted((HERE / "tables").glob("*.tex")),
        HERE / "numbers.tex",
        HERE / "refs.bib",
    ]


def uncommented(line: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", line)


def braced(text: str, start: int) -> str | None:
    """The text inside the brace group that opens at text[start], or None if it never closes."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return None


def list_todos(text: str, name: str) -> list[tuple[str, int, str]]:
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        code = uncommented(line)
        for m in re.finditer(r"\\todo\{", code):
            body = braced(code, m.end() - 1)
            found.append((name, n, body if body is not None else code[m.end() :]))
    return found


def typography_hits(text: str, name: str) -> list[str]:
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        # the triple hyphen is a hit of the double one, so report one finding per line
        for pattern, label in TYPOGRAPHY.items():
            if pattern in line:
                hits.append(f"{name}:{n}: {label}")
                if pattern == "---":
                    break
    return hits


def log_problems(log: str) -> tuple[list[str], list[str], list[str]]:
    refs = sorted(set(re.findall(r"Reference `([^']+)' on page \d+ undefined", log)))
    cites = sorted(set(re.findall(r"Citation `([^']+)' on page \d+ undefined", log)))
    fatal = [ln.strip() for ln in log.splitlines() if "Undefined control sequence" in ln]
    return refs, cites, fatal


def body_end_page(aux: str) -> int | None:
    m = re.search(r"\\newlabel\{body-end\}\{\{[^{}]*\}\{(\d+)\}", aux)
    return int(m.group(1)) if m else None


def final_failures(
    todos: list,
    refs: list[str],
    cites: list[str],
    page: int | None,
    max_pages: int = MAX_BODY_PAGES,
) -> list[str]:
    out = []
    if todos:
        out.append(f"{len(todos)} \\todo left")
    if refs or cites:
        out.append(f"{len(refs)} undefined references, {len(cites)} undefined citations")
    if page is None:
        out.append("no body-end label in the .aux")
    elif page > max_pages:
        out.append(f"body ends on page {page}, limit is {max_pages}")
    return out


def overleaf_files() -> list[Path]:
    """Everything main.tex needs to compile elsewhere, generated files included."""
    return sorted(
        [
            HERE / "main.tex",
            HERE / "numbers.tex",
            HERE / "refs.bib",
            HERE / "neurips_2025.sty",
            HERE / "plainnat-pt.bst",
            *(HERE / "sections").glob("*.tex"),
            *(HERE / "tables").glob("*.tex"),
            *(HERE / "figures").glob("*.pdf"),
        ]
    )


def write_overleaf_dir(dest: Path) -> None:
    # start empty so a file deleted here does not linger in the copy
    shutil.rmtree(dest, ignore_errors=True)
    for path in overleaf_files():
        target = dest / path.relative_to(HERE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def run_generator(script: str) -> None:
    res = subprocess.run(
        [sys.executable, str(HERE / script)], capture_output=True, text=True, check=False
    )
    sys.stdout.write(res.stdout)
    if res.returncode:
        sys.stderr.write(res.stderr)
        sys.exit(f"{script} failed")


def count_pages(pdf: Path) -> int:
    if shutil.which("pdfinfo"):
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True)
        return int(re.search(r"^Pages:\s+(\d+)", out.stdout, re.MULTILINE).group(1))
    return len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes()))


def compile_pdf() -> tuple[str, str, Path]:
    OUT.mkdir(exist_ok=True)
    res = subprocess.run(
        [TECTONIC, "-o", "out", "main.tex", "--keep-intermediates", "--keep-logs"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=False,
    )
    log_file = OUT / "main.log"
    log = log_file.read_text(errors="replace") if log_file.exists() else ""
    log += "\n" + res.stdout + "\n" + res.stderr
    if res.returncode:
        sys.stderr.write(res.stderr[-3000:])
        _, _, fatal = log_problems(log)
        sys.exit("tectonic failed" + (f": {fatal[0]}" if fatal else ""))
    aux = (OUT / "main.aux").read_text(errors="replace")
    pdf = OUT / "paper.pdf"
    shutil.copyfile(OUT / "main.pdf", pdf)
    return log, aux, pdf


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--final", action="store_true", help="fail on todo, undefined refs, page > 8")
    ap.add_argument("--overleaf", action="store_true", help="also fill out/overleaf/")
    args = ap.parse_args(argv)

    run_generator("build_numbers.py")
    run_generator("build_figures.py")
    log, aux, pdf = compile_pdf()

    todos = []
    for path in sources():
        if path.suffix == ".tex" and path.name != "numbers.tex":
            todos += list_todos(path.read_text(encoding="utf-8"), str(path.relative_to(HERE)))
    refs, cites, fatal = log_problems(log)
    page = body_end_page(aux)

    typo = []
    for path in sources():
        typo += typography_hits(path.read_text(encoding="utf-8"), str(path.relative_to(HERE)))

    body = f"body ends on page {page}" if page else "no body-end label"
    print(f"paper.pdf: {body}, {count_pages(pdf)} pages total")
    print(f"TODO ({len(todos)}):")
    for name, n, text in todos:
        print(f"  {name}:{n}  {text}")
    print(f"undefined refs: {len(refs)}, undefined citations: {len(cites)}")
    for label in refs + cites:
        print(f"  undefined: {label}")

    failures = [f"typography: {h}" for h in typo] + [f"log: {f}" for f in fatal]
    if args.final:
        failures += final_failures(todos, refs, cites, page)
    for f in failures:
        print(f"FAIL {f}", file=sys.stderr)
    if args.overleaf and not failures:
        write_overleaf_dir(OUT / "overleaf")
        print(f"overleaf: {OUT / 'overleaf'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
