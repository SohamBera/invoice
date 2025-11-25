# chat.py
"""
Azure-ready Invoice OCR + GST extractor
- Auto-starts in App Service SSH or console
- Debug messages for every step
- Process all PDFs in /home/site/wwwroot/pdfs
- Save output as JSON
"""

import os
import re
import json
import time
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageOps, ImageFilter
import pytesseract

# -----------------------------
# CONFIG
# -----------------------------
PDF_FOLDER = "/home/site/wwwroot/pdfs"   # folder containing PDFs
OUTPUT_FOLDER = "/home/site/wwwroot/output"  # folder to save JSON results

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def ocr_image(img: Image.Image) -> str:
    """
    Apply OCR to a PIL image and return text
    """
    gray = ImageOps.grayscale(img)
    gray = gray.filter(ImageFilter.MedianFilter())
    text = pytesseract.image_to_string(gray)
    return text

def extract_invoice_data(text: str) -> dict:
    """
    Extract invoice-related data using regex
    """
    data = {
        "Invoice_Number": "",
        "Buyer_GST": "",
        "Seller_GST": "",
        "Seller_State": "",
        "Seller_State_Code": ""
    }

    # Example regex, adjust for your formats
    inv_match = re.search(r"(Invoice\s*No[:\s]*)(\S+)", text, re.IGNORECASE)
    if inv_match:
        data["Invoice_Number"] = inv_match.group(2).strip()

    gst_matches = re.findall(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b", text)
    if gst_matches:
        if len(gst_matches) >= 1:
            data["Seller_GST"] = gst_matches[0]
        if len(gst_matches) >= 2:
            data["Buyer_GST"] = gst_matches[1]

    # Seller state code: first 2 digits of GST
    if data["Seller_GST"]:
        data["Seller_State_Code"] = data["Seller_GST"][:2]

    # Seller state name (basic mapping, can expand)
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
        # Add remaining as needed
    }
    code = data["Seller_State_Code"]
    if code in state_codes:
        data["Seller_State"] = state_codes[code]

    return data

def process_pdf(pdf_path: str) -> dict:
    """
    Extract text from PDF and parse invoice data
    """
    print(f"[INFO] Processing PDF: {pdf_path}")
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            if not text.strip():
                # fallback: render page as image and OCR
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = ocr_image(img)
            full_text += "\n" + text
        data = extract_invoice_data(full_text)
        return data
    except Exception as e:
        print(f"[ERROR] Failed to process {pdf_path}: {e}")
        return {}

# -----------------------------
# MAIN
# -----------------------------

def main():
    print("[INFO] Auto-starting PDF processing...")

    pdf_folder_path = Path(PDF_FOLDER)
    pdf_files = sorted(pdf_folder_path.glob("*.pdf"))

    if not pdf_files:
        print(f"[WARN] No PDFs found in {PDF_FOLDER}")
        return

    results = []

    for pdf_file in pdf_files:
        data = process_pdf(str(pdf_file))
        data["FileName"] = pdf_file.name
        results.append(data)

    # Save results to JSON
    timestamp = int(time.time())
    output_file = os.path.join(OUTPUT_FOLDER, f"invoice_data_{timestamp}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"[INFO] Processing complete. Results saved to: {output_file}")
    print(json.dumps(results, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    main()
