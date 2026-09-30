"""
Phase 5 Test Script: Closed-Loop Orchestrator
=============================================
Tests the full pipeline coordinator end-to-end:
    1. Builds a DesignSpecification
    2. Runs run_full_pipeline() — the complete closed-loop
    3. Verifies state transitions and iteration history
    4. Prints full summary table
"""
import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_phase5")


async def test_pipeline():
    from models.specification import (
        DesignSpecification, ComponentType, Dimensions,
        Load, LoadDirection, LoadType,
        BoundaryCondition, BoundaryConditionType,
        MeshSettings, ValidationConstraints,
    )
    from models.results import PipelineStage
    from orchestrator.pipeline import run_full_pipeline

    # ── Build spec (same L-bracket as Phase 4) ─────────────────────────────
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
        mesh_settings=MeshSettings(element_size=6.0, element_order=1),
        constraints=ValidationConstraints(
            max_displacement_mm=1.0,
            min_safety_factor=1.5,
        ),
        description="Phase 5 test: closed-loop pipeline",
    )

    print("\n" + "=" * 65)
    print("PHASE 5 CLOSED-LOOP ORCHESTRATOR TEST")
    print("=" * 65)
    print(f"Component  : {spec.component.value}")
    print(f"Material   : {spec.material_name}")
    print(f"SF target  : >= {spec.constraints.min_safety_factor}")
    print(f"Disp limit : <= {spec.constraints.max_displacement_mm} mm")
    print(f"Max iters  : 3 (for test speed)")
    print()

    # ── Run pipeline ────────────────────────────────────────────────────────
    pipeline_id = "test_phase5"
    state = await run_full_pipeline(
        pipeline_id=pipeline_id,
        specification=spec,
        max_loop_iterations=3,
    )

    # ── Print results ────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("PIPELINE RESULT")
    print("=" * 65)
    print(f"  Pipeline ID    : {state.pipeline_id}")
    print(f"  Final Stage    : {state.stage.value}")
    print(f"  Progress       : {state.progress_percent:.1f}%")
    print(f"  Message        : {state.message}")
    if state.error:
        print(f"  Error          : {state.error[:200]}")

    history = state.design_history
    print(f"\n  Iterations run : {history.num_iterations}")
    print(f"  Converged      : {history.converged}")

    if history.iterations:
        print("\n  Iteration Summary:")
        print(f"  {'Iter':>4}  {'Stress(MPa)':>12}  {'Disp(mm)':>9}  {'SF':>5}  {'Mass(kg)':>8}  {'Pass':>5}")
        print("  " + "-" * 55)
        for it in history.iterations:
            r = it.fea_result
            icon = "[OK]" if it.all_constraints_satisfied else "[--]"
            print(f"  {it.iteration:>4}  {r.max_stress_mpa:>12.2f}  {r.max_displacement_mm:>9.4f}  "
                  f"{r.safety_factor:>5.2f}  {r.mass_kg:>8.4f}  {icon:>5}")
            if it.modification_description:
                print(f"       Modification: {it.modification_description}")

    # ── Assertions ──────────────────────────────────────────────────────────
    assert state.stage != PipelineStage.FAILED, f"Pipeline FAILED: {state.error}"
    assert history.num_iterations >= 1, "Must have at least 1 iteration"
    assert history.latest_result is not None, "Must have a latest result"
    assert history.latest_result.mass_kg > 0, "Mass must be positive"
    assert history.latest_result.safety_factor > 0, "SF must be positive"

    print("\n[ALL ASSERTIONS PASSED] - Phase 5 Closed-Loop Orchestrator verified!")
    return state


if __name__ == "__main__":
    asyncio.run(test_pipeline())
