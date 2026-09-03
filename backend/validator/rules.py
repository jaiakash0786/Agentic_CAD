"""
Engineering Validation Rules — The Deterministic Safety Layer.

This module contains hard-coded physics and engineering rules that
act as a "compiler firewall" between the probabilistic LLM output
and the deterministic CAD/FEA engines.

Rules check:
  - Physical plausibility (thickness > 0, load > 0)
  - Material compatibility (stress < yield strength)
  - Geometric ratios (length/thickness < 100 for stability)
  - Unit sanity (displacement constraint in reasonable range)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.specification import DesignSpecification
from models.materials import MaterialLibrary


def check_physics_rules(spec: DesignSpecification) -> list[dict]:
    """
    Apply hard-coded engineering physics rules to the specification.

    Returns list of check results:
        {"name": ..., "passed": True/False, "message": ...}
    """
    checks = []

    # ─── Dimension Checks ────────────────────────────────────
    dims = spec.dimensions

    checks.append({
        "name": "Positive thickness",
        "passed": dims.thickness > 0,
        "message": f"Thickness = {dims.thickness} mm"
            if dims.thickness > 0
            else "Thickness must be > 0 mm",
        "category": "geometry",
    })

    checks.append({
        "name": "Positive length",
        "passed": dims.length > 0,
        "message": f"Length = {dims.length} mm",
        "category": "geometry",
    })

    checks.append({
        "name": "Positive width",
        "passed": dims.width > 0,
        "message": f"Width = {dims.width} mm",
        "category": "geometry",
    })

    # Slenderness check
    slenderness = dims.length / dims.thickness if dims.thickness > 0 else float("inf")
    checks.append({
        "name": "Slenderness ratio",
        "passed": slenderness < 100,
        "message": f"L/t = {slenderness:.1f}"
            if slenderness < 100
            else f"L/t = {slenderness:.1f} — too slender (max 100), increase thickness or reduce length",
        "category": "geometry",
    })

    # Hole diameter vs width
    if dims.hole_diameter:
        hole_ok = dims.hole_diameter < dims.width * 0.8
        checks.append({
            "name": "Hole size vs width",
            "passed": hole_ok,
            "message": f"Hole ∅{dims.hole_diameter} mm < 80% of width ({dims.width * 0.8:.1f} mm)"
                if hole_ok
                else f"Hole ∅{dims.hole_diameter} mm is too large for width {dims.width} mm",
            "category": "geometry",
        })

    # Fillet radius vs thickness
    if dims.fillet_radius and dims.fillet_radius > 0:
        fillet_ok = dims.fillet_radius <= dims.thickness
        checks.append({
            "name": "Fillet radius vs thickness",
            "passed": fillet_ok,
            "message": f"Fillet R{dims.fillet_radius} mm ≤ thickness {dims.thickness} mm"
                if fillet_ok
                else f"Fillet R{dims.fillet_radius} mm exceeds thickness {dims.thickness} mm",
            "category": "geometry",
        })

    # ─── Load Checks ────────────────────────────────────────
    for i, load in enumerate(spec.loads):
        checks.append({
            "name": f"Load {i + 1} positive magnitude",
            "passed": load.magnitude > 0,
            "message": f"Load {i + 1} = {load.magnitude} N"
                if load.magnitude > 0
                else f"Load {i + 1} magnitude must be > 0 N",
            "category": "loads",
        })

        # Sanity check: load not astronomically large
        checks.append({
            "name": f"Load {i + 1} magnitude sanity",
            "passed": load.magnitude < 1e8,
            "message": f"Load {i + 1} = {load.magnitude} N (reasonable range)"
                if load.magnitude < 1e8
                else f"Load {i + 1} = {load.magnitude} N — extremely large, verify units",
            "category": "loads",
        })

    # ─── Material Checks ────────────────────────────────────
    mat_exists = MaterialLibrary.exists(spec.material_name)
    checks.append({
        "name": "Material exists in library",
        "passed": mat_exists,
        "message": f"Material '{spec.material_name}' found"
            if mat_exists
            else f"Material '{spec.material_name}' not found. Available: {', '.join(MaterialLibrary.list_names())}",
        "category": "material",
    })

    # Quick stress sanity check (rough estimate)
    if mat_exists and spec.loads:
        mat = MaterialLibrary.get(spec.material_name)
        # Very rough: stress ≈ F / (width × thickness) — for order-of-magnitude check
        cross_section = dims.width * dims.thickness  # mm²
        if cross_section > 0:
            rough_stress = spec.loads[0].magnitude / cross_section  # MPa (N/mm²)
            stress_ok = rough_stress < mat.yield_strength_mpa * 2
            checks.append({
                "name": "Rough stress estimate",
                "passed": stress_ok,
                "message": f"Estimated stress ~{rough_stress:.1f} MPa vs yield {mat.yield_strength_mpa} MPa"
                    if stress_ok
                    else f"Estimated stress ~{rough_stress:.1f} MPa may exceed material capacity. Consider stronger material.",
                "category": "material",
            })

    # ─── Constraint Checks ──────────────────────────────────
    checks.append({
        "name": "Safety factor > 1",
        "passed": spec.constraints.min_safety_factor > 1,
        "message": f"Min SF = {spec.constraints.min_safety_factor}"
            if spec.constraints.min_safety_factor > 1
            else "Safety factor must be > 1",
        "category": "constraints",
    })

    checks.append({
        "name": "Displacement constraint positive",
        "passed": spec.constraints.max_displacement_mm > 0,
        "message": f"Max displacement = {spec.constraints.max_displacement_mm} mm",
        "category": "constraints",
    })

    # ─── Optimization Checks ────────────────────────────────
    opt = spec.optimization
    checks.append({
        "name": "Volume fraction valid",
        "passed": 0 < opt.volume_fraction < 1,
        "message": f"Volume fraction = {opt.volume_fraction}"
            if 0 < opt.volume_fraction < 1
            else f"Volume fraction {opt.volume_fraction} must be between 0 and 1",
        "category": "optimization",
    })

    checks.append({
        "name": "Penalty factor valid",
        "passed": opt.penalty_factor > 1,
        "message": f"Penalty p = {opt.penalty_factor}",
        "category": "optimization",
    })

    return checks
