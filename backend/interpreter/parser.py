"""
Parser — Orchestrates NL requirement → DesignSpecification.

This is the main entry point for the AI Interpreter module:
    1. Send NL requirement to LLM (via llm_client)
    2. Parse the JSON response
    3. Construct DesignSpecification from LLM output
    4. Return parsed spec + any parsing errors
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interpreter.llm_client import LLMClient
from interpreter.prompt_templates import PARAMETER_EXTRACTION_PROMPT
from models.specification import DesignSpecification
from pydantic import ValidationError


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

    # Step 2: Try to construct DesignSpecification
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
            field_path = " → ".join(str(loc) for loc in err["loc"])
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
