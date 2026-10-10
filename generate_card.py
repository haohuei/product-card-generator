#!/usr/bin/env python3
"""
Product Card Generator — overlay 品名/規格/價格 於原圖
---------------------------------------------------
背景保留原圖不後製，底部漸層黑 bar + 右上黃價格 badge + 可選左上標籤 pill。

Usage:
    python generate_card.py \\
        --image sample.jpg --name "品名" --specs "一片" --price "NT$89" \\
        --out output/card.jpg --aspect 1:1 --badge 熱銷
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------- 常數 ----------

ASPECT_SIZES = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
}

FONT_CANDIDATES_BOLD = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]
FONT_CANDIDATES_REGULAR = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def _find_font(candidates) -> str:
    for p in candidates:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "找不到中文字型。請安裝 Noto Sans CJK 或在 FONT_CANDIDATES 加入自訂路徑。"
    )


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()


# ---------- 核心 ----------

def fit_to_canvas(src: Image.Image, canvas_size: Tuple[int, int],
                  bg_mode: str = "blur") -> Image.Image:
    cw, ch = canvas_size
    canvas = Image.new("RGB", (cw, ch), (255, 255, 255))

    if bg_mode == "blur":
        bg = src.copy().convert("RGB")
        bg_ratio = max(cw / bg.width, ch / bg.height)
        bg = bg.resize((int(bg.width * bg_ratio), int(bg.height * bg_ratio)),
                       Image.LANCZOS)
        left = (bg.width - cw) // 2
        top = (bg.height - ch) // 2
        bg = bg.crop((left, top, left + cw, top + ch))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
        dark = Image.new("RGB", (cw, ch), (0, 0, 0))
        bg = Image.blend(bg, dark, 0.15)
        canvas = bg
    elif bg_mode == "black":
        canvas = Image.new("RGB", (cw, ch), (0, 0, 0))

    ratio = min(cw / src.width, ch / src.height)
    nw, nh = int(src.width * ratio), int(src.height * ratio)
    main = src.convert("RGB").resize((nw, nh), Image.LANCZOS)
    canvas.paste(main, ((cw - nw) // 2, (ch - nh) // 2))
    return canvas


def _gradient_alpha_mask(w: int, h: int, max_alpha: int = 220,
                         ease: float = 1.6) -> Image.Image:
    """單欄 L mask：上透明 → 下 max_alpha，power ease。"""
    col = Image.new("L", (1, h))
    pixels = col.load()
    for y in range(h):
        pixels[0, y] = int(max_alpha * (y / h) ** ease)
    return col.resize((w, h))


def draw_bottom_bar(img: Image.Image, name: str, specs: str,
                    badge: str | None = None) -> Image.Image:
    """底部漸層黑 bar + 品名（大）+ 規格（小、對比強）+ 可選左上角 pill。"""
    W, H = img.size
    bar_h = int(H * 0.26)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 漸層黑 bar（上透明 → 下 220 alpha，底不硬切）
    black_bar = Image.new("RGBA", (W, bar_h), (0, 0, 0, 255))
    black_bar.putalpha(_gradient_alpha_mask(W, bar_h, max_alpha=225, ease=1.5))
    overlay.paste(black_bar, (0, H - bar_h), black_bar)

    draw = ImageDraw.Draw(overlay)

    # 字型（品名放大）
    font_name = _load_font(_find_font(FONT_CANDIDATES_BOLD),
                           size=int(W * 0.078))
    font_spec = _load_font(_find_font(FONT_CANDIDATES_REGULAR),
                           size=int(W * 0.032))

    pad = int(W * 0.05)
    name_y = H - bar_h + int(bar_h * 0.42)
    draw.text((pad, name_y), name, fill=(255, 255, 255, 255), font=font_name)

    spec_y = name_y + int(W * 0.09)
    # 規格字小 + 淡灰 + 間距拉開做對比
    draw.text((pad, spec_y), specs, fill=(190, 190, 190, 230), font=font_spec)

    # 左上品牌紅 pill
    if badge:
        bfont = _load_font(_find_font(FONT_CANDIDATES_BOLD),
                           size=int(W * 0.028))
        bbox = draw.textbbox((0, 0), badge, font=bfont)
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        bpad_x, bpad_y = int(W * 0.022), int(W * 0.011)
        bx, by = int(W * 0.04), int(H * 0.04)
        draw.rounded_rectangle(
            [(bx, by), (bx + bw + bpad_x * 2, by + bh + bpad_y * 2)],
            radius=int(bh * 0.7),
            fill=(214, 69, 69, 230),  # muted brand red #D64545
        )
        draw.text((bx + bpad_x, by + bpad_y - 2), badge,
                  fill=(255, 255, 255, 255), font=bfont)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def draw_price_badge(img: Image.Image, price: str) -> Image.Image:
    """右上角黃底價格 badge（避開中央/底部主體遮擋）。"""
    W, H = img.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = _load_font(_find_font(FONT_CANDIDATES_BOLD), size=int(W * 0.062))
    bbox = draw.textbbox((0, 0), price, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = int(W * 0.032), int(W * 0.02)

    bx2 = W - int(W * 0.04)
    by1 = int(H * 0.04)
    bx1 = bx2 - (tw + pad_x * 2)
    by2 = by1 + (th + pad_y * 2)

    # 輕微陰影
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle([(bx1 + 3, by1 + 4), (bx2 + 3, by2 + 4)],
                            radius=int((by2 - by1) * 0.5),
                            fill=(0, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=4))
    overlay = Image.alpha_composite(overlay, shadow)
    draw = ImageDraw.Draw(overlay)

    draw.rounded_rectangle([(bx1, by1), (bx2, by2)],
                           radius=int((by2 - by1) * 0.5),
                           fill=(255, 221, 51, 245))
    draw.text((bx1 + pad_x, by1 + pad_y - 3), price,
              fill=(20, 20, 20, 255), font=font)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def generate_card(image_path: str, name: str, specs: str, price: str,
                  out_path: str, aspect: str = "1:1",
                  badge: str | None = None, bg_mode: str = "blur") -> str:
    if aspect not in ASPECT_SIZES:
        raise ValueError(f"aspect 必須是 {list(ASPECT_SIZES)}，收到 {aspect}")

    src = Image.open(image_path)
    canvas = fit_to_canvas(src, ASPECT_SIZES[aspect], bg_mode=bg_mode)
    canvas = draw_bottom_bar(canvas, name=name, specs=specs, badge=badge)
    if price:
        canvas = draw_price_badge(canvas, price=price)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=92)
    return str(out)


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--specs", required=True)
    ap.add_argument("--price", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--aspect", default="1:1", choices=list(ASPECT_SIZES.keys()))
    ap.add_argument("--badge", default=None)
    ap.add_argument("--bg", default="blur", choices=["blur", "white", "black"])
    args = ap.parse_args()

    out = generate_card(
        image_path=args.image, name=args.name, specs=args.specs,
        price=args.price, out_path=args.out, aspect=args.aspect,
        badge=args.badge, bg_mode=args.bg,
    )
    print(f"OK → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
