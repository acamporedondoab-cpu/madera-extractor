#!/usr/bin/env python3
"""Generate Excel workbook from extraction data."""

import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


def _hdr(ws, row, col, value, bg="2E7D32", fg="FFFFFF", size=10, bold=True):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(bold=bold, color=fg, size=size, name="Calibri")
    c.fill = PatternFill("solid", fgColor=bg)
    c.alignment = Alignment(horizontal="left", vertical="center")
    return c

def _lbl(ws, row, col, value):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(color="555555", size=10, name="Calibri")
    c.alignment = Alignment(horizontal="left", vertical="center")
    return c

def _val(ws, row, col, value, bold=False, color="111111"):
    c = ws.cell(row=row, column=col, value=value if value is not None else "—")
    c.font = Font(bold=bold, color=color, size=10, name="Calibri")
    c.alignment = Alignment(horizontal="right", vertical="center")
    return c

def _shade(ws, row, cols):
    for col in cols:
        ws.cell(row, col).fill = PatternFill("solid", fgColor="F9F9F9")


def generate_excel(raw_data: dict) -> bytes:
    ext = raw_data.get("extraction") or {}
    project = ext.get("project") or {}
    dims = ext.get("building_dimensions") or {}
    geom = ext.get("building_geometry") or {}
    specs = ext.get("technical_specifications") or {}
    structural = ext.get("structural_notes") or []
    missing = ext.get("missing_critical_fields") or []
    scope = ext.get("scope") or {}
    commercial = ext.get("commercial_terms") or {}
    scores = ext.get("confidence_scores") or {}

    wb = Workbook()

    # ── Sheet 1: Resumen ──────────────────────────────────────────
    ws = wb.active
    ws.title = "Resumen"
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 32

    ws.row_dimensions[1].height = 32
    _hdr(ws, 1, 1, "RESUMEN DEL PROYECTO", bg="1E1E1E", size=13, bold=True)
    ws.merge_cells("A1:B1")

    rows = [
        ("Ubicación", project.get("location")),
        ("Cliente", project.get("client_name")),
        ("Arquitecto", project.get("architect")),
        ("Email Arquitecto", project.get("architect_email")),
        ("Tipo de Edificio", project.get("building_type")),
        ("Plazo de entrega", project.get("deadline")),
        ("Días restantes", project.get("deadline_days_remaining")),
        (None, None),
        ("Completitud extracción", f"{scores.get('completeness_percent', 0)}%"),
        ("Confianza áreas", scores.get("areas_confidence")),
        ("Confianza especificaciones", scores.get("specs_confidence")),
    ]
    for i, (label, value) in enumerate(rows, start=2):
        ws.row_dimensions[i].height = 20
        if label is None:
            continue
        _lbl(ws, i, 1, label)
        v = value if value and str(value) not in ("unknown", "None") else "—"
        _val(ws, i, 2, str(v) if v is not None else "—")
        if i % 2 == 0:
            _shade(ws, i, [1, 2])

    r = len(rows) + 3
    _hdr(ws, r, 1, "CAMPOS FALTANTES", bg="BF360C", size=10)
    ws.merge_cells(f"A{r}:B{r}")
    for field in missing:
        r += 1
        ws.row_dimensions[r].height = 18
        c = ws.cell(row=r, column=1, value=f"⚠  {field}")
        c.font = Font(color="BF360C", size=10, name="Calibri")
        c.fill = PatternFill("solid", fgColor="FFF3E0")
        ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor="FFF3E0")

    # ── Sheet 2: Dimensiones ──────────────────────────────────────
    ws2 = wb.create_sheet("Dimensiones")
    for col, w in zip("ABCDE", [26, 16, 4, 26, 16]):
        ws2.column_dimensions[col].width = w

    ws2.row_dimensions[1].height = 32
    _hdr(ws2, 1, 1, "DIMENSIONES Y GEOMETRÍA", bg="1E1E1E", size=13)
    ws2.merge_cells("A1:E1")

    _hdr(ws2, 2, 1, "Superficie", bg="2E7D32")
    _hdr(ws2, 2, 2, "m²", bg="2E7D32")
    _hdr(ws2, 2, 4, "Geometría", bg="2E7D32")
    _hdr(ws2, 2, 5, "Valor", bg="2E7D32")

    area_rows = [
        ("Planta Baja", dims.get("ground_floor_area_m2")),
        ("Primera Planta", dims.get("first_floor_area_m2")),
        ("Ático", dims.get("attic_area_m2")),
        ("Terraza", dims.get("terrace_area_m2")),
        ("TOTAL", dims.get("total_area_m2")),
        ("Parcela", dims.get("plot_area_m2")),
    ]
    for i, (label, value) in enumerate(area_rows, start=3):
        ws2.row_dimensions[i].height = 20
        if label == "TOTAL":
            for col, v, clr in [(1, label, "1B5E20"), (2, value, "1B5E20")]:
                c = ws2.cell(row=i, column=col, value=v if v is not None else "—")
                c.font = Font(bold=True, color=clr, size=11, name="Calibri")
                c.fill = PatternFill("solid", fgColor="C8E6C9")
                c.alignment = Alignment(horizontal="right" if col == 2 else "left", vertical="center")
        else:
            _lbl(ws2, i, 1, label)
            _val(ws2, i, 2, value)
            if i % 2 == 0:
                _shade(ws2, i, [1, 2])

    gf = geom.get("ground_floor") or {}
    ff = geom.get("first_floor") or {}
    attic = geom.get("attic") or {}
    roof = geom.get("roof") or {}
    windows = geom.get("windows") or {}

    geom_rows = [
        ("── Planta Baja ──", None, True),
        ("Habitable (m²)", gf.get("habitable_area_m2"), False),
        ("Perímetro ext. (m)", gf.get("ext_perimeter_m"), False),
        ("Paredes int. (m)", gf.get("int_walls_length_m"), False),
        ("── Primera Planta ──", None, True),
        ("Habitable (m²)", ff.get("habitable_area_m2"), False),
        ("Terraza (m²)", ff.get("terrace_area_m2"), False),
        ("Perímetro ext. (m)", ff.get("ext_perimeter_m"), False),
        ("Paredes int. (m)", ff.get("int_walls_length_m"), False),
        ("── Ático ──", None, True),
        ("Superficie (m²)", attic.get("area_m2"), False),
        ("── Cubierta ──", None, True),
        ("Área proyectada (m²)", roof.get("projected_area_m2"), False),
        ("Pendiente (°)", roof.get("pitch_degrees"), False),
        ("Canalón (m)", roof.get("gutter_length_m"), False),
        ("── Ventanas ──", None, True),
        ("Cantidad (ud.)", windows.get("count"), False),
        ("Área total (m²)", windows.get("total_area_m2"), False),
        ("Tipo", windows.get("type"), False),
    ]
    for i, (label, value, is_section) in enumerate(geom_rows, start=3):
        ws2.row_dimensions[i].height = 20
        if is_section:
            c = ws2.cell(row=i, column=4, value=label)
            c.font = Font(bold=True, color="2E7D32", size=10, name="Calibri")
            c.fill = PatternFill("solid", fgColor="E8F5E9")
            ws2.cell(row=i, column=5).fill = PatternFill("solid", fgColor="E8F5E9")
        else:
            _lbl(ws2, i, 4, label)
            _val(ws2, i, 5, value)

    # ── Sheet 3: Especificaciones ─────────────────────────────────
    ws3 = wb.create_sheet("Especificaciones")
    for col, w in zip("ABCD", [26, 28, 16, 16]):
        ws3.column_dimensions[col].width = w

    ws3.row_dimensions[1].height = 32
    _hdr(ws3, 1, 1, "ESPECIFICACIONES TÉCNICAS", bg="1E1E1E", size=13)
    ws3.merge_cells("A1:D1")

    for col, title in [(1, "Elemento"), (2, "Material"), (3, "Espesor (mm)"), (4, "Estado")]:
        _hdr(ws3, 2, col, title, bg="2E7D32")

    wall = specs.get("wall_system") or {}
    ins = specs.get("insulation") or {}
    ins_wall = ins.get("walls") or {}
    ins_roof = ins.get("roof") or {}
    facade = specs.get("facade") or {}
    roof_finish = specs.get("roof_finish") or {}
    int_walls = specs.get("internal_walls") or {}

    spec_rows = [
        ("Sistema de Pared", wall.get("material"), wall.get("thickness_mm"), wall.get("status")),
        ("Aislamiento Paredes", ins_wall.get("material"), ins_wall.get("thickness_mm"), ins_wall.get("status")),
        ("Aislamiento Cubierta", ins_roof.get("material"), ins_roof.get("thickness_mm"), ins_roof.get("status")),
        ("Fachada", facade.get("material"), None, facade.get("status")),
        ("Acabado Cubierta", roof_finish.get("type"), None, roof_finish.get("status")),
        ("Paredes Interiores", int_walls.get("material"), int_walls.get("length_m"), None),
    ]
    status_style = {
        "confirmed": ("1B5E20", "C8E6C9"),
        "suggested": ("E65100", "FFF3E0"),
        "unknown":   ("555555", "F5F5F5"),
    }
    for i, (elem, mat, thick, status) in enumerate(spec_rows, start=3):
        ws3.row_dimensions[i].height = 22
        ws3.cell(i, 1, value=elem).font = Font(bold=True, color="333333", size=10, name="Calibri")
        m = mat if mat and mat != "unknown" else "—"
        ws3.cell(i, 2, value=m).font = Font(size=10, name="Calibri")
        c3 = ws3.cell(i, 3, value=thick if thick is not None else "—")
        c3.font = Font(size=10, name="Calibri")
        c3.alignment = Alignment(horizontal="center")
        c4 = ws3.cell(i, 4, value=status or "—")
        s = (status or "unknown").lower()
        fg, bg = status_style.get(s, ("555555", "F5F5F5"))
        c4.font = Font(bold=True, color=fg, size=10, name="Calibri")
        c4.fill = PatternFill("solid", fgColor=bg)
        if i % 2 == 0:
            _shade(ws3, i, [1, 2, 3])

    r = len(spec_rows) + 4
    _hdr(ws3, r, 1, "CONDICIONES COMERCIALES", bg="37474F", size=11)
    ws3.merge_cells(f"A{r}:D{r}")
    for j, (lbl, v) in enumerate([
        ("Margen (%)", commercial.get("margin_percent")),
        ("IVA (%)", commercial.get("vat_rate_percent")),
        ("Validez oferta (días)", commercial.get("quote_validity_days")),
        ("Condiciones de pago", commercial.get("payment_terms")),
        ("Moneda", commercial.get("currency", "EUR")),
    ], start=r + 1):
        ws3.row_dimensions[j].height = 20
        _lbl(ws3, j, 1, lbl)
        _val(ws3, j, 2, v)

    # ── Sheet 4: Notas Estructurales ──────────────────────────────
    ws4 = wb.create_sheet("Notas Estructurales")
    for col, w in zip("ABCD", [26, 36, 18, 42]):
        ws4.column_dimensions[col].width = w

    ws4.row_dimensions[1].height = 32
    _hdr(ws4, 1, 1, "NOTAS ESTRUCTURALES — DECISIONES PENDIENTES", bg="1E1E1E", size=13)
    ws4.merge_cells("A1:D1")
    for col, title in [(1, "Restricción"), (2, "Descripción"), (3, "Estado"), (4, "Solución Propuesta")]:
        _hdr(ws4, 2, col, title, bg="C62828", fg="FFFFFF")

    for i, note in enumerate(structural, start=3):
        ws4.row_dimensions[i].height = 36
        c1 = ws4.cell(i, 1, value=note.get("constraint", "—"))
        c1.font = Font(bold=True, color="C62828", size=10, name="Calibri")
        c1.fill = PatternFill("solid", fgColor="FFEBEE")
        c2 = ws4.cell(i, 2, value=note.get("description", "—"))
        c2.font = Font(size=10, name="Calibri")
        c2.alignment = Alignment(wrap_text=True)
        c2.fill = PatternFill("solid", fgColor="FFEBEE")
        c3 = ws4.cell(i, 3, value=note.get("status", "—"))
        c3.font = Font(bold=True, color="E65100", size=10, name="Calibri")
        c3.fill = PatternFill("solid", fgColor="FFF3E0")
        c4 = ws4.cell(i, 4, value=note.get("proposed_solution") or "—")
        c4.font = Font(size=10, italic=True, name="Calibri")
        c4.alignment = Alignment(wrap_text=True)
        c4.fill = PatternFill("solid", fgColor="FFEBEE")

    r_scope = len(structural) + 4
    _hdr(ws4, r_scope, 1, "ALCANCE", bg="37474F", size=11)
    ws4.merge_cells(f"A{r_scope}:D{r_scope}")
    ws4.cell(r_scope + 1, 1, value="INCLUIDO").font = Font(bold=True, color="1B5E20", size=10, name="Calibri")
    ws4.cell(r_scope + 1, 3, value="EXCLUIDO").font = Font(bold=True, color="C62828", size=10, name="Calibri")
    for j, item in enumerate(scope.get("in_scope") or [], start=r_scope + 2):
        c = ws4.cell(j, 1, value=f"✓  {item}")
        c.font = Font(color="2E7D32", size=10, name="Calibri")
    for j, item in enumerate(scope.get("out_of_scope") or [], start=r_scope + 2):
        c = ws4.cell(j, 3, value=f"✕  {item}")
        c.font = Font(color="C62828", size=10, name="Calibri")

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
