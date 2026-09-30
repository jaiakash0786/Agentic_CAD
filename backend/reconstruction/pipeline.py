"""
CAD Reconstruction Pipeline — Phase 7.

Chains:
    1. Load density field + mesh from Phase 6 output
    2. Voxelize density → 3D scalar grid (64³)
    3. Marching cubes → iso-surface at ρ=0.5
    4. Mesh cleaning → largest component, smoothing, fix normals
    5. Export clean STL
    6. Run lightweight validation (volume ratio, watertight check)
"""
import logging
import time
import numpy as np
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

RECON_OUTPUT_DIR = OUTPUT_DIR / "reconstruction"
RECON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Main Entry Point ────────────────────────────────────────────────────────

def run_reconstruction_pipeline(
    topo_result: dict,
    job_id: Optional[str] = None,
    grid_size: int = 64,
    threshold: float = 0.5,
    smooth_iterations: int = 5,
) -> dict:
    """
    Full CAD reconstruction pipeline from SIMP density field.

    Parameters
    ----------
    topo_result  : dict returned by run_topology_pipeline()
    job_id       : unique job ID (auto-generated if None)
    grid_size    : voxel grid resolution (default 64³)
    threshold    : iso-surface density threshold (default 0.5)
    smooth_iterations : Laplacian smoothing passes

    Returns
    -------
    dict with:
        stl_path        : path to clean STL
        n_vertices      : vertex count
        n_faces         : face count
        volume_mm3      : reconstructed volume
        volume_ratio    : reconstructed / original volume
        watertight      : bool
        material_saved  : % material removed vs original
        elapsed_s       : processing time
    """
    if job_id is None:
        import uuid
        job_id = str(uuid.uuid4())[:8]

    output_dir = RECON_OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("CAD Reconstruction Pipeline START  job_id=%s", job_id)
    logger.info("  Grid: %d³  threshold=%.2f  smooth=%d", grid_size, threshold, smooth_iterations)
    logger.info("=" * 60)

    t0 = time.time()

    density  = topo_result["density"]
    elem_ids = topo_result["elem_ids"]
    mesh_data = topo_result["mesh_data"]
    nodes    = mesh_data["nodes"]
    elements = mesh_data["elements"]

    # ── Step 1: Voxelize density field ────────────────────────────────────────
    logger.info("Step 1/4: Voxelizing density field (%d elements → %d³ grid)…",
                len(elem_ids), grid_size)
    from reconstruction.voxelizer import voxelize_density
    voxel_data = voxelize_density(
        nodes=nodes,
        elements=elements,
        density=density,
        elem_ids=elem_ids,
        grid_size=grid_size,
    )
    logger.info("  Grid: min=%.3f  max=%.3f  mean=%.3f",
                voxel_data["grid"].min(), voxel_data["grid"].max(), voxel_data["grid"].mean())

    # ── Step 2: Extract iso-surface via marching cubes ────────────────────────
    logger.info("Step 2/4: Extracting iso-surface (marching cubes, threshold=%.2f)…", threshold)
    from reconstruction.surface_extractor import extract_surface
    surface = extract_surface(voxel_data=voxel_data, threshold=threshold)

    if surface["n_faces"] == 0:
        # Fallback: direct tet surface extraction
        logger.warning("Marching cubes produced 0 faces — using direct element extraction")
        from reconstruction.mesh_cleaner import write_stl_from_elements
        stl_path = output_dir / "optimized_direct.stl"
        result = write_stl_from_elements(
            nodes=nodes, elements=elements,
            density=density, elem_ids=elem_ids,
            output_path=stl_path, threshold=threshold,
        )
        elapsed = time.time() - t0
        return _build_result(result, job_id, topo_result, output_dir, elapsed)

    logger.info("  Surface: %d vertices, %d faces", surface["n_vertices"], surface["n_faces"])

    # ── Step 3: Clean mesh ────────────────────────────────────────────────────
    logger.info("Step 3/4: Cleaning mesh (%d smoothing passes)…", smooth_iterations)
    stl_path = output_dir / "optimized.stl"
    from reconstruction.mesh_cleaner import clean_mesh
    clean_result = clean_mesh(
        surface=surface,
        output_path=stl_path,
        smooth_iterations=smooth_iterations,
    )

    # ── Step 4: Validation metrics ────────────────────────────────────────────
    logger.info("Step 4/4: Computing validation metrics…")
    original_volume = _compute_original_volume(nodes, elements)
    recon_volume    = clean_result.get("volume_mm3") or 0.0

    volume_ratio   = recon_volume / max(original_volume, 1.0)
    material_saved = round(100 * (1.0 - volume_ratio), 1)

    elapsed = time.time() - t0

    logger.info("=" * 60)
    logger.info("CAD Reconstruction COMPLETE")
    logger.info("  STL         : %s", stl_path)
    logger.info("  Vertices    : %d  Faces: %d", clean_result["n_vertices"], clean_result["n_faces"])
    logger.info("  Volume      : %.1f mm³  (original: %.1f mm³)", recon_volume, original_volume)
    logger.info("  Volume ratio: %.3f  (material saved: %.1f%%)", volume_ratio, material_saved)
    logger.info("  Watertight  : %s", clean_result["watertight"])
    logger.info("  Time        : %.1f s", elapsed)
    logger.info("=" * 60)

    return {
        "job_id":          job_id,
        "stl_path":        str(stl_path),
        "n_vertices":      clean_result["n_vertices"],
        "n_faces":         clean_result["n_faces"],
        "volume_mm3":      recon_volume,
        "original_volume_mm3": original_volume,
        "volume_ratio":    volume_ratio,
        "material_saved_pct": material_saved,
        "watertight":      clean_result["watertight"],
        "area_mm2":        clean_result.get("area_mm2", 0.0),
        "bb_size":         clean_result.get("bb_size", [0, 0, 0]),
        "elapsed_s":       elapsed,
        "success":         True,
        "voxel_grid_size": grid_size,
        "threshold":       threshold,
        "smooth_iterations": smooth_iterations,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _compute_original_volume(nodes: dict, elements: dict) -> float:
    """Compute total mesh volume from all C3D4 elements."""
    total = 0.0
    for _, conn in elements.items():
        if len(conn) >= 4:
            p = [np.array(nodes.get(n, (0, 0, 0))) for n in conn[:4]]
            Ve = abs(np.dot(p[1]-p[0], np.cross(p[2]-p[0], p[3]-p[0]))) / 6.0
            total += Ve
    return total


def _build_result(result: dict, job_id: str, topo_result: dict,
                  output_dir: Path, elapsed: float) -> dict:
    """Build output dict from fallback result."""
    original_volume = _compute_original_volume(
        topo_result["mesh_data"]["nodes"],
        topo_result["mesh_data"]["elements"],
    )
    vol  = result.get("volume_mm3") or 0.0
    return {
        "job_id":             job_id,
        "stl_path":           result.get("stl_path", str(output_dir / "optimized.stl")),
        "n_vertices":         result.get("n_vertices", 0),
        "n_faces":            result.get("n_faces", 0),
        "volume_mm3":         vol,
        "original_volume_mm3": original_volume,
        "volume_ratio":       vol / max(original_volume, 1.0),
        "material_saved_pct": round(100 * (1 - vol / max(original_volume, 1.0)), 1),
        "watertight":         result.get("watertight", False),
        "area_mm2":           result.get("area_mm2", 0.0),
        "bb_size":            [0, 0, 0],
        "elapsed_s":          elapsed,
        "success":            result.get("success", False),
        "voxel_grid_size":    0,
        "threshold":          0.5,
        "smooth_iterations":  0,
    }
