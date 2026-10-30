"""
UA Content Validator - Main Flask Application
Validates English content before German translation
"""
from flask import Flask, render_template, request, jsonify
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from services.orchestrator import Orchestrator
from services.sapterm_draft_service import SAPTermDraftService

app = Flask(__name__)
orchestrator = Orchestrator()
draft_service = SAPTermDraftService()


@app.route("/")
def index():
    """Main page."""
    return render_template("index.html")


@app.route("/guide")
def guide():
    """User guide page."""
    return render_template("guide.html")


@app.route("/validate", methods=["POST"])
def validate():
    """
    Main validation endpoint.
    
    Request JSON:
        {
            "text": "Content to validate",
            "content_type": "ui_label" | "text",
            "element_type": "app_title" | "button" | "action" | "tab" | "section_heading" | "field_label" | "column_header" | "status_text" | "message_text" | "facet_title",
            "context": "Optional context description"
        }
    """
    data = request.json

    text = data.get("text", "").strip()
    content_type = data.get("content_type", "text")
    element_type = data.get("element_type", "field_label")
    context = data.get("context", "").strip()
    target_language = data.get("target_language", "de-DE").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Length guard: UI labels are short labels; text mode allows longer content
    max_len = 300 if content_type == "ui_label" else 3000
    if len(text) > max_len:
        return jsonify({"error": f"Text exceeds {max_len} character limit for {content_type} mode"}), 400

    try:
        if content_type == "ui_label":
            result = orchestrator.validate_ui_label(text, element_type, context, target_language)
        else:
            result = orchestrator.validate_text(text, context, target_language)

        return jsonify({"success": True, **result})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Validation failed: {str(e)}"}), 500


@app.route("/status")
def status():
    """Service status endpoint."""
    return jsonify(orchestrator.get_status())


@app.route("/health")
def health():
    """Health check."""
    return jsonify({"status": "ok"})


@app.route("/draft-sapterm", methods=["POST"])
def draft_sapterm():
    """Draft a SAPterm-ready entry for a term not found in SAPterm."""
    data = request.json
    term = data.get("term", "").strip()
    context = data.get("context", "").strip()
    element_type = data.get("element_type", "field_label")

    if not term:
        return jsonify({"error": "No term provided"}), 400
    if len(term) > 200:
        return jsonify({"error": "Term too long (max 200 chars)"}), 400

    try:
        result = draft_service.draft_entry(term, context, element_type)
        return jsonify({"success": True, **result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Draft failed: {str(e)}"}), 500


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("\n" + "=" * 50)
    print("  UA Content Validator")
    print("=" * 50)
    print(f"\n  Local:   http://localhost:5000")
    print(f"  Network: http://{local_ip}:5000")
    print(f"\n  Services:")
    status_info = orchestrator.get_status()
    print(f"    SAPterm: {status_info['sapterm']['message']}")
    print(f"    AI:      {status_info['ai']['status']}")
    print("\n" + "=" * 50 + "\n")

    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
            host="0.0.0.0", port=5000)