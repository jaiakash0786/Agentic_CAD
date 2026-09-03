"""
Models package - Central data structures for the entire pipeline.
"""
from .specification import (
    ComponentType, LoadDirection, LoadType, BoundaryConditionType,
    OptimizationObjective, Dimensions, Load, BoundaryCondition,
    MeshSettings, OptimizationConfig, ValidationConstraints,
    DesignSpecification
)
from .materials import Material, MaterialLibrary
from .results import FEAResult, OptimizationIteration, DesignHistory, PipelineState, PipelineStage
