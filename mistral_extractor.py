#!/usr/bin/env python3
"""
Mistral API Extraction for Javier's Quoting System
Uses Mistral API (free tier available) to parse PDF text into structured JSON
"""

import os
import json
from typing import Dict, Any, List
import requests


class MistralExtractor:
    """Extract structured data using Mistral API"""
    
    def __init__(self, api_key: str = None):
        """
        Initialize with Mistral API key
        
        Get free API key: https://console.mistral.ai
        Free tier: $0-5 free credits/month
        
        Args:
            api_key: Mistral API key (defaults to MISTRAL_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "MISTRAL_API_KEY not found. "
                "Set it: export MISTRAL_API_KEY='your-key' "
                "or pass api_key parameter"
            )
        
        self.api_url = "https://api.mistral.ai/v1/messages"
        self.model = "mistral-large-latest"  # Best for reasoning
    
    def extract_quote_data(self, pdf_texts: Dict[str, str], email_text: str) -> Dict[str, Any]:
        """
        Extract structured quote data from PDF texts and email
        
        Args:
            pdf_texts: Dict of {pdf_name: extracted_text}
            email_text: Email body text
            
        Returns:
            Structured JSON with 40+ fields
        """
        
        # Combine all text for context
        combined_text = f"EMAIL:\n{email_text}\n\n"
        for pdf_name, text in pdf_texts.items():
            combined_text += f"\n{pdf_name}:\n{text}\n"
        
        # Mistral extraction prompt
        prompt = self._build_extraction_prompt(combined_text)
        
        # Call Mistral API
        response = self._call_mistral(prompt)
        
        # Parse response into JSON
        try:
            extraction = json.loads(response)
            return extraction
        except json.JSONDecodeError:
            # If response isn't JSON, extract what we can
            return self._fallback_extraction(combined_text)
    
    def _build_extraction_prompt(self, text: str) -> str:
        """Build the extraction prompt for Mistral"""
        
        return f"""You are an expert construction estimator analyzing a project quote request.

Extract ALL available information from the following email and PDF documents:

{text}

Return ONLY valid JSON (no markdown, no code blocks) with these fields:

{{
  "project": {{
    "location": "city, region or 'unknown'",
    "building_type": "wooden villa, house, etc.",
    "client_name": "full name or 'unknown'",
    "architect": "architect/designer name",
    "architect_email": "email if available",
    "deadline": "YYYY-MM-DD or null",
    "deadline_days_remaining": "integer or null"
  }},
  
  "building_dimensions": {{
    "ground_floor_area_m2": "number or null",
    "first_floor_area_m2": "number or null",
    "attic_area_m2": "number or null",
    "terrace_area_m2": "number or null",
    "total_area_m2": "number or null",
    "plot_area_m2": "number or null"
  }},
  
  "building_geometry": {{
    "ground_floor": {{
      "habitable_area_m2": "number",
      "terrace_area_m2": "number",
      "ext_perimeter_m": "number",
      "int_walls_length_m": "number"
    }},
    "first_floor": {{
      "habitable_area_m2": "number",
      "terrace_area_m2": "number",
      "ext_perimeter_m": "number",
      "int_walls_length_m": "number"
    }},
    "attic": {{
      "area_m2": "number",
      "height_m": "number or null"
    }},
    "roof": {{
      "projected_area_m2": "number",
      "pitch_degrees": "number or null",
      "gutter_length_m": "number or null"
    }},
    "windows": {{
      "count": "integer or null",
      "total_area_m2": "number or null",
      "type": "triple glazing, double, etc."
    }}
  }},
  
  "technical_specifications": {{
    "wall_system": {{
      "material": "X-lam 140mm, wood frame, etc.",
      "thickness_mm": "number or null",
      "status": "confirmed, suggested, unknown"
    }},
    "internal_walls": {{
      "material": "description",
      "length_m": "number or null"
    }},
    "insulation": {{
      "walls": {{
        "thickness_mm": "number",
        "material": "wood fiber, mineral wool, etc.",
        "status": "confirmed or unknown"
      }},
      "roof": {{
        "thickness_mm": "number",
        "material": "description",
        "status": "confirmed or unknown"
      }}
    }},
    "facade": {{
      "material": "larch cladding, render, stone, etc.",
      "status": "confirmed, suggested, unknown"
    }},
    "roof_finish": {{
      "type": "ceramic tiles, slate, metal, etc.",
      "color": "description or null",
      "status": "confirmed or suggested"
    }}
  }},
  
  "structural_notes": [
    {{
      "constraint": "6.4m living room span",
      "description": "May need beam support",
      "status": "flagged for decision",
      "proposed_solution": "GL24h beam (specify size) or confirm X-lam 140mm sufficient"
    }}
  ],
  
  "commercial_terms": {{
    "margin_percent": "30 or stated value",
    "vat_rate_percent": "21 or local rate",
    "quote_validity_days": "30 or stated",
    "payment_terms": "30/40/30 or stated",
    "currency": "EUR or stated"
  }},
  
  "scope": {{
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
  }},
  
  "confidence_scores": {{
    "areas_confidence": "high, medium, low",
    "specs_confidence": "high, medium, low",
    "completeness_percent": "0-100"
  }},
  
  "missing_critical_fields": [
    "facade material",
    "foundation type",
    "6.4m span solution"
  ]
}}

IMPORTANT:
- Use 'null' for unknown values, not empty strings
- For status: use only 'confirmed', 'suggested', 'unknown', 'flagged'
- Be conservative: if not explicitly stated, mark as 'unknown'
- For measurements: extract as numbers (no units in value)
- Mark structural constraints that need decision in 'structural_notes'
"""
    
    def _call_mistral(self, prompt: str) -> str:
        """Call Mistral API and return response"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1  # Low temperature for structured output
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Mistral API error: {str(e)}")
    
    def _fallback_extraction(self, text: str) -> Dict[str, Any]:
        """Fallback extraction using regex (if Mistral fails)"""
        
        import re
        
        extraction = {
            "project": {
                "location": self._find_location(text),
                "building_type": "wooden villa",
                "client_name": "unknown",
                "architect": "unknown",
                "deadline": None
            },
            "building_dimensions": {
                "total_area_m2": self._find_number(text, r'(\d+)\s*m2|(\d+)\s*m²'),
                "ground_floor_area_m2": self._find_number(text, r'ground.*?(\d+).*?m²', context=50),
                "first_floor_area_m2": None,
                "attic_area_m2": None,
            },
            "confidence_scores": {
                "completeness_percent": 30  # Fallback is incomplete
            }
        }
        
        return extraction
    
    def _find_location(self, text: str) -> str:
        """Extract location from text"""
        import re
        match = re.search(r'(Sitges|Barcelona|Valencia|Madrid|[A-Z][a-z]+)', text)
        return match.group(1) if match else "unknown"
    
    def _find_number(self, text: str, pattern: str, context: int = 0) -> Any:
        """Extract first matching number"""
        import re
        match = re.search(pattern, text[:3000], re.IGNORECASE)
        if match:
            for group in match.groups():
                if group:
                    try:
                        return float(group.replace(',', ''))
                    except:
                        pass
        return None


# Integration with PDF extractor
def extract_with_mistral(pdf_texts: Dict[str, str], email_text: str, api_key: str = None) -> Dict:
    """
    Full extraction pipeline: PDFs → Text → Mistral → Structured JSON
    
    Args:
        pdf_texts: Dict of {pdf_filename: extracted_text}
        email_text: Email body text
        api_key: Mistral API key (or use env var)
        
    Returns:
        Structured extraction JSON
    """
    
    try:
        mistral = MistralExtractor(api_key=api_key)
        extraction = mistral.extract_quote_data(pdf_texts, email_text)
        return extraction
    except Exception as e:
        print(f"Extraction error: {e}")
        return {"error": str(e)}


# Example usage
if __name__ == "__main__":
    # This would be called by n8n workflow
    # Example:
    # extraction = extract_with_mistral(
    #     pdf_texts={"floor_plan.pdf": "extracted text..."},
    #     email_text="Email body...",
    #     api_key="your-mistral-key"
    # )
    pass
