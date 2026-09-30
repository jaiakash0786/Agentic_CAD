"""
SIMP Topology Optimization Solver — Phase 6
============================================
Implements the Solid Isotropic Material with Penalization (SIMP) method
for 3D structural topology optimization on C3D4 tetrahedral meshes.

Algorithm (Sigmund 2001, extended to 3D):
    1. Initialize density field  ρ_e = V_frac  for all elements
    2. LOOP until convergence:
       a. Assemble penalized stiffness  K(ρ) = Σ ρ_e^p × K0_e
       b. Solve  K · u = F
       c. Compute sensitivity  ∂c/∂ρ_e = -p × ρ_e^(p-1) × u_e^T K0_e u_e
       d. Apply sensitivity filter (removes checkerboard patterns)
       e. OC density update (bisection on Lagrange multiplier λ)
       f. Convergence check  ||Δρ||∞ < tol
    3. Return density field + convergence history

Reference:
    Sigmund, O. (2001). A 99 line topology optimization code written
    in Matlab. Structural and Multidisciplinary Optimization, 21(2).
"""
import logging
import time
import numpy as np
from scipy.sparse import lil_matrix, csr_matrix
from scipy.sparse.linalg import spsolve
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SIMPOptimizer:
    """
    3D SIMP topology optimizer for C3D4 tetrahedral meshes.

    Parameters
    ----------
    nodes       : dict {node_id: (x,y,z)}
    elements    : dict {elem_id: [n1,n2,n3,n4]}
    bc_nodes    : set of node ids with zero displacement
    loads       : list of (node_id, dof [1-3], force_value)
    E           : Young's modulus (MPa)
    nu          : Poisson's ratio
    volume_fraction : target volume fraction (0.3 = keep 30% of material)
    penalty     : SIMP penalty exponent p (default 3)
    r_min       : filter radius in mm (default = 1.5× average element size)
    max_iter    : maximum optimization iterations
    tol         : convergence tolerance on density change
    rho_min     : minimum density (avoids singularity, default 1e-3)
    """

    def __init__(
        self,
        nodes: dict,
        elements: dict,
        bc_nodes: set,
        loads: list,
        E: float,
        nu: float,
        volume_fraction: float = 0.4,
        penalty: float = 3.0,
        r_min: Optional[float] = None,
        max_iter: int = 40,
        tol: float = 1e-3,
        rho_min: float = 1e-3,
        progress_callback=None,
    ):
        self.nodes    = nodes
        self.elements = elements
        self.bc_nodes = bc_nodes
        self.loads    = loads
        self.E        = E
        self.nu       = nu
        self.vf       = volume_fraction
        self.p        = penalty
        self.max_iter = max_iter
        self.tol      = tol
        self.rho_min  = rho_min
        self.callback = progress_callback  # fn(iter, compliance, density_change)

        # Build ordered node/element lists
        self.node_ids = sorted(nodes.keys())
        self.elem_ids = sorted(elements.keys())
        self.n_nodes  = len(self.node_ids)
        self.n_elems  = len(self.elem_ids)
        self.n_dof    = self.n_nodes * 3
        self.id_map   = {nid: i for i, nid in enumerate(self.node_ids)}
        self.eid_map  = {eid: i for i, eid in enumerate(self.elem_ids)}

        # Auto r_min = 1.5× average edge length
        if r_min is None:
            vols = []
            for eid in self.elem_ids:
                conn = elements[eid]
                p_ = [np.array(nodes[n]) for n in conn[:4]]
                Ve = abs(np.dot(p_[1]-p_[0], np.cross(p_[2]-p_[0], p_[3]-p_[0]))) / 6.0
                vols.append(Ve)
            avg_edge = float(np.mean(vols)) ** (1 / 3)
            self.r_min = 1.5 * avg_edge
        else:
            self.r_min = r_min

        logger.info(
            "SIMPOptimizer: %d nodes, %d elements, vf=%.2f, p=%.1f, "
            "r_min=%.2f mm, max_iter=%d",
            self.n_nodes, self.n_elems, self.vf, self.p, self.r_min, self.max_iter,
        )

        # Precomputed data (filled by _precompute)
        self._K0e: list[np.ndarray] = []        # element stiffness at ρ=1
        self._Ve:  np.ndarray = np.zeros(self.n_elems)   # element volumes
        self._dofs: list[list[int]] = []        # element DOF indices
        self._centroids: np.ndarray = np.zeros((self.n_elems, 3))
        self._filter_W: list[np.ndarray] = []  # filter weights per element
        self._filter_idx: list[np.ndarray] = []  # neighbour indices

        # Convergence history
        self.history: list[dict] = []

    # ─── Public API ──────────────────────────────────────────────────────────

    def optimize(self) -> dict:
        """
        Run the full SIMP optimization loop.

        Returns
        -------
        dict with keys:
            density         : np.ndarray (n_elems,) — final density field [0,1]
            compliance      : float — final compliance (strain energy)
            volume_fraction : float — actual final volume fraction
            converged       : bool
            iterations      : int
            history         : list of per-iteration metrics
            elem_ids        : list of element IDs (same order as density)
        """
        t_start = time.time()
        logger.info("SIMP: Precomputing element matrices and filter…")
        self._precompute()

        # Initialise density field uniformly at target volume fraction
        rho = np.full(self.n_elems, self.vf)

        # Force vector (constant throughout)
        F = self._build_force_vector()

        compliance = 0.0
        converged  = False

        logger.info("SIMP: Starting optimization loop…")
        for it in range(1, self.max_iter + 1):
            t_iter = time.time()

            # ── Step 1: Assemble K with penalized density ──────────────────
            K = self._assemble_K(rho)

            # ── Step 2: Apply BCs and solve ────────────────────────────────
            K, F_bc = self._apply_bc(K, F)
            try:
                U = spsolve(K.tocsr(), F_bc)
            except Exception as ex:
                logger.error("SIMP sparse solve failed: %s", ex)
                break

            # ── Step 3: Compute compliance c = F^T u ──────────────────────
            compliance = float(F_bc @ U)

            # ── Step 4: Sensitivity  ∂c/∂ρ_e ──────────────────────────────
            dc = self._sensitivity(rho, U)

            # ── Step 5: Sensitivity filter ────────────────────────────────
            dc_filt = self._filter_sensitivity(dc, rho)

            # ── Step 6: OC update ─────────────────────────────────────────
            rho_new = self._oc_update(rho, dc_filt)

            # ── Step 7: Convergence check ─────────────────────────────────
            delta = float(np.max(np.abs(rho_new - rho)))
            actual_vf = float(np.mean(rho_new))

            iter_info = {
                "iteration":     it,
                "compliance":    compliance,
                "delta":         delta,
                "volume_fraction": actual_vf,
                "time_s":        round(time.time() - t_iter, 2),
            }
            self.history.append(iter_info)

            logger.info(
                "SIMP iter %3d | c=%.4f | Δρ=%.6f | vf=%.3f | %.1fs",
                it, compliance, delta, actual_vf, iter_info["time_s"],
            )

            if self.callback:
                try:
                    self.callback(it, compliance, delta)
                except Exception:
                    pass

            rho = rho_new

            if delta < self.tol and it > 5:
                logger.info("SIMP: Converged at iteration %d (Δρ=%.2e < tol=%.2e)", it, delta, self.tol)
                converged = True
                break

        elapsed = time.time() - t_start
        logger.info(
            "SIMP done: %d iters, %.1fs total | c=%.4f | vf=%.3f | converged=%s",
            len(self.history), elapsed, compliance, float(np.mean(rho)), converged,
        )

        return {
            "density":         rho,
            "compliance":      compliance,
            "volume_fraction": float(np.mean(rho)),
            "converged":       converged,
            "iterations":      len(self.history),
            "history":         self.history,
            "elem_ids":        self.elem_ids,
            "r_min":           self.r_min,
            "penalty":         self.p,
            "elapsed_s":       elapsed,
        }

    # ─── Precomputation ───────────────────────────────────────────────────────

    def _precompute(self):
        """Precompute K0_e, DOF indices, centroids, and filter weights."""
        D = self._D_matrix()

        for i, eid in enumerate(self.elem_ids):
            conn = self.elements[eid]
            n1, n2, n3, n4 = conn[0], conn[1], conn[2], conn[3]
            p = [np.array(self.nodes[n]) for n in [n1, n2, n3, n4]]

            # Volume
            Ve = abs(np.dot(p[1]-p[0], np.cross(p[2]-p[0], p[3]-p[0]))) / 6.0
            self._Ve[i] = Ve

            # Centroid
            self._centroids[i] = np.mean(p, axis=0)

            # B matrix and K0_e
            B = self._B_matrix(p)
            K0e = Ve * (B.T @ D @ B)
            self._K0e.append(K0e)

            # DOF indices
            i1 = self.id_map[n1]; i2 = self.id_map[n2]
            i3 = self.id_map[n3]; i4 = self.id_map[n4]
            dofs = [3*i1, 3*i1+1, 3*i1+2,
                    3*i2, 3*i2+1, 3*i2+2,
                    3*i3, 3*i3+1, 3*i3+2,
                    3*i4, 3*i4+1, 3*i4+2]
            self._dofs.append(dofs)

        # Build filter weights using centroid distances
        logger.info("SIMP: Building sensitivity filter (r_min=%.2f mm)…", self.r_min)
        for i in range(self.n_elems):
            ci = self._centroids[i]
            dists = np.linalg.norm(self._centroids - ci, axis=1)
            mask  = dists <= self.r_min
            idx   = np.where(mask)[0]
            w     = self.r_min - dists[idx]
            self._filter_idx.append(idx)
            self._filter_W.append(w)

        logger.info("SIMP: Precompute done — avg neighbours per element: %.1f",
                    np.mean([len(idx) for idx in self._filter_idx]))

    # ─── FEA assembly ────────────────────────────────────────────────────────

    def _assemble_K(self, rho: np.ndarray) -> lil_matrix:
        """Assemble global stiffness matrix with SIMP penalty."""
        K = lil_matrix((self.n_dof, self.n_dof))
        for i in range(self.n_elems):
            Ke = (self.rho_min + (1 - self.rho_min) * rho[i] ** self.p) * self._K0e[i]
            dofs = self._dofs[i]
            for r, dr in enumerate(dofs):
                for c, dc in enumerate(dofs):
                    K[dr, dc] += Ke[r, c]
        return K

    def _build_force_vector(self) -> np.ndarray:
        F = np.zeros(self.n_dof)
        for nid, dof, force in self.loads:
            if nid in self.id_map:
                F[3 * self.id_map[nid] + dof - 1] += force
        return F

    def _apply_bc(self, K: lil_matrix, F: np.ndarray):
        """Apply fixed BCs via penalty method."""
        PENALTY = self.E * 1e12
        K = K.tolil()
        F_bc = F.copy()
        for nid in self.bc_nodes:
            if nid in self.id_map:
                i = self.id_map[nid]
                for d in range(3):
                    K[3*i+d, 3*i+d] += PENALTY
        return K.tocsr(), F_bc

    # ─── Sensitivity ─────────────────────────────────────────────────────────

    def _sensitivity(self, rho: np.ndarray, U: np.ndarray) -> np.ndarray:
        """
        Compute compliance sensitivity ∂c/∂ρ_e for each element.
        ∂c/∂ρ_e = -p × ρ_e^(p-1) × u_e^T × K0_e × u_e
        """
        dc = np.zeros(self.n_elems)
        U3 = U.reshape(-1, 3)
        for i in range(self.n_elems):
            dofs = self._dofs[i]
            ue = np.array([U[d] for d in dofs])
            strain_energy = float(ue @ self._K0e[i] @ ue)
            dc[i] = -self.p * rho[i] ** (self.p - 1) * strain_energy
        return dc

    def _filter_sensitivity(self, dc: np.ndarray, rho: np.ndarray) -> np.ndarray:
        """
        Apply sensitivity filter to remove checkerboard patterns.
        ĝ_e = Σ_j(H_ej × ρ_j × g_j) / (ρ_e × Σ_j H_ej)
        """
        dc_filt = np.zeros_like(dc)
        for i in range(self.n_elems):
            idx = self._filter_idx[i]
            W   = self._filter_W[i]
            num = np.sum(W * rho[idx] * dc[idx])
            den = rho[i] * np.sum(W)
            dc_filt[i] = num / max(den, 1e-15)
        return dc_filt

    # ─── Optimality Criteria Update ──────────────────────────────────────────

    def _oc_update(
        self,
        rho: np.ndarray,
        dc: np.ndarray,
        move: float = 0.2,
        eta: float = 0.5,
    ) -> np.ndarray:
        """
        Optimality Criteria (OC) update rule with bisection on λ.

        ρ_new = clip( ρ_e × (B_e / λ)^η , [ρ_e-move, ρ_e+move] ∩ [ρ_min, 1] )
        B_e   = -∂c/∂ρ_e  (always positive for compliance minimisation)
        λ found by bisection to satisfy: Σ V_e × ρ_e = V_target

        Key fix: lam bounds are initialised from actual B_e magnitudes
        (following Sigmund 2001). Using fixed (1e-20, 1e20) with linear
        bisection fails because it needs ~68 steps to reach typical B_e≈0.01.
        """
        V_target = self.vf * np.sum(self._Ve)

        # B_e = −sensitivity (positive for compliance minimisation)
        Be = np.maximum(-dc, 1e-20)

        def _new_rho(lam: float) -> np.ndarray:
            if lam <= 0:
                return np.clip(rho + move, self.rho_min, 1.0)
            rho_trial = rho * (Be / lam) ** eta
            rho_trial = np.minimum(rho_trial, rho + move)
            rho_trial = np.maximum(rho_trial, rho - move)
            rho_trial = np.clip(rho_trial, self.rho_min, 1.0)
            return rho_trial

        # ── Adaptive initial bounds (critical for convergence) ────────────
        # lam_lo = 0  → all densities hit upper bound (rho + move) → vol > target
        # lam_hi = max(Be)/rho_min → (Be/lam)^0.5 ≤ sqrt(rho_min) → all hit lower bound
        lam_lo = 0.0
        lam_hi = float(np.max(Be)) / self.rho_min  # brackets the feasible interval

        # Verify that the bracket is valid
        if np.dot(self._Ve, _new_rho(lam_hi)) > V_target:
            lam_hi *= 10  # expand if needed

        # ── Bisection (100 iters → precision ≈ lam_hi / 2^100) ───────────
        for _ in range(100):
            lam_mid = 0.5 * (lam_lo + lam_hi)
            rho_new = _new_rho(lam_mid)
            if np.dot(self._Ve, rho_new) > V_target:
                lam_lo = lam_mid
            else:
                lam_hi = lam_mid
            if (lam_hi - lam_lo) < 1e-12 * lam_hi:
                break

        return _new_rho(0.5 * (lam_lo + lam_hi))


    # ─── Element matrices (reuse from fea.solver) ────────────────────────────

    def _D_matrix(self) -> np.ndarray:
        E, nu = self.E, self.nu
        c = E / ((1 + nu) * (1 - 2 * nu))
        a = c * (1 - nu); b = c * nu; g = c * (1 - 2 * nu) / 2
        return np.array([
            [a, b, b, 0, 0, 0],
            [b, a, b, 0, 0, 0],
            [b, b, a, 0, 0, 0],
            [0, 0, 0, g, 0, 0],
            [0, 0, 0, 0, g, 0],
            [0, 0, 0, 0, 0, g],
        ])

    @staticmethod
    def _B_matrix(p: list) -> np.ndarray:
        J = np.array([p[1]-p[0], p[2]-p[0], p[3]-p[0]], dtype=float)
        if abs(np.linalg.det(J)) < 1e-15:
            return np.zeros((6, 12))
        Jinv = np.linalg.inv(J)
        dN_dxi = np.array([[-1,-1,-1],[1,0,0],[0,1,0],[0,0,1]], dtype=float)
        dN_dx  = dN_dxi @ Jinv
        B = np.zeros((6, 12))
        for i in range(4):
            dx, dy, dz = dN_dx[i]; c = 3 * i
            B[0,c]=dx; B[1,c+1]=dy; B[2,c+2]=dz
            B[3,c]=dy; B[3,c+1]=dx
            B[4,c+1]=dz; B[4,c+2]=dy
            B[5,c]=dz; B[5,c+2]=dx
        return B
