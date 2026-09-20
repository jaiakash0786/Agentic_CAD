"""
AI-Driven Engineering Design Automation Platform
=================================================
FastAPI backend serving the complete Agentic CAD pipeline.

Architecture:
    Frontend (React + Three.js)
        ↓ HTTP/WebSocket
    FastAPI Backend
        ├── /api/interpret     → AI Requirement Interpreter
        ├── /api/validate      → Engineering Spec Validator
        ├── /api/generate-cad  → Parametric CAD Generator
        ├── /api/run-fea       → FEA Pipeline
        ├── /api/optimize      → Topology Optimization
        ├── /api/run-pipeline  → Full Closed-Loop Pipeline
        ├── /api/materials     → Material Library
        ├── /api/report        → Report Generation
        └── /ws/pipeline/{id}  → Real-time pipeline updates
"""
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from config import OUTPUT_DIR, CAD_OUTPUT_DIR
from models import (
    DesignSpecification, MaterialLibrary, Material,
    PipelineState, PipelineStage, FEAResult
)

# ─── App Initialization ─────────────────────────────────────

app = FastAPI(
    title="Agentic CAD Platform",
    description="AI-Driven Engineering Design Automation — from natural language to validated CAD",
    version="1.0.0",
)

# CORS: Allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated files (CAD models, reports)
app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")


# ─── Request / Response Models ───────────────────────────────

class InterpretRequest(BaseModel):
    """Natural language engineering requirement."""
    requirement: str = Field(..., description="Natural language requirement text")


class InterpretResponse(BaseModel):
    """AI-interpreted engineering specification."""
    specification: Optional[DesignSpecification] = None
    raw_llm_output: Optional[dict] = None
    success: bool = True
    error: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Validation check result."""
    valid: bool
    checks: list[dict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CADGenerateRequest(BaseModel):
    """Request to generate CAD from specification."""
    specification: DesignSpecification


class CADGenerateResponse(BaseModel):
    """Generated CAD file paths."""
    success: bool = True
    step_file_url: Optional[str] = None
    stl_file_url: Optional[str] = None
    error: Optional[str] = None


class FEARequest(BaseModel):
    """Request to run FEA on a specification."""
    specification: DesignSpecification
    step_file_path: Optional[str] = Field(
        None, description="Path to existing STEP file. If None, CAD is auto-generated."
    )
    job_id: Optional[str] = Field(None, description="Job ID for tracking. Auto-generated if None.")


class FEAResponse(BaseModel):
    """FEA pipeline result."""
    success: bool = True
    job_id: Optional[str] = None
    fea_result: Optional[FEAResult] = None
    constraint_checks: list[dict] = Field(default_factory=list)
    all_constraints_passed: bool = False
    mesh_info: Optional[dict] = None
    solver_info: Optional[dict] = None
    inp_path: Optional[str] = None
    frd_path: Optional[str] = None
    error: Optional[str] = None


class PipelineRequest(BaseModel):
    """Full pipeline request — from NL to final CAD."""
    requirement: Optional[str] = None
    specification: Optional[DesignSpecification] = None


class PipelineResponse(BaseModel):
    """Pipeline execution result."""
    pipeline_id: str
    state: PipelineState


# ─── Health Check ────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Agentic CAD Platform",
        "version": "1.0.0",
        "status": "running",
        "modules": [
            "AI Interpreter", "Spec Validator", "CAD Generator",
            "FEA Engine", "Topology Optimizer", "CAD Reconstructor",
            "Report Generator"
        ]
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ─── Materials API ───────────────────────────────────────────

@app.get("/api/materials", response_model=list[Material])
async def list_materials():
    """Get all available materials from the library."""
    return MaterialLibrary.list_all()


@app.get("/api/materials/{name}", response_model=Material)
async def get_material(name: str):
    """Get a specific material by name."""
    try:
        return MaterialLibrary.get(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── AI Interpreter ─────────────────────────────────────────

@app.post("/api/interpret", response_model=InterpretResponse)
async def interpret_requirement(request: InterpretRequest):
    """
    Convert natural language engineering requirement into structured specification.
    
    Example input: "Design an aluminum L-bracket that supports 5 kN downward,
    fixed at mounting holes, displacement below 0.5 mm, safety factor above 2."
    """
    try:
        from interpreter.parser import parse_requirement
        result = await parse_requirement(request.requirement)
        return result
    except Exception as e:
        return InterpretResponse(success=False, error=str(e))


# ─── Validation ──────────────────────────────────────────────

@app.post("/api/validate", response_model=ValidationResult)
async def validate_specification(spec: DesignSpecification):
    """Validate an engineering specification against physics rules."""
    try:
        from validator.validator import validate_spec
        return validate_spec(spec)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── CAD Generation ──────────────────────────────────────────

@app.post("/api/generate-cad", response_model=CADGenerateResponse)
async def generate_cad(request: CADGenerateRequest):
    """Generate parametric CAD model from specification."""
    try:
        from cad.generator import generate_cad_model
        step_path, stl_path = generate_cad_model(request.specification)
        return CADGenerateResponse(
            step_file_url=f"/files/cad/{Path(step_path).name}",
            stl_file_url=f"/files/cad/{Path(stl_path).name}",
        )
    except Exception as e:
        return CADGenerateResponse(success=False, error=str(e))


# ─── FEA ─────────────────────────────────────────────────────

@app.post("/api/run-fea", response_model=FEAResponse)
async def run_fea(request: FEARequest):
    """
    Run the complete FEA pipeline on a design specification.

    If step_file_path is provided, uses that STEP file.
    Otherwise, generates CAD first via the CAD generator.

    Pipeline:
      1. Generate CAD (if no STEP provided)
      2. Gmsh mesh generation
      3. CalculiX .inp generation
      4. Run solver (CalculiX or Python fallback)
      5. Parse .frd results
      6. Compute FEAResult + constraint checks
    """
    from pathlib import Path as P
    try:
        spec = request.specification
        step_path = None

        # Step A: Get or generate STEP file
        if request.step_file_path:
            step_path = P(request.step_file_path)
            if not step_path.exists():
                return FEAResponse(
                    success=False,
                    error=f"STEP file not found: {request.step_file_path}"
                )
        else:
            # Auto-generate CAD
            from cad.generator import generate_cad_model
            step_path_str, _ = generate_cad_model(spec)
            step_path = P(step_path_str)

        # Step B: Run FEA pipeline synchronously (Gmsh needs main thread)
        from fea.pipeline import run_fea_pipeline
        pipeline_result = run_fea_pipeline(
            spec=spec,
            step_path=step_path,
            job_id=request.job_id,
        )

        # Serialize constraint checks
        checks_serialized = [
            {
                "name": c.name,
                "required_value": c.required_value,
                "actual_value": c.actual_value,
                "passed": c.passed,
                "unit": c.unit,
                "comparison": c.comparison,
            }
            for c in pipeline_result["constraint_checks"]
        ]

        return FEAResponse(
            success=True,
            job_id=pipeline_result["job_id"],
            fea_result=pipeline_result["fea_result"],
            constraint_checks=checks_serialized,
            all_constraints_passed=pipeline_result["all_passed"],
            mesh_info=pipeline_result["mesh_data"],
            solver_info=pipeline_result["solver_info"],
            inp_path=pipeline_result["inp_path"],
            frd_path=pipeline_result.get("frd_path"),
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return FEAResponse(success=False, error=f"{str(e)}\n{tb}")


# ─── Full Pipeline ───────────────────────────────────────────

@app.post("/api/run-pipeline", response_model=PipelineResponse)
async def run_pipeline(request: PipelineRequest):
    """
    Execute the full Agentic CAD pipeline:
    Requirement → Interpret → Validate → CAD → FEA → Optimize → Validate → Report
    """
    pipeline_id = str(uuid.uuid4())[:8]
    try:
        # pyrefly: ignore [missing-import]
        from orchestrator.pipeline import run_full_pipeline
        state = await run_full_pipeline(
            pipeline_id=pipeline_id,
            requirement=request.requirement,
            specification=request.specification,
        )
        return PipelineResponse(pipeline_id=pipeline_id, state=state)
    except Exception as e:
        return PipelineResponse(
            pipeline_id=pipeline_id,
            state=PipelineState(
                pipeline_id=pipeline_id,
                stage=PipelineStage.FAILED,
                error=str(e),
            )
        )


# ─── Pipeline Status ──────────────────────────────────────────────

@app.get("/api/pipeline-status/{pipeline_id}", response_model=PipelineState)
async def get_pipeline_status(pipeline_id: str):
    """Get the current state of a running or completed pipeline."""
    from orchestrator.state_manager import pipeline_state_manager
    state = pipeline_state_manager.get(pipeline_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline '{pipeline_id}' not found."
        )
    return state


@app.get("/api/pipelines")
async def list_pipelines():
    """List all known pipeline IDs and their current stages."""
    from orchestrator.state_manager import pipeline_state_manager
    all_states = pipeline_state_manager.get_all()
    return [
        {
            "pipeline_id": pid,
            "stage": s.stage.value,
            "progress_percent": s.progress_percent,
            "message": s.message,
        }
        for pid, s in all_states.items()
    ]


# ─── WebSocket: Real-time Pipeline Updates ───────────────────────────

@app.websocket("/ws/pipeline/{pipeline_id}")
async def ws_pipeline(websocket: WebSocket, pipeline_id: str):
    """
    WebSocket endpoint for real-time pipeline progress.
    Connect: ws://localhost:8000/ws/pipeline/{pipeline_id}
    Receives JSON at each stage change.
    """
    from orchestrator.state_manager import pipeline_state_manager
    await websocket.accept()

    async def _send(payload: str):
        await websocket.send_text(payload)

    pipeline_state_manager.register_ws(pipeline_id, _send)

    # Send current state immediately on connect
    import json
    state = pipeline_state_manager.get(pipeline_id)
    if state:
        await websocket.send_text(json.dumps({
            "pipeline_id": state.pipeline_id,
            "stage": state.stage.value,
            "progress_percent": state.progress_percent,
            "message": state.message,
        }))

    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        pass
    finally:
        pipeline_state_manager.unregister_ws(pipeline_id, _send)


# ─── File Serving ────────────────────────────────────────────

@app.get("/api/download/{file_type}/{filename}")
async def download_file(file_type: str, filename: str):
    """Download a generated file (cad, mesh, fea, reports)."""
    file_map = {
        "cad": CAD_OUTPUT_DIR,
        "mesh": OUTPUT_DIR / "mesh",
        "fea": OUTPUT_DIR / "fea",
        "reports": OUTPUT_DIR / "reports",
    }
    if file_type not in file_map:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")

    file_path = file_map[file_type] / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return FileResponse(path=str(file_path), filename=filename)


# ─── Run Server ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
