# chat.py
"""
Invoice OCR + GST extractor (single-file)
- Works for scanned and text PDFs
- Flexible regex for GST and invoice numbers
- Maps state codes to state names
"""

import os
import re
import json
from PIL import Image
import fitz  # PyMuPDF
import pytesseract

# -------------------------------
# Config
# -------------------------------
PDF_FOLDER = "./pdfs"  # folder containing PDF files

state_codes = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman & Diu",
    "26": "Maharashtra",
    "27": "Andhra Pradesh (Old)",
    "28": "Karnataka",
    "29": "Goa",
    "30": "Lakshadweep",
    "31": "Kerala",
    "32": "Tamil Nadu",
    "33": "Puducherry",
    "34": "Telangana",
    "35": "Andaman & Nicobar",
    "36": "Delhi",
    "37": "Ladakh"
}

# -------------------------------
# OCR helper
# -------------------------------
def ocr_image(img: Image.Image) -> str:
    """Extract text from PIL Image using pytesseract"""
    text = pytesseract.image_to_string(img)
    return text

# -------------------------------
# PDF text extraction
# -------------------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from PDF using PyMuPDF and OCR fallback"""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        # Try text layer first
        text = page.get_text()
        if not text.strip():
            # fallback to OCR
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = ocr_image(img)
        full_text += "\n" + text
    return full_text

# -------------------------------
# Extraction regex
# -------------------------------
def extract_invoice_number(text: str) -> str:
    match = re.search(r"(Invoice\s*(No|Number)?[:\s]*)([A-Z0-9\-\/]+)", text, re.IGNORECASE)
    return match.group(3).strip() if match else ""

def extract_gst_numbers(text: str) -> list:
    # Loose regex to handle OCR errors
    gst_matches = re.findall(r"\b\d{2}[A-Z0-9]{5}\d{4}[A-Z0-9]{1}Z[A-Z0-9]{1}\b", text, re.IGNORECASE)
    return gst_matches

def extract_state_code_from_gst(gst: str) -> str:
    return gst[:2] if gst else ""

# -------------------------------
# Main processing
# -------------------------------
def process_pdf(pdf_path: str) -> dict:
    text = extract_text_from_pdf(pdf_path)

    invoice_number = extract_invoice_number(text)
    gst_numbers = extract_gst_numbers(text)

    seller_gst = gst_numbers[0] if gst_numbers else ""
    buyer_gst = gst_numbers[1] if len(gst_numbers) > 1 else ""

    seller_state_code = extract_state_code_from_gst(seller_gst)
    seller_state = state_codes.get(seller_state_code, "")

    data = {
        "Invoice_Number": invoice_number,
        "Seller_GST": seller_gst,
        "Buyer_GST": buyer_gst,
        "Seller_State_Code": seller_state_code,
        "Seller_State": seller_state
    }

    return {"data": data, "status": "success"}

# -------------------------------
# Run all PDFs
# -------------------------------
if __name__ == "__main__":
    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(json.dumps({"data": {}, "status": "no PDFs found"}))
    else:
        results = []
        for pdf_file in pdf_files:
            pdf_path = os.path.join(PDF_FOLDER, pdf_file)
            print(f"Processing: {pdf_file}")
            result = process_pdf(pdf_path)
            results.append(result)
        # Output all results as JSON
        print(json.dumps(results, indent=2))
