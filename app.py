from flask import Flask, request, jsonify
import os
import cv2
import re
import pytesseract
from deepface import DeepFace
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def extract_text(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    text = pytesseract.image_to_string(thresh, lang='eng')
    clean_text = ''.join([c if ord(c) < 128 else ' ' for c in text])
    return clean_text


def extract_dob(image_path):
    text = extract_text(image_path)
    print("Extracted text:", text)
    dob_match = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", text)
    if dob_match:
        dob_str = dob_match.group().replace("-", "/")
        dob = datetime.strptime(dob_str, "%d/%m/%Y")
        age = (datetime.today() - dob).days // 365
        return dob_str, age
    return None, None


def compare_faces(aadhar_img, selfie_img):
    try:
        result = DeepFace.verify(aadhar_img, selfie_img, enforce_detection=True)
        confidence = round((1 - result["distance"]) * 100, 2)
        return result["verified"], confidence
    except Exception as e:
        print("Face match error:", e)
        return False, 0


@app.route("/verify", methods=["POST"])
def verify_identity():
    if "id_card" not in request.files or "selfie" not in request.files:
        return jsonify({"error": "Both ID card and selfie are required."})

    id_card = request.files["id_card"]
    selfie = request.files["selfie"]

    id_path = os.path.join(UPLOAD_FOLDER, secure_filename("aadhar.jpg"))
    selfie_path = os.path.join(UPLOAD_FOLDER, secure_filename("selfie.jpg"))
    id_card.save(id_path)
    selfie.save(selfie_path)

    dob_str, age = extract_dob(id_path)

    if not dob_str:
        return jsonify({"error": "DOB not found in document."})

    match_verified, match_score = compare_faces(id_path, selfie_path)

    if match_score == 0:
        return jsonify({"error": "Face not detected in one or both images."})

    return jsonify({
        "dob": dob_str,
        "age": age,
        "matchVerified": match_verified,
        "matchScore": match_score,
        "ageVerified": age >= 18
    })


if __name__ == "__main__":
    app.run(debug=True)
