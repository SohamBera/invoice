# chat.py
"""
Invoice OCR + GST extractor (Azure-ready)

Mode: Text-layer first -> High-accuracy OCR -> Fallback OCR -> Merge results
Auto scheduler: every 12 hours (optional)
"""

import os
import io
import re
import json
import sqlite3
from datetime import datetime
from typing import List, Tuple
from PIL import Image, ImageOps, ImageFilter
import fitz  # PyMuPDF
import pytesseract

pytesseract.pytesseract.tesseract_cmd = "tesseract"

# Optional OpenCV for better preprocessing
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except:
    OPENCV_AVAILABLE = False

# Google libraries
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from pypdf import PdfReader
from tabulate import tabulate
from dotenv import load_dotenv

# ---------------- CONFIG ----------------
DEBUG_OCR = False
HIGH_ACCURACY_DPI = 600
TESS_CONFIG_TEXT = r"--oem 3 --psm 6"

load_dotenv()
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")
INPUT_FOLDER_ID = os.getenv("INPUT_FOLDER_ID")
PROCESSED_FOLDER_ID = os.getenv("PROCESSED_FOLDER_ID")
SHEET_ID = os.getenv("SHEET_ID")

# ---------------- Google Setup ----------------
SCOPES = ["https://www.googleapis.com/auth/drive",
          "https://www.googleapis.com/auth/spreadsheets"]
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)
sheet_client = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)

# ---------------- SQLite Setup ----------------
DB_FILE = "invoices_new.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

COLUMNS = [
    "Date","Total_Amount","Invoice_Number","IRN",
    "Seller_Name","Seller_GSTIN_UIN","Seller_State","Seller_State_Code",
    "Buyer_Name","Buyer_GSTIN_UIN","Buyer_State","Buyer_State_Code",
    "Buyer_Order_No","Destination","HSN_SAC",
    "IGST","CGST","SGST","Taxable_Value","Total_Tax_Amount",
    "Source_File","Upload_Date","Upload_Time"
]

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES.update({"IGST":"NUMERIC","CGST":"NUMERIC","SGST":"NUMERIC",
                     "Taxable_Value":"NUMERIC","Total_Tax_Amount":"NUMERIC","Total_Amount":"NUMERIC"})
sql = ", ".join([f'"{c}" {COLUMN_TYPES[c]}' for c in COLUMNS])
cur.execute(f"CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY AUTOINCREMENT,{sql})")
conn.commit()

# ---------------- Utilities ----------------
STATE_CODES = {
    "01": "Jammu & Kashmir","02": "Himachal Pradesh","03": "Punjab",
    "04": "Chandigarh","05": "Uttarakhand","06": "Haryana","07": "Delhi",
    "08": "Rajasthan","09": "Uttar Pradesh","10": "Bihar","11": "Sikkim",
    "12": "Arunachal Pradesh","13": "Nagaland","14": "Manipur","15": "Mizoram",
    "16": "Tripura","17": "Meghalaya","18": "Assam","19": "West Bengal",
    "20": "Jharkhand","21": "Odisha","22": "Chhattisgarh","23": "Madhya Pradesh",
    "24": "Gujarat","25": "Daman & Diu","26": "Dadra & Nagar Haveli",
    "27": "Maharashtra","28": "Karnataka","29": "Goa","30": "Lakshadweep",
    "31": "Kerala","32": "Tamil Nadu","33": "Puducherry","34": "Andaman & Nicobar",
    "35": "Telangana","36": "Andhra Pradesh","37": "Ladakh"
}

GSTIN_REGEX = r"\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}"

def safe_float(x) -> float:
    try:
        if x is None: return 0.0
        s = str(x).strip().replace("₹","").replace("Rs.","").replace("INR","").replace(",","")
        s = re.sub(r'[Oo]', '0', s)
        s = re.sub(r'[^0-9\-\.\+eE]', '', s)
        return float(s) if s else 0.0
    except: return 0.0

def extract_state_code_from_gstin(gstin: str) -> str:
    gstin = (gstin or "").strip()
    return gstin[:2] if len(gstin)>=2 and gstin[:2].isdigit() else ""

def gst_code_to_state(code: str) -> str:
    return STATE_CODES.get(code, "")

def find_gstins_in_text(text: str) -> List[str]:
    found = re.findall(GSTIN_REGEX, re.sub(r'[^0-9A-Za-z]', '', text.upper()))
    return found[:2] if found else []

def normalize_ocr_line(line: str) -> str:
    if not line: return ""
    ln = line.strip().replace("\t"," ").replace("C6ST","CGST").replace("S6ST","SGST").replace("1GST","IGST")
    return re.sub(r'\s{2,}', ' ', ln)

def read_text_layer(pdf_bytes: io.BytesIO) -> str:
    text = ""
    try:
        reader = PdfReader(pdf_bytes)
        for p in reader.pages:
            t = p.extract_text()
            if t: text += t + "\n"
    except: pass
    return text

def pdf_page_to_image(pdf_bytes: io.BytesIO, page_no:int=0, dpi:int=300) -> Image.Image:
    pdf_bytes.seek(0)
    pdf = fitz.open(stream=pdf_bytes.read(), filetype="pdf")
    page = pdf[page_no]
    pix = page.get_pixmap(dpi=dpi)
    mode = "RGBA" if pix.alpha else "RGB"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if pix.alpha: img = img.convert("RGB")
    pdf.close()
    return img

def preprocess_for_high_accuracy(pil_img: Image.Image) -> Image.Image:
    try:
        img = pil_img.convert("RGB")
        if OPENCV_AVAILABLE:
            arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
            _, th = cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
            return Image.fromarray(th).convert("RGB")
        else:
            img = ImageOps.grayscale(img)
            img = img.filter(ImageFilter.MedianFilter(size=3))
            img = img.point(lambda p: 255 if p>180 else 0)
            return img.convert("RGB")
    except: return pil_img

def ocr_lines_from_image(pil_img: Image.Image) -> List[str]:
    raw = pytesseract.image_to_string(pil_img, config=TESS_CONFIG_TEXT, lang='eng')
    return [normalize_ocr_line(l) for l in raw.splitlines() if l.strip()]

def extract_invoice_number_from_lines(lines: List[str]) -> str:
    joined = "\n".join(lines)
    m = re.search(r"[A-Z0-9/-]{3,}", joined)
    return m.group() if m else ""

def extract_gstins_from_lines(lines: List[str]) -> Tuple[str,str,str,str]:
    joined = "\n".join(lines)
    found = find_gstins_in_text(joined)
    seller = found[0] if len(found)>0 else ""
    buyer  = found[1] if len(found)>1 else ""
    seller_state = extract_state_code_from_gstin(seller)
    buyer_state  = extract_state_code_from_gstin(buyer)
    return seller, seller_state, buyer, buyer_state

def extract_gst_values_from_lines(lines: List[str]) -> dict:
    res = {"Taxable_Value":0,"CGST":0,"SGST":0,"IGST":0}
    for ln in lines:
        nums = [safe_float(n) for n in re.findall(r'[\d,]+\.\d+|[\d,]+', ln)]
        ln_up = ln.upper()
        if "TAXABLE" in ln_up: res["Taxable_Value"]=max(res["Taxable_Value"], *(nums or [0]))
        if "CGST" in ln_up: res["CGST"]=max(res["CGST"], *(nums or [0]))
        if "SGST" in ln_up: res["SGST"]=max(res["SGST"], *(nums or [0]))
        if "IGST" in ln_up: res["IGST"]=max(res["IGST"], *(nums or [0]))
    return res

def extract_fields_from_pdfbytes(pdf_bytes: io.BytesIO) -> dict:
    pdf_bytes.seek(0)
    text_layer = read_text_layer(pdf_bytes)
    lines = [normalize_ocr_line(l) for l in text_layer.splitlines() if l.strip()]
    try:
        img = pdf_page_to_image(pdf_bytes, dpi=HIGH_ACCURACY_DPI)
        lines += [l for l in ocr_lines_from_image(preprocess_for_high_accuracy(img)) if l not in lines]
    except: pass

    # Deduplicate
    merged_lines = []
    seen=set()
    for l in lines:
        if l not in seen:
            merged_lines.append(l)
            seen.add(l)

    # Extract fields
    gst_values = extract_gst_values_from_lines(merged_lines)
    seller, seller_state, buyer, buyer_state = extract_gstins_from_lines(merged_lines)
    inv = extract_invoice_number_from_lines(merged_lines)

    return {
        "Invoice_Number": inv,
        "Seller_GST": seller,
        "Seller_State": gst_code_to_state(seller_state),
        "Seller_State_Code": seller_state,
        "Buyer_GST": buyer,
        "Buyer_State": gst_code_to_state(buyer_state),
        "Buyer_State_Code": buyer_state,
        "IGST": gst_values.get("IGST",0),
        "CGST": gst_values.get("CGST",0),
        "SGST": gst_values.get("SGST",0),
        "Taxable_Value": gst_values.get("Taxable_Value",0),
        "Total_Amount": gst_values.get("Taxable_Value",0) +
                        gst_values.get("IGST",0) +
                        gst_values.get("CGST",0) +
                        gst_values.get("SGST",0)
    }
