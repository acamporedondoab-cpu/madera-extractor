#!/usr/bin/env python3
"""
Flask API Server for Javier's Extraction Pipeline
Receives requests from n8n, runs extraction, returns JSON

Usage:
  python3 extraction_api.py
  
Then n8n workflow calls: http://localhost:5000/extract
"""

import base64
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from extraction_pipeline import QuoteExtractionPipeline


app = Flask(__name__)

# Configuration
UPLOAD_DIR = Path("./uploads")
EXTRACTION_DIR = Path("./extractions")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Create directories
UPLOAD_DIR.mkdir(exist_ok=True)
EXTRACTION_DIR.mkdir(exist_ok=True)

# Check for API key
if not MISTRAL_API_KEY:
    print("\n⚠️  WARNING: MISTRAL_API_KEY not set")
    print("Set it with: export MISTRAL_API_KEY='your-key'")
    print("Get free key: https://console.mistral.ai\n")


@app.route("/extract", methods=["POST"])
def extract():
    """
    Extract structured data from email + PDFs.

    Two modes:
      Cloud mode (n8n Cloud → Railway): send pdf_attachments as base64
      Local mode (testing): send pdf_files as local file paths

    Cloud payload:
    {
      "email_text": "Email body text",
      "pdf_attachments": [
        {"name": "floor_plan.pdf", "content": "<base64>"}
      ],
      "project_name": "laura_sitges_villa"
    }

    Local payload:
    {
      "email_text": "Email body text",
      "pdf_files": ["C:/path/to/floor_plan.pdf"],
      "project_name": "laura_sitges_villa"
    }
    """
    temp_dir = None
    try:
        # Try JSON body first, fall back to form data
        data = request.get_json(force=True, silent=True)
        if not data:
            data = request.form.to_dict() or {}

        if not data.get("email_text"):
            return jsonify({"error": "email_text required"}), 400

        # Auto-generate project_name if not provided
        project_name = data.get("project_name") or f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        email_text = data["email_text"]

        if data.get("pdf_attachments"):  # non-empty list
            # Cloud mode: decode base64 PDFs into a temp directory
            temp_dir = tempfile.mkdtemp()
            pdf_file_paths = []
            for attachment in data["pdf_attachments"]:
                name = attachment.get("name", "attachment.pdf")
                content_b64 = attachment.get("content", "")
                pdf_bytes = base64.b64decode(content_b64)
                temp_path = os.path.join(temp_dir, name)
                with open(temp_path, "wb") as f:
                    f.write(pdf_bytes)
                pdf_file_paths.append(temp_path)
        else:
            # Local mode: use file paths directly (may be empty list)
            pdf_file_paths = data.get("pdf_files") or []
            missing_files = [f for f in pdf_file_paths if not Path(f).exists()]
            if missing_files:
                return jsonify({
                    "error": f"PDF files not found: {missing_files}",
                    "note": "Use pdf_attachments (base64) when calling from n8n Cloud"
                }), 400

        pipeline = QuoteExtractionPipeline(
            mistral_api_key=MISTRAL_API_KEY,
            output_dir=str(EXTRACTION_DIR)
        )

        result = pipeline.extract(
            email_text=email_text,
            pdf_files=pdf_file_paths,
            project_name=project_name
        )

        return jsonify({
            "status": "success",
            "extraction": result,
            "message": f"Extraction complete for {project_name}"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.route("/dashboard")
def dashboard():
    """Serve the validation dashboard."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    return send_file(path)


@app.route("/api/extractions")
def list_extractions():
    """List all extraction JSON files with summary fields."""
    files = sorted(EXTRACTION_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ext = data.get("extraction") or {}
            project = ext.get("project") or {}
            scores = ext.get("confidence_scores") or {}
            result.append({
                "id": f.stem,
                "location": project.get("location", "Unknown"),
                "client": project.get("client_name", "Unknown"),
                "building_type": project.get("building_type", "Unknown"),
                "deadline": project.get("deadline"),
                "completeness": scores.get("completeness_percent", 0),
                "approved": data.get("approved", False),
                "status": data.get("status", "pending"),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
        except Exception:
            pass
    return jsonify(result)


@app.route("/api/extractions/<extraction_id>")
def get_extraction(extraction_id):
    """Return full extraction JSON for one project."""
    filepath = EXTRACTION_DIR / f"{extraction_id}.json"
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    return jsonify(json.loads(filepath.read_text(encoding="utf-8")))


@app.route("/api/extractions/<extraction_id>/approve", methods=["POST"])
def approve_extraction(extraction_id):
    """Mark extraction as approved."""
    filepath = EXTRACTION_DIR / f"{extraction_id}.json"
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    data = json.loads(filepath.read_text(encoding="utf-8"))
    data["approved"] = True
    data["approved_at"] = datetime.now().isoformat()
    data["status"] = "approved"
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"status": "approved", "id": extraction_id})


@app.route("/api/extractions/<extraction_id>/clarify", methods=["POST"])
def clarify_extraction(extraction_id):
    """Flag extraction as needing clarification."""
    filepath = EXTRACTION_DIR / f"{extraction_id}.json"
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    body = request.get_json(force=True, silent=True) or {}
    data = json.loads(filepath.read_text(encoding="utf-8"))
    data["status"] = "clarification_needed"
    data["clarification_note"] = body.get("note", "")
    data["clarification_at"] = datetime.now().isoformat()
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"status": "clarification_needed", "id": extraction_id})


@app.route("/api/extractions/<extraction_id>/excel")
def download_excel(extraction_id):
    """Generate and return Excel workbook for an extraction."""
    filepath = EXTRACTION_DIR / f"{extraction_id}.json"
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    from excel_generator import generate_excel
    data = json.loads(filepath.read_text(encoding="utf-8"))
    excel_bytes = generate_excel(data)
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"{extraction_id}_presupuesto.xlsx",
    )


@app.route("/debug", methods=["POST", "GET"])
def debug():
    """Echo back exactly what n8n sends — for troubleshooting only"""
    return jsonify({
        "json_body": request.get_json(force=True, silent=True),
        "form_data": request.form.to_dict(),
        "headers": dict(request.headers),
        "content_type": request.content_type,
        "raw_body_preview": request.data.decode("utf-8", errors="replace")[:500]
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    
    mistral_configured = "✓" if MISTRAL_API_KEY else "✗"
    
    return jsonify({
        "status": "healthy",
        "service": "Javier Quoting System Extraction API",
        "mistral_api_configured": mistral_configured,
        "upload_dir": str(UPLOAD_DIR),
        "extraction_dir": str(EXTRACTION_DIR)
    })


@app.route("/", methods=["GET"])
def info():
    """API information"""
    
    return {
        "service": "Javier Quoting System - Extraction API",
        "version": "1.0",
        "endpoints": {
            "POST /extract": "Extract structured data from email + PDFs",
            "GET /health": "Health check"
        },
        "payload": {
            "email_text": "string (email body)",
            "pdf_files": ["list of PDF filenames"],
            "project_name": "string (project identifier)"
        },
        "setup": {
            "1": "Get Mistral API key: https://console.mistral.ai",
            "2": "Set env var: export MISTRAL_API_KEY='your-key'",
            "3": "Install deps: pip install -r requirements.txt",
            "4": "Run server: python3 extraction_api.py"
        }
    }


if __name__ == "__main__":
    print("\n" + "="*60)
    print("EXTRACTION API SERVER")
    print("="*60)
    
    if not MISTRAL_API_KEY:
        print("\n⚠️  MISTRAL_API_KEY not configured")
        print("Set it with: export MISTRAL_API_KEY='your-key'")
        print("Get free key: https://console.mistral.ai\n")
    else:
        print(f"✓ Mistral API configured")
    
    print(f"✓ Upload dir: {UPLOAD_DIR}")
    print(f"✓ Extraction dir: {EXTRACTION_DIR}")
    print(f"\nServer starting on http://localhost:5000")
    print(f"Health check: http://localhost:5000/health")
    print("="*60 + "\n")
    
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
