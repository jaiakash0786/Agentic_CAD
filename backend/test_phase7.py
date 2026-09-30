"""
Phase 7 Test: CAD Reconstruction from Topology Density Field
=============================================================
Full end-to-end test:
    1. Run Phase 6 topology optimization (fast: 15 iters)
    2. Pass density field to reconstruction pipeline
    3. Verify clean STL is produced
    4. Check metrics: vertices, faces, volume, watertight
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_phase7")


def test_reconstruction():
    from models.specification import (
        DesignSpecification, ComponentType, Dimensions,
        Load, LoadDirection, LoadType,
        BoundaryCondition, BoundaryConditionType,
        MeshSettings, ValidationConstraints,
    )
    from cad.generator import generate_cad_model
    from optimization.pipeline import run_topology_pipeline
    from reconstruction.pipeline import run_reconstruction_pipeline

    # ── Spec ─────────────────────────────────────────────────────────────────
    spec = DesignSpecification(
        component=ComponentType.L_BRACKET,
        dimensions=Dimensions(
            length=100.0, width=50.0, height=60.0,
            thickness=8.0, hole_diameter=10.0, fillet_radius=3.0,
        ),
        material_name="aluminum_6061_t6",
        loads=[Load(
            magnitude=5000.0,
            direction=LoadDirection.NEGATIVE_Y,
            location="end_face",
            load_type=LoadType.DISTRIBUTED,
        )],
        boundary_conditions=[BoundaryCondition(
            bc_type=BoundaryConditionType.FIXED,
            location="holes",
        )],
        mesh_settings=MeshSettings(element_size=10.0, element_order=1),  # coarse for speed
        constraints=ValidationConstraints(max_displacement_mm=0.5, min_safety_factor=2.0),
        description="Phase 7 test: CAD reconstruction",
    )

    print("\n" + "=" * 60)
    print("PHASE 7 CAD RECONSTRUCTION TEST")
    print("=" * 60)
    print(f"Component       : {spec.component.value}")
    print(f"Mesh size       : {spec.mesh_settings.element_size} mm (very coarse for speed)")
    print(f"SIMP iterations : 15 (fast test)")
    print()

    # ── Step 1: CAD ───────────────────────────────────────────────────────────
    print("Step 1: Generating CAD model...")
    step_path, _ = generate_cad_model(spec)
    print(f"  STEP: {step_path}")

    # ── Step 2: Topology Optimization (fast — 15 iters) ───────────────────────
    print("\nStep 2: Running topology optimization (15 iters)...")
    topo_result = run_topology_pipeline(
        spec=spec,
        step_path=Path(step_path),
        job_id="test_phase7_topo",
        volume_fraction=0.40,
        penalty=3.0,
        max_iter=15,
        tol=1e-3,
    )
    density = topo_result["density"]
    print(f"  Elements : {topo_result['total_elements']}")
    print(f"  Solid    : {topo_result['solid_elements']} ({100*topo_result['solid_elements']/max(topo_result['total_elements'],1):.1f}%)")
    print(f"  Compliance: {topo_result['compliance']:.4f}")

    # ── Step 3: CAD Reconstruction ────────────────────────────────────────────
    print("\nStep 3: Reconstructing optimized CAD from density field...")
    recon_result = run_reconstruction_pipeline(
        topo_result=topo_result,
        job_id="test_phase7",
        grid_size=48,        # 48³ for speed (64³ is better quality)
        threshold=0.5,
        smooth_iterations=3,
    )

    # ── Print results ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RECONSTRUCTION RESULTS")
    print("=" * 60)
    print(f"  Success       : {recon_result['success']}")
    print(f"  STL path      : {recon_result['stl_path']}")
    print(f"  Vertices      : {recon_result['n_vertices']}")
    print(f"  Faces         : {recon_result['n_faces']}")
    print(f"  Volume        : {recon_result['volume_mm3']:.1f} mm³")
    print(f"  Original vol  : {recon_result['original_volume_mm3']:.1f} mm³")
    print(f"  Volume ratio  : {recon_result['volume_ratio']:.3f}")
    print(f"  Material saved: {recon_result['material_saved_pct']:.1f}%")
    print(f"  Watertight    : {recon_result['watertight']}")
    print(f"  Total time    : {recon_result['elapsed_s']:.1f} s")

    stl_path = Path(recon_result["stl_path"])
    if stl_path.exists():
        size_kb = stl_path.stat().st_size / 1024
        print(f"  STL file size : {size_kb:.1f} KB")

    # ── Assertions ────────────────────────────────────────────────────────────
    assert recon_result["success"], f"Reconstruction failed: {recon_result}"
    assert Path(recon_result["stl_path"]).exists(), "STL file not created"
    assert recon_result["n_vertices"] > 100, f"Too few vertices: {recon_result['n_vertices']}"
    assert recon_result["n_faces"] > 100, f"Too few faces: {recon_result['n_faces']}"
    assert recon_result["original_volume_mm3"] > 0, "Original volume is zero"
    assert recon_result["volume_mm3"] >= 0, "Negative volume returned"

    print("\n[ALL ASSERTIONS PASSED] - Phase 7 CAD Reconstruction verified!")
    return recon_result


if __name__ == "__main__":
    test_reconstruction()
