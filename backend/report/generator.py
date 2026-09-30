"""
PDF Report Generator — Phase 9
===============================
Generates a professional PDF engineering report using ReportLab.

Report sections:
  1. Cover page   — project title, component, material, date
  2. Specification — full DesignSpecification table
  3. FEA Results  — stress, displacement, safety factor, mass
  4. Topology     — material saved, compliance, iteration count
  5. Constraint Checks — pass/fail table
  6. Appendix     — mesh info, solver info
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Optional

# ReportLab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# ─── Colour palette ──────────────────────────────────────────────────────────

PURPLE = colors.HexColor("#8b5cf6")
CYAN   = colors.HexColor("#06b6d4")
GREEN  = colors.HexColor("#10b981")
RED    = colors.HexColor("#ef4444")
AMBER  = colors.HexColor("#f59e0b")
DARK   = colors.HexColor("#0f172a")
LIGHT  = colors.HexColor("#f1f5f9")
MUTED  = colors.HexColor("#94a3b8")
WHITE  = colors.white


# ─── Styles ──────────────────────────────────────────────────────────────────

def _build_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("Title2", parent=base["Heading1"],
            fontSize=28, textColor=WHITE, alignment=TA_CENTER,
            spaceAfter=6, fontName="Helvetica-Bold"),

        "subtitle": ParagraphStyle("Subtitle", parent=base["Normal"],
            fontSize=13, textColor=MUTED, alignment=TA_CENTER,
            spaceAfter=4),

        "section": ParagraphStyle("Section", parent=base["Heading2"],
            fontSize=14, textColor=PURPLE, spaceBefore=16, spaceAfter=8,
            fontName="Helvetica-Bold"),

        "body": ParagraphStyle("Body", parent=base["Normal"],
            fontSize=10, textColor=colors.HexColor("#334155"),
            spaceAfter=4, leading=14),

        "mono": ParagraphStyle("Mono", parent=base["Normal"],
            fontSize=9, textColor=colors.HexColor("#334155"),
            fontName="Courier", spaceAfter=2),
    }
    return styles


# ─── Table helpers ────────────────────────────────────────────────────────────

_HEADER_STYLE = TableStyle([
    ("BACKGROUND",   (0, 0), (-1, 0),  PURPLE),
    ("TEXTCOLOR",    (0, 0), (-1, 0),  WHITE),
    ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
    ("FONTSIZE",     (0, 0), (-1, 0),  10),
    ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
    ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.HexColor("#f1f5f9")]),
    ("FONTSIZE",     (0, 1), (-1, -1), 9),
    ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ("TOPPADDING",   (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ("LEFTPADDING",  (0, 0), (-1, -1), 10),
    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
])


def _kv_table(rows: list[tuple[str, str]], col_widths=(80*mm, 90*mm)) -> Table:
    """Two-column key-value table."""
    data = [["Parameter", "Value"]] + [[k, str(v)] for k, v in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(_HEADER_STYLE)
    return t


# ─── Cover page ──────────────────────────────────────────────────────────────

def _cover(styles, component: str, material: str) -> list:
    elements = []
    elements.append(Spacer(1, 60*mm))
    elements.append(Paragraph("Agentic CAD Platform", styles["title"]))
    elements.append(Paragraph("AI-Driven Engineering Design Report", styles["subtitle"]))
    elements.append(Spacer(1, 8*mm))
    elements.append(HRFlowable(width="80%", thickness=1, color=PURPLE, hAlign="CENTER"))
    elements.append(Spacer(1, 8*mm))

    meta_rows = [
        ("Component",  component or "—"),
        ("Material",   material or "—"),
        ("Generated",  datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Platform",   "Agentic CAD v1.0"),
    ]
    t = Table([[k, v] for k, v in meta_rows], colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR",    (0, 0), (0, -1),  MUTED),
        ("TEXTCOLOR",    (1, 0), (1, -1),  PURPLE),
        ("FONTNAME",     (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 11),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(PageBreak())
    return elements


# ─── Main generator ──────────────────────────────────────────────────────────

def generate_report(
    spec_dict: dict,
    fea_dict: Optional[dict],
    topo_dict: Optional[dict],
    output_path: Path,
) -> Path:
    """
    Generate the PDF report and save to output_path.

    Parameters
    ----------
    spec_dict   : DesignSpecification serialised as dict
    fea_dict    : FEAResult serialised as dict (or None)
    topo_dict   : TopologyResponse serialised as dict (or None)
    output_path : Where to write the PDF

    Returns
    -------
    Path to the written PDF file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
        title="Agentic CAD Engineering Report",
        author="Agentic CAD Platform",
    )

    styles = _build_styles()
    story  = []

    component = spec_dict.get("component", "Unknown")
    material  = spec_dict.get("material_name", "Unknown")

    # ── Cover ────────────────────────────────────────────────────────────────
    story += _cover(styles, component, material)

    # ── 1. Design Specification ──────────────────────────────────────────────
    story.append(Paragraph("1. Design Specification", styles["section"]))
    dims = spec_dict.get("dimensions", {}) or {}
    spec_rows = [
        ("Component type",    component),
        ("Material",          material),
        ("Safety factor req.",spec_dict.get("safety_factor", "—")),
    ]
    for k, v in dims.items():
        spec_rows.append((f"  {k.replace('_', ' ').title()}", f"{v} mm"))

    loads = spec_dict.get("loads", [])
    for i, ld in enumerate(loads, 1):
        spec_rows.append((f"Load {i}", f"{ld.get('magnitude', '?')} N · {ld.get('direction', '?')} @ {ld.get('location', '?')}"))

    bcs = spec_dict.get("boundary_conditions", [])
    for i, bc in enumerate(bcs, 1):
        spec_rows.append((f"BC {i}", f"{bc.get('type', '?')} @ {bc.get('location', '?')}"))

    story.append(_kv_table(spec_rows))
    story.append(Spacer(1, 6*mm))

    # ── 2. FEA Results ───────────────────────────────────────────────────────
    story.append(Paragraph("2. Finite Element Analysis Results", styles["section"]))
    if fea_dict:
        sf  = fea_dict.get("safety_factor", 0)
        sig = fea_dict.get("max_stress_mpa", 0)
        ys  = fea_dict.get("yield_strength_mpa", 270)

        fea_rows = [
            ("Max Von Mises Stress",  f"{sig:.2f} MPa"),
            ("Yield Strength",        f"{ys:.0f} MPa"),
            ("Stress Utilisation",    f"{(sig / ys * 100) if ys else '—':.1f}%"),
            ("Max Displacement",      f"{fea_dict.get('max_displacement_mm', 0):.4f} mm"),
            ("Safety Factor",         f"{sf:.3f}  ({'✓ PASS' if sf >= 2 else '✗ FAIL'})"),
            ("Estimated Mass",        f"{fea_dict.get('mass_kg', 0):.4f} kg"),
            ("Volume",                f"{fea_dict.get('volume_mm3', 0):.1f} mm³"),
            ("Mesh nodes",            str(fea_dict.get("num_nodes", "—"))),
            ("Mesh elements",         str(fea_dict.get("num_elements", "—"))),
            ("Solver time",           f"{fea_dict.get('solver_time_seconds', 0):.1f} s"),
        ]
        story.append(_kv_table(fea_rows))
    else:
        story.append(Paragraph("FEA data not available.", styles["body"]))
    story.append(Spacer(1, 6*mm))

    # ── 3. Topology Optimisation ─────────────────────────────────────────────
    story.append(Paragraph("3. Topology Optimisation", styles["section"]))
    if topo_dict and topo_dict.get("success"):
        topo_rows = [
            ("Algorithm",         "SIMP (Solid Isotropic Material with Penalisation)"),
            ("Penalty exponent",  "3.0"),
            ("Converged",         "Yes ✓" if topo_dict.get("converged") else "No (max iters)"),
            ("Iterations",        str(topo_dict.get("iterations", "—"))),
            ("Final Compliance",  f"{topo_dict.get('compliance', 0):.4f}"),
            ("Volume Fraction",   f"{topo_dict.get('volume_fraction', 0):.3f}"),
            ("Solid Elements",    f"{topo_dict.get('solid_elements', '—')} / {topo_dict.get('total_elements', '—')}"),
            ("Material Saved",    f"{topo_dict.get('material_saved_pct', 0):.1f}%"),
            ("Elapsed time",      f"{topo_dict.get('elapsed_s', 0):.1f} s"),
        ]
        story.append(_kv_table(topo_rows))
    else:
        story.append(Paragraph("Topology optimisation data not available.", styles["body"]))
    story.append(Spacer(1, 6*mm))

    # ── 4. Constraint Summary ────────────────────────────────────────────────
    story.append(Paragraph("4. Engineering Constraint Summary", styles["section"]))
    if fea_dict:
        sf  = fea_dict.get("safety_factor", 0)
        disp = fea_dict.get("max_displacement_mm", 999)
        sig  = fea_dict.get("max_stress_mpa", 0)
        ys   = fea_dict.get("yield_strength_mpa", 270)

        constraints = [
            ["Constraint",          "Requirement",  "Actual",             "Result"],
            ["Safety Factor",       "≥ 2.0",        f"{sf:.3f}",          "PASS" if sf >= 2 else "FAIL"],
            ["Max Displacement",    "< 1.0 mm",     f"{disp:.4f} mm",     "PASS" if disp < 1 else "FAIL"],
            ["Von Mises Stress",    f"< {ys:.0f} MPa", f"{sig:.1f} MPa",  "PASS" if sig < ys else "FAIL"],
        ]

        t = Table(constraints, colWidths=[60*mm, 40*mm, 40*mm, 30*mm])
        row_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
            ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.HexColor("#f1f5f9")]),
        ]
        for i, row in enumerate(constraints[1:], 1):
            c = GREEN if row[3] == "PASS" else RED
            row_styles.append(("TEXTCOLOR", (3, i), (3, i), c))
            row_styles.append(("FONTNAME",  (3, i), (3, i), "Helvetica-Bold"))
        t.setStyle(TableStyle(row_styles))
        story.append(t)
    else:
        story.append(Paragraph("Constraint data not available.", styles["body"]))

    story.append(Spacer(1, 10*mm))

    # ── Footer note ──────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        f"Generated by Agentic CAD Platform · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ParagraphStyle("Footer", fontSize=8, textColor=MUTED, alignment=TA_CENTER)
    ))

    doc.build(story)
    return output_path
