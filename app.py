from flask import Flask, request, jsonify
import base64
import json
import time
from pathlib import Path
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# ==== IMAGE & PRICE TOOLS (Drive bridge) ========================

# Local path to your Google Drive (desktop sync)
GOOGLE_DRIVE_BASE = r"G:\My Drive\ai_ad_generator"

REQUESTS_DIR = Path(GOOGLE_DRIVE_BASE) / "requests"
RESULTS_DIR = Path(GOOGLE_DRIVE_BASE) / "results"

REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

print("REQUESTS_DIR:", REQUESTS_DIR)
print("RESULTS_DIR :", RESULTS_DIR)

# ================================================================
# Routes to HTML pages
# ================================================================

@app.route("/")
def home():
    return open(os.path.join(BASE_DIR, "templates", "home.html"), "r", encoding="utf-8").read()

@app.route("/tool1")
def tool1():
    return open(os.path.join(BASE_DIR, "templates", "tool1.html"), "r", encoding="utf-8").read()

@app.route("/tool2")
def tool2():
    return open(os.path.join(BASE_DIR, "templates", "tool2.html"), "r", encoding="utf-8").read()

@app.route("/tool3")
def tool3():
    return open(os.path.join(BASE_DIR, "templates", "tool3.html"), "r", encoding="utf-8").read()

@app.route("/tool4")
def tool4():
    return open(os.path.join(BASE_DIR, "templates", "tool4.html"), "r", encoding="utf-8").read()

# ================================================================
# Tool 1: text-to-image (Colab SD)
# ================================================================

@app.route("/api/text-to-image", methods=["POST"])
def text_to_image():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "").strip()
    size = data.get("size", "512x512")

    if not prompt:
        return jsonify({"success": False, "error": "Prompt required"}), 400

    try:
        width, height = map(int, size.split("x"))
    except Exception:
        width, height = 512, 512

    job_id = str(int(time.time() * 1000))

    job = {
        "job_id": job_id,
        "mode": "txt2img",
        "prompt": prompt,
        "width": width,
        "height": height,
    }
    job_path = REQUESTS_DIR / f"{job_id}.json"
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f)

    result_path = RESULTS_DIR / f"{job_id}.png"
    timeout_seconds = 120
    poll_interval = 2
    waited = 0

    while waited < timeout_seconds:
        if result_path.exists():
            img_bytes = result_path.read_bytes()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            return jsonify({"success": True, "image": img_b64})
        time.sleep(poll_interval)
        waited += poll_interval

    return jsonify({
        "success": False,
        "error": "Timed out waiting for Colab worker. Is the notebook running?",
    }), 504

# ================================================================
# Tool 2: image-to-image (Colab SD)
# ================================================================

@app.route("/api/image-to-image", methods=["POST"])
def image_to_image():
    data = request.get_json(force=True)

    input_image_b64 = data.get("input_image", "")
    description = data.get("description", "professional product photography").strip()
    strength = float(data.get("strength", 0.4))
    size = data.get("size", "512x512")

    if not input_image_b64:
        return jsonify({"success": False, "error": "Image required"}), 400

    try:
        width, height = map(int, size.split("x"))
    except Exception:
        width, height = 512, 512

    header, b64data = input_image_b64.split(",", 1)
    img_bytes = base64.b64decode(b64data)

    job_id = str(int(time.time() * 1000))
    input_path = REQUESTS_DIR / f"{job_id}_input.png"
    input_path.write_bytes(img_bytes)

    job = {
        "job_id": job_id,
        "mode": "img2img",
        "prompt": description,
        "strength": strength,
        "width": width,
        "height": height,
    }
    job_path = REQUESTS_DIR / f"{job_id}.json"
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f)

    result_path = RESULTS_DIR / f"{job_id}.png"
    timeout_seconds = 180
    poll_interval = 2
    waited = 0

    while waited < timeout_seconds:
        if result_path.exists():
            img_bytes_out = result_path.read_bytes()
            img_b64_out = base64.b64encode(img_bytes_out).decode("utf-8")
            return jsonify({"success": True, "image": img_b64_out})
        time.sleep(poll_interval)
        waited += poll_interval

    return jsonify({
        "success": False,
        "error": "Timed out waiting for Colab worker. Is the notebook running?",
    }), 504

# ================================================================
# Tool 3: image-to-text (Colab BLIP)
# ================================================================

@app.route("/api/image-to-text", methods=["POST"])
def image_to_text():
    data = request.get_json(force=True)
    input_image_b64 = data.get("input_image", "")

    if not input_image_b64:
        return jsonify({"success": False, "error": "Image required"}), 400

    try:
        header, b64data = input_image_b64.split(",", 1)
        img_bytes = base64.b64decode(b64data)

        job_id = str(int(time.time() * 1000))
        input_path = REQUESTS_DIR / f"{job_id}_input.png"
        input_path.write_bytes(img_bytes)

        job = {
            "job_id": job_id,
            "mode": "img2text",
        }
        job_path = REQUESTS_DIR / f"{job_id}.json"
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(job, f)

        result_path = RESULTS_DIR / f"{job_id}.json"
        timeout_seconds = 60
        poll_interval = 2
        waited = 0

        while waited < timeout_seconds:
            if result_path.exists():
                with open(result_path, "r", encoding="utf-8") as f:
                    result = json.load(f)
                description = result.get("description", "")
                return jsonify({"success": True, "description": description})
            time.sleep(poll_interval)
            waited += poll_interval

        return jsonify({
            "success": False,
            "error": "Timed out waiting for Colab worker.",
        }), 504

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ================================================================
# Tool 4: price recommendation (Colab – price model)
# ================================================================

@app.route("/api/recommend-price", methods=["POST"])
def api_recommend_price():
    try:
        data = request.get_json(force=True)
        product_name = data.get("product_name", "").strip()
        brand = data.get("brand", "").strip()
        category = data.get("category", "").strip()
        material = data.get("material", "").strip()
        color = data.get("color", "").strip()
        rating = float(data.get("rating", 4.5))
        num_reviews = int(data.get("num_reviews", 0))

        if not product_name or not brand or not category:
            return jsonify({"success": False, "error": "product_name, brand and category are required"}), 400

        job_id = str(int(time.time() * 1000))

        job = {
            "job_id": job_id,
            "mode": "price",
            "product_name": product_name,
            "brand": brand,
            "category": category,
            "material": material,
            "color": color,
            "rating": rating,
            "num_reviews": num_reviews,
        }

        job_path = REQUESTS_DIR / f"{job_id}.json"
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(job, f)

        result_path = RESULTS_DIR / f"{job_id}.json"
        timeout_seconds = 60
        poll_interval = 2
        waited = 0

        while waited < timeout_seconds:
            if result_path.exists():
                with open(result_path, "r", encoding="utf-8") as f:
                    result = json.load(f)
                # Colab writes: {success: bool, price, range, error?}
                return jsonify(result)
            time.sleep(poll_interval)
            waited += poll_interval

        return jsonify({"success": False, "error": "Timed out waiting for Colab worker."}), 504

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("FLASK APP STARTING (Drive-bridge, all tools in Colab)")
    print("="*60)
    print("Open: http://localhost:5000")
    print("")
    print("Tool 1: Text → Image (Colab + SD)")
    print("Tool 2: Image → Image (Colab + SD)")
    print("Tool 3: Image → Text (Colab + Custom BLIP)")
    print("Tool 4: Best Price (Colab price model)")
    print("")
    print("⚠️  Make sure the unified Colab notebook is running for ALL tools.")
    print("="*60 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
