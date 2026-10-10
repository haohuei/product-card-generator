#!/usr/bin/env python3
"""
商品卡產生器 · Streamlit Web UI
---------------------------------------------------
手機瀏覽器打開可用、加到主畫面變類 App。
支援 3 個商品 DM 版型：clean / korean_beauty / taiwan_daigou。
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

from generate_card import generate_card, suggest_template, ASPECT_SIZES, TEMPLATES

# ============================================================
# Secrets fallback (Streamlit Cloud → env var)
# ============================================================

try:
    for key in ("GEMINI_API_KEY", "GEMINI_MODEL"):
        if key in st.secrets:
            os.environ[key] = st.secrets[key]
except Exception:
    pass  # 本機跑無 st.secrets

# ============================================================
# Page config + 緊湊化 CSS
# ============================================================

st.set_page_config(
    page_title="商品卡產生器", page_icon="🏷️",
    layout="centered", initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden; height: 0;}
.stDeployButton {display: none;}
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 1rem !important;
    max-width: 780px;
}
.stButton button, .stDownloadButton button { width: 100%; }
h1 { font-size: 1.5rem !important; margin-bottom: 0.2rem !important; }
h2 { font-size: 1.1rem !important; }
@media (max-width: 480px) {
    .block-container { padding: 0.5rem !important; }
    h1 { font-size: 1.25rem !important; }
}
</style>
""", unsafe_allow_html=True)

st.title("🏷️ 商品卡產生器")
st.caption("丟原圖 + 填 3 欄 → IG / 代購 / Line 群可用。3 個商品 DM 版型可選。")

# ============================================================
# 版型說明與對應圖
# ============================================================

TEMPLATE_LABELS = {
    "clean":          "A · 乾淨商品照（白底 / 極簡）",
    "korean_beauty":  "B · K-beauty（軟色調 + 圓貼紙）",
    "taiwan_daigou":  "C · 台灣代購（黃紅色塊 + 大價格）",
    "taiwan_dm":      "D · 台灣 DM（米色留白 + 分區塊，建議 9:16）",
    "promo_bundle":   "E · 促銷組合（黃底 + 多商品 + 大% / 大價格）",
}

# ============================================================
# 共用設定 ─ 一排三欄
# ============================================================

col_m, col_a, col_t = st.columns([1, 1, 1.4])
with col_m:
    mode = st.radio("模式", ["單張", "批次"], horizontal=True)
with col_a:
    aspect = st.selectbox("比例", list(ASPECT_SIZES.keys()), index=0)
with col_t:
    template_label = st.selectbox(
        "版型",
        ["（自動偵測）"] + list(TEMPLATE_LABELS.values()),
        index=0,
        help="自動偵測會依商品圖判斷適合版型",
    )

def resolve_template(label: str, image_path: str | None = None) -> str:
    if label == "（自動偵測）":
        if image_path:
            return suggest_template(image_path)
        return "clean"
    for k, v in TEMPLATE_LABELS.items():
        if v == label:
            return k
    return "clean"

# ============================================================
# 單張模式
# ============================================================

if mode == "單張":
    file = st.file_uploader(
        "商品原圖", type=["jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed",
    )

    # E 模板專用：額外 1-2 張組合商品圖
    extra_files = []
    if template_label == TEMPLATE_LABELS["promo_bundle"]:
        st.caption("E 模板支援組合包：可額外上傳 1-2 張商品圖，自動橫排 + 「+」連接")
        extra_files = st.file_uploader(
            "額外商品圖（可選，共 1-2 張組合包）",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True, key="extra_bundle_files",
        )
        extra_files = (extra_files or [])[:2]

    # 顯示 auto-suggest（有圖時）
    if file and template_label == "（自動偵測）":
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            tf.write(file.getvalue())
            peek_path = tf.name
        auto_t = suggest_template(peek_path)
        st.info(f"🔍 自動建議版型：**{TEMPLATE_LABELS[auto_t]}**（可在上方版型手動覆蓋）")

    # OCR inline（只在有 GEMINI_API_KEY 才顯示）
    if os.environ.get("GEMINI_API_KEY") and file:
        if st.button("🇰🇷 讀韓文包裝自動填規格/價格", type="secondary"):
            try:
                from vision_extract import extract
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                    tf.write(file.getvalue())
                    tmp_path = tf.name
                with st.spinner("Gemini Vision 讀取..."):
                    info = extract(tmp_path)
                st.success("讀取成功，欄位已預填：")
                st.json(info)
                if info.get("specs"):
                    st.session_state["prefill_specs"] = info["specs"]
                if info.get("price_display"):
                    st.session_state["prefill_price"] = info["price_display"]
                st.rerun()
            except Exception as e:
                st.error(f"OCR 失敗：{e}")

    name = st.text_input("品名（中文自己打）",
                         placeholder="MEDIHEAL 楮樹美白4D面膜")
    col_s, col_p = st.columns(2)
    specs = col_s.text_input("規格",
                             value=st.session_state.get("prefill_specs", ""),
                             placeholder="一片")
    price = col_p.text_input("價格",
                             value=st.session_state.get("prefill_price", ""),
                             placeholder="NT$89")

    with st.expander("標籤（可選）"):
        tag = st.selectbox("", ["(無)", "現貨", "預購", "熱銷", "限量", "新品", "特價"],
                           label_visibility="collapsed")

    go = st.button("✨ 產出商品卡", type="primary",
                   disabled=not (file and name))

    if go and file and name:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            tf.write(file.getvalue())
            in_path = tf.name
        template_key = resolve_template(template_label, in_path)

        # extras 寫到暫存檔
        extra_paths = []
        for ef in extra_files or []:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as etf:
                etf.write(ef.getvalue())
                extra_paths.append(etf.name)

        out_path = Path(tempfile.gettempdir()) / f"card_{Path(file.name).stem}.jpg"
        generate_card(
            image_path=in_path, name=name, specs=specs or "",
            price=price or "", out_path=str(out_path),
            aspect=aspect, template=template_key,
            tag=None if tag == "(無)" else tag,
            extra_image_paths=extra_paths,
        )
        st.image(str(out_path),
                 caption=f"{aspect} · {TEMPLATE_LABELS[template_key]}",
                 use_container_width=True)
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
                template_key = resolve_template(template_label, in_path)
                out_path = out_dir / f"card_{Path(f.name).stem}.jpg"
                generate_card(
                    image_path=in_path, name=row.品名,
                    specs=row.規格 or "", price=row.價格 or "",
                    out_path=str(out_path), aspect=aspect,
                    template=template_key, tag=row.標籤 or None,
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
