from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- AI ANALYSIS ----------------
def analyze(prompt: str):

    mappings = {
        "diabetes": "Insulin receptor pathway modulation",
        "cancer": "Cell cycle apoptosis regulation",
        "alzheimer": "Amyloid aggregation inhibition",
        "virus": "Viral protein binding inhibition",
        "fever": "Immune cytokine regulation"
    }

    target = "General metabolic modulation"
    for k, v in mappings.items():
        if k in prompt.lower():
            target = v

    return {
        "target_pathway": target,
        "strategy": "Structure-based molecular interaction simulation",
        "confidence": round(random.uniform(0.78, 0.95), 2)
    }


# ---------------- DRUG GENERATOR ----------------
def generate_smiles():

    rings = ["c1ccccc1", "c1ccncc1", "c1ccoc1"]
    chains = ["CC", "CCC", "CCO", "CCN"]
    groups = ["O", "N", "C(=O)", "S"]

    return f"{random.choice(rings)}{random.choice(chains)}{random.choice(groups)}{random.choice(chains)}"


def generate_drug():

    return {
        "name": f"DRX-{random.randint(100,999)}",
        "smiles": generate_smiles(),

        "mol3d": {
            "atoms": [
                {"elem": "C", "x": 0, "y": 0, "z": 0},
                {"elem": "C", "x": 1.4, "y": 0, "z": 0},
                {"elem": "O", "x": 2.1, "y": 1.0, "z": 0},
                {"elem": "N", "x": -1.2, "y": 0.5, "z": 0},
                {"elem": "C", "x": -2.2, "y": 0, "z": 0}
            ],
            "bonds": [[0,1],[1,2],[0,3],[3,4]]
        },

        "properties": {
            "logP": round(random.uniform(1.0, 4.5), 2),
            "binding_affinity": round(random.uniform(0.65, 0.95), 2),
            "toxicity": "Low"
        }
    }


# ---------------- VACCINE GENERATOR ----------------
def generate_vaccine():

    pdb = ""
    x = 0

    residues = ["ALA", "GLY", "SER", "VAL", "LYS", "THR"]

    for i in range(18):

        r = random.choice(residues)

        pdb += f"ATOM  {i*3+1:4d}  N   {r} A {i:3d}    {x:.2f} 0.00 0.00\n"
        pdb += f"ATOM  {i*3+2:4d}  CA  {r} A {i:3d}    {x+0.5:.2f} 0.80 0.00\n"
        pdb += f"ATOM  {i*3+3:4d}  C   {r} A {i:3d}    {x+1.0:.2f} 0.00 0.00\n"

        x += 1.2

    return {
        "name": f"VAX-{random.randint(1000,9999)}",
        "pdb": pdb,

        "epitopes": [
            "Surface loop antigen region",
            "Receptor binding domain"
        ],

        "immune_response": {
            "antibody": round(random.uniform(0.75, 0.95), 2),
            "t_cell": round(random.uniform(0.7, 0.92), 2)
        }
    }


# ---------------- API ----------------
class Query(BaseModel):
    prompt: str


@app.post("/generate")
def generate(q: Query):

    p = q.prompt.lower()

    result = {
        "analysis": analyze(p)
    }

    if "vaccine" in p or "virus" in p:
        result["type"] = "vaccine"
        result["result"] = generate_vaccine()
    else:
        result["type"] = "drug"
        result["result"] = generate_drug()

    return result


# RUN:
# uvicorn backend:app --reload
