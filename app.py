from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import cv2
import pytesseract
from deepface import DeepFace
from PIL import Image
from pdf2image import convert_from_bytes
import re

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Path to Tesseract OCR executable (change if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Change for your system

def extract_dob_from_image(image_path):
    image = cv2.imread(image_path)
    
    # Use English + multiple Indian languages
    text = pytesseract.image_to_string(image, lang='eng+hin+ben+tam+tel+kan+guj+mar')
    
    # Normalize Hindi/Indic phrases (e.g. "जन्म तिथि") to match patterns
    dob_keywords = [
        r'जन्म[ \t]*तिथि[:\-]*[ \t]*(\d{2}[\/\-]\d{2}[\/\-]\d{4})',
        r'Date of Birth[:\-]*[ \t]*(\d{2}[\/\-]\d{2}[\/\-]\d{4})',
        r'DOB[:\-]*[ \t]*(\d{2}[\/\-]\d{2}[\/\-]\d{4})'
    ]
    
    # Try keyword-specific regex
    for pattern in dob_keywords:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            dob_str = match.group(1)
            try:
                return datetime.strptime(dob_str, "%d/%m/%Y").date()
            except:
                try:
                    return datetime.strptime(dob_str, "%d-%m-%Y").date()
                except:
                    continue
    
    # Fallback: match any date-like pattern
    general_patterns = [r'\d{2}[\/\-]\d{2}[\/\-]\d{4}']
    for pattern in general_patterns:
        matches = re.findall(pattern, text)
        for dob in matches:
            try:
                return datetime.strptime(dob, "%d/%m/%Y").date()
            except:
                try:
                    return datetime.strptime(dob, "%d-%m-%Y").date()
                except:
                    continue

    return None

def calculate_age(dob):
    today = datetime.today().date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/verify", methods=["POST"])
def verify():
    id_card = request.files.get("id_card")
    selfie = request.files.get("selfie")

    if not id_card or not selfie:
        return jsonify({"error": "Missing file(s)"}), 400

    # Save files
    id_filename = secure_filename(id_card.filename)
    selfie_filename = "selfie.jpg"
    id_path = os.path.join(UPLOAD_FOLDER, id_filename)
    selfie_path = os.path.join(UPLOAD_FOLDER, selfie_filename)

    id_card.save(id_path)
    selfie.save(selfie_path)

    # Handle PDF -> Convert to image
    if id_filename.lower().endswith(".pdf"):
        pages = convert_from_bytes(open(id_path, 'rb').read())
        img_path = os.path.join(UPLOAD_FOLDER, "id_converted.jpg")
        pages[0].save(img_path, 'JPEG')
        id_path = img_path

    # OCR: extract DOB
    dob = extract_dob_from_image(id_path)
    if not dob:
        return jsonify({"error": "DOB not found in Aadhar"}), 400

    age = calculate_age(dob)

    # Face match
    try:
        result = DeepFace.verify(img1_path=id_path, img2_path=selfie_path, model_name="VGG-Face", enforce_detection=False)
        verified = result["verified"]
        match_score = (1 - result["distance"]) * 100  # convert distance to a percentage match
    except Exception as e:
        return jsonify({"error": f"Face verification failed: {str(e)}"}), 500

    return jsonify({
        "dob": dob.strftime("%d-%m-%Y"),
        "age": age,
        "matchVerified": verified,
        "ageVerified": age >= 18,
        "matchScore": round(match_score, 2)
    })

if __name__ == "__main__":
    app.run(debug=True)
