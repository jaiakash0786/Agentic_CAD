"""
Application configuration loaded from environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv(Path(__file__).parent / ".env")

# ─── API Keys ────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ─── Paths ───────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output")))
CCX_PATH = Path(os.getenv("CCX_PATH", "d:/finalyear/tools/ccx/ccx.exe"))

# Output subdirectories
CAD_OUTPUT_DIR = OUTPUT_DIR / "cad"
MESH_OUTPUT_DIR = OUTPUT_DIR / "mesh"
FEA_OUTPUT_DIR = OUTPUT_DIR / "fea"
OPTIMIZATION_OUTPUT_DIR = OUTPUT_DIR / "optimization"
REPORT_OUTPUT_DIR = OUTPUT_DIR / "reports"

# Ensure all output directories exist
for d in [CAD_OUTPUT_DIR, MESH_OUTPUT_DIR, FEA_OUTPUT_DIR,
          OPTIMIZATION_OUTPUT_DIR, REPORT_OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Defaults ────────────────────────────────────────────────
DEFAULT_MESH_ELEMENT_SIZE = 3.0        # mm
MAX_OPTIMIZATION_ITERATIONS = 50
OPTIMIZATION_CONVERGENCE_TOL = 0.01
MAX_PIPELINE_RETRIES = 10
