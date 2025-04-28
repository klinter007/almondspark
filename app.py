import base64, pathlib, json
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from gemini2_stripgen import one_sentence
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv, set_key
import os

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

# Configure Jinja2 templates directory
templates = Jinja2Templates(directory="templates")

# Serve the index page at the root path
@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Serve the index.html file explicitly
@app.get("/index.html", response_class=HTMLResponse)
async def read_index_html(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Serve the gallery page
@app.get("/gallery", response_class=HTMLResponse)
async def read_gallery(request: Request):
    return templates.TemplateResponse("gallery.html", {"request": request})

# Serve the personal note page
@app.get("/personal-note", response_class=HTMLResponse)
async def read_personal_note(request: Request):
    return templates.TemplateResponse("personal-note.html", {"request": request})

class SentenceInput(BaseModel):
    sentence: str

class GenerationResponse(BaseModel):
    filename: str
    image_base64: str

# Load environment variables from .env file
load_dotenv()

# Modify the helper function to only load the API key from the local .env file
def get_api_key():
    env_path = pathlib.Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        return os.getenv("GEMINI_API_KEY")
    return None

# Endpoint to set the API key
@app.post("/set-api-key")
def set_api_key(api_key: str = Form(...)):
    try:
        # Save the API key to the .env file
        env_path = pathlib.Path(".env")
        if not env_path.exists():
            env_path.touch()
        set_key(str(env_path), "GEMINI_API_KEY", api_key)
        return JSONResponse(content={"message": "API key saved successfully."}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/generate", response_model=GenerationResponse)
def generate_api(data: SentenceInput):
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is missing. Please set it first.")

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
INDEX_PATH = pathlib.Path("logic/index.json")

@app.get("/api/gallery")
def get_gallery(search: Optional[str] = None):
    index_path = INDEX_PATH
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