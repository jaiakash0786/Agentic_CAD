"""
Mesh Cleaner — post-processing of raw marching cubes output.

Steps:
    1. Remove degenerate triangles (zero area)
    2. Keep only the largest connected component (removes floating debris)
    3. Fill small holes
    4. Laplacian smoothing (reduces staircase artifacts from voxelisation)
    5. Save as clean ASCII STL

Uses trimesh (already in requirements.txt).
"""
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_mesh(
    surface: dict,
    output_path: Path,
    smooth_iterations: int = 5,
    min_component_ratio: float = 0.1,
) -> dict:
    """
    Clean and export the extracted surface mesh.

    Parameters
    ----------
    surface              : dict from surface_extractor.extract_surface()
    output_path          : Path to write the final .stl
    smooth_iterations    : Laplacian smoothing passes (0 = no smoothing)
    min_component_ratio  : ignore components < this fraction of largest

    Returns
    -------
    dict with mesh metrics and output path
    """
    import trimesh

    verts = surface["vertices"]
    faces = surface["faces"]

    if len(verts) == 0 or len(faces) == 0:
        logger.error("Empty surface — cannot clean mesh")
        return {"success": False, "error": "Empty surface mesh"}

    logger.info("Cleaning mesh: %d vertices, %d faces", len(verts), len(faces))

    # ── Create trimesh object (process=True auto-cleans degenerates) ─────────
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    mesh.remove_unreferenced_vertices()
    logger.info("  After processing: %d vertices, %d faces", len(mesh.vertices), len(mesh.faces))

    # ── Keep largest connected component ─────────────────────────────────────
    components = mesh.split(only_watertight=False)
    if len(components) > 1:
        sizes = [len(c.faces) for c in components]
        max_size = max(sizes)
        kept = [c for c in components if len(c.faces) >= min_component_ratio * max_size]
        mesh = trimesh.util.concatenate(kept)
        logger.info(
            "  Components: %d total, kept %d (min_ratio=%.1f)",
            len(components), len(kept), min_component_ratio,
        )

    # ── Laplacian smoothing ──────────────────────────────────────────────────
    if smooth_iterations > 0:
        trimesh.smoothing.filter_laplacian(mesh, iterations=smooth_iterations)
        logger.info("  Applied %d Laplacian smoothing passes", smooth_iterations)

    # ── Repair: fill open holes (marching cubes leaves open boundaries) ──────
    try:
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fill_holes(mesh)
    except Exception as ex:
        logger.debug("fill_holes failed (non-critical): %s", ex)

    # ── Fix normals ───────────────────────────────────────────────────────────
    mesh.fix_normals()

    # ── Metrics ──────────────────────────────────────────────────────────────
    watertight = mesh.is_watertight
    if watertight:
        volume = abs(float(mesh.volume))
    else:
        # Use convex hull volume as conservative estimate
        try:
            volume = abs(float(mesh.convex_hull.volume))
        except Exception:
            volume = 0.0
    area     = float(mesh.area)
    bounds   = mesh.bounds
    bb_size  = bounds[1] - bounds[0]

    logger.info(
        "  Clean mesh: %d vertices, %d faces | watertight=%s | "
        "volume=%.1f mm³ | area=%.1f mm²",
        len(mesh.vertices), len(mesh.faces),
        watertight, volume or 0, area,
    )

    # ── Export STL ────────────────────────────────────────────────────────────
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output_path))
    logger.info("  Exported: %s", output_path)

    return {
        "success":     True,
        "stl_path":    str(output_path),
        "n_vertices":  len(mesh.vertices),
        "n_faces":     len(mesh.faces),
        "volume_mm3":  volume,
        "area_mm2":    area,
        "watertight":  watertight,
        "bb_size":     bb_size.tolist(),
        "mesh":        mesh,
    }


def write_stl_from_elements(
    nodes: dict,
    elements: dict,
    density: np.ndarray,
    elem_ids: list,
    output_path: Path,
    threshold: float = 0.5,
) -> dict:
    """
    Simpler alternative: directly extract surface triangles from solid tet elements.
    Used as a fallback if marching cubes produces degenerate geometry.

    For each solid tet, emit faces not shared with another solid tet.
    """
    import trimesh

    eid_to_idx  = {eid: i for i, eid in enumerate(elem_ids)}
    solid_eids  = {eid for eid, (i) in zip(elem_ids, range(len(elem_ids)))
                   if density[eid_to_idx[eid]] >= threshold}

    # Build element adjacency via shared faces
    face_to_elems: dict[tuple, list] = {}
    TET_FACES = [(0,1,2), (0,1,3), (1,2,3), (0,2,3)]

    for eid in solid_eids:
        conn = elements[eid]
        for tri in TET_FACES:
            key = tuple(sorted([conn[tri[0]], conn[tri[1]], conn[tri[2]]]))
            face_to_elems.setdefault(key, []).append(eid)

    # Surface faces = faces belonging to exactly 1 solid element
    surface_faces = [k for k, v in face_to_elems.items() if len(v) == 1]

    # Build vertex array
    vert_map: dict[int, int] = {}
    vertices: list = []
    faces_arr: list = []

    def get_vert(nid):
        if nid not in vert_map:
            vert_map[nid] = len(vertices)
            vertices.append(list(nodes[nid]))
        return vert_map[nid]

    for tri in surface_faces:
        try:
            f = [get_vert(tri[0]), get_vert(tri[1]), get_vert(tri[2])]
            faces_arr.append(f)
        except KeyError:
            pass

    if not vertices:
        return {"success": False, "error": "No surface faces found"}

    mesh = trimesh.Trimesh(
        vertices=np.array(vertices),
        faces=np.array(faces_arr),
        process=True,
    )
    mesh.fix_normals()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output_path))

    return {
        "success":    True,
        "stl_path":   str(output_path),
        "n_vertices": len(mesh.vertices),
        "n_faces":    len(mesh.faces),
        "volume_mm3": abs(float(mesh.volume)) if mesh.is_watertight else None,
        "area_mm2":   float(mesh.area),
        "watertight": mesh.is_watertight,
        "mesh":       mesh,
    }
