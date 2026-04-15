from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx, os
import google.generativeai as genai

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- GEMMA ----------------
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemma-4-26b-a4b-it")


# ---------------- 🧠 GEMMA INTELLIGENT CLASSIFIER ----------------
def classify(query: str):
    """
    Uses AI instead of hardcoded rules
    """
    try:
        prompt = f"""
You are a biomedical classifier.

Classify the input into ONLY ONE category:

- drug (medicine, chemical compound, pharmaceutical)
- molecule (chemical substance, not drug)
- disease (illness like malaria, cancer, fever)
- protein (virus, enzyme, biological protein, vaccine target)

Return ONLY one word.

Input: {query}
"""

        res = model.generate_content(prompt)
        label = res.text.strip().lower()

        # safety fallback
        if label not in ["drug", "molecule", "disease", "protein"]:
            return "molecule"

        return label

    except:
        return "molecule"


# ---------------- REAL PUBCHEM SEARCH ----------------
async def search_pubchem(query: str):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/property/IsomericSMILES,CanonicalSMILES/JSON"

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)

    try:
        data = r.json()["PropertyTable"]["Properties"][0]
        return {
            "smiles": data.get("IsomericSMILES"),
            "canonical_smiles": data.get("CanonicalSMILES")
        }
    except:
        return None


# ---------------- CID FETCH ----------------
async def get_pubchem_cid(name: str):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/cids/JSON"

    async with httpx.AsyncClient() as client:
        r = await client.get(url)

    try:
        return r.json()["IdentifierList"]["CID"][0]
    except:
        return None


# ---------------- PROTEIN STRUCTURE ----------------
async def get_protein_structure(query: str):
    mapping = {
        "covid": "6LU7",
        "sars": "6LU7",
        "flu": "1RUZ",
        "rabies": "4Q6Q"
    }

    pdb = "6LU7"
    for k in mapping:
        if k in query.lower():
            pdb = mapping[k]

    return {
        "pdb_id": pdb,
        "viewer_url": f"https://3Dmol.org/viewer.html?pdb={pdb}"
    }


# ---------------- GEMMA EXPLANATION ----------------
def explain(prompt: str):
    try:
        res = model.generate_content(prompt)
        return res.text
    except:
        return "AI explanation unavailable"


# ---------------- 🧠 MAIN API ----------------
@app.get("/discover")
async def discover(q: str):

    mode = classify(q)

    # ---------------- DRUG MODE ----------------
    if mode == "drug":

        pubchem = await search_pubchem(q)
        cid = await get_pubchem_cid(q)

        return JSONResponse({
            "type": "drug",
            "query": q,
            "cid": cid,
            "pubchem": pubchem,
            "viewer_3d": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else None,

            "explanation": explain(
                f"Explain this drug, its mechanism, uses, and side effects: {q}"
            )
        })

    # ---------------- DISEASE MODE (NEW FIX 🔥) ----------------
    if mode == "disease":

        return JSONResponse({
            "type": "disease",
            "query": q,

            "causes": explain(f"What causes {q}?"),
            "treatment": explain(f"What are treatments for {q}?"),
            "biology": explain(f"Explain the biology of {q}"),

            "note": "No chemical structure because this is a disease, not a molecule."
        })

    # ---------------- PROTEIN MODE ----------------
    if mode == "protein":

        protein = await get_protein_structure(q)

        return JSONResponse({
            "type": "protein",
            "query": q,
            "structure": protein,
            "ribbon_view": protein["viewer_url"],

            "explanation": explain(
                f"Explain protein structure and vaccine relevance of: {q}"
            )
        })

    # ---------------- MOLECULE MODE ----------------
    pubchem = await search_pubchem(q)
    cid = await get_pubchem_cid(q)

    return JSONResponse({
        "type": "molecule",
        "query": q,
        "cid": cid,
        "pubchem": pubchem,
        "viewer_3d": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else None,

        "explanation": explain(
            f"Explain chemical structure and properties of: {q}"
        )
    })


# ---------------- HEALTH CHECK ----------------
@app.get("/")
async def root():
    return {"status": "Bio-AI backend running"} 
