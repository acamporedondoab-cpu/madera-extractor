#!/usr/bin/env python3
"""
Excel generator — fills Javier's pricing_and_calc.xlsx template with
extraction data. All Computo formulas cascade automatically once the
Schedule and Parameters input cells are populated.
"""

import io
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

TEMPLATE_PATH = (
    Path(__file__).parent / "javier-files" / "pricing_and_calc" / "pricing_and_calc.xlsx"
)


def _num(value, default=0):
    """Coerce to float; return default if None or non-numeric."""
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def generate_excel(extraction_data: Dict[str, Any]) -> bytes:
    """
    Populate the pricing_and_calc.xlsx template from extraction JSON.

    Fills:
      Parameters sheet  — margin, VAT, wall/insulation thicknesses
      Schedule sheet    — per-floor areas, perimeters, roof, windows

    All downstream formulas in Computo compute automatically when
    the workbook is opened in Excel / LibreOffice.

    Args:
        extraction_data: full extraction dict (may be wrapped under 'extraction' key)

    Returns:
        Raw .xlsx bytes ready to send as a download.
    """
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is required: pip install openpyxl")

    # Support both {extraction: {...}} wrapper and flat dicts
    ext = extraction_data.get("extraction") or extraction_data

    project      = ext.get("project") or {}
    dims         = ext.get("building_dimensions") or {}
    geo          = ext.get("building_geometry") or {}
    specs        = ext.get("technical_specifications") or {}
    commercial   = ext.get("commercial_terms") or {}
    struct_notes = ext.get("structural_notes") or []

    g0    = geo.get("ground_floor") or {}
    g1    = geo.get("first_floor") or {}
    attic = geo.get("attic") or {}
    roof  = geo.get("roof") or {}
    wins  = geo.get("windows") or {}

    wall_sys  = specs.get("wall_system") or {}
    ins_walls = (specs.get("insulation") or {}).get("walls") or {}
    ins_roof  = (specs.get("insulation") or {}).get("roof") or {}

    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_path = os.path.join(tmp_dir, "pricing_and_calc.xlsx")
        shutil.copy2(TEMPLATE_PATH, tmp_path)

        # keep_vba=False is fine — template has no macros
        wb = openpyxl.load_workbook(tmp_path)

        # ── Parameters sheet ─────────────────────────────────────────
        params = wb["Parameters"]

        margin = _num(commercial.get("margin_percent"), 30) / 100
        params["B4"] = round(margin, 4)           # e.g. 0.30

        vat = _num(commercial.get("vat_rate_percent"), 21) / 100
        params["B5"] = round(vat, 4)              # e.g. 0.21

        params["B8"] = _num(wall_sys.get("thickness_mm"), 140)
        params["B10"] = _num(ins_walls.get("thickness_mm"), 200)
        params["B11"] = _num(ins_roof.get("thickness_mm"), 240)

        # ── Schedule sheet — green input cells ───────────────────────
        sched = wb["Schedule"]

        # P0 Ground floor
        sched["B5"] = _num(g0.get("habitable_area_m2") or dims.get("ground_floor_area_m2"))
        sched["C5"] = _num(g0.get("terrace_area_m2"))
        sched["D5"] = _num(g0.get("ext_perimeter_m"))
        sched["E5"] = _num(g0.get("int_walls_length_m"))

        # P1 First floor
        sched["B6"] = _num(g1.get("habitable_area_m2") or dims.get("first_floor_area_m2"))
        sched["C6"] = _num(g1.get("terrace_area_m2") or dims.get("terrace_area_m2"))
        sched["D6"] = _num(g1.get("ext_perimeter_m"))
        sched["E6"] = _num(g1.get("int_walls_length_m"))

        # P2 Attic
        sched["B7"] = _num(attic.get("area_m2") or dims.get("attic_area_m2"))

        # Roof
        sched["B11"] = _num(roof.get("projected_area_m2"))
        sched["B12"] = _num(roof.get("gutter_length_m"))

        # Windows / openings
        sched["B15"] = _num(wins.get("total_area_m2"))
        sched["B16"] = _num(wins.get("count"))
        sched["B17"] = 1  # entrance door default

        # Large-span beam length — parse from structural notes or use default
        large_span_m = 8.0
        for note in struct_notes:
            m = re.search(r'(\d+(?:\.\d+)?)\s*m\b', note.get("proposed_solution", ""))
            if m:
                large_span_m = float(m.group(1))
                break
        sched["B25"] = large_span_m

        # Force Excel to recalculate all formulas on open
        wb.calculation.fullCalcOnLoad = True
        wb.save(tmp_path)
        return Path(tmp_path).read_bytes()

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
