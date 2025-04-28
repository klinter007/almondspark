#!/usr/bin/env python3
# gemini2_stripgen.py — Two-hop image generator using Gemini 2.0 Experimental API

import os, json, logging, pathlib, subprocess, sys
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types

# ─── paths & config ─────────────────────────────────────────────
HERE = pathlib.Path(__file__).parent
OUTDIR = HERE / "gemini_strips"
OUTDIR.mkdir(exist_ok=True)
INDEX_PATH = HERE / "index.json"  # index file for generated strips

# Expect the following files to exist in the project folder:
#   • rules_prompt.txt  (for hop1 prompt generation)
#   • rules_style.txt   (for additional style guidance if needed)
#   • style_ref1.jpg    (the reference style image)
RULES_PROMPT    = (HERE / "rules_prompt.txt").read_text(encoding="utf-8").strip()
RULES_STYLE     = (HERE / "rules_style.txt").read_text(encoding="utf-8").strip()  # if needed
REFERENCE_IMAGE = HERE / "style_ref1.jpg"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY is None:
    raise RuntimeError("GEMINI_API_KEY environment variable not set.")

# ─── debug log ───────────────────────────────────────────────────
LOG_PATH = HERE / "gemini2_stripgen_run.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")]
)
logging.info("─ New run ─────────────────────────────────────────────")

client = genai.Client(api_key=GEMINI_API_KEY)

# ─── helpers ───────────────────────────────────────────────────
def compose_prompt_hop1(sentence: str) -> str:
    """
    Combine the prompt rules (rules_prompt.txt) with the user sentence.
    """
    return f"{RULES_PROMPT}\n\nINSTRUCTION: \"{sentence.strip()}\""

def generate_image_prompt(sentence: str) -> str:
    """
    First hop: generate an image prompt from user input using the Gemini text model.
    """
    prompt = compose_prompt_hop1(sentence)
    logging.info("HOP1 PROMPT ►\n%s\n", prompt)
    
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=['TEXT'])
    )
    
    # Iterate over response parts to get the text output
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            generated_prompt = part.text
            logging.info("HOP1 RESPONSE ►\n%s\n", generated_prompt)
            return generated_prompt
    raise RuntimeError("No text generated in hop1.")

def generate_strip(sentence: str, out: pathlib.Path) -> pathlib.Path:
    """
    Second hop: use the generated image prompt and a reference style image to create the final image.
    """
    # Hop 1: Generate an image prompt text
    gen_prompt = generate_image_prompt(sentence)
    
    # (Optionally) combine the generated prompt with style rules if desired.
    combined_prompt = gen_prompt  # or: combined_prompt = f"{gen_prompt}\n{RULES_STYLE}"
    logging.info("Combined image prompt for hop2 ►\n%s\n", combined_prompt)
    
    # Open the reference style image
    try:
        style_image = Image.open(REFERENCE_IMAGE)
    except Exception as e:
        logging.error("Error opening reference image: %s", e)
        raise RuntimeError("Reference image not found or unable to open.") from e

    text_input = (combined_prompt,)
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp-image-generation",
        contents=[text_input, style_image],
        config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE'])
    )
    
    # Debug: Log full response candidate details
    for idx, candidate in enumerate(response.candidates):
        for part in candidate.content.parts:
            logging.info("Candidate %d part - text: %s, inline_data: %s", idx, part.text, getattr(part.inline_data, "data", None))
    
    # Process response to extract the inline image data
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if part.inline_data is not None:
                final_image = Image.open(BytesIO(part.inline_data.data))
                final_image.save(out)
                logging.info("Saved generated strip to: %s", out)
                return out
    raise RuntimeError("No image data returned in hop2.")

def preview(path: pathlib.Path):
    """
    Opens the generated image (macOS QuickLook).
    """
    subprocess.run(["open", path])

def one_sentence(text: str) -> pathlib.Path:
    """
    Generates an image strip from the sentence and updates the JSON index.
    """
    if INDEX_PATH.exists():
        with INDEX_PATH.open("r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []
    # Increment counter based on last record
    if records:
        next_counter = int(records[-1]["id"]) + 1
    else:
        next_counter = 1
    fname = f"{next_counter:06}.png"
    image_path = OUTDIR / fname

    # Generate the image strip (synchronously)
    result_path = generate_strip(text, image_path)
    
    # Append record and update JSON index
    records.append({
        "id": f"{next_counter:06}",
        "sentence": text,
        "filename": fname
    })
    with INDEX_PATH.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    return result_path

# ─── CLI (for testing manually) ───────────────────────────────────
def main():
    if len(sys.argv) == 1:
        sentence = input("Sentence → ")
        path = one_sentence(sentence)
        print(f"[green]Saved[/green] {path}")
        preview(path)
    else:
        paths = []
        input_file = pathlib.Path(sys.argv[1])
        for line in input_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                paths.append(one_sentence(line))
        print(f"[green]Generated {len(paths)} strips.[/green]")
        try:
            from PIL import Image
            pdf = HERE / "gemini_strips.pdf"
            imgs = [Image.open(p) for p in paths]
            imgs[0].save(pdf, save_all=True, append_images=imgs[1:])
            print(f"[green]Merged into[/green] {pdf}")
            preview(pdf)
        except Exception:
            pass

if __name__ == "__main__":
    main()
