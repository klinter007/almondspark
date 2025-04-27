import base64, pathlib, json
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from gemini2_stripgen import one_sentence
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Gemini 2 Strip Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files on /static instead of "/"
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# Serve the index page at the root path
@app.get("/")
def read_index():
    return FileResponse("static/index.html")

class SentenceInput(BaseModel):
    sentence: str

class GenerationResponse(BaseModel):
    filename: str
    image_base64: str

@app.post("/api/generate", response_model=GenerationResponse)
def generate_api(data: SentenceInput):
    try:
        print(f"Processing sentence: {data.sentence}")
        generated_path = one_sentence(data.sentence)
        print(f"Generated image at: {generated_path}")
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    # Load the generated image and encode it in base64
    try:
        with open(generated_path, "rb") as f:
            image_bytes = f.read()
    except Exception as e:
        print(f"Error reading generated image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to open image: {e}")
    
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return GenerationResponse(filename=generated_path.name, image_base64=image_b64)

@app.post("/api/test")
def test_api(data: SentenceInput):
    return {"received": data.sentence, "status": "ok"}

import random
import re

GALLERY_LIMIT = 5

@app.get("/api/gallery")
def get_gallery(search: Optional[str] = None):
    index_path = pathlib.Path("index.json")
    if not index_path.exists():
        return {"gallery": []}
    with index_path.open("r", encoding="utf-8") as f:
        records = json.load(f)
    # If a search query is provided, filter and highlight the matches
    if search:
        filtered = [r for r in records if search.lower() in r.get("sentence", "").lower()]
        pattern = re.compile(re.escape(search), re.IGNORECASE)
        for rec in filtered:
            rec["sentence"] = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", rec["sentence"])
        records = filtered
    # Randomly sample up to GALLERY_LIMIT records
    if len(records) > GALLERY_LIMIT:
        records = random.sample(records, GALLERY_LIMIT)
    gallery = []
    for rec in records:
        image_file = pathlib.Path("gemini_strips") / rec["filename"]
        try:
            with open(image_file, "rb") as f:
                image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        except Exception:
            image_b64 = ""
        gallery.append({
            "id": rec["id"],
            "sentence": rec["sentence"],
            "filename": rec["filename"],
            "image_base64": image_b64
        })
    return {"gallery": gallery}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8001, reload=True)