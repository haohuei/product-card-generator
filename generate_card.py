#!/usr/bin/env python3
"""
Product Card Generator — Phase 1 CLI
---------------------------------------------------
把原始商品照片疊上「品名 / 規格 / 價格」文字 overlay，
背景保留原圖不後製，產出 IG / 代購網站可直接用的商品卡。

Usage:
    python generate_card.py \\
        --image mediheal.jpg \\
        --name "MEDIHEAL 楮樹美白4D面膜" \\
        --specs "一片" \\
        --price "NT$89" \\
        --out output/card.jpg \\
        --aspect 1:1

Aspect ratios: 1:1 (1080x1080) / 9:16 (1080x1920) / 4:5 (1080x1350)
Overlay 樣式: bottom bar 半透明黑底 + 右下角價格 badge
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

# 字型路徑候選：先找 Mac 系統字型 → 再找 Linux Noto → 再找 bundled
FONT_CANDIDATES_BOLD = [
    "/System/Library/Fonts/PingFang.ttc",                       # Mac 繁中
    "/System/Library/Fonts/STHeiti Medium.ttc",                 # Mac fallback
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",      # Linux
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
    """
    把原圖等比塞進指定畫布，背景用模糊版原圖填滿（不後製主體，只補邊）。
    bg_mode: 'blur' 用模糊自身填滿 / 'white' 純白補邊 / 'black' 純黑補邊。
    """
    cw, ch = canvas_size
    canvas = Image.new("RGB", (cw, ch), (255, 255, 255))

    # 背景填充
    if bg_mode == "blur":
        bg = src.copy().convert("RGB")
        bg_ratio = max(cw / bg.width, ch / bg.height)
        bg = bg.resize((int(bg.width * bg_ratio), int(bg.height * bg_ratio)),
                       Image.LANCZOS)
        left = (bg.width - cw) // 2
        top = (bg.height - ch) // 2
        bg = bg.crop((left, top, left + cw, top + ch))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
        # 輕微暗化讓前景更突出
        dark = Image.new("RGB", (cw, ch), (0, 0, 0))
        bg = Image.blend(bg, dark, 0.15)
        canvas = bg
    elif bg_mode == "black":
        canvas = Image.new("RGB", (cw, ch), (0, 0, 0))

    # 等比縮主體
    ratio = min(cw / src.width, ch / src.height)
    nw, nh = int(src.width * ratio), int(src.height * ratio)
    main = src.convert("RGB").resize((nw, nh), Image.LANCZOS)
    canvas.paste(main, ((cw - nw) // 2, (ch - nh) // 2))
    return canvas


def draw_bottom_bar(img: Image.Image, name: str, specs: str,
                    badge: str | None = None) -> Image.Image:
    """
    底部半透明黑 bar + 品名（大）+ 規格（小）+ 可選標籤 pill。
    """
    W, H = img.size
    bar_h = int(H * 0.22)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 底部 bar 半透明漸層感（直接 fill 黑色 alpha=180）
    draw.rectangle([(0, H - bar_h), (W, H)], fill=(0, 0, 0, 180))

    # 字型
    font_bold = _load_font(_find_font(FONT_CANDIDATES_BOLD),
                           size=int(W * 0.055))
    font_small = _load_font(_find_font(FONT_CANDIDATES_REGULAR),
                            size=int(W * 0.032))

    pad = int(W * 0.045)
    # 品名
    name_y = H - bar_h + int(bar_h * 0.22)
    draw.text((pad, name_y), name, fill=(255, 255, 255, 255), font=font_bold)
    # 規格
    specs_y = name_y + int(W * 0.065)
    draw.text((pad, specs_y), specs, fill=(220, 220, 220, 255), font=font_small)

    # 可選 badge pill（頂部左上角）
    if badge:
        bfont = _load_font(_find_font(FONT_CANDIDATES_BOLD),
                           size=int(W * 0.03))
        bbox = draw.textbbox((0, 0), badge, font=bfont)
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        bpad_x, bpad_y = int(W * 0.025), int(W * 0.012)
        bx, by = int(W * 0.04), int(H * 0.04)
        draw.rounded_rectangle(
            [(bx, by), (bx + bw + bpad_x * 2, by + bh + bpad_y * 2)],
            radius=int(bh * 0.7), fill=(220, 38, 38, 230),
        )
        draw.text((bx + bpad_x, by + bpad_y - 2), badge,
                  fill=(255, 255, 255, 255), font=bfont)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def draw_price_badge(img: Image.Image, price: str) -> Image.Image:
    """
    右下角價格 badge（黃底黑字 pill）。
    """
    W, H = img.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = _load_font(_find_font(FONT_CANDIDATES_BOLD), size=int(W * 0.055))
    bbox = draw.textbbox((0, 0), price, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = int(W * 0.028), int(W * 0.018)

    bar_h = int(H * 0.22)  # 要在底部 bar 上方
    bx2 = W - int(W * 0.045)
    by2 = H - bar_h - int(H * 0.02)
    bx1 = bx2 - (tw + pad_x * 2)
    by1 = by2 - (th + pad_y * 2)

    draw.rounded_rectangle([(bx1, by1), (bx2, by2)],
                           radius=int((by2 - by1) * 0.5),
                           fill=(255, 221, 51, 240))
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
    canvas = draw_price_badge(canvas, price=price)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=92)
    return str(out)


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(
        description="Product card generator — overlay 品名/規格/價格 於原圖")
    ap.add_argument("--image", required=True, help="原始商品照路徑")
    ap.add_argument("--name", required=True, help="品名（中文），使用者自己打")
    ap.add_argument("--specs", required=True, help="規格，例：30ml / 一盒")
    ap.add_argument("--price", required=True, help="價格，例：NT$89")
    ap.add_argument("--out", required=True, help="輸出 PNG/JPG 路徑")
    ap.add_argument("--aspect", default="1:1",
                    choices=list(ASPECT_SIZES.keys()),
                    help="輸出比例 (default: 1:1)")
    ap.add_argument("--badge", default=None,
                    help="可選標籤：熱銷 / 限量 / 新品 / 預購")
    ap.add_argument("--bg", default="blur",
                    choices=["blur", "white", "black"],
                    help="留白區域填充方式 (default: blur)")
    args = ap.parse_args()

    out = generate_card(
        image_path=args.image, name=args.name, specs=args.specs,
        price=args.price, out_path=args.out, aspect=args.aspect,
        badge=args.badge, bg_mode=args.bg,
    )
    print(f"OK → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
