# Agentic-CAD

An autonomous, AI-driven engineering design automation platform that translates natural language requirements into validated, manufacturable 3D CAD models, with a pipeline designed for physics simulations and topology optimization.

## 🚀 Overview

**Agentic-CAD** leverages Large Language Models (LLMs) and parametric CAD engines to act as an autonomous mechanical engineer. 

You can input a natural language prompt, such as:
> *"Design an aluminum L-bracket that supports a 5kN downward load with a safety factor of 2"*

The platform will autonomously:
1. **Interpret** the request into strict engineering constraints.
2. **Validate** the physics, material properties, and geometric constraints.
3. **Generate** a parametric 3D CAD model (STEP and STL formats) from scratch.

## ✨ Key Features

- **🗣️ Natural Language Interface:** Converts plain English into structured engineering specifications.
- **🛡️ Automated Validation Engine:** Verifies physics limits (yield stress, displacement) and checks for completeness before generation.
- **⚙️ Parametric Generation:** Autonomously builds 3D models using `CadQuery` without human intervention.
- **🧩 Modular Architecture:** Includes a `Template Registry` making it extremely easy to add new mechanical components (brackets, beams, plates, etc.).
- **⚡ Fast API Backend:** Fully functional REST API backend built with FastAPI.

## 🏗️ Architecture Pipeline

The pipeline is built around a FastAPI backend serving various specialized agents:
- `/api/interpret` → AI Requirement Interpreter
- `/api/validate` → Engineering Spec Validator
- `/api/generate-cad` → Parametric CAD Generator
- `/api/run-fea` → Finite Element Analysis Pipeline (In Progress)
- `/api/optimize` → Topology Optimization (In Progress)

## 🛠️ Tech Stack

- **Backend:** Python, FastAPI, Pydantic
- **AI/LLM:** Groq API (Llama-3.3-70b-versatile)
- **CAD Engine:** CadQuery
- **3D Processing:** Open3D, Trimesh
- **Simulation/Meshing:** Gmsh, SciPy, NumPy

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- CadQuery installed in your virtual environment.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jaiakash0786/Agentic_CAD.git
   cd Agentic_CAD/backend
   ```

2. **Set up Virtual Environment:**
   ```bash
   python -m venv venv
   # Windows: venv\Scripts\activate
   # Linux/Mac: source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the `backend/` directory with your API keys:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   ```

### Running the Platform

To start the FastAPI server:
```bash
python main.py
```
You can view the interactive API documentation and test the endpoints directly by navigating to **http://localhost:8000/docs**.

### Running the Tests

You can run the built-in test scripts to see the AI interpreter and CAD generator in action without starting the server:

```bash
# Test the AI Interpreter and Validator
python test_phase2.py

# Test the Parametric CAD Generator (outputs to output/cad/)
python test_phase3.py
```

## 🤝 Next Phases (Roadmap)
- [ ] Build the Pipeline Orchestrator to link all stages.
- [ ] Implement automated FEA meshing and solving.
- [ ] Implement Topology Optimization algorithms.
- [ ] Create the React + Three.js Frontend.

---
*Developed by Jaiakash*
