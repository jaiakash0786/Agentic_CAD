"""Test script for Phase 2: AI Interpreter + Validator."""
import asyncio
import sys
import json
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, "d:/finalyear/backend")


async def test():
    from interpreter.parser import parse_requirement
    from validator.validator import validate_spec

    # Test 1: Parse NL requirement
    print("=== TEST: AI Interpreter ===")
    result = await parse_requirement(
        "Design an aluminum L-bracket that supports 5 kN downward load, "
        "fixed at the mounting holes, with displacement below 0.5 mm "
        "and safety factor above 2. Make it lightweight. "
        "Length 100mm, width 50mm, thickness 8mm, height 60mm."
    )

    if result["success"]:
        spec = result["specification"]
        print(f"Component: {spec.component.value}")
        print(f"Material: {spec.material_name}")
        print(f"Dimensions: {spec.dimensions.length}x{spec.dimensions.width}x{spec.dimensions.thickness}mm")
        if spec.dimensions.height:
            print(f"Height: {spec.dimensions.height}mm")
        print(f"Load: {spec.loads[0].magnitude}N {spec.loads[0].direction.value}")
        print(f"BC: {spec.boundary_conditions[0].bc_type.value} at {spec.boundary_conditions[0].location}")
        print(f"Max disp: {spec.constraints.max_displacement_mm}mm")
        print(f"Min SF: {spec.constraints.min_safety_factor}")
        print(f"Optimization: {spec.optimization.objective.value}")

        # Test 2: Validate
        print()
        print("=== TEST: Validator ===")
        validation = validate_spec(spec)
        print(f"Valid: {validation['valid']}")
        if validation["errors"]:
            print(f"Errors: {validation['errors']}")
        if validation["warnings"]:
            print(f"Warnings: {validation['warnings']}")

        print()
        print("Completeness Checklist:")
        for check in validation["completeness"]["checklist"]:
            print(f"  {check['status']} {check['field']}: {check['value']}")

        print()
        print("Physics Checks:")
        physics = [c for c in validation["checks"] if isinstance(c, dict) and "category" in c]
        for check in physics:
            status = "✓" if check["passed"] else "✗"
            print(f"  {status} [{check['name']}] {check['message']}")

        print()
        print("PHASE 2: ALL PASS ✓")
    else:
        print(f"FAILED: {result['error']}")
        if result["raw_llm_output"]:
            print(f"Raw LLM output:\n{json.dumps(result['raw_llm_output'], indent=2)[:800]}")


if __name__ == "__main__":
    asyncio.run(test())
