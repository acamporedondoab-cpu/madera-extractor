#!/usr/bin/env python3
"""
PDF Extractor for Javier's Quoting System
Extracts text and metadata from multi-page PDFs using pdfplumber
No API costs - runs locally
"""

import pdfplumber
import json
from pathlib import Path
from typing import Dict, List, Any
import re


class PDFExtractor:
    """Extract text and structured data from PDFs"""
    
    def __init__(self, pdf_path: str):
        """
        Initialize with PDF file path
        
        Args:
            pdf_path: Path to PDF file
        """
        self.pdf_path = pdf_path
        self.filename = Path(pdf_path).name
        self.pages_data = []
        
    def extract_all_pages(self) -> Dict[str, Any]:
        """
        Extract text and dimensions from all pages
        
        Returns:
            Dict with page-by-page data and metadata
        """
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                metadata = {
                    "filename": self.filename,
                    "total_pages": len(pdf.pages),
                    "file_size_mb": Path(self.pdf_path).stat().st_size / (1024 * 1024),
                    "pages": []
                }
                
                for page_num, page in enumerate(pdf.pages, 1):
                    page_data = self._extract_page_data(page, page_num)
                    metadata["pages"].append(page_data)
                
                return metadata
                
        except Exception as e:
            return {"error": f"Failed to extract PDF: {str(e)}"}
    
    def _extract_page_data(self, page, page_num: int) -> Dict[str, Any]:
        """Extract data from single page"""
        
        # Extract text
        text = page.extract_text() or ""
        
        # Extract tables (if any)
        tables = page.extract_tables()
        
        # Extract dimensions/measurements (numbers followed by m², m, mm, etc.)
        dimensions = self._find_dimensions(text)
        
        return {
            "page": page_num,
            "text": text,
            "dimensions_found": dimensions,
            "tables": tables if tables else [],
            "width": page.width,
            "height": page.height
        }
    
    def _find_dimensions(self, text: str) -> List[Dict]:
        """Find dimensions and measurements in text"""
        
        patterns = [
            (r'(\d+(?:,\d{3}|\d{3})?(?:\.\d+)?)\s*m²', 'area'),      # 115 m², 1,234.5 m²
            (r'(\d+(?:\.\d+)?)\s*m\b', 'length'),                      # 6.4 m, 48 m
            (r'(\d+(?:\.\d+)?)\s*mm', 'thickness'),                    # 140 mm, 200 mm
            (r'(\d+(?:\.\d+)?)\s*(?:m|metro|metros)', 'length'),      # Spanish: metros
            (r'(\d+)\s*[x×]\s*(\d+)', 'dimension_pair'),               # 200x400 (beam size)
        ]
        
        dimensions = []
        for pattern, dimension_type in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                dimensions.append({
                    "value": match.group(1),
                    "type": dimension_type,
                    "context": text[max(0, match.start()-20):min(len(text), match.end()+20)]
                })
        
        return dimensions
    
    def extract_by_page(self, page_num: int) -> str:
        """Extract text from specific page"""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                if page_num > len(pdf.pages):
                    return f"Page {page_num} does not exist. PDF has {len(pdf.pages)} pages."
                page = pdf.pages[page_num - 1]
                return page.extract_text() or ""
        except Exception as e:
            return f"Error extracting page: {str(e)}"


def extract_email_attachments(pdf_files: List[str]) -> Dict[str, Any]:
    """
    Extract text from multiple PDFs (email attachments)
    
    Args:
        pdf_files: List of PDF file paths
        
    Returns:
        Combined extraction with all PDFs
    """
    
    all_attachments = {
        "total_pdfs": len(pdf_files),
        "attachments": []
    }
    
    for pdf_path in pdf_files:
        print(f"Extracting: {Path(pdf_path).name}")
        extractor = PDFExtractor(pdf_path)
        extraction = extractor.extract_all_pages()
        all_attachments["attachments"].append(extraction)
    
    return all_attachments


# Example usage
if __name__ == "__main__":
    # Test extraction
    example_pdf = "test.pdf"
    
    if Path(example_pdf).exists():
        extractor = PDFExtractor(example_pdf)
        data = extractor.extract_all_pages()
        print(json.dumps(data, indent=2))
    else:
        print("Test PDF not found. This script is imported by extraction pipeline.")
