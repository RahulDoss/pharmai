from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os, httpx

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# 🧠 SAFE GEMMA CALL (FIXED)
# -----------------------------
async def ask_gemma(prompt: str):
    url = "https://router.huggingface.co/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "google/gemma-2b-it",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(url, headers=headers, json=payload)
            data = res.json()
        return data["choices"][0]["message"]["content"]
    except:
        return "Explanation unavailable."


# -----------------------------
# 🧠 AI ROUTER (NO KEYWORDS)
# -----------------------------
async def classify_query(q: str):
    prompt = f"""
Classify this query into ONE word only:

- protein (virus, vaccine, disease, infection, biological system)
- molecule (drug, chemical, compound)

Query: {q}

Return only: protein or molecule
"""

    try:
        res = await ask_gemma(prompt)
        res = res.lower()

        if "protein" in res:
            return "protein"
        return "molecule"
    except:
        return "molecule"


# -----------------------------
# 🧬 PDB MAPPING
# -----------------------------
def get_pdb_id(q: str):
    q = q.lower()

    if "nipah" in q:
        return "5Z9J"
    if "covid" in q:
        return "6LU7"
    if "spike" in q:
        return "6VSB"

    return "6LU7"


# -----------------------------
# 🧪 FAKE SMILES SAFE FALLBACK
# -----------------------------
def get_smiles(q: str):
    # simple safe demo mapping (no API crash)
    return {
        "smiles": "CCO",
        "mw": 46,
        "logP": 0.1,
        "tpsa": 20,
        "hbd": 1,
        "hba": 1
    }


# -----------------------------
# 💊 DRUG SCORE
# -----------------------------
def drug_score(p):
    if not p:
        return 0
    score = 0
    if p["mw"] < 500:
        score += 1
    if p["logP"] < 5:
        score += 1
    if p["hbd"] <= 5:
        score += 1
    if p["hba"] <= 10:
        score += 1
    return score


# -----------------------------
# 🚀 MAIN API
# -----------------------------
@app.get("/analyze")
async def analyze(q: str):

    mode = await classify_query(q)

    # ---------------- PROTEIN MODE ----------------
    if mode == "protein":
        return {
            "type": "protein",
            "pdb_id": get_pdb_id(q),
            "input": q,
            "explanation": await ask_gemma(
                f"Explain disease, vaccine and virus mechanism for: {q}"
            )
        }

    # ---------------- MOLECULE MODE ----------------
    data = get_smiles(q)

    return {
        "type": "molecule",
        "input": q,
        "smiles": data["smiles"],
        "candidate": data["smiles"],

        "properties": data,
        "drug_likeness_score": drug_score(data),
        "similarity_score": 1.0,

        "explanation": await ask_gemma(
            f"Explain drug/chemical use and mechanism of: {q}"
        )
    }


# -----------------------------
# 📂 UPLOAD
# -----------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    return {
        "type": "protein",
        "pdb_id": "6LU7",
        "message": "uploaded successfully",
        "preview": content.decode("utf-8", errors="ignore")[:2000],
        "explanation": "File interpreted as biological dataset."
    }
