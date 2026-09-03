"""
Mounting Bracket Parametric Template — U-shaped mounting bracket.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cadquery as cq
from models.specification import DesignSpecification
from cad.templates.base_template import BaseTemplate


class MountingBracketTemplate(BaseTemplate):
    """
    Parametric U-shaped mounting bracket.

    Parameters:
        length:    Overall length along X (mm)
        width:     Depth along Z (mm)
        height:    Overall height along Y (mm)
        thickness: Wall thickness (mm)
    """

    def get_required_dimensions(self) -> list[str]:
        return ["length", "width", "thickness"]

    def get_description(self) -> str:
        return "U-shaped mounting bracket with side walls"

    def generate(self, spec: DesignSpecification) -> cq.Workplane:
        d = spec.dimensions
        height = d.height if d.height else d.length * 0.6

        # Create outer box
        result = (
            cq.Workplane("XY")
            .box(d.length, height, d.width)
        )

        # Cut out the interior to create U-shape
        inner_length = d.length - 2 * d.thickness
        inner_height = height - d.thickness
        if inner_length > 0 and inner_height > 0:
            result = (
                result
                .faces(">Y")
                .workplane()
                .rect(inner_length, d.width - 2 * d.thickness)
                .cutBlind(-inner_height)
            )

        # Add mounting holes on the base
        if d.hole_diameter and d.hole_diameter > 0:
            try:
                result = (
                    result
                    .faces("<Y")
                    .workplane()
                    .pushPoints([
                        (-d.length / 4, 0),
                        (d.length / 4, 0),
                    ])
                    .hole(d.hole_diameter)
                )
            except Exception:
                pass

        return result


template = MountingBracketTemplate()
