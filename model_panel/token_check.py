"""Measure image tokens per page by diffing prompt_tokens with and without one image.

Usage: python token_check.py <model> <port>   (prints one JSON line per page size)
"""
import base64
import io
import json
import sys
import urllib.request

from PIL import Image, ImageDraw

PROMPT = "Reply with OK."
SIZES = [(616, 1540), (616, 770)]


def page(w, h):
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    for y in range(0, h - 12, 14):
        draw.text((4, y), "def f(x): return x + 1  # filler line, content does not affect token count", fill="black")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def prompt_tokens(url, model, content):
    body = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": content}],
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)["usage"]["prompt_tokens"]


def main():
    model, port = sys.argv[1], sys.argv[2]
    url = f"http://localhost:{port}/v1/chat/completions"
    text_only = prompt_tokens(url, model, [{"type": "text", "text": PROMPT}])
    for w, h in SIZES:
        image = {"type": "image_url", "image_url": {"url": "data:image/png;base64," + page(w, h)}}
        with_image = prompt_tokens(url, model, [image, {"type": "text", "text": PROMPT}])
        print(json.dumps({
            "model": model,
            "width": w,
            "height": h,
            "text_only_tokens": text_only,
            "image_tokens": with_image - text_only,
            "grid_28": round(w * h / 28**2),
            "grid_32": round(w * h / 32**2),
            "grid_48": round(w * h / 48**2),
        }), flush=True)


if __name__ == "__main__":
    main()
