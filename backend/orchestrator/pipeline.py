"""
Full Pipeline Coordinator — Phase 5.

Chains every module in the Agentic CAD platform into one automated flow:

    Step 1  : Interpret NL requirement  (Phase 2)
    Step 2  : Validate specification    (Phase 2)
    Step 3  : Generate CAD              (Phase 3)
    Step 4  : Run initial FEA           (Phase 4)
    Step 5  : Check constraints
    Step 6+ : If FAIL → Design loop iteration
                  - Propose new dimensions (design_loop.py)
                  - Regenerate CAD
                  - Re-run FEA
              If PASS → proceed
    Final   : (Hooks for Phase 6 topology opt + Phase 9 report)

WebSocket updates are sent at each step via the PipelineStateManager.
"""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from models.results import (
    PipelineState, PipelineStage, DesignHistory,
    OptimizationIteration, FEAResult,
)
from models.specification import DesignSpecification
from config import CCX_PATH, FEA_OUTPUT_DIR, CAD_OUTPUT_DIR

from .state_manager import pipeline_state_manager
from .design_loop import DesignLoop

logger = logging.getLogger(__name__)

# ─── Progress map (step → % complete) ───────────────────────────────────────

_STAGE_PROGRESS = {
    PipelineStage.INTERPRETING:    5.0,
    PipelineStage.VALIDATING:     10.0,
    PipelineStage.GENERATING_CAD: 20.0,
    PipelineStage.MESHING:        30.0,
    PipelineStage.RUNNING_FEA:    50.0,
    PipelineStage.ANALYZING_RESULTS: 60.0,
    PipelineStage.OPTIMIZING:     75.0,
    PipelineStage.RECONSTRUCTING: 85.0,
    PipelineStage.HUMAN_REVIEW:   90.0,
    PipelineStage.GENERATING_REPORT: 95.0,
    PipelineStage.COMPLETED:     100.0,
}


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_full_pipeline(
    pipeline_id: str,
    requirement: Optional[str] = None,
    specification: Optional[DesignSpecification] = None,
    max_loop_iterations: int = 5,
) -> PipelineState:
    """
    Execute the full Agentic CAD pipeline end-to-end.

    Either `requirement` (NL text) or `specification` (pre-parsed) must be provided.

    Returns the final PipelineState.
    """
    manager = pipeline_state_manager
    manager.create(pipeline_id)

    try:
        # ── Step 1: Interpret NL (if needed) ─────────────────────────────────
        spec: DesignSpecification
        if specification:
            spec = specification
            await manager.update(pipeline_id,
                stage=PipelineStage.VALIDATING,
                progress_percent=10.0,
                message="Using provided specification — skipping AI interpretation.")
        else:
            if not requirement:
                raise ValueError("Either 'requirement' or 'specification' must be provided.")

            await manager.update(pipeline_id,
                stage=PipelineStage.INTERPRETING,
                progress_percent=_STAGE_PROGRESS[PipelineStage.INTERPRETING],
                message="AI interpreting natural language requirement...")

            from interpreter.parser import parse_requirement
            interp_result = await parse_requirement(requirement)

            if not interp_result.get("success") or not interp_result.get("specification"):
                raise ValueError(
                    f"AI interpretation failed: {interp_result.get('error', 'Unknown error')}"
                )
            spec = interp_result["specification"]

        # ── Step 2: Validate ──────────────────────────────────────────────────
        await manager.update(pipeline_id,
            stage=PipelineStage.VALIDATING,
            progress_percent=_STAGE_PROGRESS[PipelineStage.VALIDATING],
            message="Validating engineering specification...")

        from validator.validator import validate_spec
        validation = validate_spec(spec)
        if not validation["valid"]:
            logger.warning("[%s] Validation warnings: %s", pipeline_id, validation["errors"])
            # Non-fatal: proceed with warnings

        # ── Step 3–6: Design loop ─────────────────────────────────────────────
        design_loop = DesignLoop(
            initial_spec=spec,
            max_iterations=max_loop_iterations,
        )
        design_history = DesignHistory()
        final_step_path: Optional[Path] = None
        final_stl_path: Optional[Path] = None

        iteration_num = 0
        while design_loop.should_continue():
            iteration_num += 1
            current_spec = design_loop.current_spec

            base_progress = 20.0 + (iteration_num - 1) * (60.0 / max_loop_iterations)

            # ── CAD Generation ───────────────────────────────────────────────
            await manager.update(pipeline_id,
                stage=PipelineStage.GENERATING_CAD,
                progress_percent=base_progress,
                message=f"Iteration {iteration_num}: Generating CAD model...")

            # NOTE: CAD and FEA run synchronously (no executor) because Gmsh
            # calls signal.signal() internally which requires the main thread.
            # This is acceptable for a single-pipeline engineering tool.
            step_path, stl_path = _generate_cad(current_spec)
            final_step_path = step_path
            final_stl_path  = stl_path

            await manager.update(pipeline_id,
                cad_step_path=str(step_path),
                cad_stl_path=str(stl_path),
                message=f"Iteration {iteration_num}: CAD generated — running FEA...")

            # ── FEA ──────────────────────────────────────────────────────────
            await manager.update(pipeline_id,
                stage=PipelineStage.MESHING,
                progress_percent=base_progress + 5.0,
                message=f"Iteration {iteration_num}: Meshing with Gmsh...")

            job_id = f"{pipeline_id}_iter{iteration_num}"

            await manager.update(pipeline_id,
                stage=PipelineStage.RUNNING_FEA,
                progress_percent=base_progress + 15.0,
                message=f"Iteration {iteration_num}: Running FEA solver...")

            from fea.pipeline import run_fea_pipeline
            fea_output = run_fea_pipeline(
                spec=current_spec,
                step_path=step_path,
                job_id=job_id,
            )

            fea_result: FEAResult = fea_output["fea_result"]
            constraint_checks = fea_output["constraint_checks"]
            all_passed        = fea_output["all_passed"]

            await manager.update(pipeline_id,
                stage=PipelineStage.ANALYZING_RESULTS,
                progress_percent=base_progress + 25.0,
                message=(
                    f"Iteration {iteration_num}: "
                    f"SF={fea_result.safety_factor:.2f}  "
                    f"stress={fea_result.max_stress_mpa:.1f} MPa  "
                    f"disp={fea_result.max_displacement_mm:.4f} mm  "
                    f"{'PASS' if all_passed else 'FAIL'}"
                ))

            # ── Record iteration ──────────────────────────────────────────────
            mod_desc = None
            if iteration_num > 1:
                # The description was set when proposing the spec
                mod_desc = _last_proposal.get(pipeline_id, "parameter update")

            recorded = design_loop.record_iteration(
                fea_result=fea_result,
                constraint_checks=constraint_checks,
                all_passed=all_passed,
                modification_description=(
                    "Initial design" if iteration_num == 1 else mod_desc
                ),
            )
            design_history.iterations.append(recorded)

            # Update state with history
            await manager.update(pipeline_id, design_history=design_history)

            if all_passed:
                break

            # ── Propose next iteration ────────────────────────────────────────
            if design_loop.should_continue():
                next_spec, description = design_loop.propose_next_spec()
                _last_proposal[pipeline_id] = description
                await manager.update(pipeline_id,
                    message=f"Iteration {iteration_num} FAIL → {description}. "
                            f"Starting iteration {iteration_num + 1}...")

        # ── Loop complete ─────────────────────────────────────────────────────
        design_history.converged     = design_loop.loop_state.converged
        design_history.final_iteration = design_loop.loop_state.num_iterations

        loop_summary = design_loop.summary()
        converged    = loop_summary["converged"]

        if converged:
            summary_msg = (
                f"Design converged in {loop_summary['num_iterations']} iteration(s)! "
                f"Final SF={loop_summary['best_safety_factor']:.2f}"
            )
        else:
            summary_msg = (
                f"Loop ended after {loop_summary['num_iterations']} iteration(s) "
                f"(best SF={loop_summary['best_safety_factor']:.2f}). "
                f"Proceeding to human review."
            )

        logger.info("[%s] %s", pipeline_id, summary_msg)

        # ── Hook: Topology Optimization (Phase 6) — placeholder ──────────────
        # Phase 6 will slot in here when built.
        # For now we skip directly to human review / report.

        # ── Final state ───────────────────────────────────────────────────────
        await manager.update(pipeline_id,
            stage=PipelineStage.HUMAN_REVIEW,
            progress_percent=_STAGE_PROGRESS[PipelineStage.HUMAN_REVIEW],
            message=summary_msg,
            design_history=design_history,
        )

        final_state = await manager.update(pipeline_id,
            stage=PipelineStage.COMPLETED,
            progress_percent=100.0,
            message="Pipeline complete. Awaiting human review.",
        )
        return final_state

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error("[%s] Pipeline FAILED: %s\n%s", pipeline_id, e, tb)
        error_state = await manager.update(pipeline_id,
            stage=PipelineStage.FAILED,
            message=f"Pipeline failed: {str(e)}",
            error=f"{str(e)}\n{tb}",
        )
        return error_state


# ─── FEA-only entry point (used by /api/run-fea) ────────────────────────────

async def run_fea_only(
    spec: DesignSpecification,
    step_path: Path,
    job_id: Optional[str] = None,
) -> dict:
    """Thin async wrapper around fea.pipeline.run_fea_pipeline.
    NOTE: runs synchronously to avoid Gmsh signal/thread restrictions."""
    from fea.pipeline import run_fea_pipeline
    return run_fea_pipeline(spec=spec, step_path=step_path, job_id=job_id)


# ─── Private helpers ─────────────────────────────────────────────────────────

# Stores the last modification description per pipeline_id
_last_proposal: dict[str, str] = {}


def _generate_cad(spec: DesignSpecification) -> tuple[Path, Path]:
    """Synchronous CAD generation wrapper."""
    from cad.generator import generate_cad_model
    step_str, stl_str = generate_cad_model(spec)
    return Path(step_str), Path(stl_str)
