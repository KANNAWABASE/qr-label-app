import streamlit as st
import pandas as pd
import os
import zipfile
from io import BytesIO
from datetime import datetime

# QR + PDF用
import qrcode
from PIL import Image
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

# ===== UI設定 =====
st.set_page_config(page_title="QRシール生成", layout="centered")

st.title("📱 QRシール生成ツール")
st.caption("1店舗70面 / スマホ対応")

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

col1, col2 = st.columns(2)
with col1:
    color_top = st.color_picker("店名カラー", "#393f4c")
    color_bottom = st.color_picker("日付カラー", "#777777")
with col2:
    color_qr = st.color_picker("QRカラー", "#000000")

# ===== ファイル読み込み =====
st.subheader("📂 データアップロード")
file = st.file_uploader("CSV または Excel", type=["csv", "xlsx"])

def make_qr(data):
    qr = qrcode.QRCode(box_size=6, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=color_qr, back_color="white").convert("RGB")
    return img

def pil_to_reader(img):
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return ImageReader(bio)

def draw_label(c, x, y, shop, url, event):
    w = 20 * mm
    h = 20 * mm

    # 店名
    c.setFont(FONT_NAME, 5.5)
    c.setFillColor(colors.HexColor(color_top))
    c.drawCentredString(x + w/2, y + h - 3 * mm, str(shop))

    # QR
    qr = make_qr(url)
    qr_reader = pil_to_reader(qr)

    size = 11 * mm
    c.drawImage(qr_reader, x + (w-size)/2, y + 4 * mm, size, size)

    # 日付
    c.setFont(FONT_NAME, 4.2)
    c.setFillColor(colors.HexColor(color_bottom))
    c.drawCentredString(x + w/2, y + 1.2 * mm, str(event))

def create_pdf(row):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for i in range(70):
        col = i % COLS
        row_i = i // COLS

        x = (LEFT + col * (LABEL_W + 4)) * mm
        y = (297 - (TOP + row_i * (LABEL_H + 4) + LABEL_H)) * mm

        draw_label(c, x, y, row["店名"], row["QRリンク"], row["開催名年月"])

    c.save()
    buffer.seek(0)
    return buffer

# ===== メイン処理 =====
if file:
    if file.name.endswith(".csv"):
        df = pd.read_csv(file, encoding="utf-8-sig")
    else:
        df = pd.read_excel(file)

    st.success(f"{len(df)}件 読み込み成功")

    # プレビュー
    st.subheader("👀 プレビュー")
    st.dataframe(df.head())

    mode = st.radio("出力方法", ["1店舗ずつPDF", "まとめてZIP"])

    if st.button("🚀 生成する", use_container_width=True):

        if mode == "1店舗ずつPDF":
            for i, row in df.iterrows():
                pdf = create_pdf(row)
                filename = f"{row.get('店舗ID',i)}_{row['店名']}.pdf"

                st.download_button(
                    f"{row['店名']} をダウンロード",
                    data=pdf,
                    file_name=filename,
                    mime="application/pdf"
                )

        else:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as z:
                for i, row in df.iterrows():
                    pdf = create_pdf(row)
                    filename = f"{row.get('店舗ID',i)}_{row['店名']}.pdf"
                    z.writestr(filename, pdf.read())

            zip_buffer.seek(0)

            st.download_button(
                "📦 ZIPダウンロード",
                data=zip_buffer,
                file_name="labels.zip",
                mime="application/zip"
            )
