# chat.py
"""
Invoice OCR + GST extractor for scanned PDFs (Azure-ready)

Mode:
1. Convert PDF pages to images
2. Run OCR using pytesseract
3. Extract GST, Invoice Number, Seller State & Code
"""

import os
import re
import json
from PIL import Image
import fitz  # PyMuPDF
import pytesseract

# Azure App Service paths
PDF_FOLDER = "./pdfs"
os.makedirs(PDF_FOLDER, exist_ok=True)

# GST/State mapping
STATE_CODE_MAPPING = {
    "01": "JAMMU & KASHMIR",
    "02": "HIMACHAL PRADESH",
    "03": "PUNJAB",
    "04": "CHANDIGARH",
    "05": "UTTARAKHAND",
    "06": "HARYANA",
    "07": "DELHI",
    "08": "RAJASTHAN",
    "09": "UTTAR PRADESH",
    "10": "BIHAR",
    "11": "SIKKIM",
    "12": "ARUNACHAL PRADESH",
    "13": "NAGALAND",
    "14": "MANIPUR",
    "15": "MIZORAM",
    "16": "TRIPURA",
    "17": "MEGHALAYA",
    "18": "ASSAM",
    "19": "WEST BENGAL",
    "20": "JHARKHAND",
    "21": "ODISHA",
    "22": "CHATTISGARH",
    "23": "MADHYA PRADESH",
    "24": "GUJARAT",
    "25": "DAMAN AND DIU",
    "26": "DADRA AND NAGAR HAVELI",
    "27": "MAHARASHTRA",
    "28": "ANDHRA PRADESH",
    "29": "KARNATAKA",
    "30": "GOA",
    "31": "LAKSHADWEEP",
    "32": "KERALA",
    "33": "TAMIL NADU",
    "34": "PUDUCHERRY",
    "35": "ANDAMAN AND NICOBAR ISLANDS",
    "36": "TELANGANA",
    "37": "ANDHRA PRADESH NEW"
}

# Regex patterns
INVOICE_REGEX = r"(Invoice\s*No\.?\s*[:\-]?\s*)(\S+)"
GST_REGEX = r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1})\b"

def ocr_pdf(pdf_path):
    """Convert PDF pages to images and extract text using pytesseract"""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img)
        full_text += text + "\n"
    return full_text

def extract_fields(text):
    """Extract invoice fields from OCR text"""
    invoice_match = re.search(INVOICE_REGEX, text, re.IGNORECASE)
    invoice_number = invoice_match.group(2) if invoice_match else ""

    gst_matches = re.findall(GST_REGEX, text)
    buyer_gst = gst_matches[0] if len(gst_matches) >= 1 else ""
    seller_gst = gst_matches[1] if len(gst_matches) >= 2 else ""

    seller_state_code = seller_gst[:2] if seller_gst else ""
    seller_state = STATE_CODE_MAPPING.get(seller_state_code, "")

    return {
        "Invoice_Number": invoice_number,
        "Buyer_GST": buyer_gst,
        "Seller_GST": seller_gst,
        "Seller_State": seller_state,
        "Seller_State_Code": seller_state_code
    }

def process_pdfs(pdf_folder=PDF_FOLDER):
    """Process all PDFs in folder and print JSON output"""
    result = []
    for file_name in os.listdir(pdf_folder):
        if file_name.lower().endswith(".pdf"):
            pdf_path = os.path.join(pdf_folder, file_name)
            print(f"Processing: {file_name}")
            text = ocr_pdf(pdf_path)
            fields = extract_fields(text)
            result.append({"file": file_name, "data": fields, "status": "success"})
    return result

if __name__ == "__main__":
    import json
    output = process_pdfs()
    print(json.dumps(output, indent=4))
