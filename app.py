import streamlit as st
import pandas as pd
import os
import zipfile
from io import BytesIO

import qrcode
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors


# ===== UI設定 =====
st.set_page_config(page_title="QRシール生成", layout="centered")

st.title("📱 鉄輪遊市QRシール生成ツール")
st.caption("1店舗70面（A-one品番31556） / PDF直接 + 店舗別ZIP対応")


# ===== フォント =====
FONT_PATH = "NotoSansJP-Regular.ttf"
FONT_NAME = "NotoJP"

if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
else:
    FONT_NAME = "Helvetica"


# ===== レイアウト設定 =====
LABEL_W = 20
LABEL_H = 20
COLS = 7
ROWS = 10

LEFT = st.number_input("左余白(mm)", value=23.0)
TOP = st.number_input("上余白(mm)", value=30.5)


# ===== 色設定 =====
st.subheader("🎨 デザイン設定")

same_color = st.checkbox("店名・日付・QRを同じ色にする", value=False)

if same_color:
    master_color = st.color_picker("共通カラー", "#393f4c")
    color_top = master_color
    color_bottom = master_color
    color_qr = master_color
else:
    col1, col2 = st.columns(2)

    with col1:
        color_top = st.color_picker("店名カラー", "#393f4c")
        color_bottom = st.color_picker("日付カラー", "#777777")

    with col2:
        color_qr = st.color_picker("QRカラー", "#000000")


# ===== ファイル読み込み =====
st.subheader("📂 データアップロード")
file = st.file_uploader("CSV または Excel", type=["csv", "xlsx"])


def safe_filename(text):
    text = str(text).strip()
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
        text = text.replace(ch, "_")
    return text


def make_qr(data):
    qr = qrcode.QRCode(box_size=6, border=1)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color=color_qr, back_color="white").convert("RGB")
    return img


def pil_to_reader(img):
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return ImageReader(bio)


def draw_label(c, x, y, shop, url, event):
    w = LABEL_W * mm
    h = LABEL_H * mm

    # 店名
    c.setFont(FONT_NAME, 5.5)
    c.setFillColor(colors.HexColor(color_top))
    c.drawCentredString(x + w / 2, y + h - 3 * mm, str(shop))

    # QR
    qr = make_qr(url)
    qr_reader = pil_to_reader(qr)

    size = 11 * mm
    c.drawImage(qr_reader, x + (w - size) / 2, y + 4 * mm, size, size)

    # 開催名年月
    c.setFont(FONT_NAME, 4.2)
    c.setFillColor(colors.HexColor(color_bottom))
    c.drawCentredString(x + w / 2, y + 1.2 * mm, str(event))


def create_pdf(row):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for i in range(70):
        col = i % COLS
        row_i = i // COLS

        x = (LEFT + col * (LABEL_W + 4)) * mm
        y = (297 - (TOP + row_i * (LABEL_H + 4) + LABEL_H)) * mm

        draw_label(
            c,
            x,
            y,
            row["店名"],
            row["QRリンク"],
            row["開催名年月"]
        )

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def create_merged_pdf(df):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for _, row in df.iterrows():
        for i in range(70):
            col = i % COLS
            row_i = i // COLS

            x = (LEFT + col * (LABEL_W + 4)) * mm
            y = (297 - (TOP + row_i * (LABEL_H + 4) + LABEL_H)) * mm

            draw_label(
                c,
                x,
                y,
                row["店名"],
                row["QRリンク"],
                row["開催名年月"]
            )

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def create_zip_with_multiple_files(files):
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for item in files:
            z.writestr(item["filename"], item["data"])

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# ===== メイン処理 =====
if file:
    if file.name.endswith(".csv"):
        df = pd.read_csv(file, encoding="utf-8-sig")
    else:
        df = pd.read_excel(file)

    required_cols = ["店名", "QRリンク", "開催名年月"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"必要な列がありません: {', '.join(missing_cols)}")
        st.stop()

    st.success(f"{len(df)}件 読み込み成功")

    st.subheader("👀 プレビュー")
    st.dataframe(df.head())

    mode = st.radio(
        "出力方法",
        ["1店舗ずつPDF", "まとめて1つのPDF"]
    )

    if st.button("🚀 生成する", use_container_width=True):

        event_name = safe_filename(df.iloc[0]["開催名年月"])

        if mode == "1店舗ずつPDF":
            single_pdfs = []

            for i, row in df.iterrows():
                pdf_bytes = create_pdf(row)

                store_id = row.get("店舗ID", i)
                shop_name = safe_filename(row["店名"])

                filename = f"{event_name}_{store_id}_{shop_name}.pdf"

                single_pdfs.append({
                    "label": f"📄 {row['店名']} のPDF",
                    "filename": filename,
                    "data": pdf_bytes
                })

            zip_bytes = create_zip_with_multiple_files(single_pdfs)

            st.session_state["single_pdfs"] = single_pdfs
            st.session_state["single_zip"] = zip_bytes
            st.session_state["single_zip_filename"] = "qr_labels_by_shop.zip"

            st.session_state.pop("merged_pdf", None)
            st.session_state.pop("merged_filename", None)

        else:
            pdf_bytes = create_merged_pdf(df)
            pdf_filename = f"{event_name}_まとめPDF.pdf"

            st.session_state["merged_pdf"] = pdf_bytes
            st.session_state["merged_filename"] = pdf_filename

            st.session_state.pop("single_pdfs", None)
            st.session_state.pop("single_zip", None)
            st.session_state.pop("single_zip_filename", None)


    # ===== 1店舗ずつダウンロード =====
    if "single_pdfs" in st.session_state:
        st.subheader("⬇️ 1店舗ずつPDFダウンロード")

        for i, item in enumerate(st.session_state["single_pdfs"]):
            st.download_button(
                label=item["label"],
                data=item["data"],
                file_name=item["filename"],
                mime="application/pdf",
                key=f"single_pdf_download_{i}",
                use_container_width=True,
                on_click="ignore"
            )

        st.download_button(
            label="📦 スマホ用：店舗別PDFをZIPでまとめてダウンロード",
            data=st.session_state["single_zip"],
            file_name=st.session_state["single_zip_filename"],
            mime="application/octet-stream",
            key="single_zip_download",
            use_container_width=True
        )

        st.caption("Android Firefoxでは、この店舗別ZIPが一番安定します。")


    # ===== まとめPDFダウンロード =====
    if "merged_pdf" in st.session_state:
        st.subheader("⬇️ まとめPDFダウンロード")

        st.download_button(
            label="📄 まとめPDFを直接ダウンロード",
            data=st.session_state["merged_pdf"],
            file_name=st.session_state["merged_filename"],
            mime="application/pdf",
            key="merged_pdf_download",
            use_container_width=True,
            on_click="ignore"
        )

        st.caption("まとめPDFが保存できないスマホでは、出力方法を「1店舗ずつPDF」にして店舗別ZIPを使ってください。")

else:
    st.info("CSVまたはExcelをアップロードしてください。")
