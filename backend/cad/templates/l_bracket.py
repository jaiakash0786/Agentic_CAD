"""
L-Bracket Parametric Template — The primary demonstration component.

Generates an L-shaped bracket with:
  - Configurable leg lengths, width, and thickness
  - Optional mounting holes on both faces
  - Optional fillet at the inner corner
  - Face identification for FEA boundary assignment

Profile sketch (XY plane):
    ┌─────────────────┐
    │                 │ ← thickness
    │    ┌────────────┘
    │    │
    │    │  ← vertical leg
    │    │
    └────┘
    ↑ horizontal leg
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cadquery as cq
from models.specification import DesignSpecification
from cad.templates.base_template import BaseTemplate


class LBracketTemplate(BaseTemplate):
    """
    Parametric L-Bracket generator.

    Parameters from spec.dimensions:
        length:        Horizontal leg length (mm)
        width:         Depth/extrusion width (mm)
        height:        Vertical leg height (mm) — defaults to length if not set
        thickness:     Wall thickness (mm)
        hole_diameter: Mounting hole diameter (mm) — optional
        fillet_radius: Inner corner fillet (mm) — optional
    """

    def get_required_dimensions(self) -> list[str]:
        return ["length", "width", "thickness"]

    def get_description(self) -> str:
        return "L-shaped mounting bracket with optional holes and fillets"

    def generate(self, spec: DesignSpecification) -> cq.Workplane:
        """
        Generate the L-bracket solid.

        The L-profile is drawn in the XY plane and extruded along Z (width).
        """
        d = spec.dimensions
        length = d.length
        width = d.width
        height = d.height if d.height else d.length  # Default height = length
        thickness = d.thickness
        hole_dia = d.hole_diameter
        fillet_r = d.fillet_radius

        # ─── Step 1: Draw L-profile sketch ───────────────────
        # Start from bottom-left corner, draw counter-clockwise
        result = (
            cq.Workplane("XY")
            .moveTo(0, 0)
            .lineTo(length, 0)                    # Bottom edge
            .lineTo(length, thickness)             # Right edge of base
            .lineTo(thickness, thickness)          # Step up to corner
            .lineTo(thickness, height)             # Left edge of vertical leg
            .lineTo(0, height)                     # Top of vertical leg
            .close()                               # Back to origin
            .extrude(width)                        # Extrude along Z
        )

        # ─── Step 2: Add fillet at inner corner ──────────────
        if fillet_r and fillet_r > 0:
            try:
                # Fillet the inner corner edge(s)
                result = result.edges("|Z").fillet(fillet_r)
            except Exception:
                # If fillet fails (e.g., radius too large), skip it
                pass

        # ─── Step 3: Add mounting holes ──────────────────────
        if hole_dia and hole_dia > 0:
            # Holes on the horizontal leg (base) — on the bottom face
            base_hole_x = length / 2
            base_hole_z = width / 2
            try:
                result = (
                    result
                    .faces("<Y")                   # Select bottom face
                    .workplane()
                    .pushPoints([(base_hole_x - length/2, base_hole_z - width/2)])
                    .hole(hole_dia, thickness)
                )
            except Exception:
                pass

            # Holes on the vertical leg — on the front face
            vert_hole_y = height / 2
            try:
                result = (
                    result
                    .faces("<X")                   # Select left face (vertical leg)
                    .workplane()
                    .pushPoints([(width/2 - width/2, vert_hole_y - height/2)])
                    .hole(hole_dia, thickness)
                )
            except Exception:
                pass

        return result


# Singleton instance for the template registry
template = LBracketTemplate()
