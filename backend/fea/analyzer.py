"""
FEA Result Analyzer.

Takes raw parsed data (from FRDParser) and the DesignSpecification,
then produces a structured FEAResult with all key engineering metrics:

    max_stress_mpa      — Maximum von Mises stress [MPa]
    max_displacement_mm — Maximum nodal displacement [mm]
    max_strain          — Maximum equivalent strain [-]
    safety_factor       — yield_strength / max_stress
    mass_kg             — Component mass [kg]
    volume_mm3          — Component volume [mm³]
    num_elements        — Number of FEA elements
    num_nodes           — Number of FEA nodes
    solver_time_seconds — Solver wall clock time [s]
"""
import logging
from pathlib import Path
from typing import Any

import numpy as np

from models.materials import MaterialLibrary
from models.results import FEAResult, ConstraintCheck
from models.specification import DesignSpecification

logger = logging.getLogger(__name__)


class FEAAnalyzer:
    """
    Converts raw FEA parsed data into a structured FEAResult.

    Parameters
    ----------
    parsed_data : dict returned by FRDParser.parse()
    mesh_data   : dict returned by GmshMesher.mesh()
    solver_info : dict returned by CalculiXSolver.run()
    spec        : DesignSpecification
    """

    def __init__(
        self,
        parsed_data: dict[str, Any],
        mesh_data: dict[str, Any],
        solver_info: dict[str, Any],
        spec: DesignSpecification,
    ):
        self.parsed_data = parsed_data
        self.mesh_data   = mesh_data
        self.solver_info = solver_info
        self.spec        = spec
        self.material    = MaterialLibrary.get(spec.material_name)

    # ─── Public API ──────────────────────────────────────────────────────────

    def analyze(self) -> FEAResult:
        """
        Compute all engineering metrics and return a FEAResult.
        """
        parsed   = self.parsed_data
        fallback = self.solver_info.get("fallback_results")

        # ── Stress ───────────────────────────────────────────────────────────
        max_stress_mpa = parsed.get("max_stress_mpa", 0.0)

        # Use fallback values if better (Python FEA fallback embeds pre-computed)
        if fallback and fallback.get("max_stress_mpa", 0) > 0:
            max_stress_mpa = max(max_stress_mpa, fallback["max_stress_mpa"])

        # Sanity-check against a minimum (numerical noise threshold)
        max_stress_mpa = max(max_stress_mpa, 1e-6)

        # ── Displacement ─────────────────────────────────────────────────────
        max_disp_mm = parsed.get("max_displacement_mm", 0.0)
        if fallback and fallback.get("max_displacement_mm", 0) > 0:
            max_disp_mm = max(max_disp_mm, fallback["max_displacement_mm"])
        max_disp_mm = max(max_disp_mm, 1e-10)

        # ── Strain ───────────────────────────────────────────────────────────
        E = self.material.youngs_modulus_mpa
        max_strain = max_stress_mpa / E  # engineering approximation: ε = σ/E

        # ── Safety Factor ────────────────────────────────────────────────────
        yield_str = self.material.yield_strength_mpa
        safety_factor = yield_str / max_stress_mpa

        # ── Volume & Mass ────────────────────────────────────────────────────
        volume_mm3 = self._compute_volume()
        density_g_mm3 = self.material.density_g_mm3  # g/mm³
        mass_kg = volume_mm3 * density_g_mm3 / 1000.0  # kg

        if fallback and fallback.get("volume_mm3", 0) > 0:
            volume_mm3 = fallback["volume_mm3"]
            mass_kg = fallback.get("mass_kg", mass_kg)

        # ── Mesh metrics ─────────────────────────────────────────────────────
        num_nodes    = self.mesh_data.get("num_nodes", parsed.get("node_ids") and len(parsed["node_ids"]) or 0)
        num_elements = self.mesh_data.get("num_elements", 0)

        solver_time = self.solver_info.get("solver_time", 0.0)
        solver_mode = self.solver_info.get("solver_mode", "unknown")

        logger.info(
            "[%s] max_stress=%.2f MPa  max_disp=%.4f mm  SF=%.2f  mass=%.4f kg",
            solver_mode, max_stress_mpa, max_disp_mm, safety_factor, mass_kg,
        )

        return FEAResult(
            max_stress_mpa=round(max_stress_mpa, 4),
            max_displacement_mm=round(max_disp_mm, 6),
            max_strain=round(max_strain, 8),
            safety_factor=round(safety_factor, 4),
            mass_kg=round(mass_kg, 6),
            volume_mm3=round(volume_mm3, 2),
            num_elements=num_elements,
            num_nodes=num_nodes,
            solver_time_seconds=round(solver_time, 3),
        )

    def check_constraints(self, result: FEAResult) -> list[ConstraintCheck]:
        """
        Check whether the FEA result satisfies the design constraints.

        Returns a list of ConstraintCheck objects (one per constraint).
        """
        constraints = self.spec.constraints
        checks: list[ConstraintCheck] = []

        # 1. Safety factor ≥ min_safety_factor
        checks.append(ConstraintCheck(
            name="Safety Factor",
            required_value=constraints.min_safety_factor,
            actual_value=result.safety_factor,
            passed=result.safety_factor >= constraints.min_safety_factor,
            unit="",
            comparison=">=",
        ))

        # 2. Displacement ≤ max_displacement_mm
        checks.append(ConstraintCheck(
            name="Max Displacement",
            required_value=constraints.max_displacement_mm,
            actual_value=result.max_displacement_mm,
            passed=result.max_displacement_mm <= constraints.max_displacement_mm,
            unit="mm",
            comparison="<=",
        ))

        # 3. Stress ≤ max_stress_mpa (if specified, else derive from SF)
        if constraints.max_stress_mpa:
            max_allowed_stress = constraints.max_stress_mpa
        else:
            max_allowed_stress = self.material.yield_strength_mpa / constraints.min_safety_factor

        checks.append(ConstraintCheck(
            name="Max Von Mises Stress",
            required_value=max_allowed_stress,
            actual_value=result.max_stress_mpa,
            passed=result.max_stress_mpa <= max_allowed_stress,
            unit="MPa",
            comparison="<=",
        ))

        all_passed = all(c.passed for c in checks)
        logger.info(
            "Constraint check: %s  (%d/%d passed)",
            "✓ ALL PASSED" if all_passed else "✗ FAILED",
            sum(1 for c in checks if c.passed),
            len(checks),
        )
        for c in checks:
            icon = "✓" if c.passed else "✗"
            logger.info(
                "  %s %s: %.4f %s (required %s %.4f)",
                icon, c.name, c.actual_value, c.unit, c.comparison, c.required_value,
            )

        return checks

    # ─── Private ─────────────────────────────────────────────────────────────

    def _compute_volume(self) -> float:
        """
        Compute total mesh volume from C3D4 tetrahedra.
        Falls back to bounding-box estimate if mesh data is unavailable.
        """
        nodes    = self.mesh_data.get("nodes", {})
        elements = self.mesh_data.get("elements", {})

        if not nodes or not elements:
            # Bounding box fallback
            bbox_min = self.mesh_data.get("bbox_min", (0, 0, 0))
            bbox_max = self.mesh_data.get("bbox_max", (100, 50, 8))
            vol = 1.0
            for lo, hi in zip(bbox_min, bbox_max):
                vol *= max(hi - lo, 1e-6)
            return vol * 0.5  # fill factor

        total = 0.0
        for _, conn in elements.items():
            if len(conn) >= 4:
                p = [np.array(nodes[c]) for c in conn[:4] if c in nodes]
                if len(p) == 4:
                    v = abs(np.dot(p[1] - p[0], np.cross(p[2] - p[0], p[3] - p[0]))) / 6.0
                    total += v
        return total if total > 0 else 1.0
