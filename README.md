# Agentic CAD — AI-Powered Structural Design Platform

> *"Describe your part in plain English. Get a validated, optimized 3D CAD model."*

**Agentic CAD** is an autonomous mechanical engineering platform that translates natural language requirements into physics-validated, topology-optimized 3D CAD models — with zero manual CAD work.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue?logo=react)](https://react.dev)
[![Groq](https://img.shields.io/badge/Groq-qwen3.8b-orange)](https://groq.com)

---

## 🎬 How It Works

Type a requirement like:
> *"Design an aluminum L-bracket 150mm long supporting 10kN downward, safety factor ≥ 2"*

The platform autonomously runs a **7-stage pipeline**:

```
Natural Language
      ↓
 AI Interpreter  (Groq LLM → structured JSON spec)
      ↓
   Validator     (physics rules, material limits, geometry checks)
      ↓
 CAD Generator   (CadQuery → STEP + STL files)
      ↓
  FEA Solver     (Gmsh mesh → C3D4 tetrahedral FEA → stress / safety factor)
      ↓
Topo Optimizer   (SIMP algorithm → material removal → mass savings %)
      ↓
  Human Review   (engineer approve / reject → autonomous redesign loop)
```

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🗣️ **Natural Language Input** | Plain English → structured `DesignSpecification` via Groq LLM |
| 🛡️ **Physics Validation** | Yield stress, displacement, safety factor rules checked before generation |
| ⚙️ **Parametric CAD** | CadQuery generates STEP & STL — L-brackets, beams, plates, shafts |
| 🔬 **FEA Solver** | Gmsh tetrahedral mesher + CalculiX-style C3D4 FEA pipeline |
| ⚡ **SIMP Topology** | Iterative density-based material optimization with convergence chart |
| 🔄 **Autonomous Redesign** | Orchestrator retries failed designs automatically |
| 👁️ **3D Viewer** | Real-time STL viewer with Three.js (original + optimized model toggle) |
| 💬 **AI Chat Assistant** | Context-aware chatbot explains FEA results and design decisions |
| 📊 **PDF Reports** | Full engineering report with spec, FEA results, and optimization data |
| ⚙️ **Settings Panel** | Mesh size, volume fraction, safety factor — all configurable |

---

## 🏗️ Architecture

```
d:\finalyear\
├── backend/
│   ├── main.py                   # FastAPI app — all REST endpoints
│   ├── config.py                 # Groq API key, model config
│   ├── models/
│   │   └── specification.py      # Pydantic DesignSpecification schema
│   ├── interpreter/
│   │   ├── llm_client.py         # Groq API wrapper (async, think-tag stripping)
│   │   ├── parser.py             # NL → spec with dimension defaults
│   │   └── prompt_templates.py   # System prompts for Llama/Qwen
│   ├── validator/
│   │   └── validator.py          # Physics rules validation
│   ├── cad/
│   │   └── generator.py          # CadQuery parametric models
│   ├── fea/
│   │   ├── mesher.py             # Gmsh tetrahedral mesher
│   │   ├── solver.py             # C3D4 FEA solver
│   │   ├── inp_generator.py      # CalculiX .inp file generator
│   │   └── result_parser.py      # Stress/displacement extraction
│   ├── optimization/
│   │   └── simp.py               # SIMP topology optimization
│   ├── orchestrator/
│   │   ├── pipeline.py           # 7-stage pipeline orchestrator
│   │   └── design_loop.py        # Autonomous redesign loop
│   ├── reconstruction/
│   │   └── pipeline.py           # Mesh → STEP reconstruction
│   └── report/
│       └── generator.py          # PDF report generation
│
└── frontend/
    ├── src/
    │   ├── App.jsx               # Main app — pipeline state machine
    │   ├── api.js                # Dynamic API client (localStorage URL)
    │   ├── index.css             # Cohere-inspired design system
    │   └── components/
    │       ├── RequirementInput.jsx   # NL prompt input
    │       ├── SpecForm.jsx           # Editable spec fields
    │       ├── PipelineStatus.jsx     # 7-step progress tracker
    │       ├── ModelViewer.jsx        # Three.js STL viewer
    │       ├── ResultsPanel.jsx       # FEA metrics + topo results
    │       ├── HumanReview.jsx        # Approve / reject panel
    │       ├── OptimizationHistory.jsx # Convergence chart
    │       ├── ChatPanel.jsx          # AI assistant chatbot
    │       ├── SettingsModal.jsx      # Config panel
    │       └── TopoMeshView.jsx       # Topology mesh visualization
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI 0.115, Uvicorn |
| **AI / LLM** | Groq API — `qwen/qwen3.8-27b` (reasoning model) |
| **CAD Engine** | CadQuery 2.4 |
| **Meshing** | Gmsh 4.13 |
| **FEA** | SciPy sparse solver (C3D4 tetrahedral) |
| **Optimization** | NumPy SIMP (Solid Isotropic Material with Penalization) |
| **3D Processing** | Open3D, Trimesh, scikit-image |
| **Reports** | ReportLab PDF |
| **Frontend** | React 18, Vite, Three.js (via @react-three/fiber) |
| **Data Viz** | Recharts |
| **Schema** | Pydantic v2 |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- A free [Groq API key](https://console.groq.com)

### 1. Clone

```bash
git clone https://github.com/jaiakash0786/Agentic_CAD.git
cd Agentic_CAD
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Create environment file
echo GROQ_API_KEY=your_key_here > .env
echo GROQ_MODEL=qwen/qwen3.8-27b >> .env
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

### 4. Run

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Backend health check |
| `POST` | `/api/interpret` | NL → DesignSpecification |
| `POST` | `/api/validate` | Validate spec against physics rules |
| `POST` | `/api/generate-cad` | Generate STEP + STL files |
| `POST` | `/api/run-fea` | Run FEA (mesh + solve + parse) |
| `POST` | `/api/optimize` | SIMP topology optimization |
| `POST` | `/api/generate-report` | Generate PDF report |
| `GET` | `/api/materials` | List all available materials |
| `GET` | `/files/{path}` | Serve generated files (STL, STEP, PDF) |

---

## 🎨 UI Design

The frontend is inspired by **[Cohere's enterprise platform](https://cohere.com)** — warm off-white base, deep forest green accents, pill-shaped CTAs, and large rounded dark feature cards.

---

## 📋 Example Prompts

```
"Design an aluminum L-bracket 150mm long, 10kN downward load, safety factor ≥ 2"

"Steel mounting bracket 200mm × 80mm, fixed at base, 5kN horizontal force, SF ≥ 3"

"Aluminum beam 300mm long, 2kN vertical load at midpoint, max deflection 0.5mm"

"Titanium support plate 200×150mm, 20kN compression, safety factor 4"
```

---

## 👥 Developed By

**Jaiakash** — Final Year Project, 2026

---

*Built with ❤️ using FastAPI, React, CadQuery, Groq AI, and lots of coffee.*
