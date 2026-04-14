pip install fastapi uvicorn httpx rdkit-pypi python-dotenv selfies

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

import os, random, httpx
import selfies as sf

from rdkit import Chem
from rdkit.Chem import Descriptors, AllChem, DataStructs

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
# 🧠 LLM (Gemma - HuggingFace)
# -----------------------------
async def ask_gemma(prompt: str):
    url = "https://api-inference.huggingface.co/models/google/gemma-2b-it"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            res = await client.post(url, headers=headers, json={"inputs": prompt})
            data = res.json()

            if isinstance(data, list):
                return data[0].get("generated_text", "")

            return "LLM unavailable"
        except:
            return "LLM error"


# -----------------------------
# 🧪 PubChem → SMILES
# -----------------------------
def get_smiles(name: str):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/IsomericSMILES/JSON"
    try:
        r = httpx.get(url, timeout=10)
        return r.json()["PropertyTable"]["Properties"][0]["IsomericSMILES"]
    except:
        return None


# -----------------------------
# ⚗️ Molecular Properties
# -----------------------------
def analyze(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None

    return {
        "molecular_weight": round(Descriptors.MolWt(mol), 2),
        "logP": round(Descriptors.MolLogP(mol), 2),
        "H_donors": Descriptors.NumHDonors(mol),
        "H_acceptors": Descriptors.NumHAcceptors(mol),
        "TPSA": round(Descriptors.TPSA(mol), 2),
    }


# -----------------------------
# 💊 Drug-likeness score
# -----------------------------
def drug_score(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return 0

    score = 0

    if Descriptors.MolWt(mol) < 500:
        score += 1
    if Descriptors.MolLogP(mol) < 5:
        score += 1
    if Descriptors.NumHDonors(mol) <= 5:
        score += 1
    if Descriptors.NumHAcceptors(mol) <= 10:
        score += 1

    return score


# -----------------------------
# 🧬 SELFIES-based molecule generator
# -----------------------------
def generate_candidate(smiles: str):
    try:
        selfies_str = sf.encoder(smiles)
        tokens = list(sf.split_selfies(selfies_str))

        if len(tokens) > 3:
            i = random.randint(0, len(tokens) - 1)
            tokens[i] = random.choice(tokens)

        mutated = "".join(tokens)
        new_smiles = sf.decoder(mutated)

        mol = Chem.MolFromSmiles(new_smiles)
        if mol:
            return new_smiles
    except:
        pass

    return smiles


# -----------------------------
# 🧪 Similarity (Tanimoto)
# -----------------------------
def similarity(smiles1, smiles2):
    mol1 = Chem.MolFromSmiles(smiles1)
    mol2 = Chem.MolFromSmiles(smiles2)

    if not mol1 or not mol2:
        return 0.0

    fp1 = AllChem.GetMorganFingerprintAsBitVect(mol1, 2, nBits=2048)
    fp2 = AllChem.GetMorganFingerprintAsBitVect(mol2, 2, nBits=2048)

    return round(DataStructs.TanimotoSimilarity(fp1, fp2), 3)


# -----------------------------
# 🧠 Query understanding
# -----------------------------
async def resolve_query(q: str):

    ql = q.lower()

    # SMILES detection
    if any(x in ql for x in ["=", "(", ")", "#"]):
        return {"type": "molecule", "value": q}

    # protein / disease case
    if any(x in ql for x in ["virus", "covid", "protein", "vaccine", "disease"]):
        return {"type": "protein", "value": "6LU7"}

    # fallback LLM → drug name guess
    drug = await ask_gemma(f"Return only a known drug name for: {q}")

    if len(drug.split()) <= 3 and drug:
        return {"type": "molecule", "value": drug.strip()}

    return {"type": "molecule", "value": q}


# -----------------------------
# 🚀 MAIN ANALYZE API
# -----------------------------
@app.get("/analyze")
async def analyze_query(q: str):

    decision = await resolve_query(q)

    # -------------------------
    # 🦠 PROTEIN MODE
    # -------------------------
    if decision["type"] == "protein":
        return {
            "type": "protein",
            "pdb_id": decision["value"],
            "explanation": await ask_gemma(
                f"Explain mechanism and therapeutic relevance of {q}"
            ),
        }

    # -------------------------
    # 🧪 MOLECULE MODE
    # -------------------------
    smiles = decision["value"]

    # PubChem lookup if not SMILES
    if not any(x in smiles for x in ["=", "(", ")"]):
        fetched = get_smiles(smiles)
        if fetched:
            smiles = fetched
        else:
            smiles = "CCO"  # fallback ethanol

    candidate = generate_candidate(smiles)

    return {
        "type": "molecule",
        "input": q,
        "smiles": smiles,
        "candidate": candidate,

        "properties": analyze(smiles),

        "drug_likeness_score": drug_score(candidate),

        "similarity_score": similarity(smiles, candidate),

        "explanation": await ask_gemma(
            f"Explain pharmacology and therapeutic use of {q}"
        ),
    }


# -----------------------------
# 📂 PROTEIN UPLOAD
# -----------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):

    content = await file.read()
    text = content.decode("utf-8", errors="ignore")

    return {
        "type": "protein",
        "preview": text[:4000],
        "message": "Protein uploaded successfully",
        "status": "Ready for docking module (future upgrade)",
    }
