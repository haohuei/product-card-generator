#!/usr/bin/env python3
"""
app.py — Phase 3 Streamlit Web UI
---------------------------------------------------
在瀏覽器上傳商品圖 + 填 3 欄 → 一鍵產卡。
支援單張與批次（多張同時上傳 + 編輯表格）。

Run:
    pip install streamlit pillow pandas requests --break-system-packages
    streamlit run app.py --server.port 8505
"""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

from generate_card import generate_card, ASPECT_SIZES

st.set_page_config(page_title="商品卡產生器", page_icon="🏷️", layout="wide")
st.title("🏷️ 商品卡產生器")
st.caption("丟原圖 + 填 3 欄 → 產出 IG / 代購網站 / Line 群用的商品卡。背景不後製，只加文字 overlay。")

mode = st.radio("模式", ["單張", "批次（多張）"], horizontal=True)

aspect = st.selectbox("輸出比例", list(ASPECT_SIZES.keys()), index=0)
bg_mode = st.selectbox("留白填充", ["blur", "white", "black"], index=0,
                       help="原圖等比塞進畫布後，上下/左右空白怎麼補")

# =========================================================
# 單張
# =========================================================
if mode == "單張":
    col_in, col_out = st.columns([1, 1])

    with col_in:
        file = st.file_uploader("商品原圖", type=["jpg", "jpeg", "png", "webp"])
        name  = st.text_input("品名（中文，自己打）", placeholder="MEDIHEAL 楮樹美白4D面膜")
        specs = st.text_input("規格", placeholder="一片")
        price = st.text_input("價格", placeholder="NT$89")
        badge = st.selectbox("標籤（可選）",
                             ["(無)", "熱銷", "限量", "新品", "預購", "特價"])
        use_ocr = st.checkbox("🇰🇷 Gemini Vision 讀韓文（自動 fill 規格/價格）",
                              value=False,
                              help="需設 GEMINI_API_KEY 環境變數。品名不會自動填。")

        go = st.button("產出商品卡", type="primary", disabled=not (file and name))

        if use_ocr and file:
            if st.button("🔍 先讀韓文包裝"):
                try:
                    from vision_extract import extract
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                        tf.write(file.getvalue())
                        tmp_path = tf.name
                    with st.spinner("呼叫 Gemini Vision..."):
                        info = extract(tmp_path)
                    st.success("讀取成功，請確認/修改：")
                    st.json(info)
                    if info.get("specs"):
                        st.session_state["prefill_specs"] = info["specs"]
                    if info.get("price_display"):
                        st.session_state["prefill_price"] = info["price_display"]
                except Exception as e:
                    st.error(f"OCR 失敗：{e}")

    with col_out:
        if go and file and name:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                tf.write(file.getvalue())
                in_path = tf.name
            out_path = Path(tempfile.gettempdir()) / f"card_{Path(file.name).stem}.jpg"
            generate_card(
                image_path=in_path, name=name, specs=specs or "",
                price=price or "", out_path=str(out_path),
                aspect=aspect,
                badge=None if badge == "(無)" else badge,
                bg_mode=bg_mode,
            )
            st.image(str(out_path), caption=f"{aspect} 商品卡", use_column_width=True)
            with open(out_path, "rb") as f:
                st.download_button("⬇️ 下載 JPG", f, file_name=out_path.name,
                                   mime="image/jpeg")

# =========================================================
# 批次
# =========================================================
else:
    st.subheader("批次模式")
    st.caption("上傳多張圖 → 下方表格編輯品名/規格/價格 → 一次產出全部。")

    files = st.file_uploader("多張商品原圖", type=["jpg", "jpeg", "png", "webp"],
                             accept_multiple_files=True)
    if files:
        default_rows = [
            {"檔名": f.name, "品名": "", "規格": "", "價格": "", "標籤": ""}
            for f in files
        ]
        df = st.data_editor(pd.DataFrame(default_rows), num_rows="fixed",
                            use_container_width=True, key="batch_table")

        if st.button("批次產出", type="primary"):
            out_dir = Path(tempfile.gettempdir()) / "product_cards_batch"
            out_dir.mkdir(exist_ok=True)
            results = []
            progress = st.progress(0.0)
            for i, (f, row) in enumerate(zip(files, df.itertuples(index=False))):
                if not row.品名:
                    continue
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                    tf.write(f.getvalue())
                    in_path = tf.name
                out_path = out_dir / f"card_{Path(f.name).stem}.jpg"
                generate_card(
                    image_path=in_path, name=row.品名,
                    specs=row.規格 or "", price=row.價格 or "",
                    out_path=str(out_path), aspect=aspect,
                    badge=row.標籤 or None, bg_mode=bg_mode,
                )
                results.append(out_path)
                progress.progress((i + 1) / len(files))

            st.success(f"產出 {len(results)} 張")
            cols = st.columns(3)
            for i, p in enumerate(results):
                with cols[i % 3]:
                    st.image(str(p), caption=p.name, use_column_width=True)

            # 打包 zip 給下載
            import zipfile
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                for p in results:
                    zf.write(p, arcname=p.name)
            st.download_button("⬇️ 下載全部（ZIP）", buf.getvalue(),
                               file_name="product_cards.zip",
                               mime="application/zip")
