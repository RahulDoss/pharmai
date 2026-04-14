from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

import os, random, httpx
import selfies as sf

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
# 🧠 LLM (HuggingFace - Gemma)
# -----------------------------
async def ask_gemma(prompt: str):
    url = "https://router.huggingface.co/hf-inference/models/google/gemma-2b-it"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            res = await client.post(url, headers=headers, json={"inputs": prompt})
            data = res.json()

            if isinstance(data, list) and "generated_text" in data[0]:
                return data[0]["generated_text"]

            if isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"]

            return str(data)

        except Exception as e:
            return f"LLM error: {str(e)}"


# -----------------------------
# 🧪 PubChem SMILES + properties
# -----------------------------
def get_smiles(name: str):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/IsomericSMILES,MW,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount/JSON"
    try:
        r = httpx.get(url, timeout=10)
        data = r.json()["PropertyTable"]["Properties"][0]

        return {
            "smiles": data["IsomericSMILES"],
            "mw": data.get("MW"),
            "logP": data.get("XLogP"),
            "tpsa": data.get("TPSA"),
            "hbd": data.get("HBondDonorCount"),
            "hba": data.get("HBondAcceptorCount"),
        }
    except:
        return None


# -----------------------------
# ⚗️ Drug-likeness score
# -----------------------------
def drug_score(props: dict):
    if not props:
        return 0

    score = 0

    if props.get("mw") and props["mw"] < 500:
        score += 1
    if props.get("logP") and props["logP"] < 5:
        score += 1
    if props.get("hbd") is not None and props["hbd"] <= 5:
        score += 1
    if props.get("hba") is not None and props["hba"] <= 10:
        score += 1

    return score


# -----------------------------
# 🧬 SELFIES mutation
# -----------------------------
def generate_candidate(smiles: str):
    try:
        selfies_str = sf.encoder(smiles)
        tokens = list(sf.split_selfies(selfies_str))

        if len(tokens) > 3:
            i = random.randint(0, len(tokens) - 1)
            tokens[i] = random.choice(tokens)

        mutated = ".".join(tokens)
        new_smiles = sf.decoder(mutated)

        return new_smiles if new_smiles else smiles

    except:
        return smiles


# -----------------------------
# 🧪 similarity (lightweight)
# -----------------------------
def similarity(a: str, b: str):
    set1, set2 = set(a), set(b)

    if not set1 or not set2:
        return 0.0

    return round(len(set1 & set2) / len(set1 | set2), 3)


# -----------------------------
# 🧠 Protein detection
# -----------------------------
def is_protein_query(q: str):
    keywords = [
        "virus", "protein", "covid", "enzyme", "spike",
        "receptor", "pdb", "rna", "dna"
    ]
    return any(k in q.lower() for k in keywords)


# -----------------------------
# 🧬 Protein mapping
# -----------------------------
def get_pdb_id(query: str):
    q = query.lower()

    if "covid" in q or "virus" in q or "protease" in q:
        return "6LU7"

    if "spike" in q:
        return "6VSB"

    return "6LU7"


# -----------------------------
# 🧠 Query resolver
# -----------------------------
async def resolve_query(q: str):

    if is_protein_query(q):
        return {
            "type": "protein",
            "value": get_pdb_id(q)
        }

    drug = await ask_gemma(f"Return only a known drug or chemical name for: {q}")

    if drug and len(drug.split()) <= 4:
        return {"type": "molecule", "value": drug.strip()}

    return {"type": "molecule", "value": q}


# -----------------------------
# 🚀 MAIN API
# -----------------------------
@app.get("/analyze")
async def analyze(q: str):

    decision = await resolve_query(q)
    name = decision["value"]

    # ---------------- PROTEIN MODE ----------------
    if decision["type"] == "protein":

        return {
            "type": "protein",
            "pdb_id": name,
            "input": q,
            "explanation": await ask_gemma(
                f"Explain structure and drug targeting of {q}"
            ),
        }

    # ---------------- MOLECULE MODE ----------------
    data = get_smiles(name)

    smiles = data["smiles"] if data else "CCO"

    candidate = generate_candidate(smiles)

    return {
        "type": "molecule",
        "input": q,
        "molecule": name,
        "smiles": smiles,
        "candidate": candidate,

        "properties": data,
        "drug_likeness_score": drug_score(data),
        "similarity_score": similarity(smiles, candidate),

        "explanation": await ask_gemma(
            f"Explain pharmacology and therapeutic use of {name}"
        ),
    }


# -----------------------------
# 📂 upload endpoint
# -----------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()

    return {
        "type": "protein",
        "preview": content.decode("utf-8", errors="ignore")[:4000],
        "message": "uploaded successfully"
    }
