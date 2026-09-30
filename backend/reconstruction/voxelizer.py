"""
Voxelizer — converts a C3D4 element density field to a 3D voxel grid.

The density field from SIMP gives one density value per tetrahedron.
For marching cubes we need a regular 3D grid of scalar values.

Strategy:
    1. Get bounding box from all mesh nodes
    2. Create an NxNxN scalar grid (default 64³)
    3. For each voxel centre, use inverse-distance weighting from the
       nearest element centroids to interpolate density
    4. Return the 3D array + grid metadata (origin, spacing)
"""
import logging
import numpy as np
from scipy.spatial import cKDTree

logger = logging.getLogger(__name__)


def voxelize_density(
    nodes: dict,
    elements: dict,
    density: np.ndarray,
    elem_ids: list,
    grid_size: int = 64,
    padding: float = 0.05,
) -> dict:
    """
    Convert element density field to a 3D voxel scalar field.

    Parameters
    ----------
    nodes       : {node_id: (x,y,z)}
    elements    : {elem_id: [n1,n2,n3,n4]}
    density     : np.ndarray (n_elems,) — density per element
    elem_ids    : list of element IDs (same order as density)
    grid_size   : resolution of the voxel grid (default 64)
    padding     : fractional padding around bounding box

    Returns
    -------
    dict with:
        grid        : np.ndarray (grid_size, grid_size, grid_size)
        origin      : np.ndarray (3,) — grid origin in mm
        spacing     : np.ndarray (3,) — voxel size in mm
        grid_size   : int
    """
    # ── Element centroids ────────────────────────────────────────────────────
    eid_to_idx = {eid: i for i, eid in enumerate(elem_ids)}
    centroids  = np.zeros((len(elem_ids), 3))
    for eid in elem_ids:
        conn = elements[eid]
        pts  = [np.array(nodes[n]) for n in conn[:4] if n in nodes]
        if pts:
            centroids[eid_to_idx[eid]] = np.mean(pts, axis=0)

    # ── Bounding box with padding ────────────────────────────────────────────
    all_xyz = np.array(list(nodes.values()))
    bb_min  = all_xyz.min(axis=0)
    bb_max  = all_xyz.max(axis=0)
    extent  = bb_max - bb_min
    pad     = padding * extent
    origin  = bb_min - pad
    end     = bb_max + pad
    spacing = (end - origin) / grid_size

    logger.info(
        "Voxelizing %d elements into %d³ grid | bb=[%.1f,%.1f,%.1f]→[%.1f,%.1f,%.1f] | spacing=%.2f mm",
        len(elem_ids), grid_size,
        bb_min[0], bb_min[1], bb_min[2],
        bb_max[0], bb_max[1], bb_max[2],
        np.min(spacing),
    )

    # ── Build KD-tree on centroids for fast lookup ──────────────────────────
    tree = cKDTree(centroids)

    # ── Fill grid using k-nearest neighbours ────────────────────────────────
    grid = np.zeros((grid_size, grid_size, grid_size), dtype=np.float32)
    k_nn = min(8, len(elem_ids))  # number of nearest neighbours for IDW

    # Vectorised: create all voxel centres at once
    ix = np.arange(grid_size)
    gx, gy, gz = np.meshgrid(ix, ix, ix, indexing='ij')
    vox_centres = np.stack([
        origin[0] + (gx + 0.5) * spacing[0],
        origin[1] + (gy + 0.5) * spacing[1],
        origin[2] + (gz + 0.5) * spacing[2],
    ], axis=-1).reshape(-1, 3)  # (grid_size³, 3)

    # Query k nearest elements for each voxel centre
    dists, idxs = tree.query(vox_centres, k=k_nn, workers=-1)

    # Inverse-distance weighting
    eps = 1e-10
    weights   = 1.0 / (dists + eps)
    weights  /= weights.sum(axis=1, keepdims=True)
    interp    = np.sum(weights * density[idxs], axis=1)

    grid = interp.reshape(grid_size, grid_size, grid_size).astype(np.float32)

    logger.info(
        "Voxel grid: min=%.3f  max=%.3f  mean=%.3f | "
        "solid(>0.5)=%.1f%%",
        grid.min(), grid.max(), grid.mean(),
        100.0 * (grid > 0.5).mean(),
    )

    return {
        "grid":     grid,
        "origin":   origin,
        "spacing":  spacing,
        "grid_size": grid_size,
        "bb_min":   bb_min,
        "bb_max":   bb_max,
    }
