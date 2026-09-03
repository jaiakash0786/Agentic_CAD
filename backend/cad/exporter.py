"""
CAD Exporter — STEP and STL export utilities.

Exports CadQuery solids to standard engineering formats:
  - STEP: For engineering (editable, exact geometry)
  - STL: For 3D viewing and meshing (triangle mesh)
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadquery as cq
from config import CAD_OUTPUT_DIR


def export_step(solid: cq.Workplane, filename: str) -> Path:
    """
    Export a CadQuery solid to STEP format.

    Args:
        solid: CadQuery Workplane
        filename: Base filename (without extension)

    Returns:
        Path to the exported STEP file
    """
    path = CAD_OUTPUT_DIR / f"{filename}.step"
    cq.exporters.export(solid, str(path))
    return path


def export_stl(
    solid: cq.Workplane,
    filename: str,
    tolerance: float = 0.1,
) -> Path:
    """
    Export a CadQuery solid to STL format.

    Args:
        solid: CadQuery Workplane
        filename: Base filename (without extension)
        tolerance: Mesh tolerance (lower = finer mesh, larger file)

    Returns:
        Path to the exported STL file
    """
    path = CAD_OUTPUT_DIR / f"{filename}.stl"
    cq.exporters.export(solid, str(path), exportType="STL", tolerance=tolerance)
    return path


def export_both(
    solid: cq.Workplane,
    filename: str,
) -> tuple[Path, Path]:
    """
    Export to both STEP and STL formats.

    Returns:
        Tuple of (step_path, stl_path)
    """
    step_path = export_step(solid, filename)
    stl_path = export_stl(solid, filename)
    return step_path, stl_path
