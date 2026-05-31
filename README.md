# Javier's Quoting System - Extraction Pipeline

**Cost-effective alternative to Claude API**: Uses free/cheap tools for rapid quote extraction.

```
Email + PDFs → pdfplumber (local) + Mistral API (free tier) → Structured JSON
```

---

## Quick Start (5 minutes)

### 1. Get Mistral API Key (free)
```bash
# Sign up for free tier: https://console.mistral.ai
# You get $0-5 free credits/month (more than enough for testing)

# Set the key:
export MISTRAL_API_KEY='your-mistral-key-here'
```

### 2. Install Dependencies
```bash
# Navigate to project directory
cd /home/claude/javier_quoting_system

# Install Python packages
pip install -r requirements.txt
```

### 3. Start the Extraction API Server
```bash
# In one terminal:
python3 extraction_api.py

# You'll see:
# ============================================================
# EXTRACTION API SERVER
# ============================================================
# ✓ Mistral API configured
# ✓ Upload dir: ./uploads
# ✓ Extraction dir: ./extractions
# 
# Server starting on http://localhost:5000
# Health check: http://localhost:5000/health
# ============================================================
```

### 4. Test the API
```bash
# In another terminal, test extraction:
curl -X POST http://localhost:5000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "email_text": "Hi Javier, here is the Sitges villa project. 240 m2 over 2 floors.",
    "pdf_files": ["floor_plan.pdf"],
    "project_name": "test_project"
  }'
```

---

## Architecture

### Components

```
┌─────────────────────────────────────────────┐
│ 1. PDF EXTRACTOR (pdfplumber)               │
│    - Extracts text from PDFs (local, free)  │
│    - No API calls needed                     │
│    - Fast: processes pages in seconds       │
│    File: pdf_extractor.py                   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 2. MISTRAL EXTRACTOR (Mistral API)          │
│    - Parses text into structured JSON       │
│    - Free tier: $0-5 credits/month          │
│    - 40+ fields extracted                   │
│    File: mistral_extractor.py               │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 3. EXTRACTION PIPELINE                      │
│    - Orchestrates extraction flow           │
│    - Combines both extractors               │
│    - Outputs structured JSON                │
│    File: extraction_pipeline.py             │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 4. FLASK API SERVER                         │
│    - HTTP endpoint for n8n                  │
│    - Receives email + PDFs                  │
│    - Returns extraction JSON                │
│    File: extraction_api.py                  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ 5. n8n WORKFLOW                             │
│    - Email trigger (Gmail)                  │
│    - Extract PDF attachments                │
│    - Call Flask API                         │
│    - Save results to Google Drive           │
│    File: n8n_workflow.json                  │
└─────────────────────────────────────────────┘
```

---

## How It Works (Step-by-Step)

### Data Flow

```
STEP 1: Email arrives in Gmail
┌────────────────────────────────┐
│ From: Laura Martin             │
│ Subject: Sitges villa quote    │
│ Attachments:                   │
│ • floor_plan_ground.pdf        │
│ • floor_plan_first.pdf         │
│ • sections.pdf                 │
└────────────────────────────────┘
              ↓
STEP 2: n8n workflow triggers
┌────────────────────────────────┐
│ 1. Gmail node reads email      │
│ 2. Extract PDF attachments     │
│ 3. Format data                 │
│ 4. Call Flask API              │
└────────────────────────────────┘
              ↓
STEP 3: PDF Extraction (local, free)
┌────────────────────────────────┐
│ pdfplumber extracts text from: │
│ • floor_plan_ground.pdf        │
│   → "Ground floor: 115 m²"     │
│ • floor_plan_first.pdf         │
│   → "1st floor: 110 m²"        │
│ • sections.pdf                 │
│   → "6.4m living room span"    │
└────────────────────────────────┘
              ↓
STEP 4: Mistral API Parsing
┌────────────────────────────────┐
│ Mistral (free tier) receives:  │
│ - Email text                   │
│ - Extracted PDF text           │
│                                │
│ Returns structured JSON:       │
│ {                              │
│   "ground_floor_area_m2": 115, │
│   "first_floor_area_m2": 110,  │
│   "living_room_span_m": 6.4,   │
│   ... (40+ fields)             │
│ }                              │
└────────────────────────────────┘
              ↓
STEP 5: Save to Google Drive
┌────────────────────────────────┐
│ n8n saves extraction.json to   │
│ Google Drive /Quotes/ folder   │
│                                │
│ File: laura_extraction.json    │
└────────────────────────────────┘
```

---

## File Structure

```
javier_quoting_system/
├── pdf_extractor.py              (PDF text extraction)
├── mistral_extractor.py          (Mistral API calls)
├── extraction_pipeline.py        (Orchestration)
├── extraction_api.py             (Flask server)
├── n8n_workflow.json             (n8n template)
├── requirements.txt              (Python deps)
│
├── uploads/                      (PDF uploads folder)
├── extractions/                  (Output JSON files)
│
└── README.md                     (This file)
```

---

## Cost Analysis

### No Claude API Subscription Needed ✓

**Instead:**

1. **PDF Extraction (pdfplumber)**: FREE
   - Runs locally
   - No API calls
   - No tokens used
   - Fast (processes pages instantly)

2. **Mistral API**: FREE TIER ($0-5/month free credits)
   - One API call per quote
   - ~2000 tokens per extraction
   - Free tier covers ~100+ quotes/month
   - Cost: $0 (free credits)

3. **n8n**: FREE
   - Self-hosted (open source)
   - Or use n8n Cloud free tier

4. **Google Drive**: FREE
   - Store extraction results

**Total cost**: $0 per month (using free tiers)

**vs Claude API**: Would cost $0.60-1.50 per quote

---

## Setup: n8n Workflow

### Option A: Import Workflow to n8n Cloud

1. Copy contents of `n8n_workflow.json`
2. In n8n: Click "Import Workflow"
3. Paste JSON
4. Connect Gmail credentials
5. Update Flask API URL to `http://your-server:5000/extract`

### Option B: Self-Hosted n8n

```bash
# Install n8n
docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n

# Access at: http://localhost:5678
# Import workflow from JSON
```

### Configuration Steps

**1. Gmail Connection**
- In n8n: Add Gmail node
- Click "Authenticate"
- Select your Gmail account
- Allow access

**2. Flask API Endpoint**
- Update n8n "Call Extraction API" node
- URL: `http://localhost:5000/extract`
- (Or your server's IP if remote)

**3. Google Drive (Optional)**
- Save extraction results to Drive
- Add Google Drive node
- Authenticate and select folder

---

## Usage

### Manual Test (without n8n)

```bash
# Terminal 1: Start API server
python3 extraction_api.py

# Terminal 2: Send test request
curl -X POST http://localhost:5000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "email_text": "Hi Javier, 240 m2 wooden villa in Sitges. X-lam 140mm. Deadline: May 29",
    "pdf_files": ["./test_pdfs/floor_plan.pdf"],
    "project_name": "laura_sitges_villa"
  }'

# Response:
# {
#   "status": "success",
#   "extraction": {
#     "project": {
#       "location": "Sitges",
#       "building_type": "wooden villa",
#       ...
#     },
#     "building_dimensions": {
#       "total_area_m2": 240,
#       "ground_floor_area_m2": 115,
#       ...
#     },
#     ...
#   },
#   "output_file": "./extractions/laura_sitges_villa_extraction.json"
# }
```

### With n8n (Automated)

1. Email arrives in Gmail
2. n8n trigger activates
3. PDFs extracted automatically
4. Mistral API processes
5. JSON saved to Google Drive
6. **Done** - Javier has extraction ready

---

## Troubleshooting

### Issue: "MISTRAL_API_KEY not set"

**Solution:**
```bash
export MISTRAL_API_KEY='your-key-here'
# Or add to ~/.bashrc or ~/.zshrc for permanent
```

### Issue: "PDF files not found"

**Solution:**
- Ensure PDF paths are correct
- PDFs should exist before calling API
- In n8n workflow, save attachments first

### Issue: "Mistral API error"

**Solution:**
- Check API key is valid
- Check internet connection
- Check Mistral API status: https://status.mistral.ai
- Check API rate limits (free tier: ~10 req/min)

### Issue: n8n can't reach Flask API

**Solution:**
- Make sure API server is running: `python3 extraction_api.py`
- Check API health: `curl http://localhost:5000/health`
- If n8n is remote, use server IP instead of localhost
- Check firewall: port 5000 must be open

---

## Extraction Output Format

### JSON Structure

```json
{
  "extraction_id": "laura_sitges_villa",
  
  "extraction": {
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
      "roof": { ... },
      "windows": { ... }
    },
    
    "technical_specifications": {
      "wall_system": {
        "material": "X-lam 140mm",
        "thickness_mm": 140,
        "status": "suggested"
      },
      "insulation": { ... },
      "facade": { ... },
      "roof_finish": { ... }
    },
    
    "structural_notes": [
      {
        "constraint": "6.4m living room span",
        "description": "May need beam support",
        "status": "flagged for decision",
        "proposed_solution": "GL24h beam sizing needed"
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
      "in_scope": ["Structure", "Envelope", "Insulation", "Facade", "Roof"],
      "out_of_scope": ["MEP", "Interior finishes", "Landscaping"]
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
  },
  
  "source_data": {
    "email_text": "Full email body...",
    "pdf_names": ["floor_plan_ground.pdf", "floor_plan_first.pdf", "sections.pdf"],
    "pdf_page_count": 9
  },
  
  "metadata": {
    "extraction_tool": "pdfplumber + mistral-large",
    "pipeline_version": "1.0",
    "note": "Free tier: pdfplumber (local) + Mistral API"
  }
}
```

---

## Next Steps

1. ✓ **Setup extraction pipeline** (this guide)
2. **Import n8n workflow**
3. **Connect to Gmail**
4. **Test with sample email + PDFs**
5. **Build dashboard** (next phase)

---

## Support

- **Mistral API Docs**: https://docs.mistral.ai
- **pdfplumber Docs**: https://github.com/jsvine/pdfplumber
- **n8n Docs**: https://docs.n8n.io
- **Flask Docs**: https://flask.palletsprojects.com

---

## Summary

You now have:
- ✓ **PDF extraction** (local, free)
- ✓ **Mistral API integration** (free tier)
- ✓ **Flask API server** (ready for n8n)
- ✓ **n8n workflow template** (ready to import)
- ✓ **Complete documentation**

**Cost**: $0/month (using free tiers)
**No Claude API subscription needed** ✓
