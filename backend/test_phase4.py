"""
Phase 4 Test Script: FEA Pipeline
===================================
Tests the complete FEA pipeline end-to-end:
    1. Creates a sample DesignSpecification
    2. Generates CAD (reuses Phase 3 generator)
    3. Runs FEA pipeline (mesh → inp → solver → parse → analyze)
    4. Prints results
"""
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_phase4")


def test_fea_pipeline():
    from models.specification import (
        DesignSpecification, ComponentType, Dimensions,
        Load, LoadDirection, LoadType,
        BoundaryCondition, BoundaryConditionType,
        MeshSettings, ValidationConstraints,
    )
    from cad.generator import generate_cad_model
    from fea.pipeline import run_fea_pipeline

    # ── 1. Build sample specification ──────────────────────────────────────
    spec = DesignSpecification(
        component=ComponentType.L_BRACKET,
        dimensions=Dimensions(
            length=100.0,
            width=50.0,
            height=60.0,
            thickness=8.0,
            hole_diameter=10.0,
            fillet_radius=3.0,
        ),
        material_name="aluminum_6061_t6",
        loads=[
            Load(
                magnitude=5000.0,
                direction=LoadDirection.NEGATIVE_Y,
                location="end_face",
                load_type=LoadType.DISTRIBUTED,
            )
        ],
        boundary_conditions=[
            BoundaryCondition(
                bc_type=BoundaryConditionType.FIXED,
                location="holes",
            )
        ],
        mesh_settings=MeshSettings(
            element_size=5.0,   # Coarser mesh = faster test
            element_order=1,
        ),
        constraints=ValidationConstraints(
            max_displacement_mm=0.5,
            min_safety_factor=2.0,
        ),
        description="Test: 5 kN aluminum L-bracket FEA",
    )

    print("\n" + "=" * 60)
    print("PHASE 4 FEA PIPELINE TEST")
    print("=" * 60)
    print(f"Component : {spec.component.value}")
    print(f"Material  : {spec.material_name}")
    print(f"Load      : {spec.loads[0].magnitude} N @ {spec.loads[0].direction}")
    print(f"Mesh size : {spec.mesh_settings.element_size} mm")
    print()

    # ── 2. Generate CAD ─────────────────────────────────────────────────────
    print("Step 1: Generating CAD...")
    step_path, stl_path = generate_cad_model(spec)
    print(f"  [OK] STEP: {step_path}")
    print(f"  [OK] STL : {stl_path}")
    assert Path(step_path).exists(), "STEP file missing!"
    assert Path(step_path).stat().st_size > 1000, "STEP file too small!"

    # ── 3. Run FEA pipeline ─────────────────────────────────────────────────
    print("\nStep 2-6: Running FEA pipeline...")
    result = run_fea_pipeline(
        spec=spec,
        step_path=Path(step_path),
        job_id="test_phase4",
    )

    # ── 4. Print results ────────────────────────────────────────────────────
    fea = result["fea_result"]
    checks = result["constraint_checks"]

    print("\n" + "=" * 60)
    print("FEA RESULTS")
    print("=" * 60)
    print(f"  Max von Mises Stress : {fea.max_stress_mpa:.2f} MPa")
    print(f"  Max Displacement     : {fea.max_displacement_mm:.4f} mm")
    print(f"  Max Strain           : {fea.max_strain:.6f}")
    print(f"  Safety Factor        : {fea.safety_factor:.2f}")
    print(f"  Mass                 : {fea.mass_kg:.4f} kg")
    print(f"  Volume               : {fea.volume_mm3:.1f} mm³")
    print(f"  Nodes                : {fea.num_nodes}")
    print(f"  Elements             : {fea.num_elements}")
    print(f"  Solver time          : {fea.solver_time_seconds:.2f} s")
    print(f"  Solver mode          : {result['solver_info']['solver_mode']}")

    print("\n  Constraint Checks:")
    all_passed = result["all_passed"]
    for c in checks:
        icon = "[OK]  " if c.passed else "[FAIL]"
        print(f"    {icon} {c.name}: {c.actual_value:.4f} {c.unit} "
              f"(required {c.comparison} {c.required_value:.4f})")

    print(f"\n  Overall: {'[PASS] ALL CONSTRAINTS PASSED' if all_passed else '[FAIL] CONSTRAINTS FAILED'}")
    print(f"\n  Output files:")
    print(f"    .inp : {result['inp_path']}")
    print(f"    .frd : {result.get('frd_path', 'N/A')}")

    # ── 5. Assertions ───────────────────────────────────────────────────────
    assert fea.max_stress_mpa > 0, "Stress must be positive"
    assert fea.max_displacement_mm > 0, "Displacement must be positive"
    assert fea.safety_factor > 0, "Safety factor must be positive"
    assert fea.mass_kg > 0, "Mass must be positive"
    assert fea.volume_mm3 > 0, "Volume must be positive"
    assert fea.num_nodes > 0, "Must have nodes"
    assert fea.num_elements > 0, "Must have elements"

    print("\n[ALL DONE] ALL ASSERTIONS PASSED - Phase 4 FEA Pipeline verified!")
    return result


if __name__ == "__main__":
    test_fea_pipeline()
