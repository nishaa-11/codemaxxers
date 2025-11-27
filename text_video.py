#!/usr/bin/env python3
import sys
import json
import re
import time
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


MODEL_NAME = "google/flan-t5-base"
OUTPUT_ROOT = Path("outputs")
OUTPUT_ROOT.mkdir(exist_ok=True)


# Load Model
def load_model():
    print("[INFO] Loading model...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    return tokenizer, model


# Main Instruction Prompt
def build_prompt(text):
    return f"""
You convert educational animation instructions into JSON.

OUTPUT RULES:
- ONLY valid JSON
- No explanations
- No markdown
- Must contain key: "scenes"

Format:

{{
  "scenes": [
    {{
      "type": "graph_plot" | "algorithm_sort",
      "function": string (optional),
      "range": list (optional),
      "data": list (optional)
    }}
  ]
}}

User instruction: "{text}"
JSON:
""".strip()


# Fallback Prompt
def build_fallback_prompt(text):
    return f"""
Your previous JSON was invalid.

Now produce a SIMPLE fallback animation JSON
so animation engine can still work.

Rules:
- ONLY valid JSON
- If unsure: use "graph_plot" with sin(x)

Format example:

{{
  "scenes": [
    {{
      "type": "graph_plot",
      "function": "sin(x)",
      "range": [0, "2π"],
      "highlights": []
    }}
  ]
}}

Do this for: "{text}"
JSON:
""".strip()


# Fix JSON
def clean_json(raw):
    try:
        raw = raw[raw.index("{") : raw.rindex("}") + 1]
    except:
        pass
    return raw.replace("'", '"')


# AI fallback attempt
def ai_fallback(tokenizer, model, text):
    print("[INFO] Retrying LLM fallback...", file=sys.stderr)
    prompt = build_fallback_prompt(text)
    inp = tokenizer(prompt, return_tensors="pt")
    out = model.generate(**inp, max_length=200)
    raw = tokenizer.decode(out[0], skip_special_tokens=True).strip()

    print(f"[DEBUG] fallback llm output:\n{raw}\n", file=sys.stderr)

    try:
        return json.loads(clean_json(raw))
    except:
        # Final guaranteed fallback
        return {
            "scenes": [
                {"type": "graph_plot", "function": "sin(x)", "range": [0, "2π"]}
            ]
        }


# Generate JSON using LLM + fallback
def generate_scene(tokenizer, model, text):
    prompt = build_prompt(text)
    inp = tokenizer(prompt, return_tensors="pt")
    out = model.generate(**inp, max_length=250)

    raw = tokenizer.decode(out[0], skip_special_tokens=True).strip()
    print(f"[DEBUG] primary llm output:\n{raw}\n", file=sys.stderr)

    try:
        cleaned = clean_json(raw)
        data = json.loads(cleaned)
        if "scenes" not in data:
            raise ValueError
        return data
    except:
        return ai_fallback(tokenizer, model, text)


# JSON → Manim
def make_manim(scene):
    if scene.get("type") == "algorithm_sort":
        values = scene.get("data", [3, 1, 2])
        bars = ", ".join(map(str, values))
        return f"""
from manim import *

class AutoScene(Scene):
    def construct(self):
        values = [{bars}]
        bars = VGroup(*[
            Rectangle(width=0.6, height=v*0.3, color=BLUE)
            for v in values
        ])
        bars.arrange(RIGHT, buff=0.3).shift(DOWN)

        self.play(LaggedStartMap(FadeIn, bars))
        self.wait(1)
"""
    return """
from manim import *
import numpy as np

class AutoScene(Scene):
    def construct(self):
        axes = Axes(
            x_range=[0, 2*PI, PI/2],
            y_range=[-1.5, 1.5, 0.5],
            tips=False
        ).to_edge(DOWN)

        graph = axes.plot(lambda x: np.sin(x), color=BLUE)
        self.play(Create(axes), Create(graph))
        self.wait(1)
"""


def safe_filename(txt):
    fn = re.sub(r"[^a-z0-9]+", "_", txt.lower()).strip("_")
    return fn or "animation"


# Render Video
def render(code, user_text):
    safe = safe_filename(user_text)
    fname = f"{safe}_{int(time.time())}.mp4"

    temp = Path(tempfile.mkdtemp())
    script = temp / "scene.py"
    script.write_text(code)

    cmd = ["manim", "-qk", "-o", fname, script.name, "AutoScene"]
    subprocess.run(cmd, check=True, cwd=temp)

    vids = list((temp / "media/videos").rglob(fname))
    shutil.move(str(vids[0]), str(OUTPUT_ROOT / fname))

    return OUTPUT_ROOT / fname


# Main
def main():
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter: ")

    tokenizer, model = load_model()
    data = generate_scene(tokenizer, model, text)

    scene = data["scenes"][0]
    code = make_manim(scene)
    video = render(code, text)

    print("\n🎯 Completed Successfully!")
    print("Video Saved At:", video)


if __name__ == "__main__":
    main()

