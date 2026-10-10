#!/usr/bin/env python3
"""
商品卡產生器 — Streamlit Web UI
---------------------------------------------------
手機瀏覽器打開可用、加到主畫面變類 App。
"""
from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

from generate_card import generate_card, ASPECT_SIZES

# ============================================================
# Page config + 緊湊化 CSS（修 Streamlit 預設頂部 toolbar + 手機排版）
# ============================================================

st.set_page_config(
    page_title="商品卡產生器", page_icon="🏷️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* 隱藏 Streamlit 預設 header 的紅 bar / 工具列 */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden; height: 0;}
.stDeployButton {display: none;}

/* 主容器緊貼頂部，手機也不浪費空間 */
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 1rem !important;
    max-width: 780px;
}

/* 按鈕全寬，手機更好按 */
.stButton button, .stDownloadButton button { width: 100%; }

/* 標題緊湊 */
h1 { font-size: 1.5rem !important; margin-bottom: 0.2rem !important; }
h2 { font-size: 1.1rem !important; }

/* 手機 viewport */
@media (max-width: 480px) {
    .block-container { padding: 0.5rem !important; }
    h1 { font-size: 1.25rem !important; }
    .stRadio label p, .stSelectbox label p, .stTextInput label p { font-size: 0.9rem; }
}
</style>
""", unsafe_allow_html=True)

st.title("🏷️ 商品卡產生器")
st.caption("丟原圖 + 填 3 欄 → IG / 代購 / Line 群可用。背景不後製，只加 overlay。")

# ============================================================
# 模式 + 共用設定（compact：one row）
# ============================================================

col_m, col_a, col_bg = st.columns([1.1, 1, 1])
with col_m:
    mode = st.radio("模式", ["單張", "批次"], horizontal=True, label_visibility="visible")
with col_a:
    aspect = st.selectbox("比例", list(ASPECT_SIZES.keys()), index=0)
with col_bg:
    bg_mode = st.selectbox("留白", ["blur", "white", "black"], index=0,
                           help="原圖等比塞進畫布後，上下/左右空白怎麼補")

# ============================================================
# 單張模式
# ============================================================

if mode == "單張":
    file = st.file_uploader(
        "商品原圖", type=["jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed",
    )

    # OCR inline：縮小不佔空間
    use_ocr = False
    if os.environ.get("GEMINI_API_KEY"):
        use_ocr = st.checkbox("🇰🇷 Vision 讀韓文自動填規格/價格（品名仍自己打）",
                              value=False)

    col_n = st.container()
    name  = col_n.text_input("品名（中文自己打）",
                             placeholder="MEDIHEAL 楮樹美白4D面膜")

    col_s, col_p = st.columns(2)
    specs = col_s.text_input("規格",
                             value=st.session_state.get("prefill_specs", ""),
                             placeholder="一片")
    price = col_p.text_input("價格",
                             value=st.session_state.get("prefill_price", ""),
                             placeholder="NT$89")

    with st.expander("標籤（可選）"):
        badge = st.selectbox("", ["(無)", "熱銷", "限量", "新品", "預購", "特價"],
                             label_visibility="collapsed")

    # OCR 預讀（用 inline button，不浮空）
    if use_ocr and file:
        if st.button("🔍 先讀韓文包裝（可省略跳過）", type="secondary"):
            try:
                from vision_extract import extract
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                    tf.write(file.getvalue())
                    tmp_path = tf.name
                with st.spinner("Gemini Vision 讀取..."):
                    info = extract(tmp_path)
                st.success("讀取成功，請確認/修改欄位：")
                st.json(info)
                if info.get("specs"):
                    st.session_state["prefill_specs"] = info["specs"]
                if info.get("price_display"):
                    st.session_state["prefill_price"] = info["price_display"]
                st.rerun()
            except Exception as e:
                st.error(f"OCR 失敗：{e}")

    # 主按鈕
    go = st.button("✨ 產出商品卡", type="primary",
                   disabled=not (file and name))

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
        st.image(str(out_path), caption=f"{aspect} 商品卡", use_container_width=True)
        with open(out_path, "rb") as f:
            st.download_button("⬇️ 下載 JPG", f, file_name=out_path.name,
                               mime="image/jpeg")

# ============================================================
# 批次模式
# ============================================================

else:
    st.caption("上傳多張 → 表格填 3 欄 → 一鍵全部產出 + ZIP 下載")
    files = st.file_uploader("多張商品原圖", type=["jpg", "jpeg", "png", "webp"],
                             accept_multiple_files=True,
                             label_visibility="collapsed")
    if files:
        default_rows = [
            {"檔名": f.name, "品名": "", "規格": "", "價格": "", "標籤": ""}
            for f in files
        ]
        df = st.data_editor(pd.DataFrame(default_rows), num_rows="fixed",
                            use_container_width=True, key="batch_table")

        if st.button("✨ 批次產出", type="primary"):
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
            cols = st.columns(2)
            for i, p in enumerate(results):
                with cols[i % 2]:
                    st.image(str(p), caption=p.name, use_container_width=True)

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                for p in results:
                    zf.write(p, arcname=p.name)
            st.download_button("⬇️ 下載全部（ZIP）", buf.getvalue(),
                               file_name="product_cards.zip",
                               mime="application/zip")
