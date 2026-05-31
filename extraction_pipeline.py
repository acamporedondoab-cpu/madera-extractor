#!/usr/bin/env python3
"""
Complete Extraction Pipeline for Javier's Quoting System

Flow:
1. PDFs extracted to text (local, no cost) → pdf_extractor.py
2. Text + email sent to Mistral API (free tier) → mistral_extractor.py
3. Structured JSON output stored
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from pdf_extractor import PDFExtractor, extract_email_attachments
from mistral_extractor import extract_with_mistral


class QuoteExtractionPipeline:
    """Complete pipeline: email + PDFs → structured quote data"""
    
    def __init__(self, mistral_api_key: str = None, output_dir: str = None):
        """
        Initialize pipeline
        
        Args:
            mistral_api_key: Mistral API key (or use env var)
            output_dir: Where to save extracted JSON
        """
        self.mistral_api_key = mistral_api_key
        self.output_dir = Path(output_dir) if output_dir else Path("./extractions")
        self.output_dir.mkdir(exist_ok=True)
    
    def extract(
        self,
        email_text: str,
        pdf_files: List[str],
        project_name: str
    ) -> Dict[str, Any]:
        """
        Extract structured data from email + PDFs
        
        Args:
            email_text: Email body text
            pdf_files: List of PDF file paths
            project_name: Project identifier (for output file)
            
        Returns:
            Complete extraction with metadata and citations
        """
        
        print(f"\n{'='*60}")
        print(f"EXTRACTION PIPELINE: {project_name}")
        print(f"{'='*60}\n")
        
        # Step 1: Extract text from PDFs
        print("STEP 1: Extracting text from PDFs...")
        pdf_texts = self._extract_pdfs(pdf_files)
        
        # Step 2: Call Mistral API
        print("\nSTEP 2: Calling Mistral API for structured extraction...")
        extraction = extract_with_mistral(
            pdf_texts=pdf_texts,
            email_text=email_text,
            api_key=self.mistral_api_key
        )
        
        # Step 3: Add metadata and citations
        print("\nSTEP 3: Adding metadata and source citations...")
        result = self._add_metadata(
            extraction,
            email_text,
            pdf_texts,
            project_name
        )
        
        # Step 4: Save to file
        print("\nSTEP 4: Saving extraction to file...")
        output_file = self._save_extraction(result, project_name)
        
        print(f"\n✓ Extraction complete: {output_file}")
        return result
    
    def _extract_pdfs(self, pdf_files: List[str]) -> Dict[str, str]:
        """Extract text from all PDFs"""
        
        pdf_texts = {}
        
        for pdf_path in pdf_files:
            path = Path(pdf_path)
            if not path.exists():
                print(f"  ⚠ File not found: {pdf_path}")
                continue
            
            print(f"  • {path.name}...", end=" ", flush=True)
            
            try:
                extractor = PDFExtractor(pdf_path)
                extraction = extractor.extract_all_pages()
                
                # Combine all page text
                full_text = "\n".join([
                    f"\nPAGE {p['page']}:\n{p['text']}"
                    for p in extraction.get('pages', [])
                ])
                
                pdf_texts[path.name] = full_text
                print(f"✓ ({extraction['total_pages']} pages)")
                
            except Exception as e:
                print(f"✗ Error: {e}")
        
        return pdf_texts
    
    def _add_metadata(
        self,
        extraction: Dict,
        email_text: str,
        pdf_texts: Dict[str, str],
        project_name: str
    ) -> Dict[str, Any]:
        """Add source citations and metadata"""
        
        return {
            "extraction_id": project_name,
            "extraction": extraction,
            "source_data": {
                "email_text": email_text,
                "pdf_names": list(pdf_texts.keys()),
                "pdf_page_count": sum(
                    len(pdf_texts[name].split("\nPAGE")) - 1
                    for name in pdf_texts
                )
            },
            "metadata": {
                "extraction_tool": "pdfplumber + mistral-large",
                "pipeline_version": "1.0",
                "note": "Free tier: pdfplumber (local) + Mistral API"
            }
        }
    
    def _save_extraction(self, result: Dict, project_name: str) -> Path:
        """Save extraction to JSON file"""
        
        output_file = self.output_dir / f"{project_name}_extraction.json"
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        return output_file


def main():
    """Example usage: extract from sample files"""
    
    # Check for Mistral API key
    import os
    mistral_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_key:
        print("\n❌ ERROR: MISTRAL_API_KEY not set")
        print("\nTo use this pipeline:")
        print("1. Get Mistral API key: https://console.mistral.ai")
        print("2. Set env var: export MISTRAL_API_KEY='your-key'")
        print("3. Or pass api_key to QuoteExtractionPipeline()")
        sys.exit(1)
    
    # Example: Laura's Sitges villa project
    email_text = """
    From: Laura Martin <laura@arquitectos.example.com>
    Date: May 18, 2026
    
    Hi Javier,
    
    We're working on a residential project in Sitges with a buildable area around 
    240 m2 over two floors plus a small attic/technical level.
    
    We were thinking X-lam 140 mm but I'd like your opinion on the spans of the 
    living room which is about 6.4m.
    
    Please find attached the floor plans and sections.
    
    Deadline: May 29 (11 days)
    
    Best,
    Laura
    """
    
    pdf_files = [
        "floor_plan_ground.pdf",
        "floor_plan_first.pdf",
        "sections_and_elevations.pdf",
        "measurements_and_notes.pdf"
    ]
    
    # Run pipeline
    pipeline = QuoteExtractionPipeline(
        mistral_api_key=mistral_key,
        output_dir="./extractions"
    )
    
    # This would fail if PDFs don't exist, but shows the flow
    # In real use, PDFs come from n8n workflow
    print("Example: QuoteExtractionPipeline ready")
    print("(PDFs would come from n8n email trigger)")


if __name__ == "__main__":
    main()
