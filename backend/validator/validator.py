"""
Validator Orchestrator — Combines completeness checks and physics rules.

This is the main entry point for the deterministic validation layer:
    AI output → Validator → Valid Engineering Specification

The validator acts as the bridge between probabilistic LLM output
and deterministic engineering systems.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.specification import DesignSpecification
from validator.rules import check_physics_rules
from validator.completeness import check_completeness


def validate_spec(spec: DesignSpecification) -> dict:
    """
    Validate an engineering specification against:
      1. Completeness — are all required parameters present?
      2. Physics rules — are values physically plausible?

    Returns:
        {
            "valid": True/False,
            "checks": [...],   # All rule check results
            "errors": [...],   # Critical failures
            "warnings": [...], # Non-critical notes
        }
    """
    errors = []
    warnings = []

    # ─── Step 1: Completeness Check ──────────────────────────
    completeness = check_completeness(spec)
    if not completeness["complete"]:
        errors.append(
            f"Missing required fields: {', '.join(completeness['missing_fields'])}"
        )
    warnings.extend(completeness.get("warnings", []))

    # ─── Step 2: Physics Rules Check ─────────────────────────
    physics_checks = check_physics_rules(spec)
    for check in physics_checks:
        if not check["passed"]:
            errors.append(f"[{check['name']}] {check['message']}")

    # ─── Combine Results ─────────────────────────────────────
    all_checks = completeness["checklist"] + physics_checks

    return {
        "valid": len(errors) == 0,
        "checks": all_checks,
        "errors": errors,
        "warnings": warnings,
        "completeness": completeness,
    }
