"""
CalculiX Result Parser.

Reads raw CalculiX output files:
    .frd  — full field results (nodal U, S per element)
    .dat  — printed summary tables

Extracts per-node displacement and stress arrays and computes
aggregate values (max von Mises stress, max displacement magnitude).

CalculiX .frd Format Reference
--------------------------------
The .frd (FRD) file uses a fixed-format record structure:
    Record key -1 : nodal result value
    Record key -2 : element result value
    Record key -3 : end of dataset
    Record key -4 : start of a result set (with component count)
    Record key -5 : component header
    Record key 9999 : end of file

We only need to parse the DISP and STRESS datasets.
"""
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ─── Parser ──────────────────────────────────────────────────────────────────

class FRDParser:
    """
    Parses a CalculiX .frd file and a .dat file.

    Usage:
        parser = FRDParser(frd_path, dat_path)
        data   = parser.parse()
        # data["max_displacement_mm"], data["nodal_stress"], etc.
    """

    def __init__(self, frd_path: str | Path, dat_path: str | Path | None = None):
        self.frd_path = Path(frd_path)
        self.dat_path = Path(dat_path) if dat_path else None

    # ─── Public ──────────────────────────────────────────────────────────────

    def parse(self) -> dict[str, Any]:
        """
        Parse .frd (and optionally .dat) and return aggregate result dict.

        Returns
        -------
        dict with:
            nodal_displacement_mm : np.ndarray shape (N,3) — Ux,Uy,Uz per node
            nodal_stress_mpa      : np.ndarray shape (N,6) — Sxx..Szx per node
            nodal_von_mises_mpa   : np.ndarray shape (N,)  — von Mises per node
            max_displacement_mm   : float
            max_stress_mpa        : float (max von Mises)
            max_strain            : float (max_stress / E → computed in analyzer)
            node_ids              : list[int]
        """
        logger.info("Parsing .frd file: %s", self.frd_path)

        # Check if this is a fallback synthetic file
        is_fallback = self._is_python_fallback()

        nodal_disp, nodal_stress, node_ids = self._parse_frd()

        # Compute von Mises stress from stress tensor
        von_mises = _von_mises_from_stress_tensor(nodal_stress)

        max_disp = float(np.max(np.linalg.norm(nodal_disp, axis=1))) if nodal_disp.size else 0.0
        max_vm   = float(np.max(von_mises)) if von_mises.size else 0.0

        # Try to get better values from .dat if available
        if self.dat_path and self.dat_path.exists():
            dat_info = self._parse_dat()
            if dat_info.get("max_displacement_mm") and dat_info["max_displacement_mm"] > 0:
                max_disp = dat_info["max_displacement_mm"]
            if dat_info.get("max_stress_mpa") and dat_info["max_stress_mpa"] > 0:
                max_vm = dat_info["max_stress_mpa"]

        logger.info("Parsed: max_disp=%.4f mm, max_von_mises=%.2f MPa, nodes=%d",
                    max_disp, max_vm, len(node_ids))

        return {
            "nodal_displacement_mm": nodal_disp,
            "nodal_stress_mpa": nodal_stress,
            "nodal_von_mises_mpa": von_mises,
            "max_displacement_mm": max_disp,
            "max_stress_mpa": max_vm,
            "node_ids": node_ids,
            "is_fallback": is_fallback,
        }

    # ─── Private ─────────────────────────────────────────────────────────────

    def _is_python_fallback(self) -> bool:
        """Check if .dat file was written by our Python fallback."""
        if not self.dat_path or not self.dat_path.exists():
            return False
        try:
            content = self.dat_path.read_text()
            return "PYTHON_FALLBACK=TRUE" in content
        except Exception:
            return False

    def _parse_frd(self) -> tuple[np.ndarray, np.ndarray, list[int]]:
        """
        Parse .frd records.
        Returns (nodal_disp, nodal_stress, node_ids).
        """
        node_ids: list[int] = []
        disp_rows: list[list[float]] = []
        stress_rows: list[list[float]] = []

        current_dataset: str | None = None   # "DISP" | "STRESS" | None
        n_components: int = 0

        try:
            with open(self.frd_path, errors="replace") as f:
                for raw in f:
                    line = raw.rstrip("\n")
                    if not line:
                        continue

                    rec = line[:3].strip()

                    # ── Dataset header ───────────────────────────────────────
                    if rec == "-4":
                        header = line.upper()
                        if "DISP" in header or "U " in header or "D1" in header:
                            current_dataset = "DISP"
                        elif "STRESS" in header or "S " in header or "SXX" in header:
                            current_dataset = "STRESS"
                        else:
                            current_dataset = None
                        # Extract component count (field after last integer in header)
                        parts = line.split()
                        for p in reversed(parts):
                            try:
                                n_components = int(p)
                                break
                            except ValueError:
                                pass
                        continue

                    # ── Component labels ─────────────────────────────────────
                    if rec == "-5":
                        continue

                    # ── End of dataset ────────────────────────────────────────
                    if rec == "-3" or line.strip() == "9999":
                        current_dataset = None
                        continue

                    # ── Nodal values ─────────────────────────────────────────
                    if rec == "-1" and current_dataset in ("DISP", "STRESS"):
                        values = _parse_frd_record_line(line)
                        if not values:
                            continue

                        node_id = values[0]
                        data_vals = values[1:]

                        if current_dataset == "DISP":
                            if len(node_ids) == 0 or node_id not in node_ids:
                                node_ids.append(node_id)
                            disp_rows.append(data_vals[:3] if len(data_vals) >= 3 else data_vals + [0.0] * (3 - len(data_vals)))
                        elif current_dataset == "STRESS":
                            stress_rows.append(data_vals[:6] if len(data_vals) >= 6 else data_vals + [0.0] * (6 - len(data_vals)))

        except Exception as e:
            logger.error("Error parsing .frd file: %s", e)

        # Build arrays
        if disp_rows:
            nodal_disp = np.array(disp_rows, dtype=float)
            if not node_ids:
                node_ids = list(range(1, len(disp_rows) + 1))
        else:
            logger.warning(".frd contained no displacement data.")
            nodal_disp = np.zeros((1, 3))
            node_ids = [1]

        if stress_rows:
            nodal_stress = np.array(stress_rows, dtype=float)
            # Pad/trim to match node count
            n = len(node_ids)
            if len(stress_rows) < n:
                pad = np.zeros((n - len(stress_rows), 6))
                nodal_stress = np.vstack([nodal_stress, pad])
            elif len(stress_rows) > n:
                nodal_stress = nodal_stress[:n]
        else:
            logger.warning(".frd contained no stress data.")
            nodal_stress = np.zeros((len(node_ids), 6))

        return nodal_disp, nodal_stress, node_ids

    def _parse_dat(self) -> dict:
        """
        Parse .dat file for summary values.
        Handles both real CalculiX .dat and our synthetic fallback .dat.
        """
        result: dict[str, float] = {}
        if not self.dat_path or not self.dat_path.exists():
            return result

        try:
            text = self.dat_path.read_text(errors="replace")

            # Fallback synthetic format
            m = re.search(r"Max Displacement \(mm\):\s*([\d.Ee+\-]+)", text)
            if m:
                result["max_displacement_mm"] = float(m.group(1))

            m = re.search(r"Max Von Mises Stress \(MPa\):\s*([\d.Ee+\-]+)", text)
            if m:
                result["max_stress_mpa"] = float(m.group(1))

            # Real CalculiX .dat format
            # Displacement summary line: "   MAX U   0.1234E+00"
            for line in text.splitlines():
                upper = line.upper()
                if "MAX" in upper and "U" in upper:
                    nums = re.findall(r"[+-]?\d+\.?\d*[Ee][+-]?\d+|[+-]?\d+\.\d+", line)
                    if nums:
                        result.setdefault("max_displacement_mm", float(nums[0]))
                if "MAX" in upper and ("MISES" in upper or "STRESS" in upper or " S " in upper):
                    nums = re.findall(r"[+-]?\d+\.?\d*[Ee][+-]?\d+|[+-]?\d+\.\d+", line)
                    if nums:
                        result.setdefault("max_stress_mpa", float(nums[0]))

        except Exception as e:
            logger.warning("Could not parse .dat file: %s", e)

        return result


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_frd_record_line(line: str) -> list[float] | None:
    """
    Parse a -1 record line in .frd format.

    Line format (Fortran fixed width):
        ' -1' + node_id(10d) + val1(12.5E) + val2(12.5E) + ...
    or free format with spaces.
    """
    try:
        rest = line[3:]  # skip ' -1'
        # Try fixed-format first
        node_id = int(rest[:10])
        val_str = rest[10:]
        values_raw = [val_str[i : i + 12] for i in range(0, len(val_str), 12)]
        values = [float(v) for v in values_raw if v.strip()]
        return [float(node_id)] + values
    except (ValueError, IndexError):
        pass

    # Fall back to space-separated
    try:
        parts = line.split()
        return [float(p) for p in parts]
    except ValueError:
        return None


def _von_mises_from_stress_tensor(stress: np.ndarray) -> np.ndarray:
    """
    Compute von Mises stress from 6-component stress tensor.

    stress columns: [Sxx, Syy, Szz, Sxy, Syz, Szx]

    σ_vm = sqrt(0.5 * [(Sxx-Syy)² + (Syy-Szz)² + (Szz-Sxx)² + 6(Sxy²+Syz²+Szx²)])
    """
    if stress.shape[1] < 6:
        # Pad with zeros
        pad = np.zeros((stress.shape[0], 6 - stress.shape[1]))
        stress = np.hstack([stress, pad])

    Sxx = stress[:, 0]
    Syy = stress[:, 1]
    Szz = stress[:, 2]
    Sxy = stress[:, 3]
    Syz = stress[:, 4]
    Szx = stress[:, 5]

    vm = np.sqrt(
        0.5 * (
            (Sxx - Syy) ** 2 +
            (Syy - Szz) ** 2 +
            (Szz - Sxx) ** 2 +
            6.0 * (Sxy ** 2 + Syz ** 2 + Szx ** 2)
        )
    )
    return vm
