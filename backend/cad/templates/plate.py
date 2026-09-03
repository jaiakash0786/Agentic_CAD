"""
Plate Parametric Template — Flat plate with optional hole pattern.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cadquery as cq
from models.specification import DesignSpecification
from cad.templates.base_template import BaseTemplate


class PlateTemplate(BaseTemplate):
    """
    Parametric flat plate generator.

    Parameters:
        length:    Plate length along X (mm)
        width:     Plate width along Z (mm)
        thickness: Plate thickness along Y (mm)
    """

    def get_required_dimensions(self) -> list[str]:
        return ["length", "width", "thickness"]

    def get_description(self) -> str:
        return "Flat rectangular plate with optional holes"

    def generate(self, spec: DesignSpecification) -> cq.Workplane:
        d = spec.dimensions
        result = (
            cq.Workplane("XY")
            .box(d.length, d.thickness, d.width)
        )

        # Add corner holes if specified
        if d.hole_diameter and d.hole_diameter > 0:
            margin = d.hole_diameter * 2
            try:
                result = (
                    result
                    .faces(">Y")
                    .workplane()
                    .pushPoints([
                        (-d.length / 2 + margin, -d.width / 2 + margin),
                        (d.length / 2 - margin, -d.width / 2 + margin),
                        (-d.length / 2 + margin, d.width / 2 - margin),
                        (d.length / 2 - margin, d.width / 2 - margin),
                    ])
                    .hole(d.hole_diameter)
                )
            except Exception:
                pass

        return result


template = PlateTemplate()
