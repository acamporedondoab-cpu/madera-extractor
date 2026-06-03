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
import tempfile
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from extraction_pipeline import QuoteExtractionPipeline
import supabase_client as supa


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

        stored_pdfs = []  # [{name, url}] populated in cloud mode
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
                if supa.is_configured():
                    try:
                        url = supa.upload_pdf(project_name, name, pdf_bytes)
                        stored_pdfs.append({"name": name, "url": url})
                    except Exception as e:
                        # Log full error so Railway logs reveal the exact HTTP status/body.
                        # pdf_attachments will be absent from the saved record if all uploads fail.
                        print(f"⚠ PDF upload failed for {name}: {e}")
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

        # Attach PDF storage URLs so dashboard can show them
        if stored_pdfs:
            result["pdf_attachments"] = stored_pdfs

        # Persist to Supabase (non-fatal if it fails)
        if supa.is_configured():
            try:
                supa.save(project_name, result)
            except Exception as e:
                print(f"⚠ Supabase save failed (extraction still returned): {e}")

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
    """List all extractions (Supabase when configured, local disk fallback)."""
    if supa.is_configured():
        rows = supa.list_all()
        result = []
        for row in rows:
            data = row.get("data") or {}
            ext = data.get("extraction") or {}
            project = ext.get("project") or {}
            scores = ext.get("confidence_scores") or {}
            result.append({
                "id": row["id"],
                "location": project.get("location", "Unknown"),
                "client": project.get("client_name", "Unknown"),
                "building_type": project.get("building_type", "Unknown"),
                "deadline": project.get("deadline"),
                "completeness": scores.get("completeness_percent", 0),
                "approved": row.get("approved", False),
                "status": row.get("status", "pending"),
                "modified": row.get("updated_at") or row.get("created_at"),
            })
        return jsonify(result)

    # Local disk fallback
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


@app.route("/api/extractions/import", methods=["POST"])
def import_extraction():
    """
    Directly insert a pre-built extraction record into Supabase.
    Useful for importing records from n8n or other sources.

    Payload: { "id": "project_xxx", "data": { ...full extraction JSON... } }
    """
    body = request.get_json(force=True, silent=True) or {}
    extraction_id = body.get("id")
    data = body.get("data")

    if not extraction_id or not data:
        return jsonify({"error": "id and data are required"}), 400

    if supa.is_configured():
        supa.save(extraction_id, data)
        return jsonify({"status": "imported", "id": extraction_id})
    else:
        filepath = EXTRACTION_DIR / f"{extraction_id}.json"
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return jsonify({"status": "imported_local", "id": extraction_id})


@app.route("/api/extractions/<extraction_id>")
def get_extraction(extraction_id):
    """Return full extraction JSON for one project."""
    if supa.is_configured():
        row = supa.get_one(extraction_id)
        if not row:
            return jsonify({"error": "Not found"}), 404
        result = row.get("data") or {}
        result["approved"] = row.get("approved", False)
        result["status"] = row.get("status", "pending")
        return jsonify(result)

    filepath = EXTRACTION_DIR / f"{extraction_id}.json"
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    return jsonify(json.loads(filepath.read_text(encoding="utf-8")))


_UNRESOLVED_STATUSES = {"flagged for decision", "flagged", "pending", "unresolved"}


def _unresolved_decisions(extraction_data: dict) -> list:
    """Return list of unresolved structural note constraint strings."""
    ext = extraction_data.get("extraction") or extraction_data
    notes = ext.get("structural_notes") or []
    return [
        note.get("constraint") or note.get("description") or "Unknown constraint"
        for note in notes
        if (note.get("status") or "").lower().strip() in _UNRESOLVED_STATUSES
    ]


@app.route("/api/extractions/<extraction_id>/approve", methods=["POST"])
def approve_extraction(extraction_id):
    """Mark extraction as approved. Blocked if unresolved engineering decisions exist."""
    if supa.is_configured():
        row = supa.get_one(extraction_id)
        if not row:
            return jsonify({"error": "Not found"}), 404
        data = row.get("data") or {}
        unresolved = _unresolved_decisions(data)
        if unresolved:
            return jsonify({
                "error": "Cannot approve: unresolved engineering decisions exist",
                "unresolved_items": unresolved,
                "action": "Resolve all flagged structural decisions in the Decisión tab first"
            }), 409
        supa.update(extraction_id, {"approved": True, "status": "approved"})
        return jsonify({"status": "approved", "id": extraction_id})

    filepath = EXTRACTION_DIR / f"{extraction_id}.json"
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    data = json.loads(filepath.read_text(encoding="utf-8"))
    unresolved = _unresolved_decisions(data)
    if unresolved:
        return jsonify({
            "error": "Cannot approve: unresolved engineering decisions exist",
            "unresolved_items": unresolved,
            "action": "Resolve all flagged structural decisions in the Decisión tab first"
        }), 409
    data["approved"] = True
    data["approved_at"] = datetime.now().isoformat()
    data["status"] = "approved"
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"status": "approved", "id": extraction_id})


@app.route("/api/extractions/<extraction_id>/clarify", methods=["POST"])
def clarify_extraction(extraction_id):
    """Flag extraction as needing clarification."""
    body = request.get_json(force=True, silent=True) or {}
    note = body.get("note", "")

    if supa.is_configured():
        row = supa.get_one(extraction_id)
        if not row:
            return jsonify({"error": "Not found"}), 404
        updated_data = (row.get("data") or {}).copy()
        updated_data["clarification_note"] = note
        updated_data["clarification_at"] = datetime.now().isoformat()
        supa.update(extraction_id, {"status": "clarification_needed", "data": updated_data})
        return jsonify({"status": "clarification_needed", "id": extraction_id})

    filepath = EXTRACTION_DIR / f"{extraction_id}.json"
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    data = json.loads(filepath.read_text(encoding="utf-8"))
    data["status"] = "clarification_needed"
    data["clarification_note"] = note
    data["clarification_at"] = datetime.now().isoformat()
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"status": "clarification_needed", "id": extraction_id})


@app.route("/api/extractions/<extraction_id>/excel")
def download_excel(extraction_id):
    """Generate and return Excel workbook for an extraction."""
    if supa.is_configured():
        row = supa.get_one(extraction_id)
        if not row:
            return jsonify({"error": "Not found"}), 404
        data = row.get("data") or {}
    else:
        filepath = EXTRACTION_DIR / f"{extraction_id}.json"
        if not filepath.exists():
            return jsonify({"error": "Not found"}), 404
        data = json.loads(filepath.read_text(encoding="utf-8"))

    from excel_generator import generate_excel
    excel_bytes = generate_excel(data)
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"{extraction_id}_presupuesto.xlsx",
    )


@app.route("/api/extractions/<extraction_id>/word")
def download_word(extraction_id):
    """Generate and return the filled final_offer.docx for an extraction."""
    if supa.is_configured():
        row = supa.get_one(extraction_id)
        if not row:
            return jsonify({"error": "Not found"}), 404
        data = row.get("data") or {}
    else:
        filepath = EXTRACTION_DIR / f"{extraction_id}.json"
        if not filepath.exists():
            return jsonify({"error": "Not found"}), 404
        data = json.loads(filepath.read_text(encoding="utf-8"))

    from word_generator import generate_word
    word_bytes = generate_word(data)
    return send_file(
        io.BytesIO(word_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"{extraction_id}_oferta_final.docx",
    )


def _deep_set(obj: dict, path: str, value) -> None:
    """Set a value at a dot-separated path inside a nested dict, creating keys as needed."""
    keys = path.split(".")
    for key in keys[:-1]:
        if not isinstance(obj.get(key), dict):
            obj[key] = {}
        obj = obj[key]
    obj[keys[-1]] = value


@app.route("/api/extractions/<extraction_id>/fields", methods=["PATCH"])
def update_fields(extraction_id):
    """
    Apply Javier's manual edits for missing fields from the Decision tab.

    Payload:
      {
        "patches": [{"path": "technical_specifications.facade.material", "value": "larch"}],
        "resolved_fields": ["facade material"]   ← field names to drop from missing_critical_fields
      }
    """
    body = request.get_json(force=True, silent=True) or {}
    patches = body.get("patches", [])
    resolved = body.get("resolved_fields", [])

    if supa.is_configured():
        row = supa.get_one(extraction_id)
        if not row:
            return jsonify({"error": "Not found"}), 404
        stored = (row.get("data") or {}).copy()
    else:
        filepath = EXTRACTION_DIR / f"{extraction_id}.json"
        if not filepath.exists():
            return jsonify({"error": "Not found"}), 404
        stored = json.loads(filepath.read_text(encoding="utf-8"))

    ext = stored.get("extraction") or {}

    for patch in patches:
        path = patch.get("path", "")
        value = patch.get("value")
        if not path or value is None or value == "":
            continue
        if path == "_structural_note_solution":
            notes = ext.setdefault("structural_notes", [])
            if notes:
                notes[0]["proposed_solution"] = str(value)
                notes[0]["status"] = "resolved"
            else:
                notes.append({"constraint": "Vano", "proposed_solution": str(value), "status": "resolved"})
        elif path.startswith("_unknown."):
            ext.setdefault("extra_fields", {})[path[9:]] = value
        else:
            _deep_set(ext, path, value)

    # Remove resolved fields from missing_critical_fields
    mf = ext.get("missing_critical_fields") or []
    resolved_lower = {f.lower() for f in resolved}
    new_mf = [f for f in mf if f.lower() not in resolved_lower]
    ext["missing_critical_fields"] = new_mf

    # Boost completeness proportionally
    total_was_missing = len(new_mf) + len(resolved)
    if total_was_missing > 0 and resolved:
        scores = ext.setdefault("confidence_scores", {})
        old_pct = scores.get("completeness_percent") or 0
        boost = round(len(resolved) / total_was_missing * (100 - old_pct))
        scores["completeness_percent"] = min(100, old_pct + boost)

    stored["extraction"] = ext

    if supa.is_configured():
        supa.update(extraction_id, {"data": stored})
    else:
        filepath.write_text(json.dumps(stored, indent=2, ensure_ascii=False), encoding="utf-8")

    scores = ext.get("confidence_scores") or {}
    return jsonify({
        "status": "updated",
        "missing_remaining": len(new_mf),
        "completeness": scores.get("completeness_percent", 0),
    })


@app.route("/api/extractions/<extraction_id>/notes/resolve", methods=["POST"])
def resolve_structural_note(extraction_id):
    """
    Resolve a single structural note by index or constraint string.

    Payload:
      {
        "note_index": 0,                          ← preferred — zero-based array index
        "constraint": "6.4m living room span",    ← fallback fuzzy match if index absent
        "proposed_solution": "GL24h 240x480 beam"
      }

    Sets status=resolved, proposed_solution, resolved_at on the matched note only.
    Other notes are not touched.
    """
    body = request.get_json(force=True, silent=True) or {}
    note_index   = body.get("note_index")
    constraint   = body.get("constraint", "")
    proposed_sol = (body.get("proposed_solution") or "").strip()

    if not proposed_sol:
        return jsonify({"error": "proposed_solution is required"}), 400

    if supa.is_configured():
        row = supa.get_one(extraction_id)
        if not row:
            return jsonify({"error": "Not found"}), 404
        stored = (row.get("data") or {}).copy()
    else:
        filepath = EXTRACTION_DIR / f"{extraction_id}.json"
        if not filepath.exists():
            return jsonify({"error": "Not found"}), 404
        stored = json.loads(filepath.read_text(encoding="utf-8"))

    ext   = stored.get("extraction") or {}
    notes = ext.get("structural_notes") or []

    if not notes:
        return jsonify({"error": "No structural notes found on this extraction"}), 404

    # 1) Find by index (preferred)
    target_idx = None
    if note_index is not None:
        idx = int(note_index)
        if 0 <= idx < len(notes):
            target_idx = idx

    # 2) Fallback: fuzzy match on constraint string
    if target_idx is None and constraint:
        cl = constraint.lower().strip()
        for i, note in enumerate(notes):
            nc = (note.get("constraint") or "").lower().strip()
            if nc == cl or cl in nc or nc in cl:
                target_idx = i
                break

    if target_idx is None:
        return jsonify({
            "error": f"Structural note not found",
            "detail": f"index={note_index}, constraint='{constraint}', available={len(notes)}"
        }), 404

    # Mutate only the matched note
    notes[target_idx]["proposed_solution"] = proposed_sol
    notes[target_idx]["status"]            = "resolved"
    notes[target_idx]["resolved_at"]       = datetime.now().isoformat()

    ext["structural_notes"] = notes
    stored["extraction"]    = ext

    if supa.is_configured():
        supa.update(extraction_id, {"data": stored})
    else:
        filepath.write_text(json.dumps(stored, indent=2, ensure_ascii=False), encoding="utf-8")

    unresolved_remaining = len(_unresolved_decisions(stored))
    return jsonify({
        "status":               "resolved",
        "note_index":           target_idx,
        "constraint":           notes[target_idx].get("constraint"),
        "unresolved_remaining": unresolved_remaining,
    })


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
