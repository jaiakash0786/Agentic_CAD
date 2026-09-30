"""
Topology Optimization Pipeline — Phase 6.

Chains:
    1. Load existing FEA mesh (from Phase 4 .inp) or re-mesh
    2. Run SIMP optimization
    3. Save density field to .npy + export element density CSV
    4. Generate density-coloured STL for preview
    5. Return results dict compatible with Phase 7 (reconstruction)
"""
import logging
import time
import json
import numpy as np
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR
from models.specification import DesignSpecification
from models.results import FEAResult

logger = logging.getLogger(__name__)

TOPO_OUTPUT_DIR = OUTPUT_DIR / "topology"
TOPO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Main Entry Point ────────────────────────────────────────────────────────

def run_topology_pipeline(
    spec: DesignSpecification,
    step_path: Path,
    job_id: Optional[str] = None,
    volume_fraction: float = 0.4,
    penalty: float = 3.0,
    max_iter: int = 40,
    tol: float = 1e-3,
    progress_callback=None,
) -> dict:
    """
    Full topology optimization pipeline.

    Parameters
    ----------
    spec            : DesignSpecification (for loads, BCs, material)
    step_path       : Path to the STEP file (used to generate mesh)
    job_id          : Unique job identifier
    volume_fraction : Target volume fraction (0.4 = keep 40% of material)
    penalty         : SIMP penalty exponent (3 is standard)
    max_iter        : Max iterations (40 is usually enough)
    tol             : Convergence tolerance
    progress_callback : fn(iter, compliance, delta) for UI updates

    Returns
    -------
    dict with density field, convergence info, file paths
    """
    if job_id is None:
        import uuid
        job_id = str(uuid.uuid4())[:8]

    output_dir = TOPO_OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Topology Optimization Pipeline START  job_id=%s", job_id)
    logger.info("  STEP  : %s", step_path)
    logger.info("  VF    : %.2f  penalty=%.1f  max_iter=%d", volume_fraction, penalty, max_iter)
    logger.info("=" * 60)

    t0 = time.time()

    # ── Step 1: Generate mesh ────────────────────────────────────────────────
    logger.info("Step 1/4: Meshing with Gmsh…")
    from fea.mesher import GmshMesher
    from models.specification import LoadDirection

    load_locations = [load.location for load in spec.loads]
    bc_locations   = [bc.location for bc in spec.boundary_conditions]

    mesher = GmshMesher(
        step_path=step_path,
        output_dir=output_dir,
        element_size=spec.mesh_settings.element_size,
        element_order=1,
    )
    mesh_data = mesher.mesh(
        load_locations=load_locations,
        bc_locations=bc_locations,
    )
    logger.info("  Mesh: %d nodes, %d elements", mesh_data["num_nodes"], mesh_data["num_elements"])

    # ── Step 2: Extract material properties ──────────────────────────────────
    from models.materials import MaterialLibrary
    mat = MaterialLibrary.get(spec.material_name)
    E  = mat.youngs_modulus_mpa if mat else 69000.0
    nu = mat.poisson_ratio       if mat else 0.33

    # Build loads list from spec
    loads = _build_loads_from_spec(spec, mesh_data)

    # ── Step 3: Run SIMP ─────────────────────────────────────────────────────
    logger.info("Step 2/4: Running SIMP optimization…")
    from optimization.simp import SIMPOptimizer

    optimizer = SIMPOptimizer(
        nodes=mesh_data["nodes"],
        elements=mesh_data["elements"],
        bc_nodes=mesh_data["bc_nodes"],
        loads=loads,
        E=E,
        nu=nu,
        volume_fraction=volume_fraction,
        penalty=penalty,
        max_iter=max_iter,
        tol=tol,
        progress_callback=progress_callback,
    )
    result = optimizer.optimize()

    density = result["density"]
    logger.info(
        "  SIMP done: %d iters, converged=%s, c=%.4f, vf=%.3f",
        result["iterations"], result["converged"],
        result["compliance"], result["volume_fraction"],
    )

    # ── Step 4: Save outputs ─────────────────────────────────────────────────
    logger.info("Step 3/4: Saving density field…")

    # Save density array
    density_path = output_dir / "density.npy"
    np.save(str(density_path), density)

    # Save element density CSV
    csv_path = output_dir / "element_density.csv"
    elem_ids = result["elem_ids"]
    with open(csv_path, "w") as f:
        f.write("element_id,density\n")
        for eid, rho in zip(elem_ids, density):
            f.write(f"{eid},{rho:.6f}\n")

    # Save convergence history JSON
    hist_path = output_dir / "convergence.json"
    with open(hist_path, "w") as f:
        json.dump(result["history"], f, indent=2)

    # Save mesh data for Phase 7
    mesh_path = output_dir / "mesh_data.npz"
    _save_mesh_data(mesh_path, mesh_data)

    # ── Step 5: Generate density-coloured preview STL ─────────────────────────
    logger.info("Step 4/4: Generating preview STL…")
    stl_path = _generate_density_stl(
        mesh_data=mesh_data,
        density=density,
        output_dir=output_dir,
        threshold=0.5,  # keep elements with ρ > 0.5
    )

    elapsed = time.time() - t0
    solid_elements = int(np.sum(density >= 0.5))

    logger.info("=" * 60)
    logger.info("Topology Optimization COMPLETE")
    logger.info("  Solid elements (ρ≥0.5) : %d / %d  (%.1f%%)",
                solid_elements, len(density), 100 * solid_elements / max(len(density), 1))
    logger.info("  Material saved         : %.1f%%", 100 * (1 - result["volume_fraction"]))
    logger.info("  Total time             : %.1f s", elapsed)
    logger.info("=" * 60)

    return {
        "job_id":          job_id,
        "density":         density,
        "elem_ids":        elem_ids,
        "converged":       result["converged"],
        "iterations":      result["iterations"],
        "compliance":      result["compliance"],
        "volume_fraction": result["volume_fraction"],
        "solid_elements":  solid_elements,
        "total_elements":  len(density),
        "material_saved_pct": round(100 * (1 - result["volume_fraction"]), 1),
        "history":         result["history"],
        "density_path":    str(density_path),
        "csv_path":        str(csv_path),
        "hist_path":       str(hist_path),
        "mesh_path":       str(mesh_path),
        "stl_path":        str(stl_path) if stl_path else None,
        "mesh_data":       mesh_data,
        "elapsed_s":       elapsed,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_loads_from_spec(spec: DesignSpecification, mesh_data: dict) -> list:
    """Convert DesignSpecification loads → [(node_id, dof, force)] list."""
    from models.specification import LoadDirection

    DIR_DOF = {
        LoadDirection.POSITIVE_X: (1, +1.0),
        LoadDirection.NEGATIVE_X: (1, -1.0),
        LoadDirection.POSITIVE_Y: (2, +1.0),
        LoadDirection.NEGATIVE_Y: (2, -1.0),
        LoadDirection.POSITIVE_Z: (3, +1.0),
        LoadDirection.NEGATIVE_Z: (3, -1.0),
    }

    load_node_ids = mesh_data["load_nodes"]
    n_load_nodes  = max(len(load_node_ids), 1)
    loads = []

    for load in spec.loads:
        dof, sign = DIR_DOF.get(load.direction, (2, -1.0))
        force_per_node = sign * load.magnitude / n_load_nodes
        for nid in load_node_ids:
            loads.append((nid, dof, force_per_node))

    return loads


def _save_mesh_data(path: Path, mesh_data: dict) -> None:
    """Save mesh arrays to .npz for Phase 7 reconstruction."""
    nodes    = mesh_data["nodes"]
    elements = mesh_data["elements"]

    node_ids_arr  = np.array(list(nodes.keys()), dtype=np.int32)
    node_xyz_arr  = np.array(list(nodes.values()), dtype=np.float64)
    elem_ids_arr  = np.array(list(elements.keys()), dtype=np.int32)
    elem_conn_arr = np.array(list(elements.values()), dtype=np.int32)

    np.savez_compressed(
        str(path),
        node_ids=node_ids_arr,
        node_xyz=node_xyz_arr,
        elem_ids=elem_ids_arr,
        elem_conn=elem_conn_arr,
    )


def _generate_density_stl(
    mesh_data: dict,
    density: np.ndarray,
    output_dir: Path,
    threshold: float = 0.5,
) -> Optional[Path]:
    """
    Generate a simple STL file containing only elements with ρ >= threshold.
    Each C3D4 tetrahedron is decomposed into 4 triangular faces.
    """
    try:
        stl_path = output_dir / "density_preview.stl"
        nodes    = mesh_data["nodes"]
        elements = mesh_data["elements"]
        elem_ids = sorted(elements.keys())

        # C3D4 face connectivity (4 triangular faces per tet)
        TET_FACES = [(0,1,2), (0,1,3), (1,2,3), (0,2,3)]

        solid_count = 0
        with open(stl_path, "w") as f:
            f.write("solid density_preview\n")
            for i, eid in enumerate(elem_ids):
                if density[i] < threshold:
                    continue
                conn = elements[eid]
                pts  = [np.array(nodes[n]) for n in conn[:4]]
                solid_count += 1
                for face in TET_FACES:
                    v0, v1, v2 = pts[face[0]], pts[face[1]], pts[face[2]]
                    n_ = np.cross(v1 - v0, v2 - v0)
                    norm = np.linalg.norm(n_)
                    n_ = n_ / norm if norm > 1e-12 else np.array([0, 0, 1])
                    f.write(f"  facet normal {n_[0]:.4f} {n_[1]:.4f} {n_[2]:.4f}\n")
                    f.write("    outer loop\n")
                    for v in [v0, v1, v2]:
                        f.write(f"      vertex {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
                    f.write("    endloop\n")
                    f.write("  endfacet\n")
            f.write("endsolid density_preview\n")

        logger.info("  Preview STL: %d solid elements → %s", solid_count, stl_path)
        return stl_path

    except Exception as e:
        logger.warning("Could not write preview STL: %s", e)
        return None
