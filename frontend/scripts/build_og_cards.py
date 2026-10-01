"""Generate one branded Open Graph card per blog post (1200x630).

Every post needs its own social image: a single shared og-blog.png means every
link previews identically on LinkedIn/X/WhatsApp/Slack, which suppresses click
through. These cards are rendered from the brand tokens + real typefaces, so
they stay on-system and cost no third-party image licence.

Fonts are vendored in scripts/fonts (variable TTFs) so the build is offline
and deterministic. Output is committed; re-run after editing a title.

Usage:
    python scripts/build_og_cards.py            # all posts
    python scripts/build_og_cards.py --force    # rewrite even if unchanged
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "data" / "posts.json"
OUT_DIR = ROOT / "img" / "og"
FONT_DIR = Path(__file__).resolve().parent / "fonts"

W, H = 1200, 630
NAVY, NAVY2 = (8, 13, 26), (14, 22, 39)
GREEN, GOLD = (0, 107, 60), (212, 160, 23)
CREAM, SLATE = (245, 240, 232), (138, 155, 176)

# Right-hand wash per cover theme (mirrors .cover-0..5 in the templates)
THEMES = [
    (0, 107, 60), (28, 42, 74), (14, 116, 144), (124, 58, 237), (180, 83, 9), (42, 74, 124),
]

STAR = [(50, 0), (61, 35), (98, 35), (68, 57), (79, 91), (50, 70), (21, 91), (32, 57), (2, 35), (39, 35)]


def stable_hash(s):
    h = 0
    for ch in str(s):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def font(name, size, weight=None, opsz=None):
    """Load a variable font, setting axes by name.

    Axes must be set in the font's own declared order. Inter ships
    [Optical size, Weight], so a positional guess silently renders Thin text
    (wght clamps to its 100 minimum) instead of the requested weight.
    """
    f = ImageFont.truetype(str(FONT_DIR / name), size)
    if weight is None and opsz is None:
        return f
    values = []
    for axis in f.get_variation_axes():
        axis_name = axis["name"]
        if isinstance(axis_name, bytes):
            axis_name = axis_name.decode("utf-8", "replace")
        axis_name = axis_name.lower()
        low, high, default = axis["minimum"], axis["maximum"], axis["default"]
        if "weight" in axis_name and weight is not None:
            values.append(min(max(weight, low), high))
        elif "optical" in axis_name and opsz is not None:
            values.append(min(max(opsz, low), high))
        else:
            values.append(default)
    f.set_variation_by_axes(values)
    return f


def wrap(draw, text, fnt, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_card(post):
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)

    # vertical navy gradient + themed wash on the right
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(
            int(NAVY[0] + (NAVY2[0] - NAVY[0]) * t),
            int(NAVY[1] + (NAVY2[1] - NAVY[1]) * t),
            int(NAVY[2] + (NAVY2[2] - NAVY[2]) * t),
        ))
    tint = THEMES[stable_hash(post.get("slug", "")) % len(THEMES)]
    wash = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wash)
    for i in range(60, 0, -1):
        wd.ellipse([W - 300 - i * 5, -300 - i * 4, W + 260 + i * 5, 460 + i * 4],
                   fill=(*tint, 5))
    img = Image.alpha_composite(img.convert("RGBA"), wash).convert("RGB")
    d = ImageDraw.Draw(img)

    # 60px grid
    for x in range(0, W + 1, 60):
        d.line([(x, 0), (x, H)], fill=(20, 28, 46), width=1)
    for y in range(0, H + 1, 60):
        d.line([(0, y), (W, y)], fill=(20, 28, 46), width=1)

    # gold rail
    d.rectangle([0, 0, 14, H], fill=GOLD)

    # logomark: green rounded square + gold star
    d.rounded_rectangle([90, 74, 90 + 72, 74 + 72], radius=22, fill=GREEN)
    cx, cy, r = 90 + 36, 74 + 36, 30
    d.polygon([(cx + (px - 50) / 50 * r, cy + (py - 50) / 50 * r) for px, py in STAR], fill=GOLD)

    # category chip
    f_chip = font("Inter.ttf", 21, weight=600)
    label = (post.get("category") or "Intelligence").upper()
    cw = d.textlength(label, font=f_chip)
    d.rounded_rectangle([90, 196, 90 + cw + 44, 196 + 46], radius=23, fill=(30, 24, 8), outline=(74, 58, 14), width=1)
    d.text((90 + 22, 196 + 11), label, font=f_chip, fill=GOLD)

    # title
    f_title = font("SpaceGrotesk.ttf", 58, weight=700)
    lines = wrap(d, post.get("title") or "Untitled", f_title, W - 200)[:3]
    if len(lines) == 3 and len(wrap(d, post.get("title", ""), f_title, W - 200)) > 3:
        lines[2] = lines[2][: len(lines[2]) - 1].rstrip() + "\u2026"
    y = 282
    for line in lines:
        d.text((90, y), line, font=f_title, fill=CREAM)
        y += 68

    # hairline + footer
    d.line([(90, H - 118), (W - 90, H - 118)], fill=(30, 40, 62), width=1)
    f_foot = font("Inter.ttf", 22, weight=600)
    d.text((90, H - 92), "SPORAFIND", font=f_foot, fill=CREAM)
    f_foot2 = font("Inter.ttf", 22, weight=400)
    d.text((90 + d.textlength("SPORAFIND", font=f_foot) + 12, H - 92), "INTELLIGENCE", font=f_foot2, fill=SLATE)

    f_date = font("Inter.ttf", 21, weight=400)
    date_text = (post.get("dateLabel") or "")[:24]
    if date_text:
        d.text((W - 90 - d.textlength(date_text, font=f_date), H - 92), date_text, font=f_date, fill=SLATE)

    return img


def date_label(value):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return ""
    return f"{dt.day} {dt.strftime('%b %Y')}"


def main():
    force = "--force" in sys.argv
    posts = [p for p in json.loads(POSTS.read_text(encoding="utf-8")) if p.get("status") == "published"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = skipped = 0

    for p in posts:
        p["dateLabel"] = date_label(p.get("publishedAt"))
        out = OUT_DIR / f"{p['slug']}.jpg"
        if out.exists() and not force:
            skipped += 1
            continue
        draw_card(p).save(out, "JPEG", quality=84, optimize=True, progressive=True)
        written += 1

    print(f"og cards: {written} written, {skipped} unchanged ({len(posts)} posts) -> {OUT_DIR}")


if __name__ == "__main__":
    main()