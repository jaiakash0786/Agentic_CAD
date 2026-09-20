"""
Closed-Loop Design Iteration Engine.

When the FEA result fails constraints, this module decides HOW to
modify the design parameters for the next iteration to get closer
to a passing design.

Modification Strategy (in priority order):
    1. Safety Factor too low (stress too high)
       → Increase thickness by THICKNESS_STEP_MM (up to max)
       → Decrease load application area (if applicable)

    2. Displacement too large
       → Increase thickness AND/OR increase cross-section dimensions

    3. Stress too high (explicitly constrained)
       → Same as SF strategy

    4. Volume/mass budget exceeded (after optimization)
       → Reduce target dimensions, accept lower SF margin

Each iteration's modification is recorded with a human-readable
description so the history table in the report makes sense.

Convergence:
    - All constraints satisfied                → converged = True
    - Max iterations reached without pass      → converged = False (best result returned)
    - Design can no longer improve (stalled)   → converged = False
"""
import logging
import copy
from dataclasses import dataclass, field
from typing import Optional

from models.specification import DesignSpecification, Dimensions
from models.results import FEAResult, ConstraintCheck, OptimizationIteration

logger = logging.getLogger(__name__)

# ─── Tuning constants ────────────────────────────────────────────────────────

THICKNESS_STEP_MM   = 2.0    # Increment thickness by this each fail iteration
MAX_THICKNESS_MM    = 30.0   # Hard upper bound on thickness
DIM_SCALE_FACTOR    = 1.10   # Scale width/height by this if SF still failing
MAX_DIM_SCALE       = 2.0    # Maximum cumulative scaling factor vs original
STALL_WINDOW        = 3      # If SF improves < 5% over last N iters → stall
STALL_THRESHOLD     = 0.05   # 5% improvement threshold


@dataclass
class LoopState:
    """Tracks the full history of the design loop."""
    iterations: list[OptimizationIteration] = field(default_factory=list)
    converged: bool = False
    stalled: bool = False
    best_iteration_idx: int = 0  # Index into iterations with best SF

    @property
    def num_iterations(self) -> int:
        return len(self.iterations)

    @property
    def best_result(self) -> Optional[FEAResult]:
        if not self.iterations:
            return None
        return self.iterations[self.best_iteration_idx].fea_result

    @property
    def best_spec_index(self) -> int:
        return self.best_iteration_idx


class DesignLoop:
    """
    Closed-loop design iteration controller.

    Parameters
    ----------
    initial_spec : DesignSpecification — starting point
    max_iterations : int — maximum loop iterations before giving up
    """

    def __init__(
        self,
        initial_spec: DesignSpecification,
        max_iterations: int = 10,
    ):
        self.initial_spec = initial_spec
        self.max_iterations = max_iterations
        self.loop_state = LoopState()
        # Working copy of spec — mutated each iteration
        self._current_spec: DesignSpecification = copy.deepcopy(initial_spec)
        # Track original dimensions for ratio limits
        self._original_dims = copy.deepcopy(initial_spec.dimensions)
        self._dim_scale_applied = 1.0

    # ─── Public API ──────────────────────────────────────────────────────────

    @property
    def current_spec(self) -> DesignSpecification:
        """Current (possibly modified) design specification."""
        return self._current_spec

    def record_iteration(
        self,
        fea_result: FEAResult,
        constraint_checks: list[ConstraintCheck],
        all_passed: bool,
        volume_fraction: float = 1.0,
        objective_value: float = 0.0,
        modification_description: str | None = None,
    ) -> OptimizationIteration:
        """
        Record a completed FEA run as an iteration.
        Updates best_iteration tracking.
        Returns the recorded OptimizationIteration.
        """
        n = self.loop_state.num_iterations + 1
        iteration = OptimizationIteration(
            iteration=n,
            fea_result=fea_result,
            constraint_checks=constraint_checks,
            all_constraints_satisfied=all_passed,
            volume_fraction=volume_fraction,
            objective_value=objective_value or fea_result.max_stress_mpa,
            modification_description=modification_description,
        )
        self.loop_state.iterations.append(iteration)

        # Track best (highest safety factor so far)
        best_sf = self.loop_state.iterations[self.loop_state.best_iteration_idx].fea_result.safety_factor
        if fea_result.safety_factor > best_sf:
            self.loop_state.best_iteration_idx = len(self.loop_state.iterations) - 1

        if all_passed:
            self.loop_state.converged = True
            logger.info("[DesignLoop] Iteration %d PASSED — converged!", n)
        else:
            logger.info(
                "[DesignLoop] Iteration %d FAILED — SF=%.2f, disp=%.4f mm",
                n, fea_result.safety_factor, fea_result.max_displacement_mm,
            )

        return iteration

    def should_continue(self) -> bool:
        """
        Returns True if the loop should run another iteration.
        False when: converged, max iterations reached, or stalled.
        """
        if self.loop_state.converged:
            return False
        if self.loop_state.num_iterations >= self.max_iterations:
            logger.info("[DesignLoop] Max iterations (%d) reached.", self.max_iterations)
            return False
        if self._is_stalled():
            self.loop_state.stalled = True
            logger.info("[DesignLoop] Design loop stalled — no meaningful improvement.")
            return False
        return True

    def propose_next_spec(self) -> tuple[DesignSpecification, str]:
        """
        Analyse the latest FEA result and propose a modified spec
        for the next iteration.

        Returns
        -------
        (modified_spec, description_of_change)
        """
        if not self.loop_state.iterations:
            return self._current_spec, "Initial design"

        last = self.loop_state.iterations[-1]
        result = last.fea_result
        checks = {c.name: c for c in last.constraint_checks}

        mods: list[str] = []
        dims = dict(self._current_spec.dimensions.__dict__)

        # ── Strategy 1: Safety Factor too low ────────────────────────────────
        sf_check = checks.get("Safety Factor")
        if sf_check and not sf_check.passed:
            deficit = sf_check.required_value / max(result.safety_factor, 1e-6)
            logger.info("[DesignLoop] SF deficit=%.2fx — increasing thickness", deficit)

            new_thickness = min(
                dims["thickness"] + THICKNESS_STEP_MM,
                MAX_THICKNESS_MM,
            )
            if new_thickness != dims["thickness"]:
                dims["thickness"] = new_thickness
                mods.append(f"thickness {dims['thickness']-THICKNESS_STEP_MM:.1f}→{new_thickness:.1f} mm")

            # If still very deficient, also scale cross-section
            if deficit > 2.0 and self._dim_scale_applied < MAX_DIM_SCALE:
                scale = min(DIM_SCALE_FACTOR, MAX_DIM_SCALE / self._dim_scale_applied)
                dims["width"]  = round(dims["width"]  * scale, 1)
                dims["height"] = round(dims["height"] * scale, 1) if dims.get("height") else dims.get("height")
                self._dim_scale_applied *= scale
                mods.append(f"width/height scaled x{scale:.2f}")

        # ── Strategy 2: Displacement too large ───────────────────────────────
        disp_check = checks.get("Max Displacement")
        if disp_check and not disp_check.passed:
            logger.info("[DesignLoop] Displacement too large — increasing thickness")
            new_thickness = min(dims["thickness"] + THICKNESS_STEP_MM * 1.5, MAX_THICKNESS_MM)
            if new_thickness != dims["thickness"]:
                dims["thickness"] = new_thickness
                mods.append(f"thickness bumped to {new_thickness:.1f} mm (disp fix)")

        # Build the modified dimensions
        try:
            new_dims = Dimensions(
                length=dims["length"],
                width=dims["width"],
                height=dims.get("height"),
                thickness=dims["thickness"],
                hole_diameter=dims.get("hole_diameter"),
                hole_spacing=dims.get("hole_spacing"),
                fillet_radius=dims.get("fillet_radius"),
            )
        except Exception as e:
            logger.warning("[DesignLoop] Dimension validation failed: %s — keeping previous dims", e)
            new_dims = self._current_spec.dimensions

        # Apply modifications to a fresh copy
        new_spec = copy.deepcopy(self._current_spec)
        object.__setattr__(new_spec, "dimensions", new_dims)
        self._current_spec = new_spec

        description = "; ".join(mods) if mods else "no geometric change (re-running FEA)"
        logger.info("[DesignLoop] Next spec: %s", description)
        return new_spec, description

    def summary(self) -> dict:
        """Return a summary dict of the loop results."""
        history = self.loop_state
        iterations_data = []
        for it in history.iterations:
            iterations_data.append({
                "iteration": it.iteration,
                "max_stress_mpa": it.fea_result.max_stress_mpa,
                "max_displacement_mm": it.fea_result.max_displacement_mm,
                "safety_factor": it.fea_result.safety_factor,
                "mass_kg": it.fea_result.mass_kg,
                "all_passed": it.all_constraints_satisfied,
                "modification": it.modification_description,
            })
        return {
            "converged": history.converged,
            "stalled": history.stalled,
            "num_iterations": history.num_iterations,
            "best_iteration": history.best_iteration_idx + 1,
            "best_safety_factor": history.best_result.safety_factor if history.best_result else 0.0,
            "iterations": iterations_data,
        }

    # ─── Private ─────────────────────────────────────────────────────────────

    def _is_stalled(self) -> bool:
        """
        Detect if SF improvement has stalled over the last STALL_WINDOW iterations.
        """
        n = self.loop_state.num_iterations
        if n < STALL_WINDOW:
            return False

        recent = self.loop_state.iterations[-STALL_WINDOW:]
        sfs = [it.fea_result.safety_factor for it in recent]
        improvement = (max(sfs) - min(sfs)) / max(abs(min(sfs)), 1e-6)
        stalled = improvement < STALL_THRESHOLD
        if stalled:
            logger.info("[DesignLoop] SF values last %d iters: %s — improvement=%.1f%%",
                        STALL_WINDOW, [f"{s:.2f}" for s in sfs], improvement * 100)
        return stalled
