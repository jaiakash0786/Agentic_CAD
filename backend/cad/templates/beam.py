"""
Beam Parametric Template — Simple rectangular beam.

Generates a rectangular beam with optional holes.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cadquery as cq
from models.specification import DesignSpecification
from cad.templates.base_template import BaseTemplate


class BeamTemplate(BaseTemplate):
    """
    Parametric rectangular beam generator.

    Parameters:
        length:    Beam length along X (mm)
        width:     Beam width along Z (mm)
        thickness: Beam height along Y (mm)
    """

    def get_required_dimensions(self) -> list[str]:
        return ["length", "width", "thickness"]

    def get_description(self) -> str:
        return "Rectangular beam (cantilever/simply supported)"

    def generate(self, spec: DesignSpecification) -> cq.Workplane:
        d = spec.dimensions
        result = (
            cq.Workplane("XY")
            .box(d.length, d.thickness, d.width)
        )

        # Add holes if specified
        if d.hole_diameter and d.hole_diameter > 0:
            spacing = d.hole_spacing if d.hole_spacing else d.length * 0.8
            try:
                result = (
                    result
                    .faces(">Y")
                    .workplane()
                    .pushPoints([
                        (-spacing / 2, 0),
                        (spacing / 2, 0),
                    ])
                    .hole(d.hole_diameter)
                )
            except Exception:
                pass

        return result


template = BeamTemplate()
