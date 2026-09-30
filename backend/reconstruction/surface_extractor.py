"""
Surface Extractor — marching cubes iso-surface extraction.

Takes the 3D voxel density grid from voxelizer.py and extracts
the iso-surface at threshold=0.5 using marching cubes.

Falls back to direct face extraction from the tet mesh if
skimage is not available.
"""
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_surface(
    voxel_data: dict,
    threshold: float = 0.5,
    output_path: Path = None,
) -> dict:
    """
    Extract triangulated iso-surface from voxel scalar field.

    Parameters
    ----------
    voxel_data  : dict from voxelizer.voxelize_density()
    threshold   : iso-surface level (0.5 = boundary between solid and void)
    output_path : optional path to write intermediate .stl

    Returns
    -------
    dict with:
        vertices  : np.ndarray (N, 3) in mm
        faces     : np.ndarray (M, 3) — triangle face indices
        normals   : np.ndarray (M, 3)
        n_vertices: int
        n_faces   : int
    """
    grid    = voxel_data["grid"]
    origin  = voxel_data["origin"]
    spacing = voxel_data["spacing"]

    logger.info("Extracting iso-surface at threshold=%.2f…", threshold)

    try:
        from skimage.measure import marching_cubes
        verts, faces, normals, _ = marching_cubes(
            grid,
            level=threshold,
            spacing=tuple(spacing),
            allow_degenerate=False,
        )
        # Shift vertices to world coordinates
        verts = verts + origin
        method = "skimage marching_cubes"

    except ImportError:
        logger.warning("skimage not available — using scipy marching cubes fallback")
        verts, faces, normals = _scipy_marching_cubes(grid, threshold, origin, spacing)
        method = "scipy fallback"

    logger.info(
        "Surface extracted (%s): %d vertices, %d faces",
        method, len(verts), len(faces),
    )

    return {
        "vertices":  verts,
        "faces":     faces,
        "normals":   normals if normals is not None else _compute_normals(verts, faces),
        "n_vertices": len(verts),
        "n_faces":   len(faces),
        "method":    method,
    }


def _compute_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Compute face normals from vertex positions."""
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    n  = np.cross(v1 - v0, v2 - v0)
    mag = np.linalg.norm(n, axis=1, keepdims=True)
    mag = np.where(mag < 1e-10, 1.0, mag)
    return n / mag


def _scipy_marching_cubes(
    grid: np.ndarray,
    threshold: float,
    origin: np.ndarray,
    spacing: np.ndarray,
) -> tuple:
    """
    Simple marching cubes fallback using scipy.
    Uses the dual contouring approach on grid edges.
    """
    from scipy.ndimage import label, binary_fill_holes

    # Binarise grid
    binary = (grid >= threshold).astype(np.uint8)

    # Extract surface triangles from grid boundary faces
    vertices = []
    faces    = []
    vert_map = {}

    def get_vert_idx(vi, vj, vk):
        key = (vi, vj, vk)
        if key not in vert_map:
            vert_map[key] = len(vertices)
            x = origin[0] + vi * spacing[0]
            y = origin[1] + vj * spacing[1]
            z = origin[2] + vk * spacing[2]
            vertices.append([x, y, z])
        return vert_map[key]

    gs = grid.shape[0]
    # Check each voxel face
    for i in range(gs):
        for j in range(gs):
            for k in range(gs):
                if binary[i, j, k] == 0:
                    continue
                # 6 faces of voxel (i,j,k)
                # Only emit face if neighbour is void (surface face)
                faces_def = [
                    (i+1 == gs or binary[i+1,j,k]==0,
                     [(i+1,j,k),(i+1,j+1,k),(i+1,j+1,k+1),(i+1,j,k+1)]),
                    (i == 0 or binary[i-1,j,k]==0,
                     [(i,j,k),(i,j,k+1),(i,j+1,k+1),(i,j+1,k)]),
                    (j+1 == gs or binary[i,j+1,k]==0,
                     [(i,j+1,k),(i,j+1,k+1),(i+1,j+1,k+1),(i+1,j+1,k)]),
                    (j == 0 or binary[i,j-1,k]==0,
                     [(i,j,k),(i+1,j,k),(i+1,j,k+1),(i,j,k+1)]),
                    (k+1 == gs or binary[i,j,k+1]==0,
                     [(i,j,k+1),(i+1,j,k+1),(i+1,j+1,k+1),(i,j+1,k+1)]),
                    (k == 0 or binary[i,j,k-1]==0,
                     [(i,j,k),(i,j+1,k),(i+1,j+1,k),(i+1,j,k)]),
                ]
                for is_surface, quad in faces_def:
                    if is_surface:
                        v0 = get_vert_idx(*quad[0])
                        v1 = get_vert_idx(*quad[1])
                        v2 = get_vert_idx(*quad[2])
                        v3 = get_vert_idx(*quad[3])
                        faces.append([v0, v1, v2])
                        faces.append([v0, v2, v3])

    verts = np.array(vertices, dtype=np.float64) if vertices else np.zeros((0, 3))
    faces_arr = np.array(faces, dtype=np.int32) if faces else np.zeros((0, 3), dtype=np.int32)
    return verts, faces_arr, None
