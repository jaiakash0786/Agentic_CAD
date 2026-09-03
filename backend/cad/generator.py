"""
CAD Generator — Routes specifications to the correct template and generates CAD.

Architecture:
    DesignSpecification
            ↓
    ComponentType → Template Registry
            ↓
    Template.generate(spec)
            ↓
    CadQuery Workplane (3D solid)
            ↓
    Export to STEP + STL
"""
import sys
import os
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadquery as cq
from models.specification import DesignSpecification, ComponentType
from cad.templates.l_bracket import LBracketTemplate
from cad.templates.beam import BeamTemplate
from cad.templates.plate import PlateTemplate
from cad.templates.mounting_bracket import MountingBracketTemplate
from cad.exporter import export_step, export_stl
from config import CAD_OUTPUT_DIR


# ─── Template Registry ──────────────────────────────────────
# Maps ComponentType → Template instance
TEMPLATE_REGISTRY = {
    ComponentType.L_BRACKET: LBracketTemplate(),
    ComponentType.BEAM: BeamTemplate(),
    ComponentType.PLATE: PlateTemplate(),
    ComponentType.MOUNTING_BRACKET: MountingBracketTemplate(),
}


def get_template(component_type: ComponentType):
    """Get the template for a component type."""
    if component_type not in TEMPLATE_REGISTRY:
        available = ", ".join(t.value for t in TEMPLATE_REGISTRY.keys())
        raise ValueError(
            f"No template for '{component_type.value}'. "
            f"Available: {available}"
        )
    return TEMPLATE_REGISTRY[component_type]


def generate_cad_solid(spec: DesignSpecification) -> cq.Workplane:
    """
    Generate the 3D CAD solid from a specification.

    Args:
        spec: Validated DesignSpecification

    Returns:
        CadQuery Workplane containing the solid
    """
    template = get_template(spec.component)

    # Validate dimensions
    missing = template.validate_dimensions(spec)
    if missing:
        raise ValueError(
            f"Missing required dimensions for {spec.component.value}: "
            f"{', '.join(missing)}"
        )

    # Generate the solid
    return template.generate(spec)


def generate_cad_model(
    spec: DesignSpecification,
    output_id: str = None,
) -> tuple[str, str]:
    """
    Generate CAD model and export to STEP + STL files.

    Args:
        spec: Validated DesignSpecification
        output_id: Optional ID for filenames (auto-generated if not provided)

    Returns:
        Tuple of (step_file_path, stl_file_path)
    """
    if output_id is None:
        output_id = str(uuid.uuid4())[:8]

    # Generate solid
    solid = generate_cad_solid(spec)

    # Export files
    filename_base = f"{spec.component.value}_{output_id}"
    step_path = export_step(solid, filename_base)
    stl_path = export_stl(solid, filename_base)

    return str(step_path), str(stl_path)
