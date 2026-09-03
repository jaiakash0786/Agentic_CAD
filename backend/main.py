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
from fastapi import FastAPI, HTTPException
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

@app.post("/api/run-fea")
async def run_fea(request: CADGenerateRequest):
    """Run FEA analysis on a specification (generates CAD → mesh → solve)."""
    try:
        from orchestrator.pipeline import run_fea_pipeline
        result = await run_fea_pipeline(request.specification)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Full Pipeline ───────────────────────────────────────────

@app.post("/api/run-pipeline", response_model=PipelineResponse)
async def run_pipeline(request: PipelineRequest):
    """
    Execute the full Agentic CAD pipeline:
    Requirement → Interpret → Validate → CAD → FEA → Optimize → Validate → Report
    """
    pipeline_id = str(uuid.uuid4())[:8]
    try:
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
