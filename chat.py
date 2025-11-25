import os
import re
import json
from PIL import Image
import fitz
import pytesseract

PDF_FOLDER = "./pdfs"

state_codes = {
    "17": "Meghalaya",
    "27": "Maharashtra",
    "19": "West Bengal",
    # ... add all states as needed
}

def ocr_image(img: Image.Image) -> str:
    return pytesseract.image_to_string(img)

def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        text = page.get_text()
        if not text.strip():
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = ocr_image(img)
        full_text += "\n" + text
    return full_text

def clean_gst(text: str) -> str:
    """Fix common OCR issues in GST"""
    if not text:
        return ""
    text = text.replace(" ", "").upper()
    text = text.replace("O", "0").replace("I", "1")
    return text

def extract_invoice_number(text: str) -> str:
    match = re.search(r"Invoice\s*(No|Number)?[:\s]*([A-Z0-9\-/]+)", text, re.IGNORECASE)
    return match.group(2).strip() if match else ""

def extract_gst_numbers(text: str) -> list:
    text = text.replace(" ", "").upper()
    gst_matches = re.findall(r"\d{2}[A-Z0-9]{5}\d{4}[A-Z0-9]{1}Z[A-Z0-9]{1}", text)
    gst_matches = [clean_gst(g) for g in gst_matches]
    return gst_matches

def extract_state_code_from_gst(gst: str) -> str:
    return gst[:2] if gst else ""

def process_pdf(pdf_path: str) -> dict:
    text = extract_text_from_pdf(pdf_path)
    invoice_number = extract_invoice_number(text) or ""
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

if __name__ == "__main__":
    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf")]
    results = []
    for pdf_file in pdf_files:
        result = process_pdf(os.path.join(PDF_FOLDER, pdf_file))
        results.append(result)
    print(json.dumps(results, indent=2))
