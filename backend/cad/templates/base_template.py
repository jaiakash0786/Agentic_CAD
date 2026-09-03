"""
Base Template — Abstract base class for all parametric CAD templates.

Each template defines:
  - generate(spec) → CadQuery Workplane (the 3D solid)
  - get_required_dimensions() → list of required dimension fields
  - get_load_face_selector() → CadQuery face selector for load application
  - get_bc_face_selector() → CadQuery face selector for boundary conditions
"""
from abc import ABC, abstractmethod
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cadquery as cq
from models.specification import DesignSpecification


class BaseTemplate(ABC):
    """Abstract base class for parametric CAD component templates."""

    @abstractmethod
    def generate(self, spec: DesignSpecification) -> cq.Workplane:
        """
        Generate the parametric 3D solid from a DesignSpecification.

        Args:
            spec: Validated engineering specification

        Returns:
            CadQuery Workplane containing the solid geometry
        """
        pass

    @abstractmethod
    def get_required_dimensions(self) -> list[str]:
        """Return list of required dimension field names."""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Return human-readable description of this template."""
        pass

    def validate_dimensions(self, spec: DesignSpecification) -> list[str]:
        """
        Check that all required dimensions are present.

        Returns:
            List of missing dimension names (empty if all present)
        """
        missing = []
        for dim_name in self.get_required_dimensions():
            val = getattr(spec.dimensions, dim_name, None)
            if val is None or val <= 0:
                missing.append(dim_name)
        return missing
