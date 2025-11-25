# chat.py
"""
Invoice OCR + GST extractor for scanned PDFs (Azure-ready)

Features:
1. Converts PDF pages to images
2. Performs OCR using pytesseract
3. Extracts full invoice fields:
   Invoice_Number, Invoice_Date, Total_Amount, IRN,
   Seller_Name, Seller_GSTIN_UIN, Seller_State_Name_Code,
   Buyer_Name, Buyer_GSTIN_UIN, Buyer_State_Name_Code,
   Buyer_Order_No, Destination, HSN_SAC, IGST, CGST, SGST,
   Taxable_Value, Total_Tax_Amount, Source_File, Upload_Date, Upload_Time
"""

import os
import re
import json
import io
from datetime import datetime
from PIL import Image, ImageOps, ImageFilter
import fitz  # PyMuPDF
import pytesseract

# Folder for PDF uploads in Azure
PDF_FOLDER = "./pdfs"
os.makedirs(PDF_FOLDER, exist_ok=True)

# GST/State mapping
STATE_CODE_MAPPING = {
    "01": "JAMMU & KASHMIR", "02": "HIMACHAL PRADESH", "03": "PUNJAB",
    "04": "CHANDIGARH", "05": "UTTARAKHAND", "06": "HARYANA",
    "07": "DELHI", "08": "RAJASTHAN", "09": "UTTAR PRADESH",
    "10": "BIHAR", "11": "SIKKIM", "12": "ARUNACHAL PRADESH",
    "13": "NAGALAND", "14": "MANIPUR", "15": "MIZORAM", "16": "TRIPURA",
    "17": "MEGHALAYA", "18": "ASSAM", "19": "WEST BENGAL", "20": "JHARKHAND",
    "21": "ODISHA", "22": "CHATTISGARH", "23": "MADHYA PRADESH",
    "24": "GUJARAT", "25": "DAMAN AND DIU", "26": "DADRA AND NAGAR HAVELI",
    "27": "MAHARASHTRA", "28": "ANDHRA PRADESH", "29": "KARNATAKA",
    "30": "GOA", "31": "LAKSHADWEEP", "32": "KERALA", "33": "TAMIL NADU",
    "34": "PUDUCHERRY", "35": "ANDAMAN AND NICOBAR ISLANDS",
    "36": "TELANGANA", "37": "ANDHRA PRADESH NEW"
}

# Regex patterns
REGEX_PATTERNS = {
    "Invoice_Number": r"(?:Invoice\s*No\.?\s*[:\-]?\s*)(\S+)",
    "Invoice_Date": r"(?:Invoice\s*Date|Date)\s*[:\-]?\s*(\d{2}[\/\-]\d{2}[\/\-]\d{4})",
    "Total_Amount": r"Total\s*Amount\s*[:\-]?\s*([0-9,]+\.\d{2})",
    "IRN": r"IRN\s*[:\-]?\s*(\S+)",
    "HSN_SAC": r"(?:HSN\s*\/\s*SAC)\s*[:\-]?\s*(\S+)",
    "IGST": r"IGST\s*[:\-]?\s*([0-9,]+\.\d{2})",
    "CGST": r"CGST\s*[:\-]?\s*([0-9,]+\.\d{2})",
    "SGST": r"SGST\s*[:\-]?\s*([0-9,]+\.\d{2})",
    "Taxable_Value": r"Taxable\s*Value\s*[:\-]?\s*([0-9,]+\.\d{2})",
    "Total_Tax_Amount": r"Total\s*Tax\s*Amount\s*[:\-]?\s*([0-9,]+\.\d{2})",
    "Buyer_Order_No": r"Order\s*No\.?\s*[:\-]?\s*(\S+)",
    "Destination": r"Destination\s*[:\-]?\s*(\S+)"
}

GST_REGEX = r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1})\b"

def ocr_pdf(pdf_path):
    """Convert PDF pages to images and extract OCR text."""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # Convert to grayscale and enhance
        img = ImageOps.grayscale(img)
        img = img.filter(ImageFilter.MedianFilter())
        text = pytesseract.image_to_string(img)
        full_text += text + "\n"
    # Normalize whitespace
    full_text = re.sub(r'\s+', ' ', full_text)
    return full_text

def extract_fields(text):
    """Extract invoice fields from OCR text using regex."""
    data = {}
    for key, pattern in REGEX_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        data[key] = match.group(1) if match else ""

    # Extract GST numbers
    gst_matches = re.findall(GST_REGEX, text)
    data["Seller_GSTIN_UIN"] = gst_matches[0] if len(gst_matches) >= 1 else ""
    data["Buyer_GSTIN_UIN"] = gst_matches[1] if len(gst_matches) >= 2 else ""

    # Map state code from GST
    seller_code = data["Seller_GSTIN_UIN"][:2] if data["Seller_GSTIN_UIN"] else ""
    buyer_code = data["Buyer_GSTIN_UIN"][:2] if data["Buyer_GSTIN_UIN"] else ""
    data["Seller_State_Name_Code"] = STATE_CODE_MAPPING.get(seller_code, "")
    data["Buyer_State_Name_Code"] = STATE_CODE_MAPPING.get(buyer_code, "")

    # Placeholder names (can improve by OCR context detection)
    data["Seller_Name"] = ""
    data["Buyer_Name"] = ""

    # Add source file and timestamps
    data["Upload_Date"] = datetime.now().strftime("%Y-%m-%d")
    data["Upload_Time"] = datetime.now().strftime("%H:%M:%S")
    return data

def extract_fields_from_pdfbytes(pdf_bytes):
    """Extract fields from uploaded PDF in memory."""
    doc = fitz.open(stream=pdf_bytes.read(), filetype="pdf")
    full_text = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = ImageOps.grayscale(img)
        img = img.filter(ImageFilter.MedianFilter())
        text = pytesseract.image_to_string(img)
        full_text += text + "\n"
    full_text = re.sub(r'\s+', ' ', full_text)
    return extract_fields(full_text)

def process_pdfs(pdf_folder=PDF_FOLDER):
    """Process all PDFs in folder (legacy)."""
    result = []
    for file_name in os.listdir(pdf_folder):
        if file_name.lower().endswith(".pdf"):
            pdf_path = os.path.join(pdf_folder, file_name)
            print(f"Processing: {file_name}")
            text = ocr_pdf(pdf_path)
            fields = extract_fields(text)
            fields["Source_File"] = file_name
            result.append({"file": file_name, "data": fields, "status": "success"})
    return result

if __name__ == "__main__":
    output = process_pdfs()
    print(json.dumps(output, indent=4))
