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


# ─── Topology Optimization ────────────────────────────────

class TopologyRequest(BaseModel):
    """Request to run SIMP topology optimization."""
    specification: DesignSpecification
    step_file_path: Optional[str] = Field(None, description="Path to STEP file. Auto-generated if None.")
    job_id: Optional[str] = Field(None, description="Job ID. Auto-generated if None.")
    volume_fraction: float = Field(0.4, ge=0.1, le=0.9, description="Target volume fraction.")
    penalty: float = Field(3.0, ge=1.0, le=5.0, description="SIMP penalty exponent.")
    max_iter: int = Field(40, ge=5, le=100, description="Max optimization iterations.")


class TopologyResponse(BaseModel):
    """SIMP topology optimization result."""
    success: bool = True
    job_id: Optional[str] = None
    converged: bool = False
    iterations: int = 0
    compliance: float = 0.0
    volume_fraction: float = 0.0
    solid_elements: int = 0
    total_elements: int = 0
    material_saved_pct: float = 0.0
    density_path: Optional[str] = None
    stl_path: Optional[str] = None
    csv_path: Optional[str] = None
    history: list[dict] = Field(default_factory=list)
    elapsed_s: float = 0.0
    error: Optional[str] = None


@app.post("/api/optimize", response_model=TopologyResponse)
async def run_optimize(request: TopologyRequest):
    """
    Run SIMP topology optimization on a design specification.
    Removes unnecessary material while maintaining structural integrity.

    Pipeline:
      1. Generate CAD (if no STEP provided)
      2. Gmsh mesh generation
      3. SIMP optimization loop (penalty=3, OC update, sensitivity filter)
      4. Save density field (.npy + CSV)
      5. Generate density-coloured preview STL
    """
    from pathlib import Path as P
    try:
        spec = request.specification
        step_path = None

        if request.step_file_path:
            step_path = P(request.step_file_path)
            if not step_path.exists():
                return TopologyResponse(success=False, error=f"STEP file not found: {request.step_file_path}")
        else:
            from cad.generator import generate_cad_model
            step_str, _ = generate_cad_model(spec)
            step_path = P(step_str)

        from optimization.pipeline import run_topology_pipeline
        result = run_topology_pipeline(
            spec=spec,
            step_path=step_path,
            job_id=request.job_id,
            volume_fraction=request.volume_fraction,
            penalty=request.penalty,
            max_iter=request.max_iter,
        )

        return TopologyResponse(
            success=True,
            job_id=result["job_id"],
            converged=result["converged"],
            iterations=result["iterations"],
            compliance=result["compliance"],
            volume_fraction=result["volume_fraction"],
            solid_elements=result["solid_elements"],
            total_elements=result["total_elements"],
            material_saved_pct=result["material_saved_pct"],
            density_path=result["density_path"],
            stl_path=result["stl_path"],
            csv_path=result["csv_path"],
            history=result["history"],
            elapsed_s=result["elapsed_s"],
        )

    except Exception as e:
        import traceback
        return TopologyResponse(success=False, error=f"{str(e)}\n{traceback.format_exc()}")


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


# ─── Report Generation ──────────────────────────────────────────

class ReportRequest(BaseModel):
    """Request to generate a PDF engineering report."""
    specification: DesignSpecification
    fea_result: Optional[FEAResult] = Field(None, description="FEA results to include")
    topo_result: Optional[dict] = Field(None, description="Topology results dict to include")
    job_id: Optional[str] = Field(None, description="Job ID for filename. Auto-generated if None.")


class ReportResponse(BaseModel):
    """Report generation result."""
    success: bool = True
    report_url: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None


@app.post("/api/report", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """
    Generate a PDF engineering report from specification + FEA + topology results.

    Returns a download URL for the generated PDF.
    """
    import uuid as _uuid
    from config import REPORT_OUTPUT_DIR
    try:
        from report.generator import generate_report as _gen

        job_id   = request.job_id or _uuid.uuid4().hex[:8]
        filename = f"report_{job_id}.pdf"
        out_path = REPORT_OUTPUT_DIR / filename

        spec_dict = request.specification.model_dump()
        fea_dict  = request.fea_result.model_dump() if request.fea_result else None
        topo_dict = request.topo_result or None

        _gen(
            spec_dict=spec_dict,
            fea_dict=fea_dict,
            topo_dict=topo_dict,
            output_path=out_path,
        )

        return ReportResponse(
            success=True,
            report_url=f"/files/reports/{filename}",
            filename=filename,
        )

    except Exception as e:
        import traceback
        return ReportResponse(success=False, error=f"{str(e)}\n{traceback.format_exc()}")



# ─── AI Design Chatbot ──────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str

class ChatRequest(BaseModel):
    """Conversational chat request with optional design context."""
    messages: list[ChatMessage] = Field(..., description="Conversation history")
    specification: Optional[DesignSpecification] = None
    fea_result: Optional[FEAResult] = None
    topo_result: Optional[dict] = None


class ChatResponse(BaseModel):
    reply: str
    success: bool = True
    error: Optional[str] = None


@app.post("/api/chat", response_model=ChatResponse)
async def design_chat(request: ChatRequest):
    """
    AI chatbot that answers questions about the current design results.
    Injects FEA + topology context into the system prompt so the model
    can answer precise engineering questions about THIS specific design.
    """
    try:
        from groq import Groq
        from config import GROQ_API_KEY, GROQ_MODEL

        # ── Build context string from available results ───────────────────
        ctx_parts: list[str] = []

        if request.specification:
            s = request.specification
            ctx_parts.append(
                f"COMPONENT: {s.component} | MATERIAL: {s.material_name} | "
                f"MIN SAFETY FACTOR REQUIRED: {s.constraints.min_safety_factor} | "
                f"MAX DISPLACEMENT ALLOWED: {s.constraints.max_displacement_mm}mm"
            )
            if s.dimensions:
                d = s.dimensions
                ctx_parts.append(
                    f"DIMENSIONS: length={getattr(d,'length','-')}mm, "
                    f"width={getattr(d,'width','-')}mm, "
                    f"height={getattr(d,'height','-')}mm, "
                    f"thickness={getattr(d,'thickness','-')}mm"
                )
            for ld in (s.loads or []):
                ctx_parts.append(f"LOAD: {ld.magnitude}N {ld.direction} at {ld.location}")
            for bc in (s.boundary_conditions or []):
                ctx_parts.append(f"BC: {bc.bc_type} at {bc.location}")

        if request.fea_result:
            f = request.fea_result
            ctx_parts.append(
                f"FEA RESULTS: max_stress={f.max_stress_mpa:.2f}MPa, "
                f"max_displacement={f.max_displacement_mm:.4f}mm, "
                f"safety_factor={f.safety_factor:.3f}, "
                f"yield_strength={f.yield_strength_mpa:.0f}MPa, "
                f"mass={f.mass_kg:.4f}kg, volume={f.volume_mm3:.1f}mm³, "
                f"mesh={f.num_nodes}nodes/{f.num_elements}elements"
            )
            sf = f.safety_factor
            ctx_parts.append(
                f"CONSTRAINT STATUS: SF {'PASS' if sf>=2 else 'FAIL'} (req ≥2.0), "
                f"Displacement {'PASS' if f.max_displacement_mm<1 else 'FAIL'} (req <1mm), "
                f"Stress {'PASS' if f.max_stress_mpa<f.yield_strength_mpa else 'FAIL'}"
            )

        if request.topo_result:
            t = request.topo_result
            ctx_parts.append(
                f"TOPOLOGY OPT: {t.get('iterations',0)} iterations, "
                f"converged={t.get('converged',False)}, "
                f"compliance={t.get('compliance',0):.4f}, "
                f"material_saved={t.get('material_saved_pct',0):.1f}%, "
                f"solid={t.get('solid_elements',0)}/{t.get('total_elements',0)} elements"
            )

        context_block = "\n".join(ctx_parts) if ctx_parts else "No design results available yet."

        system_prompt = f"""You are an expert structural engineering AI assistant embedded in the Agentic CAD platform.
You help engineers understand their FEA and topology optimization results in plain English.

CURRENT DESIGN CONTEXT:
{context_block}

Guidelines:
- Answer concisely and precisely using the numbers from the design context above.
- If asked about safety factor, stress, displacement, or mass — use the exact values above.
- Explain WHY a result is good/bad using engineering principles.
- If the design fails a constraint, explain the physical reason and suggest a fix.
- For topology optimization questions, explain what the compliance/volume fraction means.
- Keep answers to 2-4 sentences unless asked for more detail.
- Do NOT make up numbers not in the context above."""

        client = Groq(api_key=GROQ_API_KEY)
        messages = [{"role": "system", "content": system_prompt}]
        for m in request.messages:
            messages.append({"role": m.role, "content": m.content})

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=512,
        )
        reply = response.choices[0].message.content.strip()
        return ChatResponse(reply=reply)

    except Exception as e:
        import traceback
        err_detail = traceback.format_exc()
        logger.error("Chat endpoint error: %s", err_detail)
        return ChatResponse(
            success=False,
            error=str(e),
            reply=f"Sorry, I ran into an error: {str(e)}"
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
