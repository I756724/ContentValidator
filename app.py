"""
UA Content Validator - Main Flask Application
Validates English content before German translation
"""
from flask import Flask, render_template, request, jsonify
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from services.orchestrator import Orchestrator

app = Flask(__name__)
orchestrator = Orchestrator()


@app.route("/")
def index():
    """Main page."""
    return render_template("index.html")


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
    """Service status endpoint."""
    return jsonify(orchestrator.get_status())


@app.route("/health")
def health():
    """Health check."""
    return jsonify({"status": "ok"})


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

    app.run(debug=True, host="0.0.0.0", port=5000)