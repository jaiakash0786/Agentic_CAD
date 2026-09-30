"""
Phase 6 Test: SIMP Topology Optimization
==========================================
Tests the full topology optimization pipeline:
    1. Build DesignSpecification
    2. Generate CAD (STEP)
    3. Run SIMP optimizer (40 iters, vf=0.4)
    4. Verify density field, convergence, output files
    5. Print iteration table
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
logger = logging.getLogger("test_phase6")


def test_topology_optimization():
    from models.specification import (
        DesignSpecification, ComponentType, Dimensions,
        Load, LoadDirection, LoadType,
        BoundaryCondition, BoundaryConditionType,
        MeshSettings, ValidationConstraints,
    )
    from cad.generator import generate_cad_model
    from optimization.pipeline import run_topology_pipeline

    # ── Specification ────────────────────────────────────────────────────────
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
        mesh_settings=MeshSettings(element_size=8.0, element_order=1),  # coarser for speed
        constraints=ValidationConstraints(max_displacement_mm=0.5, min_safety_factor=2.0),
        description="Phase 6 test: topology optimization",
    )

    print("\n" + "=" * 60)
    print("PHASE 6 TOPOLOGY OPTIMIZATION TEST")
    print("=" * 60)
    print(f"Component       : {spec.component.value}")
    print(f"Target VF       : 0.40  (remove 60% material)")
    print(f"Mesh size       : {spec.mesh_settings.element_size} mm (coarser for speed)")
    print(f"Max iterations  : 40")
    print()

    # ── Generate CAD ─────────────────────────────────────────────────────────
    print("Step 1: Generating CAD...")
    step_path, _ = generate_cad_model(spec)
    print(f"  STEP: {step_path}")

    # ── Progress callback ─────────────────────────────────────────────────────
    prev_compliance = [None]
    def on_progress(it, compliance, delta):
        if it <= 5 or it % 5 == 0 or delta < 1e-3:
            trend = ""
            if prev_compliance[0] is not None:
                trend = f"  ({compliance - prev_compliance[0]:+.4f})"
            print(f"  iter {it:3d} | compliance={compliance:.4f}{trend} | delta={delta:.6f}")
            prev_compliance[0] = compliance

    # ── Run optimization ──────────────────────────────────────────────────────
    print("\nStep 2: Running SIMP topology optimization...")
    result = run_topology_pipeline(
        spec=spec,
        step_path=Path(step_path),
        job_id="test_phase6",
        volume_fraction=0.40,
        penalty=3.0,
        max_iter=40,
        tol=1e-3,
        progress_callback=on_progress,
    )

    # ── Print results ─────────────────────────────────────────────────────────
    density = result["density"]
    print("\n" + "=" * 60)
    print("TOPOLOGY OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"  Converged         : {result['converged']}")
    print(f"  Iterations        : {result['iterations']}")
    print(f"  Final compliance  : {result['compliance']:.4f}")
    print(f"  Final VF          : {result['volume_fraction']:.3f}  (target=0.40)")
    print(f"  Solid elements    : {result['solid_elements']} / {result['total_elements']}")
    print(f"  Material saved    : {result['material_saved_pct']:.1f}%")
    print(f"  Total time        : {result['elapsed_s']:.1f} s")
    print(f"\n  Density stats:")
    print(f"    min={density.min():.4f}  max={density.max():.4f}  mean={density.mean():.4f}")
    solid = density >= 0.5
    void  = density <= 0.1
    mid   = ~solid & ~void
    print(f"    solid (>=0.5)   : {solid.sum()} elements ({100*solid.mean():.1f}%)")
    print(f"    void  (<=0.1)   : {void.sum()} elements ({100*void.mean():.1f}%)")
    print(f"    grey  (0.1-0.5) : {mid.sum()} elements  (intermediate)")
    print(f"\n  Output files:")
    print(f"    Density .npy : {result['density_path']}")
    print(f"    CSV          : {result['csv_path']}")
    print(f"    Convergence  : {result['hist_path']}")
    print(f"    Preview STL  : {result['stl_path']}")

    # ── Convergence table ─────────────────────────────────────────────────────
    print("\n  Convergence history (selected):")
    print(f"  {'Iter':>4}  {'Compliance':>12}  {'Delta':>10}  {'VF':>6}")
    print("  " + "-" * 40)
    hist = result["history"]
    rows_to_show = set([0, 1, 2, 3, 4] + list(range(0, len(hist), 5)) + [len(hist)-1])
    for i in sorted(rows_to_show):
        if i < len(hist):
            h = hist[i]
            print(f"  {h['iteration']:>4}  {h['compliance']:>12.4f}  {h['delta']:>10.6f}  {h['volume_fraction']:>6.3f}")

    # ── Assertions ───────────────────────────────────────────────────────────
    assert len(density) > 0, "Empty density field"
    assert density.min() >= 0.0, "Density below 0"
    assert density.max() <= 1.0 + 1e-6, "Density above 1"
    assert result["total_elements"] > 0, "No elements"
    assert result["solid_elements"] > 0, "No solid elements"
    assert result["solid_elements"] < result["total_elements"], "All elements solid (no optimization)"
    assert Path(result["density_path"]).exists(), ".npy not written"
    assert Path(result["csv_path"]).exists(), "CSV not written"
    assert result["iterations"] >= 1, "Zero iterations"

    print("\n[ALL ASSERTIONS PASSED] - Phase 6 Topology Optimization verified!")
    return result


if __name__ == "__main__":
    test_topology_optimization()
