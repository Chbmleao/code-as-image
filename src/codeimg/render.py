"""Packed rendering of the repository context, as in studies/pilot/run_pilot.py (render_packed).

Lines flow across rows of 616 px with a visible marker for each line break, and leading spaces are
kept, so indentation survives. A page holds at most 1540 px of rows; when the context needs more
than one page, the rows are spread evenly over the pages (the last page is at most one row per page shorter),
and each page is cut to the height of its rows.
"""
import os

from PIL import Image, ImageDraw, ImageFont

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "JetBrainsMono-Regular.ttf")
PAGE_W = 616
PAGE_H = 1540
PAD = 6
# JetBrains Mono has no U+21B5 (pxpipe's marker), so U+23CE is used, as in the pilot
NEWLINE_MARK = "⏎"

_fonts = {}


def font(px):
    if px not in _fonts:
        # raqm, when Pillow has it, gives fractional advances (7.2 px for M at 12 px instead of 7),
        # so fewer columns and more pages; the basic engine renders the same on every machine
        _fonts[px] = ImageFont.truetype(FONT, px, layout_engine=ImageFont.Layout.BASIC)
    return _fonts[px]


def line_height(px):
    return round(px * 1.25)


def capacity(px):
    """(columns per row, rows per page) at this font size."""
    cols = int((PAGE_W - 2 * PAD) // font(px).getlength("M"))
    return cols, (PAGE_H - 2 * PAD) // line_height(px)


def layout(code, px):
    """Rows of each page, without drawing anything."""
    cols, rows_per_page = capacity(px)
    flow = NEWLINE_MARK.join(line.rstrip() for line in code.expandtabs(4).split("\n"))
    rows = [flow[i:i + cols] for i in range(0, len(flow), cols)]
    if not rows:
        return []
    n_pages = -(-len(rows) // rows_per_page)
    per_page = -(-len(rows) // n_pages)
    return [rows[i:i + per_page] for i in range(0, len(rows), per_page)]


def render(code, px):
    f, lh = font(px), line_height(px)
    pages = []
    for chunk in layout(code, px):
        im = Image.new("RGB", (PAGE_W, lh * len(chunk) + 2 * PAD), "white")
        d = ImageDraw.Draw(im)
        for j, r in enumerate(chunk):
            d.text((PAD, PAD + j * lh), r, font=f, fill="black")
        pages.append(im)
    return pages
