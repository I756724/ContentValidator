"""
UA Content Validator - BTP Cloud Foundry Version
Uses environment variables for API endpoints instead of localhost
"""
from flask import Flask, render_template, request, jsonify
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Override config for BTP
os.environ.setdefault("DEPLOYMENT", "btp")

from services.orchestrator import Orchestrator

app = Flask(__name__)
orchestrator = Orchestrator()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/guide")
def guide():
    return render_template("guide.html")


@app.route("/validate", methods=["POST"])
def validate():
    data = request.json
    text = data.get("text", "").strip()
    content_type = data.get("content_type", "text")
    element_type = data.get("element_type", "field_label")
    context = data.get("context", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        if content_type == "ui_label":
            result = orchestrator.validate_ui_label(text, element_type, context)
        else:
            result = orchestrator.validate_text(text, context)
        return jsonify({"success": True, **result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Validation failed: {str(e)}"}), 500


@app.route("/status")
def status():
    return jsonify(orchestrator.get_status())


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)