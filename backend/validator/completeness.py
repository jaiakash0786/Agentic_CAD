"""
Completeness Checker — Detects missing engineering parameters.

Generates a human-readable checklist showing which parameters
were provided (✓) and which are missing (✗).

Example output:
    Component          ✓
    Material           ✓
    Load               ✓
    Load location      ✗
    Boundary condition ✗
    Optimization       ✓
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.specification import DesignSpecification, ComponentType


# Required fields per component type
REQUIRED_FIELDS = {
    ComponentType.L_BRACKET: {
        "dimensions": ["length", "width", "thickness"],
        "optional_dimensions": ["height", "hole_diameter", "fillet_radius"],
        "required_sections": ["loads", "boundary_conditions", "constraints"],
    },
    ComponentType.BEAM: {
        "dimensions": ["length", "width", "thickness"],
        "optional_dimensions": ["height"],
        "required_sections": ["loads", "boundary_conditions", "constraints"],
    },
    ComponentType.PLATE: {
        "dimensions": ["length", "width", "thickness"],
        "optional_dimensions": ["hole_diameter"],
        "required_sections": ["loads", "boundary_conditions", "constraints"],
    },
    ComponentType.MOUNTING_BRACKET: {
        "dimensions": ["length", "width", "thickness"],
        "optional_dimensions": ["height", "hole_diameter", "fillet_radius"],
        "required_sections": ["loads", "boundary_conditions", "constraints"],
    },
}

# Default for any component not specifically listed
DEFAULT_REQUIRED = {
    "dimensions": ["length", "width", "thickness"],
    "optional_dimensions": ["height", "hole_diameter"],
    "required_sections": ["loads", "boundary_conditions", "constraints"],
}


def check_completeness(spec: DesignSpecification) -> dict:
    """
    Check if a DesignSpecification has all required fields.

    Returns:
        {
            "complete": True/False,
            "checklist": [
                {"field": "Component", "status": "✓", "value": "l_bracket"},
                {"field": "Load location", "status": "✗", "value": None},
                ...
            ],
            "missing_fields": ["load_location", ...],
            "warnings": ["No fillet radius specified, defaulting to 0", ...]
        }
    """
    reqs = REQUIRED_FIELDS.get(spec.component, DEFAULT_REQUIRED)
    checklist = []
    missing = []
    warnings = []

    # ─── Component ───────────────────────────────────────────
    checklist.append({
        "field": "Component Type",
        "status": "✓",
        "value": spec.component.value,
    })

    # ─── Material ────────────────────────────────────────────
    checklist.append({
        "field": "Material",
        "status": "✓",
        "value": spec.material_name,
    })

    # ─── Dimensions ──────────────────────────────────────────
    dims = spec.dimensions
    for dim_name in reqs["dimensions"]:
        val = getattr(dims, dim_name, None)
        if val is not None and val > 0:
            checklist.append({
                "field": f"Dimension: {dim_name}",
                "status": "✓",
                "value": f"{val} mm",
            })
        else:
            checklist.append({
                "field": f"Dimension: {dim_name}",
                "status": "✗",
                "value": None,
            })
            missing.append(dim_name)

    for dim_name in reqs.get("optional_dimensions", []):
        val = getattr(dims, dim_name, None)
        if val is not None and val > 0:
            checklist.append({
                "field": f"Dimension: {dim_name}",
                "status": "✓",
                "value": f"{val} mm",
            })
        else:
            checklist.append({
                "field": f"Dimension: {dim_name} (optional)",
                "status": "○",
                "value": "Not specified (using default)",
            })
            warnings.append(f"Optional: {dim_name} not specified")

    # ─── Loads ───────────────────────────────────────────────
    if spec.loads:
        for i, load in enumerate(spec.loads):
            checklist.append({
                "field": f"Load {i + 1} magnitude",
                "status": "✓",
                "value": f"{load.magnitude} N",
            })
            checklist.append({
                "field": f"Load {i + 1} direction",
                "status": "✓",
                "value": load.direction.value,
            })
            checklist.append({
                "field": f"Load {i + 1} location",
                "status": "✓" if load.location else "✗",
                "value": load.location or None,
            })
            if not load.location:
                missing.append(f"load_{i + 1}_location")
    else:
        checklist.append({
            "field": "Loads",
            "status": "✗",
            "value": None,
        })
        missing.append("loads")

    # ─── Boundary Conditions ─────────────────────────────────
    if spec.boundary_conditions:
        for i, bc in enumerate(spec.boundary_conditions):
            checklist.append({
                "field": f"BC {i + 1} type",
                "status": "✓",
                "value": bc.bc_type.value,
            })
            checklist.append({
                "field": f"BC {i + 1} location",
                "status": "✓" if bc.location else "✗",
                "value": bc.location or None,
            })
            if not bc.location:
                missing.append(f"bc_{i + 1}_location")
    else:
        checklist.append({
            "field": "Boundary Conditions",
            "status": "✗",
            "value": None,
        })
        missing.append("boundary_conditions")

    # ─── Constraints ─────────────────────────────────────────
    checklist.append({
        "field": "Max displacement",
        "status": "✓",
        "value": f"{spec.constraints.max_displacement_mm} mm",
    })
    checklist.append({
        "field": "Min safety factor",
        "status": "✓",
        "value": str(spec.constraints.min_safety_factor),
    })

    # ─── Optimization ────────────────────────────────────────
    checklist.append({
        "field": "Optimization objective",
        "status": "✓",
        "value": spec.optimization.objective.value,
    })
    checklist.append({
        "field": "Volume fraction",
        "status": "✓",
        "value": str(spec.optimization.volume_fraction),
    })

    return {
        "complete": len(missing) == 0,
        "checklist": checklist,
        "missing_fields": missing,
        "warnings": warnings,
    }
