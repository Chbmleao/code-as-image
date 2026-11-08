import hashlib
import io

from codeimg.render import NEWLINE_MARK, PAD, PAGE_H, PAGE_W, capacity, layout, line_height, render


def test_empty_code_has_no_pages():
    assert layout("", 12) == []
    assert render("", 12) == []


def test_lines_are_joined_with_the_marker_and_indentation_is_kept():
    rows = layout("def f():\n    return 1   \n", 12)
    assert rows == [["def f():" + NEWLINE_MARK + "    return 1" + NEWLINE_MARK]]


def test_tabs_expand_to_four_spaces():
    assert layout("\tx", 10) == [["    x"]]


def test_rows_fill_the_width_and_pages_stay_under_the_height():
    for px in (10, 12, 14):
        cols, per_page = capacity(px)
        code = "\n".join("x" * 200 for _ in range(400))
        pages = layout(code, px)
        assert len(pages) > 1
        assert all(len(r) <= cols for p in pages for r in p)
        assert all(len(p) <= per_page for p in pages)
        # every page but the last is full to the same row count, and the last is not left near empty
        assert len({len(p) for p in pages[:-1]}) == 1
        assert len(pages[0]) - len(pages[-1]) < len(pages)


def test_each_page_is_cut_to_its_rows():
    pages = render("a\nb", 14)
    assert len(pages) == 1
    assert pages[0].size == (PAGE_W, line_height(14) + 2 * PAD)
    big = render("\n".join("y" * 80 for _ in range(1000)), 10)
    assert all(im.size[0] == PAGE_W and im.size[1] <= PAGE_H for im in big)


def test_rendering_is_deterministic():
    code = "public int f(int x) {\n    return x + 1;\n}\n"

    def digest():
        buf = io.BytesIO()
        render(code, 12)[0].save(buf, "PNG")
        return hashlib.sha256(buf.getvalue()).hexdigest()

    assert digest() == digest()


def test_capacity_matches_the_token_counting_layout():
    # the numbers benchmarks/shared/count_tokens.py used for the prompt-token buckets
    assert [capacity(px) for px in (10, 12, 14)] == [(100, 127), (86, 101), (75, 84)]


def test_layout_engine_is_pinned():
    from PIL import ImageFont

    from codeimg.render import font
    assert font(12).layout_engine == ImageFont.Layout.BASIC
