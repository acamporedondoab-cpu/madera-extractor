# Javier's Quoting System - Project Documentation

**Claude.md** - Complete project guide for Claude Code in VS Code

---

## 📋 Project Overview

**Goal:** Automate Javier's 3-5 day manual quote process to 15-30 minutes using AI extraction + n8n automation + custom dashboard.

**Status:** Phase 1 (Extraction) COMPLETE ✓ | Phase 2 (Automation) IN PROGRESS | Phase 3 (Dashboard) PENDING

---

## 🏗️ System Architecture

### Complete Data Flow

```
Email with PDFs (Gmail)
    ↓
n8n Workflow (Cloud)
    ↓
Flask API (http://localhost:5000 or deployed to Railway)
    ↓
PDF Extraction (pdfplumber - LOCAL)
    ↓
Mistral API (free tier - structured parsing)
    ↓
Structured JSON (40+ fields)
    ↓
Google Drive (storage)
    ↓
Dashboard (validation + decision)
    ↓
Excel + Word generation (auto-documents)
```

### Technology Stack

| Component | Technology | Cost | Status |
|-----------|-----------|------|--------|
| PDF Extraction | pdfplumber (Python) | FREE | ✓ DONE |
| LLM Parsing | Mistral API | FREE (tier) | ✓ DONE |
| API Server | Flask (Python) | FREE | ✓ DONE |
| Automation | n8n Cloud | FREE (tier) | ⏳ IN PROGRESS |
| Cloud Deployment | Railway/Render | FREE (tier) | ⏳ NEXT |
| Dashboard | React/HTML | TBD | ⏳ PHASE 3 |
| Google Drive | n8n integration | FREE | ⏳ PHASE 2 |

---

## 📁 Project Files (Current)

### Location
```
F:\Madera\
├── extraction_api.py          (Flask server)
├── extraction_pipeline.py      (orchestration)
├── mistral_extractor.py        (Mistral integration)
├── pdf_extractor.py            (PDF text extraction)
├── requirements.txt            (Python dependencies)
├── README.md                   (setup guide)
└── n8n_workflow_simple.json    (n8n workflow)
```

### File Descriptions

**extraction_api.py** (200 lines)
- Flask server listening on http://localhost:5000
- Endpoints:
  - POST /extract → receives email_text, pdf_files, project_name
  - GET /health → returns API status
- Dependencies: Flask, requests
- Currently: Running locally on your machine
- Next: Deploy to Railway.app

**extraction_pipeline.py** (250 lines)
- Orchestrates complete extraction flow
- Steps:
  1. Extract text from PDFs (pdfplumber)
  2. Call Mistral API to structure data
  3. Add metadata and citations
  4. Save to JSON file
- Used by: extraction_api.py (called when /extract endpoint is hit)

**mistral_extractor.py** (400 lines)
- Calls Mistral API (free tier)
- Input: PDF text + email text
- Output: Structured JSON with 40+ fields
- Prompt: Extracts project info, dimensions, specs, etc.
- Confidence scoring: high/medium/low

**pdf_extractor.py** (300 lines)
- Extracts text from multi-page PDFs
- Uses pdfplumber library (local, no API cost)
- Finds measurements automatically (regex: m², m, mm)
- Fast: processes pages in seconds
- Privacy: runs on your machine, no uploads

**requirements.txt**
```
pdfplumber==0.10.4         # PDF text extraction
requests==2.31.0           # HTTP calls to Mistral
Flask==3.0.0               # API server
python-dateutil==2.8.2     # Date handling
python-dotenv==1.0.0       # .env file support
```

**n8n_workflow_simple.json**
- Minimal n8n workflow (no credential issues)
- Nodes:
  1. Webhook (receives POST requests)
  2. HTTP Request (calls Flask API)
  3. Respond (returns result)
- Ready to import into n8n Cloud

---

## 🔄 Current Status (Updated: May 31, 2026)

### ✓ COMPLETE (Phase 1)

- [x] PDF extraction module (pdfplumber)
- [x] Mistral API integration (free tier)
- [x] Flask API server
- [x] Python extraction pipeline
- [x] Local testing (curl works)
- [x] Health check endpoint
- [x] n8n workflow template
- [x] Requirements file
- [x] Documentation

**Evidence:**
```bash
# API Server running:
Server starting on http://localhost:5000

# Health check working:
curl http://localhost:5000/health
# Response: 200 OK, status: healthy, mistral_api_configured: ✓
```

### ⏳ IN PROGRESS (Phase 2)

- [ ] Deploy Flask API to Railway.app
  - Current: Running on localhost:5000
  - Issue: n8n Cloud can't reach localhost
  - Solution: Deploy to Railway, get public URL
  
- [ ] Connect n8n workflow to deployed API
  - Currently: Webhook URL exists, but API unreachable from cloud
  - Action: Update HTTP Request node URL after deployment
  
- [ ] Test end-to-end with sample email + PDFs
  - Once deployed: Send test email → n8n triggers → extraction works

- [ ] Add Google Drive integration (optional)
  - Save extraction.json to Google Drive
  - n8n node: "Google Drive" → upload file

### ⏰ PENDING (Phase 3 & 4)

- [ ] Build validation dashboard (4 tabs)
- [ ] PDF attachment viewer
- [ ] Javier's decision logic (Approve/Edit/Clarify)
- [ ] Excel auto-population
- [ ] Word document generation

---

## 🔑 API Reference

### Mistral API Key

**Where it's stored:**
```bash
# Windows environment variable:
setx MISTRAL_API_KEY "sk-your-key-here"
```

**Verify it's set:**
```bash
echo %MISTRAL_API_KEY%
```

**Current status:** ✓ SET (verified with health check)

### Flask API Endpoints

**POST /extract**
```bash
curl -X POST http://localhost:5000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "email_text": "Hi Javier, 240 m2 wooden villa...",
    "pdf_files": ["floor_plan.pdf"],
    "project_name": "laura_sitges_villa"
  }'
```

**Response:**
```json
{
  "status": "success",
  "extraction": {
    "project": { ... },
    "building_dimensions": { ... },
    "building_geometry": { ... },
    "technical_specifications": { ... },
    "structural_notes": [ ... ],
    "commercial_terms": { ... },
    "scope": { ... },
    "confidence_scores": { ... },
    "missing_critical_fields": [ ... ]
  },
  "output_file": "./extractions/laura_sitges_villa_extraction.json"
}
```

**GET /health**
```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "Javier Quoting System Extraction API",
  "mistral_api_configured": "✓",
  "upload_dir": "./uploads",
  "extraction_dir": "./extractions"
}
```

---

## 🎯 What Gets Extracted (40+ Fields)

### extraction.json Structure

```json
{
  "project": {
    "location": "Sitges",
    "building_type": "wooden villa",
    "client_name": "Garcia Family",
    "architect": "Laura Martin",
    "architect_email": "laura@arquitectos.example.com",
    "deadline": "2026-05-29",
    "deadline_days_remaining": 11
  },
  
  "building_dimensions": {
    "ground_floor_area_m2": 115,
    "first_floor_area_m2": 110,
    "attic_area_m2": 15,
    "terrace_area_m2": 30,
    "total_area_m2": 240,
    "plot_area_m2": 600
  },
  
  "building_geometry": {
    "ground_floor": {
      "habitable_area_m2": 115,
      "terrace_area_m2": 0,
      "ext_perimeter_m": 48,
      "int_walls_length_m": 32
    },
    "first_floor": { ... },
    "attic": { ... },
    "roof": {
      "projected_area_m2": 150,
      "pitch_degrees": 45,
      "gutter_length_m": 38
    },
    "windows": {
      "count": 14,
      "total_area_m2": 43,
      "type": "triple glazing"
    }
  },
  
  "technical_specifications": {
    "wall_system": {
      "material": "X-lam 140mm",
      "thickness_mm": 140,
      "status": "suggested"
    },
    "insulation": {
      "walls": {
        "thickness_mm": 200,
        "material": "wood fiber",
        "status": "confirmed"
      },
      "roof": { ... }
    },
    "facade": {
      "material": "larch cladding",
      "status": "confirmed"
    },
    "roof_finish": {
      "type": "ceramic tiles",
      "color": "natural",
      "status": "preferred"
    }
  },
  
  "structural_notes": [
    {
      "constraint": "6.4m living room span",
      "description": "May need beam support",
      "status": "flagged for decision",
      "proposed_solution": "GL24h 240x480 or confirm X-lam sufficient"
    }
  ],
  
  "commercial_terms": {
    "margin_percent": 30,
    "vat_rate_percent": 21,
    "quote_validity_days": 30,
    "payment_terms": "30/40/30",
    "currency": "EUR"
  },
  
  "scope": {
    "in_scope": [
      "Structure",
      "Envelope (walls, roof, windows)",
      "Insulation",
      "Facade",
      "Roof finish"
    ],
    "out_of_scope": [
      "Heating/plumbing/electrical (MEP)",
      "Interior finishes",
      "Landscaping"
    ]
  },
  
  "confidence_scores": {
    "areas_confidence": "medium",
    "specs_confidence": "low",
    "completeness_percent": 72
  },
  
  "missing_critical_fields": [
    "facade_material",
    "foundation_type",
    "6.4m_span_solution"
  ]
}
```

---

## 🚀 Next Steps (Priority Order)

### IMMEDIATE (This Session)

1. **Deploy Flask API to Railway.app**
   ```
   Steps:
   1. Go to railway.app → Sign up
   2. Create new project
   3. Upload your F:\Madera folder (or connect GitHub)
   4. Set environment variable: MISTRAL_API_KEY=your-key
   5. Deploy
   6. Get public URL: https://madera-qoutation-system.up.railway.app
   ```

2. **Update n8n workflow with new API URL**
   ```
   In n8n Cloud:
   1. Click HTTP Request node
   2. Change URL to: https://madera-qoutation-system.up.railway.app/extract
   3. Save & test
   ```

3. **Test end-to-end**
   ```
   1. Send curl request to webhook
   2. Watch n8n execute
   3. See extraction JSON returned
   ```

### SHORT TERM (Next Days)

4. **Add Google Drive integration** (optional)
   - n8n node: Save extraction.json to Google Drive

5. **Test with real PDFs**
   - Modify workflow to handle PDF attachments
   - Currently: only processes email text

### MEDIUM TERM (Next Week)

6. **Build validation dashboard**
   - 4 tabs: Compare, Verify, Completeness, Decision
   - Javier reviews extracted data
   - Approve/Edit/Clarify decisions

7. **Add PDF viewer to dashboard**
   - Show original PDFs alongside extracted data
   - Links from extracted fields to source PDFs

8. **Document generation**
   - Populate Excel (pricing_and_calc.xlsx)
   - Generate Word (final_offer.docx)

---

## 🛠️ Common Commands

### Start Flask API Server
```bash
cd F:\Madera
python extraction_api.py
```

### Test API Health
```bash
curl http://localhost:5000/health
```

### Test Extraction
```bash
curl -X POST http://localhost:5000/extract ^
  -H "Content-Type: application/json" ^
  -d "{\"email_text\": \"test\", \"pdf_files\": [], \"project_name\": \"test\"}"
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Check Mistral API Key
```bash
echo %MISTRAL_API_KEY%
```

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| README.md | Setup guide (5 minutes) |
| claude.md | This file - project overview |
| extraction_api.py | Has docstrings explaining functions |
| extraction_pipeline.py | Has docstrings explaining steps |
| mistral_extractor.py | Has docstrings for API calls |
| pdf_extractor.py | Has docstrings for PDF handling |

---

## 🔗 External Resources

**Mistral API:**
- Docs: https://docs.mistral.ai
- Console: https://console.mistral.ai
- Free tier: $0-5/month

**n8n:**
- Cloud: https://app.n8n.cloud
- Docs: https://docs.n8n.io
- Free tier available

**Railway (Deployment):**
- Website: https://railway.app
- Docs: https://docs.railway.app
- Free tier: $5/month credit

**pdfplumber:**
- Docs: https://github.com/jsvine/pdfplumber
- Best for: Text extraction from PDFs

**Flask:**
- Docs: https://flask.palletsprojects.com
- Best for: Building REST APIs in Python

---

## 💾 Folder Structure (When Deployed)

```
F:\Madera\
├── extraction_api.py
├── extraction_pipeline.py
├── mistral_extractor.py
├── pdf_extractor.py
├── requirements.txt
├── README.md
├── claude.md                  (this file)
│
├── uploads/                   (PDFs stored here)
│   └── floor_plan.pdf
│
├── extractions/               (JSON results stored here)
│   └── project_extraction.json
│
└── .env                       (optional, stores MISTRAL_API_KEY)
    MISTRAL_API_KEY=sk-...
```

---

## ⚡ Quick Reference

**API is working?**
→ Check: `curl http://localhost:5000/health` (should return 200)

**Mistral key set?**
→ Check: `echo %MISTRAL_API_KEY%` (should show your key)

**Flask running?**
→ Check: Terminal should show "Server starting on http://localhost:5000"

**n8n workflow active?**
→ Check: n8n Cloud should show green checkmark on webhook

**Need to deploy?**
→ Use: Railway.app (easiest for Flask)

**Want to test extraction?**
→ Use: `curl` command above (or Postman)

---

## 📝 Notes for Claude Code

**When working in VS Code with Claude Code:**

1. Read this file first to understand the project
2. Check the current status before making changes
3. Always keep extraction_api.py and extraction_pipeline.py in sync
4. Test changes with: `python extraction_api.py` + curl
5. Update this file when significant changes are made

**Code style:**
- Use type hints (Python 3.7+)
- Add docstrings to all functions
- Keep functions focused and testable
- Add error handling with try/except

**Testing:**
- Always test new changes with curl before deploying
- Check logs in Flask server terminal
- Verify Mistral API responses are valid JSON

---

## 🎯 Success Criteria

**Phase 1 (Extraction) - ✓ COMPLETE**
- [x] PDF extraction works locally
- [x] Mistral integration works
- [x] Flask API running
- [x] Health check passes
- [x] curl tests return 200

**Phase 2 (Automation) - IN PROGRESS**
- [ ] API deployed to Railway
- [ ] n8n workflow connected to deployed API
- [ ] Webhook tests pass
- [ ] End-to-end extraction works

**Phase 3 (Dashboard) - PENDING**
- [ ] Validation UI built
- [ ] Javier can approve/edit/clarify
- [ ] PDF viewer implemented

**Phase 4 (Documents) - PENDING**
- [ ] Excel auto-population
- [ ] Word generation
- [ ] Ready to send to client

---

## 🆘 Troubleshooting

**Problem: "MISTRAL_API_KEY not found"**
- Solution: Run `setx MISTRAL_API_KEY "your-key"` and restart terminal

**Problem: "Port 5000 already in use"**
- Solution: Find what's using it: `netstat -ano | findstr :5000`
- Kill it or change port in extraction_api.py

**Problem: "n8n can't reach API"**
- Solution: n8n Cloud can't reach localhost. Deploy to Railway instead.

**Problem: "Workflow contains credentials not shared"**
- Solution: Use n8n_workflow_simple.json (no credentials in JSON)

**Problem: "PDF extraction returns empty text"**
- Solution: Check if PDF is image-based (scanned). Need OCR (not implemented yet).

---

## 📞 Contact/Questions

When you need to ask Claude Code to help:

**For code modifications:**
"I need to [modify/add/fix] [component]. Here's what needs to change: [details]"

**For troubleshooting:**
"I'm getting [error]. I've tried [what you tried]. What should be next?"

**For new features:**
"I want to add [feature] to [component]. Here's the requirement: [details]"

---

**Last Updated:** May 31, 2026 21:15 UTC
**Status:** Phase 1 Complete, Phase 2 In Progress
**Next Action:** Deploy to Railway.app
