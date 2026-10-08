#!/usr/bin/env python3
"""
vision_extract.py — Phase 2
---------------------------------------------------
把韓國商品原圖丟給 Gemini Vision，吐出 JSON：
    { brand_ko, brand_zh_guess, specs, price_kr, price_display, ingredients_highlights }

**品名欄不自動填**（使用者說要自己翻譯中文命名）。
只回「輔助資訊」給 Line Bot / Streamlit 預帶 specs + price 兩欄。

Usage:
    python vision_extract.py --image mediheal.jpg
    # 需設環境變數 GEMINI_API_KEY

Model: gemini-2.5-flash（省費用、Vision 讀包裝 OK）
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests  # pip install requests

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

PROMPT = """你是韓國代購商品助理。這張圖是韓國商品的包裝照片。

請從包裝讀出以下欄位，回純 JSON（不要 markdown 包裹）：
{
  "brand_ko": "包裝上原韓文品牌名",
  "brand_zh_guess": "品牌中文（若有常見譯名，否則 null）",
  "specs": "容量/數量，例 '30ml' 或 '10片入' 或 '一盒20包'",
  "price_kr": "若包裝上有標韓元價格，填數字（含千分位），否則 null",
  "price_display": "顯示用價格字串，優先用 'NT$xx'；若無新台幣只給 KRW 原價",
  "ingredients_highlights": ["成分亮點 1", "成分亮點 2"]
}

規則：
- 讀不到的欄位填 null
- **不要回品名**（使用者會自己翻譯中文品名）
- 只回 JSON，不要說明文字
"""


def _b64_image(path: str) -> tuple[str, str]:
    ext = Path(path).suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        return mime, base64.b64encode(f.read()).decode()


def extract(image_path: str, api_key: str | None = None) -> dict:
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("需要 GEMINI_API_KEY（環境變數或 --api-key）")

    mime, b64 = _b64_image(image_path)
    body = {
        "contents": [{
            "parts": [
                {"text": PROMPT},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    resp = requests.post(
        f"{GEMINI_ENDPOINT}?key={api_key}",
        json=body, timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini 回傳格式異常: {data}") from e
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()
    result = extract(args.image, api_key=args.api_key)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
