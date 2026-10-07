"""
Parser — Orchestrates NL requirement → DesignSpecification.

This is the main entry point for the AI Interpreter module:
    1. Send NL requirement to LLM (via llm_client)
    2. Apply dimension defaults for any null fields the LLM omitted
    3. Try to construct DesignSpecification (Pydantic validates it)
    4. Return parsed spec + any parsing errors
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interpreter.llm_client import LLMClient
from interpreter.prompt_templates import PARAMETER_EXTRACTION_PROMPT
from models.specification import DesignSpecification
from pydantic import ValidationError


# ─── Default dimension fill-in ────────────────────────────────────────────────

# Component-specific sensible defaults when LLM omits required numeric fields
_DIMENSION_DEFAULTS: dict[str, dict] = {
    "l_bracket": {
        "length":    150.0,
        "width":      60.0,
        "height":    100.0,
        "thickness":   8.0,
    },
    "beam": {
        "length":    300.0,
        "width":      40.0,
        "height":     40.0,
        "thickness":   5.0,
    },
    "plate": {
        "length":    200.0,
        "width":    150.0,
        "height":     10.0,
        "thickness":  10.0,
    },
    "mounting_bracket": {
        "length":    100.0,
        "width":      80.0,
        "height":     60.0,
        "thickness":   6.0,
    },
    "shaft": {
        "length":    250.0,
        "width":      30.0,
        "height":     30.0,
        "thickness":  30.0,
    },
    "support_structure": {
        "length":    200.0,
        "width":    100.0,
        "height":    150.0,
        "thickness":  10.0,
    },
}
_DEFAULT_DIMS = {"length": 150.0, "width": 60.0, "height": 100.0, "thickness": 8.0}


def _apply_dimension_defaults(raw_output: dict) -> dict:
    """
    Fill null/missing dimension fields with component-appropriate defaults.

    Reasoning models (like qwen3.8-27b) sometimes return null for dimensions
    the user didn't explicitly state. Pydantic requires width and thickness to
    be non-null, so we supply sensible engineering defaults.
    """
    dims = raw_output.get("dimensions")
    if not isinstance(dims, dict):
        return raw_output

    component = raw_output.get("component", "l_bracket")
    defaults = _DIMENSION_DEFAULTS.get(component, _DEFAULT_DIMS)

    # Only override fields that are explicitly None (not user-provided)
    for field, default_val in defaults.items():
        if dims.get(field) is None:
            dims[field] = default_val

    raw_output["dimensions"] = dims
    return raw_output


# ─── Main entry point ─────────────────────────────────────────────────────────

async def parse_requirement(requirement: str) -> dict:
    """
    Convert a natural language engineering requirement into a
    validated DesignSpecification.

    Args:
        requirement: Natural language text from the engineer

    Returns:
        Dictionary with:
            - specification: DesignSpecification (if successful)
            - raw_llm_output: Raw JSON from LLM
            - success: True/False
            - error: Error message (if any)
            - missing_fields: List of missing required fields
    """
    client = LLMClient()

    # Step 1: Extract parameters via LLM
    raw_output = await client.extract_parameters(
        requirement=requirement,
        system_prompt=PARAMETER_EXTRACTION_PROMPT,
    )

    # Step 2: Fill in defaults for any null dimension fields
    raw_output = _apply_dimension_defaults(raw_output)

    # Step 3: Try to construct DesignSpecification
    try:
        spec = DesignSpecification(**raw_output)
        return {
            "specification": spec,
            "raw_llm_output": raw_output,
            "success": True,
            "error": None,
            "missing_fields": [],
        }
    except ValidationError as e:
        # Extract which fields failed
        missing = []
        errors = []
        for err in e.errors():
            field_path = " > ".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            errors.append(f"{field_path}: {msg}")
            missing.append(field_path)

        return {
            "specification": None,
            "raw_llm_output": raw_output,
            "success": False,
            "error": f"Validation failed: {'; '.join(errors)}",
            "missing_fields": missing,
        }
    except Exception as e:
        return {
            "specification": None,
            "raw_llm_output": raw_output,
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "missing_fields": [],
        }


async def get_clarification(requirement: str, missing_fields: list[str]) -> str:
    """
    Ask the LLM to generate a clarification request for missing parameters.

    Args:
        requirement: Original NL requirement
        missing_fields: List of missing field names

    Returns:
        Human-readable clarification message
    """
    client = LLMClient()
    return await client.ask_clarification(requirement, missing_fields)
