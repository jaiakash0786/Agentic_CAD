"""
Optimization-specific schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional
import numpy as np


class SIMPConfig(BaseModel):
    """Configuration for the SIMP topology optimization algorithm."""
    nelx: int = Field(default=60, gt=0, description="Number of elements in X direction")
    nely: int = Field(default=20, gt=0, description="Number of elements in Y direction")
    nelz: Optional[int] = Field(None, gt=0, description="Number of elements in Z direction (None=2D)")
    volume_fraction: float = Field(default=0.4, gt=0, lt=1, description="Target volume fraction")
    penalty: float = Field(default=3.0, gt=1, description="Penalization factor (p)")
    filter_radius: float = Field(default=1.5, gt=0, description="Sensitivity filter radius")
    max_iterations: int = Field(default=50, gt=0, description="Maximum iterations")
    convergence_tolerance: float = Field(default=0.01, gt=0, description="Change tolerance for convergence")
    youngs_modulus: float = Field(default=1.0, gt=0, description="Young's modulus (normalized)")
    poisson_ratio: float = Field(default=0.3, gt=0, lt=0.5, description="Poisson's ratio")
    min_density: float = Field(default=1e-9, gt=0, description="Minimum element density (avoid singularity)")

    class Config:
        arbitrary_types_allowed = True


class OptimizationResult(BaseModel):
    """Output from topology optimization."""
    converged: bool = Field(..., description="Whether optimization converged")
    num_iterations: int = Field(..., description="Number of iterations performed")
    final_compliance: float = Field(..., description="Final compliance value")
    final_volume_fraction: float = Field(..., description="Final volume fraction")
    compliance_history: list[float] = Field(default_factory=list, description="Compliance at each iteration")
    volume_history: list[float] = Field(default_factory=list, description="Volume fraction at each iteration")

    class Config:
        arbitrary_types_allowed = True
