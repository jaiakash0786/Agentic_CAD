"""
Result schemas - FEA results, optimization iterations, and pipeline state tracking.

These models capture:
  - Individual FEA results (stress, displacement, safety factor)
  - Optimization iteration history
  - Full design history with pass/fail tracking
  - Pipeline execution state for real-time frontend updates
"""
from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class FEAResult(BaseModel):
    """
    Results extracted from a single FEA run.

    The Result Analyzer extracts these key metrics from raw FEA output:
        Node 1 → stress = 20 MPa
        Node 2 → stress = 25 MPa
        ...
        Node 10000 → stress = 140 MPa

    Condensed to:
        max_stress_mpa = 140.0
        safety_factor = 1.97
    """
    max_stress_mpa: float = Field(..., description="Maximum von Mises stress in MPa")
    max_displacement_mm: float = Field(..., description="Maximum displacement magnitude in mm")
    max_strain: float = Field(..., description="Maximum equivalent strain")
    safety_factor: float = Field(..., description="Yield strength / max stress")
    mass_kg: float = Field(..., description="Component mass in kg")
    volume_mm3: float = Field(..., description="Component volume in mm³")
    num_elements: int = Field(default=0, description="Number of mesh elements")
    num_nodes: int = Field(default=0, description="Number of mesh nodes")
    solver_time_seconds: float = Field(default=0, description="FEA solver wall time")


class ConstraintCheck(BaseModel):
    """Result of checking a single engineering constraint."""
    name: str = Field(..., description="Constraint name")
    required_value: float = Field(..., description="Required threshold")
    actual_value: float = Field(..., description="Actual computed value")
    passed: bool = Field(..., description="Whether constraint is satisfied")
    unit: str = Field(default="", description="Unit of measurement")
    comparison: str = Field(default="<=", description="Comparison operator (<=, >=)")


class OptimizationIteration(BaseModel):
    """Record of a single optimization iteration."""
    iteration: int = Field(..., description="Iteration number (1-indexed)")
    fea_result: FEAResult = Field(..., description="FEA results for this iteration")
    constraint_checks: list[ConstraintCheck] = Field(
        default_factory=list, description="Constraint satisfaction results"
    )
    all_constraints_satisfied: bool = Field(..., description="True if all constraints pass")
    volume_fraction: float = Field(default=1.0, description="Current volume fraction")
    objective_value: float = Field(default=0, description="Current objective function value")
    timestamp: datetime = Field(default_factory=datetime.now)

    # Design modification info
    modification_description: Optional[str] = Field(
        None, description="What was changed in this iteration"
    )


class DesignHistory(BaseModel):
    """
    Complete optimization history for a design.

    Tracks the evolution from initial design to final validated result:
        Iteration 1: Mass=2.50kg  Stress=180MPa  SF=1.65  ❌ FAIL
        Iteration 2: Mass=2.10kg  Stress=150MPa  SF=2.10  ✓ PASS
    """
    iterations: list[OptimizationIteration] = Field(
        default_factory=list, description="All optimization iterations"
    )
    converged: bool = Field(default=False, description="Whether optimization converged")
    final_iteration: Optional[int] = Field(None, description="Iteration number of final design")

    @property
    def num_iterations(self) -> int:
        return len(self.iterations)

    @property
    def latest_result(self) -> Optional[FEAResult]:
        if self.iterations:
            return self.iterations[-1].fea_result
        return None

    @property
    def mass_reduction_percent(self) -> Optional[float]:
        if len(self.iterations) >= 2:
            initial = self.iterations[0].fea_result.mass_kg
            final = self.iterations[-1].fea_result.mass_kg
            if initial > 0:
                return ((initial - final) / initial) * 100
        return None


class PipelineStage(str, Enum):
    """Current stage of the design pipeline."""
    IDLE = "idle"
    INTERPRETING = "interpreting"
    VALIDATING = "validating"
    GENERATING_CAD = "generating_cad"
    MESHING = "meshing"
    RUNNING_FEA = "running_fea"
    ANALYZING_RESULTS = "analyzing_results"
    OPTIMIZING = "optimizing"
    RECONSTRUCTING = "reconstructing"
    VALIDATION_FEA = "validation_fea"
    HUMAN_REVIEW = "human_review"
    GENERATING_REPORT = "generating_report"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineState(BaseModel):
    """
    Real-time pipeline execution state — sent to frontend via WebSocket.

    Tracks which of the 15 steps we're currently on:
        1. Requirement → 2. Interpretation → 3. Validation → ...
    """
    pipeline_id: str = Field(..., description="Unique pipeline execution ID")
    stage: PipelineStage = Field(default=PipelineStage.IDLE)
    progress_percent: float = Field(default=0, ge=0, le=100)
    message: str = Field(default="", description="Human-readable status message")
    started_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # File paths (populated as pipeline progresses)
    cad_step_path: Optional[str] = Field(None, description="Path to generated STEP file")
    cad_stl_path: Optional[str] = Field(None, description="Path to generated STL file")
    mesh_path: Optional[str] = Field(None, description="Path to mesh file")
    report_path: Optional[str] = Field(None, description="Path to PDF report")

    # Results
    design_history: DesignHistory = Field(default_factory=DesignHistory)

    # Error info
    error: Optional[str] = Field(None, description="Error message if pipeline failed")
