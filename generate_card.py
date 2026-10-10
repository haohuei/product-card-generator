#!/usr/bin/env python3
"""
Product Card Generator — 3 商品 DM 版型
---------------------------------------------------
Templates:
    A · clean        — 乾淨商品照用（白底 / 淡 blur，產品為主，文字極簡）
    B · korean_beauty — K-beauty 風（軟色調 + 圓形促銷貼紙 + 氣質排版）
    C · taiwan_daigou — 台灣代購（高對比黃紅色塊 + 大價格數字 + 現貨/預購 tag）

Usage:
    python generate_card.py --image x.jpg \\
        --name "品名" --specs "一片" --price "NT$89" \\
        --template korean_beauty --tag 現貨 --out output/x.jpg
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat

# ---------- 常數 ----------

ASPECT_SIZES = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
}

TEMPLATES = ["clean", "korean_beauty", "taiwan_daigou", "taiwan_dm"]

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
    raise FileNotFoundError("找不到中文字型 — 需 Noto Sans CJK 或系統 PingFang")


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()


# ---------- 共用 helpers ----------

def _gradient_alpha(w: int, h: int, max_alpha: int = 220,
                    ease: float = 1.6, direction: str = "down") -> Image.Image:
    """漸層 alpha mask。direction: down/up。"""
    col = Image.new("L", (1, h))
    px = col.load()
    for y in range(h):
        t = y / h if direction == "down" else 1 - y / h
        px[0, y] = int(max_alpha * t ** ease)
    return col.resize((w, h))


def _fit_contain(src: Image.Image, canvas: Image.Image,
                 pad_ratio: float = 0.0) -> Tuple[int, int, int, int]:
    """等比塞進畫布中央，回傳 (x, y, w, h)。"""
    cw, ch = canvas.size
    avail_w = int(cw * (1 - pad_ratio * 2))
    avail_h = int(ch * (1 - pad_ratio * 2))
    ratio = min(avail_w / src.width, avail_h / src.height)
    nw, nh = int(src.width * ratio), int(src.height * ratio)
    x, y = (cw - nw) // 2, (ch - nh) // 2
    return x, y, nw, nh


def suggest_template(image_path: str) -> str:
    """
    根據圖片特徵自動建議 template。
    - 低 std + 低 edge → clean（乾淨商品照）
    - 高 edge density → taiwan_daigou（截圖/包裝字多，用色塊蓋）
    - 中間 → korean_beauty
    """
    try:
        img = Image.open(image_path).convert("RGB")
        img.thumbnail((400, 400))
        gray = img.convert("L")
        stddev = sum(ImageStat.Stat(img).stddev) / 3
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_mean = ImageStat.Stat(edges).mean[0]

        if stddev < 55 and edge_mean < 18:
            return "clean"
        if edge_mean > 35:
            return "taiwan_daigou"
        return "korean_beauty"
    except Exception:
        return "clean"


# ============================================================
# Template A · clean
# ============================================================

def _render_clean(src: Image.Image, size: Tuple[int, int],
                  name: str, specs: str, price: str,
                  tag: str | None = None) -> Image.Image:
    """白底 + 商品置中 + 底部細白 bar + 小價格 badge。"""
    cw, ch = size
    canvas = Image.new("RGB", size, (248, 247, 245))

    # 商品等比塞入上方 75% 區域
    x, y, nw, nh = _fit_contain(
        src, Image.new("RGB", (cw, int(ch * 0.72))), pad_ratio=0.08)
    main = src.convert("RGB").resize((nw, nh), Image.LANCZOS)
    # 輕微陰影
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([(x + 8, y + 12), (x + nw + 8, y + nh + 12)],
                         radius=14, fill=(0, 0, 0, 55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
    canvas.paste(main, (x, y))

    draw = ImageDraw.Draw(canvas)
    font_spec = _load_font(_find_font(FONT_CANDIDATES_REGULAR), int(cw * 0.028))
    font_price = _load_font(_find_font(FONT_CANDIDATES_BOLD), int(cw * 0.055))
    # 品名自動縮字
    name_font_path = _find_font(FONT_CANDIDATES_BOLD)
    pad = int(cw * 0.06)
    size_px = int(cw * 0.052)
    while size_px > int(cw * 0.03):
        font_name = _load_font(name_font_path, size_px)
        bbox = draw.textbbox((0, 0), name, font=font_name)
        if (bbox[2] - bbox[0]) <= cw - pad * 2 - int(cw * 0.18):
            break
        size_px -= 2

    txt_y = int(ch * 0.78)
    # 細分隔線
    draw.rectangle([(pad, txt_y - 6), (cw - pad, txt_y - 4)], fill=(220, 215, 208))

    draw.text((pad, txt_y + 8), name, fill=(40, 40, 40), font=font_name)
    draw.text((pad, txt_y + int(cw * 0.072)), specs, fill=(135, 128, 118),
              font=font_spec)

    # 價格右下，純文字（no bg），簡潔
    if price:
        bbox = draw.textbbox((0, 0), price, font=font_price)
        pw = bbox[2] - bbox[0]
        draw.text((cw - pad - pw, txt_y + int(cw * 0.055)),
                  price, fill=(30, 30, 30), font=font_price)

    # 選用 tag：左上小 pill
    if tag:
        _draw_small_tag(canvas, tag, pos="top-left",
                        bg=(80, 80, 80, 230), fg=(255, 255, 255))
    return canvas


# ============================================================
# Template B · korean_beauty
# ============================================================

def _render_kbeauty(src: Image.Image, size: Tuple[int, int],
                    name: str, specs: str, price: str,
                    tag: str | None = None) -> Image.Image:
    """軟色調漸層 + 商品浮空 + 右上圓形促銷貼紙 + 氣質排版。"""
    cw, ch = size
    # 米色漸層底
    canvas = Image.new("RGB", size, (253, 246, 240))
    # 底部淡粉綠漸層
    grad = Image.new("RGBA", size, (0, 0, 0, 0))
    gmask = _gradient_alpha(cw, ch, max_alpha=90, ease=1.3, direction="down")
    tint = Image.new("RGBA", size, (217, 232, 220, 255))  # soft sage
    tint.putalpha(gmask)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), tint).convert("RGB")

    # 商品等比塞 60% 區域，置中偏上
    sub = Image.new("RGB", (cw, int(ch * 0.65)))
    x, y, nw, nh = _fit_contain(src, sub, pad_ratio=0.1)
    y += int(ch * 0.04)
    main = src.convert("RGB").resize((nw, nh), Image.LANCZOS)
    # 柔和陰影
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([(x + 10, y + 20), (x + nw + 10, y + nh + 20)],
                         radius=20, fill=(120, 100, 80, 50))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=25))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
    canvas.paste(main, (x, y))

    draw = ImageDraw.Draw(canvas)

    # 字型對比（brand 小+regular；品名大+bold）— 品名自動縮
    font_label = _load_font(_find_font(FONT_CANDIDATES_REGULAR), int(cw * 0.028))
    font_spec = _load_font(_find_font(FONT_CANDIDATES_REGULAR), int(cw * 0.03))
    name_font_path = _find_font(FONT_CANDIDATES_BOLD)
    pad = int(cw * 0.08)
    size_px = int(cw * 0.062)
    while size_px > int(cw * 0.035):
        font_name = _load_font(name_font_path, size_px)
        bbox = draw.textbbox((0, 0), name, font=font_name)
        if (bbox[2] - bbox[0]) <= cw - pad * 2:
            break
        size_px -= 2
    txt_y = int(ch * 0.72)
    # 小 label
    draw.text((pad, txt_y), "— K-BEAUTY", fill=(76, 125, 94), font=font_label)
    # 品名
    draw.text((pad, txt_y + int(cw * 0.04)), name,
              fill=(50, 55, 50), font=font_name)
    # 規格 with · 分隔
    draw.text((pad, txt_y + int(cw * 0.12)), specs,
              fill=(140, 130, 120), font=font_spec)

    # 右上圓形促銷貼紙（含價格）
    if price:
        r = int(cw * 0.11)
        cx, cy = cw - int(cw * 0.11), int(cw * 0.11)
        # 外圈淺色
        draw.ellipse([(cx - r - 6, cy - r - 6), (cx + r + 6, cy + r + 6)],
                     fill=(255, 221, 220, 255))
        # 內圈品牌紅
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                     fill=(226, 92, 95, 255))
        # 價格文字置中
        font_pricec = _load_font(_find_font(FONT_CANDIDATES_BOLD), int(cw * 0.045))
        bbox = draw.textbbox((0, 0), price, font=font_pricec)
        pw = bbox[2] - bbox[0]
        ph = bbox[3] - bbox[1]
        draw.text((cx - pw // 2, cy - ph // 2 - 4), price,
                  fill=(255, 255, 255), font=font_pricec)

    if tag:
        _draw_small_tag(canvas, tag, pos="top-left",
                        bg=(76, 125, 94, 230), fg=(255, 255, 255))
    return canvas


# ============================================================
# Template C · taiwan_daigou
# ============================================================

def _render_daigou(src: Image.Image, size: Tuple[int, int],
                   name: str, specs: str, price: str,
                   tag: str | None = None) -> Image.Image:
    """黃紅對比色塊 + 大價格數字 + 現貨/預購 tag。"""
    cw, ch = size
    canvas = Image.new("RGB", size, (255, 255, 255))

    # 商品等比塞 55%，置上
    sub = Image.new("RGB", (cw, int(ch * 0.58)))
    x, y, nw, nh = _fit_contain(src, sub, pad_ratio=0.08)
    y += int(ch * 0.03)
    main = src.convert("RGB").resize((nw, nh), Image.LANCZOS)
    canvas.paste(main, (x, y))

    draw = ImageDraw.Draw(canvas)

    # 底部黃色大色塊 (覆蓋 42%)
    bar_h = int(ch * 0.42)
    draw.rectangle([(0, ch - bar_h), (cw, ch)], fill=(255, 204, 0))
    # 斜切紅色角（左下）
    tri_h = int(bar_h * 0.6)
    draw.polygon([(0, ch - bar_h), (int(cw * 0.6), ch - bar_h),
                  (0, ch - bar_h + tri_h)], fill=(230, 57, 70))

    # 品名放色塊上緣（黑色 bold 大）— 自動縮字避免溢出
    pad = int(cw * 0.06)
    avail_w = cw - pad * 2
    name_font_path = _find_font(FONT_CANDIDATES_BOLD)
    size_px = int(cw * 0.075)
    while size_px > int(cw * 0.04):
        font_name = _load_font(name_font_path, size_px)
        bbox = draw.textbbox((0, 0), name, font=font_name)
        if (bbox[2] - bbox[0]) <= avail_w:
            break
        size_px -= 4
    draw.text((pad, ch - bar_h + int(bar_h * 0.1)), name,
              fill=(20, 20, 20), font=font_name)

    # 規格（白色小字，紅色色塊內）
    font_spec = _load_font(_find_font(FONT_CANDIDATES_REGULAR), int(cw * 0.034))
    draw.text((pad, ch - bar_h + int(bar_h * 0.33)), specs,
              fill=(255, 255, 255, 230), font=font_spec)

    # 右下巨大價格
    if price:
        font_price_huge = _load_font(_find_font(FONT_CANDIDATES_BOLD),
                                     int(cw * 0.14))
        bbox = draw.textbbox((0, 0), price, font=font_price_huge)
        pw = bbox[2] - bbox[0]
        ph = bbox[3] - bbox[1]
        px = cw - pad - pw
        py = ch - int(bar_h * 0.75)
        # 深色陰影
        draw.text((px + 3, py + 4), price, fill=(100, 60, 0), font=font_price_huge)
        draw.text((px, py), price, fill=(20, 20, 20), font=font_price_huge)

    # 右上 tag（現貨 / 預購，預設 '現貨'）
    tag_text = tag or "現貨"
    _draw_small_tag(canvas, tag_text, pos="top-right",
                    bg=(230, 57, 70, 240), fg=(255, 255, 255),
                    font_size_ratio=0.034)
    return canvas


# ============================================================
# Template D · taiwan_dm  （參考 Pinterest 「產品 dm 排版 設計」）
# ============================================================
# Design notes:
# - 大量留白 60%+（商品小而精）
# - 米色底 / 淡 sage / warm grey 文字
# - 商品置上，下方分區塊：brand label → 品名 → 規格 → 價格 pill
# - 文字絕不蓋在商品上
# - 「件/折」風格 badge 可選（price 填 "8折" / "2件75折" 也可）

def _render_taiwan_dm(src: Image.Image, size: Tuple[int, int],
                      name: str, specs: str, price: str,
                      tag: str | None = None) -> Image.Image:
    cw, ch = size
    # 米色底
    canvas = Image.new("RGB", size, (247, 242, 236))

    # 商品等比塞入上方 55% 區域（直式）/ 50%（方圖）
    product_zone_ratio = 0.55 if ch > cw else 0.50
    sub = Image.new("RGB", (cw, int(ch * product_zone_ratio)))
    x, y, nw, nh = _fit_contain(src, sub, pad_ratio=0.15)
    y += int(ch * 0.05)
    main = src.convert("RGB").resize((nw, nh), Image.LANCZOS)

    # 商品柔和陰影（warm grey）
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([(x + 6, y + 18), (x + nw + 6, y + nh + 18)],
                         radius=8, fill=(120, 100, 80, 45))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=22))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
    canvas.paste(main, (x, y))

    draw = ImageDraw.Draw(canvas)

    # 分區塊起點（商品下方）
    pad = int(cw * 0.09)
    zone_top = int(ch * (product_zone_ratio + 0.06))

    # 1) Brand label：細線 + 小字
    label_font = _load_font(_find_font(FONT_CANDIDATES_REGULAR),
                            int(cw * 0.022))
    # 短橫線
    draw.rectangle([(pad, zone_top), (pad + int(cw * 0.06), zone_top + 2)],
                   fill=(140, 160, 140))
    draw.text((pad + int(cw * 0.08), zone_top - 10),
              "SELECTED  —  精選",
              fill=(130, 125, 115), font=label_font)

    # 2) 品名：bold warm dark，自動縮字
    name_font_path = _find_font(FONT_CANDIDATES_BOLD)
    name_y = zone_top + int(ch * 0.035)
    size_px = int(cw * 0.052)
    while size_px > int(cw * 0.03):
        font_name = _load_font(name_font_path, size_px)
        bbox = draw.textbbox((0, 0), name, font=font_name)
        if (bbox[2] - bbox[0]) <= cw - pad * 2:
            break
        size_px -= 2
    draw.text((pad, name_y), name, fill=(55, 50, 42), font=font_name)

    # 3) 規格：dusty 灰細字 with · 分隔感
    spec_font = _load_font(_find_font(FONT_CANDIDATES_REGULAR),
                           int(cw * 0.025))
    spec_y = name_y + int(cw * 0.065)
    draw.text((pad, spec_y), specs, fill=(145, 135, 120), font=spec_font)

    # 4) 底部價格/優惠 pill — 細線框，不填滿，避免搶眼
    if price:
        price_font = _load_font(_find_font(FONT_CANDIDATES_BOLD),
                                int(cw * 0.038))
        bbox = draw.textbbox((0, 0), price, font=price_font)
        pw = bbox[2] - bbox[0]
        ph = bbox[3] - bbox[1]
        px_pad, py_pad = int(cw * 0.028), int(cw * 0.016)
        p_x1 = pad
        p_y1 = spec_y + int(cw * 0.055)
        p_x2 = p_x1 + pw + px_pad * 2
        p_y2 = p_y1 + ph + py_pad * 2
        # 細線框，米色底
        draw.rounded_rectangle([(p_x1, p_y1), (p_x2, p_y2)],
                               radius=int((p_y2 - p_y1) * 0.5),
                               outline=(76, 125, 94), width=2,
                               fill=(252, 248, 243))
        draw.text((p_x1 + px_pad, p_y1 + py_pad - 2), price,
                  fill=(76, 125, 94), font=price_font)

        # 右側小字補充（若 price 看起來不像 NT$，加「參考價」）
        if "NT$" not in price and "元" not in price and "%" not in price:
            hint_font = _load_font(_find_font(FONT_CANDIDATES_REGULAR),
                                   int(cw * 0.02))
            draw.text((p_x2 + int(cw * 0.025),
                       p_y1 + py_pad + 4),
                      "/ 單件", fill=(160, 155, 145), font=hint_font)

    # 5) tag：右上 sage pill（低調）
    if tag:
        _draw_small_tag(canvas, tag, pos="top-right",
                        bg=(76, 125, 94, 220), fg=(255, 255, 255),
                        font_size_ratio=0.024)
    return canvas


# ---------- 共用 tag ----------

def _draw_small_tag(canvas: Image.Image, text: str,
                    pos: str = "top-left",
                    bg=(214, 69, 69, 230), fg=(255, 255, 255),
                    font_size_ratio: float = 0.028):
    W, H = canvas.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(_find_font(FONT_CANDIDATES_BOLD),
                      int(W * font_size_ratio))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = int(W * 0.022), int(W * 0.011)

    pad = int(W * 0.04)
    if pos == "top-left":
        x1, y1 = pad, pad
    elif pos == "top-right":
        x1 = W - pad - (tw + px * 2)
        y1 = pad
    elif pos == "bottom-left":
        x1, y1 = pad, H - pad - (th + py * 2)
    else:
        x1 = W - pad - (tw + px * 2)
        y1 = H - pad - (th + py * 2)
    x2, y2 = x1 + tw + px * 2, y1 + th + py * 2

    draw.rounded_rectangle([(x1, y1), (x2, y2)],
                           radius=int((y2 - y1) * 0.5), fill=bg)
    draw.text((x1 + px, y1 + py - 2), text, fill=fg, font=font)
    composed = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    # 把 composed 的像素 paste 回 canvas，保留 reference
    canvas.paste(composed)


# ---------- 入口 ----------

def generate_card(image_path: str, name: str, specs: str, price: str,
                  out_path: str, aspect: str = "1:1",
                  template: str = "clean",
                  tag: str | None = None) -> str:
    if aspect not in ASPECT_SIZES:
        raise ValueError(f"aspect 必須是 {list(ASPECT_SIZES)}")
    if template == "auto":
        template = suggest_template(image_path)
    if template not in TEMPLATES:
        raise ValueError(f"template 必須是 {TEMPLATES} 或 'auto'")

    src = Image.open(image_path)
    size = ASPECT_SIZES[aspect]

    renderer = {
        "clean": _render_clean,
        "korean_beauty": _render_kbeauty,
        "taiwan_daigou": _render_daigou,
        "taiwan_dm": _render_taiwan_dm,
    }[template]
    canvas = renderer(src, size, name=name, specs=specs, price=price, tag=tag)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=92)
    return str(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--specs", required=True)
    ap.add_argument("--price", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--aspect", default="1:1", choices=list(ASPECT_SIZES.keys()))
    ap.add_argument("--template", default="clean",
                    choices=TEMPLATES + ["auto"])
    ap.add_argument("--tag", default=None,
                    help="可選標籤：熱銷 / 現貨 / 預購 / 限量 / 新品")
    args = ap.parse_args()

    out = generate_card(
        image_path=args.image, name=args.name, specs=args.specs,
        price=args.price, out_path=args.out, aspect=args.aspect,
        template=args.template, tag=args.tag,
    )
    print(f"OK → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
