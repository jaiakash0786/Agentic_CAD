"""
DesignSpecification - The central data structure of the entire system.

Every module reads from this specification:
  - CAD Generator reads dimensions + component type
  - FEA reads material + loads + boundary conditions + mesh settings
  - Optimizer reads optimization config + constraints
  - Validator checks completeness + engineering rules
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


# ─── Enums ───────────────────────────────────────────────────

class ComponentType(str, Enum):
    """Supported parametric CAD component types."""
    L_BRACKET = "l_bracket"
    BEAM = "beam"
    PLATE = "plate"
    MOUNTING_BRACKET = "mounting_bracket"
    SHAFT = "shaft"
    SUPPORT_STRUCTURE = "support_structure"


class LoadDirection(str, Enum):
    """Direction of applied force."""
    POSITIVE_X = "+x"
    NEGATIVE_X = "-x"
    POSITIVE_Y = "+y"
    NEGATIVE_Y = "-y"
    POSITIVE_Z = "+z"
    NEGATIVE_Z = "-z"
    DOWNWARD = "-y"       # Alias for gravity direction
    UPWARD = "+y"


class LoadType(str, Enum):
    """Type of mechanical load."""
    POINT = "point"
    DISTRIBUTED = "distributed"
    PRESSURE = "pressure"


class BoundaryConditionType(str, Enum):
    """Type of support/constraint."""
    FIXED = "fixed"            # All DOFs constrained
    PINNED = "pinned"          # Translation constrained, rotation free
    ROLLER = "roller"          # One translation free
    SIMPLY_SUPPORTED = "simply_supported"


class OptimizationObjective(str, Enum):
    """What to optimize for."""
    MINIMIZE_MASS = "minimize_mass"
    MINIMIZE_COMPLIANCE = "minimize_compliance"
    MAXIMIZE_STIFFNESS = "maximize_stiffness"


# ─── Sub-Models ──────────────────────────────────────────────

class Dimensions(BaseModel):
    """Geometric dimensions for the parametric CAD template."""
    length: float = Field(..., gt=0, description="Length in mm")
    width: float = Field(..., gt=0, description="Width in mm")
    height: Optional[float] = Field(None, gt=0, description="Height in mm (for 3D components)")
    thickness: float = Field(..., gt=0, description="Wall/plate thickness in mm")
    hole_diameter: Optional[float] = Field(None, gt=0, description="Hole diameter in mm")
    hole_spacing: Optional[float] = Field(None, gt=0, description="Spacing between holes in mm")
    fillet_radius: Optional[float] = Field(None, ge=0, description="Fillet radius in mm")

    @model_validator(mode="after")
    def validate_geometry_ratios(self):
        """Ensure geometry is physically reasonable."""
        if self.hole_diameter and self.thickness:
            if self.hole_diameter > self.width * 0.8:
                raise ValueError(
                    f"Hole diameter ({self.hole_diameter}mm) is too large "
                    f"relative to width ({self.width}mm). Max = {self.width * 0.8:.1f}mm"
                )
        if self.fillet_radius and self.fillet_radius > self.thickness:
            raise ValueError(
                f"Fillet radius ({self.fillet_radius}mm) cannot exceed "
                f"thickness ({self.thickness}mm)"
            )
        return self


class Load(BaseModel):
    """A mechanical load applied to the component."""
    magnitude: float = Field(..., gt=0, description="Load magnitude in Newtons (N)")
    direction: LoadDirection = Field(..., description="Direction of the load")
    location: str = Field(..., description="Where the load is applied (e.g., 'end_face', 'top_face', 'center')")
    load_type: LoadType = Field(default=LoadType.DISTRIBUTED, description="Point, distributed, or pressure load")


class BoundaryCondition(BaseModel):
    """A support/constraint on the component."""
    bc_type: BoundaryConditionType = Field(..., description="Type of boundary condition")
    location: str = Field(..., description="Where the BC is applied (e.g., 'holes', 'base_face', 'left_end')")


class MeshSettings(BaseModel):
    """Meshing configuration for FEA."""
    element_size: float = Field(default=3.0, gt=0, description="Target element size in mm")
    element_order: int = Field(default=1, ge=1, le=2, description="Element order (1=linear, 2=quadratic)")
    refinement_regions: Optional[list[str]] = Field(default=None, description="Regions to refine mesh")


class OptimizationConfig(BaseModel):
    """Topology optimization settings."""
    objective: OptimizationObjective = Field(
        default=OptimizationObjective.MINIMIZE_MASS,
        description="What to optimize"
    )
    volume_fraction: float = Field(
        default=0.4, gt=0, lt=1,
        description="Target volume fraction (0.4 = keep 40% of material)"
    )
    max_iterations: int = Field(default=50, gt=0, le=200, description="Max optimization iterations")
    penalty_factor: float = Field(default=3.0, gt=1, description="SIMP penalization exponent")
    filter_radius: float = Field(default=1.5, gt=0, description="Sensitivity filter radius (in elements)")


class ValidationConstraints(BaseModel):
    """Engineering constraints that the final design must satisfy."""
    max_displacement_mm: float = Field(..., gt=0, description="Maximum allowable displacement in mm")
    min_safety_factor: float = Field(..., gt=1, description="Minimum required safety factor")
    max_stress_mpa: Optional[float] = Field(None, gt=0, description="Maximum allowable stress in MPa (auto-calculated from SF if not set)")


# ─── Main Specification ──────────────────────────────────────

class DesignSpecification(BaseModel):
    """
    The central data structure of the entire Agentic CAD system.

    Everything downstream reads from this specification:
        Engineering Spec
              │
     ┌────────┼────────┐
     ↓        ↓        ↓
    CAD      FEA   Optimization
    """
    # Component identification
    component: ComponentType = Field(..., description="Type of mechanical component")

    # Geometry
    dimensions: Dimensions = Field(..., description="Geometric dimensions")

    # Material
    material_name: str = Field(..., description="Material name (must exist in MaterialLibrary)")

    # Loading
    loads: list[Load] = Field(..., min_length=1, description="Applied loads")

    # Constraints
    boundary_conditions: list[BoundaryCondition] = Field(
        ..., min_length=1, description="Support conditions"
    )

    # Mesh
    mesh_settings: MeshSettings = Field(
        default_factory=MeshSettings,
        description="Mesh configuration"
    )

    # Optimization
    optimization: OptimizationConfig = Field(
        default_factory=OptimizationConfig,
        description="Topology optimization settings"
    )

    # Validation targets
    constraints: ValidationConstraints = Field(
        ..., description="Design must satisfy these constraints"
    )

    # Metadata
    description: Optional[str] = Field(None, description="Original natural language requirement")

    class Config:
        json_schema_extra = {
            "example": {
                "component": "l_bracket",
                "dimensions": {
                    "length": 100, "width": 50, "height": 60,
                    "thickness": 8, "hole_diameter": 10,
                    "fillet_radius": 3
                },
                "material_name": "aluminum_6061_t6",
                "loads": [{
                    "magnitude": 5000, "direction": "-y",
                    "location": "end_face", "load_type": "distributed"
                }],
                "boundary_conditions": [{
                    "bc_type": "fixed", "location": "holes"
                }],
                "constraints": {
                    "max_displacement_mm": 0.5,
                    "min_safety_factor": 2.0
                },
                "optimization": {
                    "objective": "minimize_mass",
                    "volume_fraction": 0.4
                },
                "description": "Design an aluminum L-bracket that supports 5 kN downward load"
            }
        }
