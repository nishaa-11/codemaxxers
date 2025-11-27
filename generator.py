import sys, subprocess, tempfile, shutil, time, re
from pathlib import Path
from groq import Groq
import os

client = Groq()  # Needs environment: export GROQ_API_KEY="your_key_here"

OUTPUT_DIR = Path("static/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_PROMPT = """
You are an expert Manim CE coder.
Generate a complete working Manim script.

Rules:
- Only Python code (NO markdown / backticks)
- Must include: from manim import *
- Must define class AutoScene(Scene):
- Inside construct(): animate the instruction visually
- End with: self.wait(1)

Instruction: "{instruction}"
"""

def clean_code(text):
    text = text.replace("```python", "").replace("```", "")
    match = re.search(r"from manim import .*", text, re.DOTALL)
    return match.group(0).strip() if match else text.strip()

def call_llama(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def safe_name(text):
    return re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()) or "video"

def render(code, name):
    tmp = Path(tempfile.mkdtemp())
    script = tmp / "auto.py"
    script.write_text(code)

    out = f"{name}_{int(time.time())}.mp4"

    try:
        # Tell manim where to render videos
        env = os.environ.copy()
        env["MANIM_MEDIA_DIR"] = str(tmp / "media")

        cmd = [
            "manim",
            "-ql",
            "--media_dir", str(tmp / "media"),
            "-o", out,
            script.name,
            "AutoScene"
        ]

        subprocess.run(cmd, cwd=tmp, env=env, check=True)

        video = next((tmp / "media/videos").rglob("*.mp4"))
        final = OUTPUT_DIR / out
        shutil.move(video, final)
        return True, str(final)

    except Exception as e:
        return False, str(e)

def fix_code(code, err, instruction):
    fix_prompt = f"""
Fix this script. Python only.

Instruction: "{instruction}"
Error: {err}

Code:
{code}

Return only fixed code:
"""
    return clean_code(call_llama(fix_prompt))

def generate_video(instruction):
    prompt = BASE_PROMPT.format(instruction=instruction)
    code = clean_code(call_llama(prompt))

    for i in range(5):
        ok, res = render(code, safe_name(instruction))
        if ok:
            return True, res
        code = fix_code(code, res, instruction)

    return False, "Failed after 5 attempts"
