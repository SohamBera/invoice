from flask import Flask, render_template, request, jsonify
import io, threading, os
from chat import extract_fields_from_pdfbytes

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY", "supersecret")

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/extract", methods=["POST"])
def extract_api():
    if "file" not in request.files:
        return jsonify({"status":"error","message":"No file"}),400
    pdf_bytes = io.BytesIO(request.files["file"].read())
    try:
        fields = extract_fields_from_pdfbytes(pdf_bytes)
        return jsonify({"status":"success","data":fields})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}),500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8000)), debug=True)
