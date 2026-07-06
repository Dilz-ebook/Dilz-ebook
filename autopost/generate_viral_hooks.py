"""
AI Copywriting Paraphraser (Viral Hook Generator).
Reads viral posts from viral_inputs.txt, uses Gemini API to paraphrase them
for promoting the Ebook, validates them, and appends them to hook-viral-promo.md.

Usage:
    export GEMINI_API_KEY="your-api-key"
    python autopost/generate_viral_hooks.py
"""

import os
import re
import sys
from pathlib import Path

# Paths
INPUT_FILE = Path(__file__).parent / "viral_inputs.txt"
HOOK_FILE = Path(__file__).parent.parent / "marketing" / "organik-viral-hooks.md"

def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'").strip('"')

# Load env variables
load_env_file()

# Config
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MOCK_MODE = os.environ.get("MOCK_MODE", "").lower() == "true" or not GEMINI_API_KEY


def read_viral_inputs():
    """Read and clean inputs from viral_inputs.txt."""
    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} tidak ditemukan. Silakan buat filenya terlebih dahulu.")
        sys.exit(1)
        
    content = INPUT_FILE.read_text(encoding="utf-8")
    blocks = content.split("\n---")
    cleaned_inputs = []
    
    for block in blocks:
        # Remove comment lines
        lines = [line.strip() for line in block.split("\n") if line.strip() and not line.strip().startswith("#")]
        text = "\n".join(lines).strip()
        if text:
            cleaned_inputs.append(text)
            
    return cleaned_inputs


def get_next_hook_number():
    """Find the next hook index number in HOOK_FILE."""
    if not HOOK_FILE.exists():
        return 1
    content = HOOK_FILE.read_text(encoding="utf-8")
    # Find all line starts like "1. ", "12. ", etc.
    numbers = [int(n) for n in re.findall(r'^(\d+)\.\s+', content, re.MULTILINE)]
    return max(numbers) + 1 if numbers else 1


def mock_paraphrase(viral_text, index):
    """Simulate an organic copywriting tip hook for offline testing."""
    return (
        "Rahasia biar konten lu gak di-skip dalam 3 detik pertama:\n\n"
        "Fokus ke kalimat pertama (hook) yang langsung nyentuh masalah audiens.\n"
        "Gak usah bertele-tele, langsung sebutin solusi spesifik yang mereka butuhin."
    )


def generate_paraphrase(viral_text, index):
    """Call Google Gemini API to paraphrase the post into organic content."""
    if MOCK_MODE:
        return mock_paraphrase(viral_text, index)
        
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    
    # We use gemini-2.5-flash as the default model
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    prompt = f"""
You are an expert copywriter. Analyze the following viral post structure and psychology, then write a paraphrased version that functions as a high-value, organic educational copywriting or content creation tip for social media.

Objective:
- Create an educational/value-giving post that teaches copywriting, content creation, or social media growth.
- Do NOT promote any product, ebook, or brand. Do NOT include any links or call-to-actions to buy anything.
- The post must be 100% organic and value-focused.

Original viral post:
\"\"\"
{viral_text}
\"\"\"

Requirements:
1. The rewritten post MUST follow the same psychological hook structure/formula as the original post, but be rewritten for copywriting/content marketing tips.
2. The rewritten post MUST be strictly UNDER 480 characters (to fit within the 500-char limit of Threads).
3. Keep it simple, extremely sharp, and punchy. Avoid verbose introductions or preambles like "Gara-gara terinspirasi post viral ini" or "Saya baru sadar". Get straight to the point.
4. The language/tone MUST be Indonesian, causal/informal (using words like 'gua', 'lu', 'kamu', 'aja', 'kalo', dll. suitable for social media/Threads/X), punchy, and engaging.
5. The output must NOT contain any placeholders like [X] or [link] or brackets. Fill them in with actual values or delete them.
6. Output ONLY the rewritten post text. Do not output any explanation or wrapper quotes.
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean potential wrapper quotes from LLM output
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        return text
    except Exception as e:
        print(f"Error calling Gemini API: {e}. Falling back to Mock Mode.")
        return mock_paraphrase(viral_text, index)


def validate_hook(text, original_num):
    """Verify the generated hook meets quality standards."""
    errors = []
    
    # 1. Length check
    if len(text) > 500:
        errors.append(f"Panjang karakter ({len(text)}) melebihi batas 500.")
        
    # 2. Placeholder presence
    brackets = re.findall(r'\[([^\]]+)\]', text)
    if brackets:
        errors.append(f"Mengandung placeholder: {brackets}")
        
    return errors


def append_hook_to_file(hook_text, hook_num):
    """Append the generated hook to marketing/hook-viral-promo.md."""
    if not HOOK_FILE.exists():
        print(f"ERROR: {HOOK_FILE} tidak ditemukan.")
        sys.exit(1)
        
    # Format the hook line
    formatted_hook = f"\n{hook_num}. {hook_text}\n"
    
    with open(HOOK_FILE, "a", encoding="utf-8") as f:
        f.write(formatted_hook)
        
    print(f"✅ Sukses menambahkan Hook #{hook_num} ke {HOOK_FILE.name}")


def main():
    if not GEMINI_API_KEY:
        print("⚠️  Peringatan: GEMINI_API_KEY tidak ditemukan di environment.")
        print("    Berjalan dalam MODE SIMULASI (MOCK MODE).")
        print("    Untuk menggunakan API asli, silakan jalankan dengan:")
        print("    export GEMINI_API_KEY=\"your-key\" && python3 autopost/generate_viral_hooks.py\n")
        
    inputs = read_viral_inputs()
    if not inputs:
        print("Tidak ada input postingan viral baru di viral_inputs.txt.")
        return
        
    print(f"Menemukan {len(inputs)} postingan viral untuk diparafrase.")
    next_num = get_next_hook_number()
    
    import time
    for idx, viral_text in enumerate(inputs, 1):
        print(f"\nProcessing post #{idx}...")
        print(f"Original hook preview: \"{viral_text.splitlines()[0][:60]}...\"")
        
        generated_hook = generate_paraphrase(viral_text, next_num)
        
        # Validate
        errors = validate_hook(generated_hook, next_num)
        if errors:
            print(f"❌ Validasi gagal untuk hasil parafrase:")
            for err in errors:
                print(f"   - {err}")
            print(f"   Teks gagal: \"{generated_hook}\"")
        else:
            print(f"Hasil Parafrase:")
            print("-" * 50)
            print(generated_hook)
            print("-" * 50)
            append_hook_to_file(generated_hook, next_num)
            next_num += 1
            
        # Sleep to respect Gemini Free Tier 5 RPM rate limit
        if not MOCK_MODE and idx < len(inputs):
            print("Menunggu 12 detik untuk menjaga batas rate-limit API...")
            time.sleep(12)


if __name__ == "__main__":
    main()
