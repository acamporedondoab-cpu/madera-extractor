#!/usr/bin/env python3
"""
Word generator — fills Javier's final_offer.docx template with extraction data.

Variable zones replaced:
  Zone 1 (P001-P014): recipient firm, contacts, offer number, client, date
  Zone 2 (P025-P048): dimensional table values
  Zone 3 (P122/P176/P186): solution totals computed from price list + quantities
"""

import io
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict

TEMPLATE_PATH = (
    Path(__file__).parent / "javier-files" / "final_offer" / "final_offer.docx"
)

# Unit cost prices (EUR) — mirrors PriceList sheet
_PRICES = {
    "STR-001": 285,   # X-lam ext wall 140mm / m2
    "STR-002": 230,   # X-lam int wall 100mm / m2
    "STR-010": 165,   # GL24h beam 200x400 / m
    "STR-011": 245,   # GL24h beam 240x480 / m
    "STR-020": 315,   # X-lam intermediate slab / m2
    "STR-021": 295,   # X-lam roof slab / m2
    "ENV-001":  78,   # Wall insulation 200mm / m2
    "ENV-002":  92,   # Roof insulation 240mm / m2
    "ENV-003": 145,   # Ventilated facade larch / m2
    "ENV-004":  95,   # Ceramic tile roof package / m2
    "ENV-005":  48,   # Flashings + gutter / m
    "WIN-001": 720,   # Triple-glazing window / m2
    "WIN-010": 380,   # External shutter / unit
    "WIN-020": 1850,  # Glazed entrance door / unit
    "SITE-01": 2200,  # Crane rental / month
    "SITE-02":  950,  # Scaffolding / month
    "SITE-10": 18000, # Engineering lump sum
    "SITE-20":  780,  # Assembly labour / day
}

_PLASTERBOARD_FIXED = 110_000  # Solution 3 increment over Solution 2 (EUR cost)
_ASSEMBLY_DAYS = 35


def _num(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _compute_totals(ext: dict) -> tuple:
    """Return (sol1_selling, sol2_selling, sol3_selling) with margin applied."""
    dims = ext.get("building_dimensions") or {}
    geo  = ext.get("building_geometry") or {}
    specs = ext.get("technical_specifications") or {}
    commercial = ext.get("commercial_terms") or {}
    struct_notes = ext.get("structural_notes") or []

    g0    = geo.get("ground_floor") or {}
    g1    = geo.get("first_floor") or {}
    g2    = geo.get("attic") or {}
    roof  = geo.get("roof") or {}
    wins  = geo.get("windows") or {}

    margin = _num(commercial.get("margin_percent"), 30) / 100

    # Per-floor arrays for SUMPRODUCT
    floor_height = 2.8  # default from Parameters sheet
    perimeters = [
        _num(g0.get("ext_perimeter_m")),
        _num(g1.get("ext_perimeter_m")),
        _num(g2.get("area_m2")) and 0,  # attic perimeter often not extracted
    ]
    int_lengths = [
        _num(g0.get("int_walls_length_m")),
        _num(g1.get("int_walls_length_m")),
        0,
    ]
    heights = [floor_height, floor_height, 1.5]

    ext_wall_m2     = sum(p * h for p, h in zip(perimeters, heights))
    int_wall_m2     = sum(l * h for l, h in zip(int_lengths, heights))
    p0_hab          = _num(g0.get("habitable_area_m2") or dims.get("ground_floor_area_m2"))
    p1_hab          = _num(g1.get("habitable_area_m2") or dims.get("first_floor_area_m2"))
    attic_m2        = _num(g2.get("area_m2") or dims.get("attic_area_m2"))
    intermediate_slab = p1_hab + attic_m2
    roof_slab_m2    = _num(roof.get("projected_area_m2"))
    gutter_m        = _num(roof.get("gutter_length_m"))
    window_m2       = _num(wins.get("total_area_m2"))
    shutters        = int(_num(wins.get("count"), 0))
    site_months     = 3

    # Large-span beam — check constraint first (e.g. "6.4m living room span"),
    # fall back to proposed_solution, then default 8.0m
    large_span_m = 8.0
    for note in struct_notes:
        for field in ("constraint", "proposed_solution"):
            m = re.search(r'(\d+(?:\.\d+)?)\s*m\b', note.get(field, ""))
            if m:
                large_span_m = float(m.group(1))
                break
        else:
            continue
        break
    std_beam_m = intermediate_slab * 0.18

    # Line-item costs
    str_cost = (
        ext_wall_m2 * _PRICES["STR-001"]
        + int_wall_m2 * _PRICES["STR-002"]
        + std_beam_m * _PRICES["STR-010"]
        + large_span_m * _PRICES["STR-011"]
        + intermediate_slab * _PRICES["STR-020"]
        + roof_slab_m2 * _PRICES["STR-021"]
    )
    env_cost = (
        ext_wall_m2 * _PRICES["ENV-001"]
        + roof_slab_m2 * _PRICES["ENV-002"]
        + ext_wall_m2 * _PRICES["ENV-003"]
        + roof_slab_m2 * _PRICES["ENV-004"]
        + gutter_m * _PRICES["ENV-005"]
    )
    win_cost = (
        window_m2 * _PRICES["WIN-001"]
        + shutters * _PRICES["WIN-010"]
        + 1 * _PRICES["WIN-020"]
    )
    site_cost = (
        site_months * _PRICES["SITE-01"]
        + site_months * _PRICES["SITE-02"]
        + _PRICES["SITE-10"]
        + _ASSEMBLY_DAYS * _PRICES["SITE-20"]
    )

    def selling(cost):
        return round(cost / (1 - margin), -3) if margin < 1 else cost

    sol1 = selling(str_cost + site_cost)
    sol2 = selling(str_cost + env_cost + win_cost + site_cost)
    sol3 = selling(str_cost + env_cost + win_cost + site_cost + _PLASTERBOARD_FIXED)

    return sol1, sol2, sol3


def _fmt_eur(amount: float) -> str:
    return f"EUR {amount:,.2f}"  # international format: EUR 277,000.00


def _set_para_text(para, new_text: str):
    """Replace all text in a paragraph's runs with new_text, preserving formatting of first run."""
    if not para.runs:
        return
    # Put all text in the first run, clear the rest
    para.runs[0].text = new_text
    for run in para.runs[1:]:
        run.text = ""


def _replace_in_para(para, old: str, new: str):
    """Replace old with new across all runs in a paragraph (handles split runs)."""
    full = "".join(r.text for r in para.runs)
    if old not in full:
        return False
    new_full = full.replace(old, new)
    _set_para_text(para, new_full)
    return True


def generate_word(extraction_data: Dict[str, Any]) -> bytes:
    """
    Fill the final_offer.docx template with extraction data.

    Args:
        extraction_data: full extraction dict (may be wrapped under 'extraction' key)

    Returns:
        Raw .docx bytes ready to send as a download.
    """
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError("python-docx is required: pip install python-docx")

    ext = extraction_data.get("extraction") or extraction_data
    project = ext.get("project") or {}
    geo     = ext.get("building_geometry") or {}
    dims    = ext.get("building_dimensions") or {}

    g0    = geo.get("ground_floor") or {}
    g1    = geo.get("first_floor") or {}
    attic = geo.get("attic") or {}
    roof  = geo.get("roof") or {}

    # Offer number: use a date-based ID
    offer_date   = date.today()
    try:
        offer_date_str = offer_date.strftime("%d %B %Y").lstrip("0")
    except Exception:
        offer_date_str = str(offer_date)

    # Project fields
    firm_name    = project.get("architect_firm") or project.get("architect") or "—"
    arch_contact = project.get("architect") or "—"
    arch_email   = project.get("architect_email") or "—"
    client_name  = project.get("client_name") or "—"
    location     = project.get("location") or "—"
    building_type = project.get("building_type") or "wooden-structure building"

    # Compute solution totals
    sol1, sol2, sol3 = _compute_totals(ext)

    # Dimensional values (rounded integers for the table)
    p0_hab   = int(_num(g0.get("habitable_area_m2") or dims.get("ground_floor_area_m2")))
    p1_hab   = int(_num(g1.get("habitable_area_m2") or dims.get("first_floor_area_m2")))
    p1_ter   = int(_num(g1.get("terrace_area_m2") or dims.get("terrace_area_m2")))
    p1_ter_c = int(round(p1_ter * 0.30))  # 30% coefficient
    attic_m2 = int(_num(attic.get("area_m2") or dims.get("attic_area_m2")))
    roof_m2  = int(_num(roof.get("projected_area_m2")))

    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_path = tmp_dir + "/final_offer.docx"
        shutil.copy2(TEMPLATE_PATH, tmp_path)
        doc = Document(tmp_path)

        paras = doc.paragraphs

        # ── Zone 1: header fields (P001-P014) ────────────────────────
        # "To:" block uses architect_firm; "Att.:" block uses person name
        zone1_replacements = {
            "M+M Arquitectos":           firm_name,
            "Laura Martin":              arch_contact,
            "Carlos Vega":               "",
            "Garcia Family (private)":   client_name,
            "Carrer Major 18, 08870 Sitges": location,
            "Sitges 042":                location,
            "22 May 2026":               offer_date_str,
            "wooden-structure villa":    building_type,
        }

        offer_num = offer_date.strftime('%Y%m')
        for para in paras:
            full = "".join(r.text for r in para.runs)
            # Offer N has tabs between label and value — use regex, not exact match
            if "Offer N:" in full:
                new_full = re.sub(r'(Offer N:[\s\t]*)(\S+)', rf'\g<1>{offer_num}', full)
                if new_full != full:
                    _set_para_text(para, new_full)
                continue
            for old, new in zone1_replacements.items():
                _replace_in_para(para, old, new)

        # ── Zone 2: dimensional table values ─────────────────────────
        # Strategy: find each row-label paragraph then set the numeric paragraph(s) that follow
        table_map = {
            "Ground floor (P0) - habitable": [str(p0_hab), "100%", str(p0_hab)],
            "First floor (P1) - habitable":  [str(p1_hab), "100%", str(p1_hab), str(p1_hab)],
            "First floor (P1) - terrace":    [str(p1_ter), "30%", str(p1_ter_c), str(p1_ter)],
            "Attic (P2) - technical":        [str(attic_m2), "100%", str(attic_m2), str(attic_m2)],
            "Roof":                          [str(roof_m2), "0%", "0", str(roof_m2)],
        }

        for i, para in enumerate(paras):
            label = "".join(r.text for r in para.runs).strip()
            if label in table_map:
                replacements = table_map[label]
                offset = 1
                for j, new_val in enumerate(replacements):
                    if i + offset + j < len(paras):
                        next_para = paras[i + offset + j]
                        next_text = "".join(r.text for r in next_para.runs).strip()
                        # Only replace if it looks like a number or a percentage
                        if re.match(r'^\d+(?:\.\d+)?%?$', next_text):
                            _set_para_text(next_para, new_val)
                        else:
                            offset += 1  # skip non-numeric paragraphs

        # ── Zone 3: solution totals ───────────────────────────────────
        for para in paras:
            full = "".join(r.text for r in para.runs)
            if "TOTAL SOLUTION 1" in full:
                _set_para_text(para, f"TOTAL SOLUTION 1     {_fmt_eur(sol1)} + VAT")
            elif "TOTAL SOLUTION 2" in full:
                _set_para_text(para, f"TOTAL SOLUTION 2     {_fmt_eur(sol2)} + VAT")
            elif "TOTAL SOLUTION 3" in full:
                _set_para_text(para, f"TOTAL SOLUTION 3     {_fmt_eur(sol3)} + VAT")

        # ── Zone 4: validity clause ───────────────────────────────────
        validity = int(_num((ext.get("commercial_terms") or {}).get("quote_validity_days"), 30))
        for para in paras:
            _replace_in_para(para, "valid for 30 days", f"valid for {validity} days")

        out = io.BytesIO()
        doc.save(out)
        return out.getvalue()

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
