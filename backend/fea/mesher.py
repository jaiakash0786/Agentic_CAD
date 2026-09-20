"""
FEA Mesher — Gmsh-based tetrahedral mesh generator.

Workflow:
    1. Import STEP geometry into Gmsh
    2. Define physical groups for load faces and BC faces
    3. Generate 3D tetrahedral mesh (C3D4 / C3D10 elements)
    4. Write node + element data to a dict for inp_generator.py

Face identification strategy:
    - The geometry bounding box is used to identify faces by their
      centroid position (e.g. "bottom_face" → lowest Z centroid).
    - Supported location tokens:
        bottom_face, top_face, left_face, right_face,
        front_face, back_face, end_face, base_face,
        holes (→ cylindrical surfaces), center, all_faces
"""
import logging
import os
import sys
import math
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ─── Location token normaliser ───────────────────────────────────────────────

_LOCATION_ALIASES: dict[str, str] = {
    # gravity / structural
    "bottom": "bottom_face",
    "top": "top_face",
    "left": "left_face",
    "right": "right_face",
    "front": "front_face",
    "back": "back_face",
    "end": "end_face",
    "base": "base_face",
    "rear": "back_face",
    "fixed_end": "bottom_face",
    "free_end": "end_face",
    "downward": "end_face",   # ambiguous, mapped conservatively
    "upper": "top_face",
    "lower": "bottom_face",
}


def _normalise_location(loc: str) -> str:
    """Lower-case and strip, then apply alias map."""
    cleaned = loc.lower().strip().replace(" ", "_")
    return _LOCATION_ALIASES.get(cleaned, cleaned)


# ─── Face classifier ─────────────────────────────────────────────────────────

def _classify_face_by_centroid(
    centroid: tuple[float, float, float],
    bbox_min: tuple[float, float, float],
    bbox_max: tuple[float, float, float],
    tol_fraction: float = 0.10,
) -> list[str]:
    """
    Return a list of face-name tokens that match this surface centroid.

    A centroid is considered "on a face" when it sits within
    `tol_fraction * span` of that face's extreme coordinate.
    """
    cx, cy, cz = centroid
    xmin, ymin, zmin = bbox_min
    xmax, ymax, zmax = bbox_max

    span_x = max(xmax - xmin, 1e-6)
    span_y = max(ymax - ymin, 1e-6)
    span_z = max(zmax - zmin, 1e-6)

    tol_x = tol_fraction * span_x
    tol_y = tol_fraction * span_y
    tol_z = tol_fraction * span_z

    names: list[str] = []

    if abs(cz - zmin) < tol_z:
        names += ["bottom_face", "base_face", "fixed_end"]
    if abs(cz - zmax) < tol_z:
        names += ["top_face"]
    if abs(cy - ymin) < tol_y:
        names += ["front_face"]
    if abs(cy - ymax) < tol_y:
        names += ["back_face"]
    if abs(cx - xmin) < tol_x:
        names += ["left_face"]
    if abs(cx - xmax) < tol_x:
        names += ["right_face", "end_face", "free_end"]

    # middle section → "center" token
    if (
        abs(cx - (xmin + xmax) / 2) < tol_x * 2
        and abs(cy - (ymin + ymax) / 2) < tol_y * 2
    ):
        names += ["center"]

    return names


# ─── Main Mesher ─────────────────────────────────────────────────────────────

class GmshMesher:
    """
    Wraps Gmsh to produce a tetrahedral FEA mesh from a STEP file.

    Parameters
    ----------
    step_path : Path
        Path to the input STEP file.
    output_dir : Path
        Directory where mesh output files will be written.
    element_size : float
        Target global element size in mm (default 3.0 mm).
    element_order : int
        1 = linear C3D4, 2 = quadratic C3D10.
    """

    def __init__(
        self,
        step_path: Path,
        output_dir: Path,
        element_size: float = 3.0,
        element_order: int = 1,
    ):
        self.step_path = Path(step_path)
        self.output_dir = Path(output_dir)
        self.element_size = element_size
        self.element_order = element_order
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ─── Public API ──────────────────────────────────────────────────────────

    def mesh(
        self,
        load_locations: list[str],
        bc_locations: list[str],
    ) -> dict[str, Any]:
        """
        Generate the mesh and return a mesh data dict.

        Returns
        -------
        dict with keys:
            nodes      : dict[int, tuple[float,float,float]]  node_id → (x,y,z) in mm
            elements   : dict[int, list[int]]                 elem_id → [node_ids]
            load_nodes : set[int]                             node IDs on load faces
            bc_nodes   : set[int]                             node IDs on BC faces
            mesh_path  : str                                  path to .inp mesh file
            num_nodes  : int
            num_elements : int
        """
        import gmsh

        stem = self.step_path.stem
        mesh_path = self.output_dir / f"{stem}.inp"

        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)  # suppress console spam
        gmsh.model.add("fea_model")

        try:
            # 1. Import STEP
            logger.info("Loading STEP: %s", self.step_path)
            gmsh.merge(str(self.step_path))
            gmsh.model.occ.synchronize()

            # 2. Get bounding box
            entities = gmsh.model.getEntities(3)  # 3D volumes
            if not entities:
                # Try 2D if no 3D volume (should not happen with valid STEP)
                entities = gmsh.model.getEntities(2)
                logger.warning("No 3D volumes found; falling back to 2D entities.")

            bbox_min_all = [+1e9, +1e9, +1e9]
            bbox_max_all = [-1e9, -1e9, -1e9]
            for dim, tag in entities:
                xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
                bbox_min_all = [min(bbox_min_all[i], v) for i, v in enumerate([xmin, ymin, zmin])]
                bbox_max_all = [max(bbox_max_all[i], v) for i, v in enumerate([xmax, ymax, zmax])]
            bbox_min = tuple(bbox_min_all)
            bbox_max = tuple(bbox_max_all)
            logger.info("Bounding box: min=%s  max=%s", bbox_min, bbox_max)

            # 3. Mesh settings
            gmsh.option.setNumber("Mesh.CharacteristicLengthMin", self.element_size * 0.5)
            gmsh.option.setNumber("Mesh.CharacteristicLengthMax", self.element_size)
            gmsh.option.setNumber("Mesh.ElementOrder", self.element_order)
            gmsh.option.setNumber("Mesh.Algorithm3D", 1)  # Delaunay 3D
            gmsh.option.setNumber("Mesh.Optimize", 1)

            # 4. Generate mesh
            logger.info("Generating 3D mesh (element size=%.1f mm, order=%d)…",
                        self.element_size, self.element_order)
            gmsh.model.mesh.generate(3)
            gmsh.model.mesh.optimize("Netgen")

            # 5. Identify surface faces and tag load / BC nodes
            load_locs_norm = [_normalise_location(l) for l in load_locations]
            bc_locs_norm   = [_normalise_location(l) for l in bc_locations]

            load_surface_tags: list[int] = []
            bc_surface_tags:   list[int] = []

            surfaces = gmsh.model.getEntities(2)
            for _, stag in surfaces:
                # centroid of surface
                xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, stag)
                cx = (xmin + xmax) / 2
                cy = (ymin + ymax) / 2
                cz = (zmin + zmax) / 2
                face_tokens = _classify_face_by_centroid(
                    (cx, cy, cz), bbox_min, bbox_max
                )

                # "holes" token → cylindrical surfaces (aspect ratio check)
                span_x = xmax - xmin
                span_y = ymax - ymin
                span_z = zmax - zmin
                is_cylindrical = (
                    span_x < 0.3 * (bbox_max[0] - bbox_min[0])
                    and span_y < 0.3 * (bbox_max[1] - bbox_min[1])
                )
                if is_cylindrical:
                    face_tokens.append("holes")

                # "all_faces" always matches
                face_tokens.append("all_faces")

                matched_load = any(t in face_tokens for t in load_locs_norm)
                matched_bc   = any(t in face_tokens for t in bc_locs_norm)

                if matched_load:
                    load_surface_tags.append(stag)
                if matched_bc:
                    bc_surface_tags.append(stag)

            # Fallback: if nothing matched, use extreme faces
            if not load_surface_tags:
                logger.warning("No load surfaces matched (%s). Using end_face fallback.", load_locs_norm)
                for _, stag in surfaces:
                    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, stag)
                    cx = (xmin + xmax) / 2
                    if abs(cx - bbox_max[0]) < 0.1 * (bbox_max[0] - bbox_min[0]):
                        load_surface_tags.append(stag)

            if not bc_surface_tags:
                logger.warning("No BC surfaces matched (%s). Using bottom_face fallback.", bc_locs_norm)
                for _, stag in surfaces:
                    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, stag)
                    cz = (zmin + zmax) / 2
                    if abs(cz - bbox_min[2]) < 0.1 * (bbox_max[2] - bbox_min[2]):
                        bc_surface_tags.append(stag)

            logger.info("Load surfaces: %s  |  BC surfaces: %s",
                        load_surface_tags, bc_surface_tags)

            # 6. Physical groups for load and BC
            if load_surface_tags:
                gmsh.model.addPhysicalGroup(2, load_surface_tags, name="LOAD_FACE")
            if bc_surface_tags:
                gmsh.model.addPhysicalGroup(2, bc_surface_tags, name="BC_FACE")

            # Volume group
            vol_tags = [t for _, t in gmsh.model.getEntities(3)]
            if vol_tags:
                gmsh.model.addPhysicalGroup(3, vol_tags, name="SOLID")

            gmsh.model.mesh.renumberNodes()
            gmsh.model.mesh.renumberElements()

            # 7. Extract nodes
            node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
            nodes: dict[int, tuple[float, float, float]] = {}
            for i, ntag in enumerate(node_tags):
                x = node_coords[3 * i]
                y = node_coords[3 * i + 1]
                z = node_coords[3 * i + 2]
                nodes[int(ntag)] = (x, y, z)

            # 8. Extract 3D elements (C3D4 = type 4, C3D10 = type 11)
            elem_types, elem_tags, elem_conn = gmsh.model.mesh.getElements(3)
            elements: dict[int, list[int]] = {}
            for et, etags, econn in zip(elem_types, elem_tags, elem_conn):
                npe = len(econn) // len(etags)  # nodes per element
                for i, etag in enumerate(etags):
                    elements[int(etag)] = [int(econn[i * npe + j]) for j in range(npe)]

            if not elements:
                raise RuntimeError(
                    "Gmsh produced 0 3D elements. Check STEP geometry or increase element size."
                )

            # 9. Extract load / BC node sets from surface tags
            def nodes_on_surfaces(surf_tags: list[int]) -> set[int]:
                nset: set[int] = set()
                for stag in surf_tags:
                    try:
                        ntags, _ = gmsh.model.mesh.getNodes(2, stag)
                        nset.update(int(n) for n in ntags)
                    except Exception:
                        pass
                return nset

            load_nodes = nodes_on_surfaces(load_surface_tags)
            bc_nodes   = nodes_on_surfaces(bc_surface_tags)

            # Fallback: if sets empty, pick nodes near bounding extremes
            if not load_nodes:
                max_x = bbox_max[0]
                tol = self.element_size
                load_nodes = {nid for nid, (x, y, z) in nodes.items() if abs(x - max_x) < tol}

            if not bc_nodes:
                min_z = bbox_min[2]
                tol = self.element_size
                bc_nodes = {nid for nid, (x, y, z) in nodes.items() if abs(z - min_z) < tol}

            logger.info("Mesh: %d nodes, %d elements, %d load nodes, %d BC nodes",
                        len(nodes), len(elements), len(load_nodes), len(bc_nodes))

            # 10. Write Gmsh .inp file (for reference / debugging)
            gmsh.write(str(mesh_path))

            return {
                "nodes": nodes,
                "elements": elements,
                "load_nodes": load_nodes,
                "bc_nodes": bc_nodes,
                "mesh_path": str(mesh_path),
                "num_nodes": len(nodes),
                "num_elements": len(elements),
                "bbox_min": bbox_min,
                "bbox_max": bbox_max,
            }

        finally:
            gmsh.finalize()
