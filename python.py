#!/usr/bin/env python3
import sys, subprocess, tempfile, shutil, time, re
from pathlib import Path
from groq import Groq

client = Groq()  # Requires: export GROQ_API_KEY="your_key_here"

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

BASE_PROMPT = """
You are an expert Manim CE coder.
Generate a COMPLETE working Manim script.

Rules:
- Only Python code (NO backticks, NO markdown, NO extra text)
- Must include: from manim import *
- Must define: class AutoScene(Scene):
- Inside construct(): animate the instruction visually
- End with: self.wait(1)

Instruction: "{instruction}"
"""


def clean_code(text):
    # Remove ANY ``` or fencing junk
    text = text.replace("```python", "").replace("```py", "").replace("```", "")

    # Ensure code begins properly
    match = re.search(r"from manim import .*", text, re.DOTALL)
    if match:
        text = match.group(0)

    # Remove trailing spaces & junk outside Python code
    return text.strip()


def call_llama(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def safe_name(text):
    return re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_") or "video"


def render(code, name):
    tmp = Path(tempfile.mkdtemp())
    script = tmp / "auto.py"
    script.write_text(code)

    out = f"{name}_{int(time.time())}.mp4"
    cmd = ["manim", "-ql", "-o", out, script.name, "AutoScene"]

    try:
        subprocess.run(cmd, cwd=tmp, check=True)
        video = next((tmp / "media/videos").rglob("*.mp4"))
        final = OUTPUT_DIR / out
        shutil.move(video, final)
        return True, final
    except Exception as e:
        return False, str(e)


def fix_code(code, error, instruction):
    fix_prompt = f"""
Fix this Manim CE script. Do not add markdown.

Instruction: "{instruction}"

Code:
{code}

Error:
{error}

Output only corrected python code:
"""
    return clean_code(call_llama(fix_prompt))


def main():
    instruction = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Instruction: ")

    prompt = BASE_PROMPT.format(instruction=instruction)
    code = clean_code(call_llama(prompt))

    for i in range(1, 6):
        print(f"\n[INFO] Rendering Attempt {i}...")
        ok, result = render(code, safe_name(instruction))

        if ok:
            print("\n🎯 SUCCESS! Video saved at:\n➡", result)
            return

        print("\n[WARN] Failed → Fixing script...")
        code = fix_code(code, result, instruction)

    print("\n❌ Could not render after multiple fixes :(")


if __name__ == "__main__":
    main()

