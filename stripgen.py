#!/usr/bin/env python3
# stripgen.py — one-shot strip generator with full log (overwrites each run)

import asyncio, aiohttp, hashlib, json, logging, pathlib, subprocess, sys, base64
from openai import AsyncOpenAI, OpenAIError
from rich import print

# ─── paths & config ────────────────────────────────────────────
HERE    = pathlib.Path(__file__).parent
OUTDIR  = HERE / "strips"
OUTDIR.mkdir(exist_ok=True)
INDEX_PATH = HERE / "index.json"  # index file for generated strips

APIKEY  = (HERE / "openai_key.txt").read_text().strip()
RULES   = (HERE / "ruleset.txt").read_text().strip()

# ─── debug log (overwrite every run) ───────────────────────────
LOG_PATH = HERE / "stripgen_run.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")]
)
logging.info("─ New run ─────────────────────────────────────────────")

client = AsyncOpenAI(api_key=APIKEY)

# ─── helpers ───────────────────────────────────────────────────
def compose_prompt(sentence: str) -> str:
    return (
        RULES
        + '\n\nINSTRUCTION: "' + sentence.strip() + '"\n'
        + "Generate the 4- or 5-panel strip exactly as specified above."
    )

async def generate_strip(sentence: str, out: pathlib.Path) -> pathlib.Path:
    prompt = compose_prompt(sentence)
    logging.info("PROMPT ►\n%s\n", prompt)

    try:
        img = await client.images.generate(
            model="gpt-image-1",          
            prompt=prompt,
            n=1,
            size="1536x1024",              # landscape strip (other valid: 1024x1024, 1024x1536)
            quality="medium"
        )
    except OpenAIError as e:
        logging.error("OpenAI error: %s", e)
        raise RuntimeError(f"OpenAI Images error: {e}") from None

    logging.info("RESPONSE ◄\n%s\n", json.dumps(img.model_dump(), indent=2))

    b64_json = img.data[0].b64_json
    if not isinstance(b64_json, str):
        logging.error("No image data returned. Revised prompt: %s", getattr(img.data[0], "revised_prompt", None))
        raise RuntimeError("Image generation returned no image data. Check policy / prompt.")

    image_bytes = base64.b64decode(b64_json)
    out.write_bytes(image_bytes)

    logging.info("Saved strip to: %s", out)
    return out

def preview(path: pathlib.Path):
    subprocess.run(["open", path])      # macOS QuickLook

async def one_sentence(text: str) -> pathlib.Path:
    # Load the JSON index if it exists
    if INDEX_PATH.exists():
        with INDEX_PATH.open("r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []
    # Determine next counter number based on last record (or start at 1)
    if records:
        next_counter = int(records[-1]["id"]) + 1
    else:
        next_counter = 1
    fname = f"{next_counter:06}.png"
    image_path = OUTDIR / fname

    # Generate the strip image
    result_path = await generate_strip(text, image_path)
    
    # Append new record to index and save the JSON index
    records.append({
        "id": f"{next_counter:06}",
        "sentence": text,
        "filename": fname
    })
    with INDEX_PATH.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    return result_path

# ─── CLI ───────────────────────────────────────────────────────
async def main():
    if len(sys.argv) == 1:
        sentence = input("Sentence → ")
        path = await one_sentence(sentence)
        print(f"[green]Saved[/green] {path}")
        preview(path)
    else:
        paths = []
        for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
            if line.strip():
                paths.append(await one_sentence(line))
        print(f"[green]Generated {len(paths)} strips.[/green]")
        # optional PDF merge (needs Pillow)
        try:
            from PIL import Image
            pdf = HERE / "strips.pdf"
            imgs = [Image.open(p) for p in paths]
            imgs[0].save(pdf, save_all=True, append_images=imgs[1:])
            print(f"[green]Merged into[/green] {pdf}")
            preview(pdf)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())