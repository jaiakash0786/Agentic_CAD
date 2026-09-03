"""Test Phase 3: Parametric CAD Generation."""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, "d:/finalyear/backend")

from models.specification import (
    DesignSpecification, ComponentType, Dimensions, Load, LoadDirection,
    BoundaryCondition, BoundaryConditionType, ValidationConstraints,
    OptimizationConfig, OptimizationObjective
)
from cad.generator import generate_cad_model, generate_cad_solid
import os


def test():
    print("=== TEST: Phase 3 — CAD Generator ===\n")

    # Create specification
    spec = DesignSpecification(
        component=ComponentType.L_BRACKET,
        dimensions=Dimensions(
            length=100, width=50, height=60,
            thickness=8, hole_diameter=10, fillet_radius=3
        ),
        material_name="aluminum_6061_t6",
        loads=[Load(magnitude=5000, direction=LoadDirection.NEGATIVE_Y, location="end_face")],
        boundary_conditions=[BoundaryCondition(bc_type=BoundaryConditionType.FIXED, location="holes")],
        constraints=ValidationConstraints(max_displacement_mm=0.5, min_safety_factor=2.0),
        optimization=OptimizationConfig(objective=OptimizationObjective.MINIMIZE_MASS, volume_fraction=0.4),
    )

    # Generate L-bracket
    print("Generating L-bracket...")
    step_path, stl_path = generate_cad_model(spec, output_id="test_lbracket")

    print(f"  STEP: {step_path}")
    print(f"  STL:  {stl_path}")
    print(f"  STEP size: {os.path.getsize(step_path):,} bytes")
    print(f"  STL size:  {os.path.getsize(stl_path):,} bytes")

    # Test other templates
    print("\nTesting Beam template...")
    spec_beam = spec.model_copy(update={"component": ComponentType.BEAM})
    step2, stl2 = generate_cad_model(spec_beam, output_id="test_beam")
    print(f"  STEP: {os.path.getsize(step2):,} bytes")
    print(f"  STL:  {os.path.getsize(stl2):,} bytes")

    print("\nTesting Plate template...")
    spec_plate = spec.model_copy(update={"component": ComponentType.PLATE})
    step3, stl3 = generate_cad_model(spec_plate, output_id="test_plate")
    print(f"  STEP: {os.path.getsize(step3):,} bytes")
    print(f"  STL:  {os.path.getsize(stl3):,} bytes")

    print("\nTesting Mounting Bracket template...")
    spec_mb = spec.model_copy(update={"component": ComponentType.MOUNTING_BRACKET})
    step4, stl4 = generate_cad_model(spec_mb, output_id="test_mounting")
    print(f"  STEP: {os.path.getsize(step4):,} bytes")
    print(f"  STL:  {os.path.getsize(stl4):,} bytes")

    print("\n✓ PHASE 3: ALL PASS — 4 templates generating STEP+STL successfully!")


if __name__ == "__main__":
    test()
