"""
Generate content queue from marketing markdown files.
Parses all captions, hooks, and teasers into a single JSON queue
ready for auto-posting.

Usage:
    python autopost/generate_queue.py

Output:
    autopost/content_queue.json
    autopost/x_export.txt (for manual scheduling on X/Buffer)
"""

import re
import json
from pathlib import Path

MARKETING_DIR = Path(__file__).parent.parent / "marketing"
OUTPUT_FILE = Path(__file__).parent / "content_queue.json"
X_EXPORT_FILE = Path(__file__).parent / "x_export.txt"


def parse_hook_viral_promo():
    """Parse organik-viral-hooks.md for single-post hooks."""
    filepath = MARKETING_DIR / "organik-viral-hooks.md"
    if not filepath.exists():
        return []
    
    content = filepath.read_text(encoding="utf-8")
    hooks = []
    
    # Split content by double newlines followed by a digit and a period to isolate hook blocks
    blocks = re.split(r'\n\n(?=\d+\.\s)', content)
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        # Match starting with number like "1. " or "12. "
        match = re.match(r'^\d+\.\s+(.+)$', block, re.DOTALL)
        if match:
            text = match.group(1).strip()
            if text and len(text) > 20 and not text.startswith("|") and not text.startswith("Hook"):
                hooks.append({
                    "text": text,
                    "category": "organik-viral-hook",
                    "type": "single_post",
                })
    
    return hooks



def inject_link(text):
    """
    Clean up double newlines, trailing spaces, and leading spaces on lines.
    """
    # Clean up double newlines, trailing spaces, leading spaces on lines
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


def validate_queue(queue):
    """
    Validate all posts in the queue.
    Checks for:
    1. Characters exceeding 500 limit (Threads).
    2. Leftover placeholders like [X] or unreplaced brackets.
    """
    errors = []
    
    # Whitelist of brackets that are allowed (e.g. formula explanations)
    allowed_brackets = {
        "Trigger emosi",
        "Spesifik/Angka",
        "Janji/Penasaran",
    }
    
    for i, item in enumerate(queue, 1):
        text = item["text"]
        category = item["category"]
        
        # 1. Length check
        if len(text) > 500:
            errors.append(
                f"POST #{i} ({category}) MELEBIHI batas 500 karakter Threads ({len(text)} karakter).\n"
                f"Teks: \"{text[:60]}...\""
            )
            
        # 2. Placeholder check
        # Match anything inside square brackets
        brackets = re.findall(r'\[([^\]]+)\]', text)
        for b in brackets:
            if b not in allowed_brackets:
                errors.append(
                    f"POST #{i} ({category}) MENGANDUNG PLACEHOLDER: [{b}].\n"
                    f"Teks: \"{text[:60]}...\""
                )
            
    if errors:
        print("\n❌ ERROR VALIDASI: Ditemukan kesalahan pada konten marketing!")
        for e in errors:
            print(f"   - {e}")
        print("\nAntrean konten TIDAK akan diperbarui karena kegagalan validasi. Silakan perbaiki file di folder marketing/ terlebih dahulu.")
        import sys
        sys.exit(1)
        
    print("\n✅ Semua konten berhasil melewati validasi kualitas (Karakter & Placeholder aman).")


def generate_queue():
    """Generate the full content queue from organic hooks."""
    print("Parsing marketing files...")
    
    hooks = parse_hook_viral_promo()
    print(f"  organik-viral-hooks.md: {len(hooks)} hooks")
    
    queue = hooks
    
    # Inject Lynk.id link and clean up hashtags
    for item in queue:
        item["text"] = inject_link(item["text"])
        # Remove #PinokioArab (Threads treats it as group tag)
        item["text"] = re.sub(r'\n*#PinokioArab\n*', '', item["text"], flags=re.IGNORECASE)
        item["text"] = item["text"].strip()
    
    print(f"\nTotal queue: {len(queue)} posts")
    
    # Run validation before saving
    validate_queue(queue)
    
    # Save JSON queue
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
    print(f"Saved: {OUTPUT_FILE}")
    
    # Generate X export (plain text, one post per section)
    with open(X_EXPORT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("EXPORT KONTEN UNTUK X (TWITTER)\n")
        f.write("Copy-paste satu per satu ke X atau Buffer Free\n")
        f.write("=" * 60 + "\n\n")
        
        for i, item in enumerate(queue, 1):
            f.write(f"--- POST #{i} ({item['category']}) ---\n")
            f.write(item["text"] + "\n")
            f.write("\n" + "-" * 40 + "\n\n")
    
    print(f"Saved: {X_EXPORT_FILE}")
    print("\nDone! Content queue is ready.")
    print(f"  - Threads: will auto-post from content_queue.json")
    print(f"  - X: copy from x_export.txt → paste to Buffer/X manually")


if __name__ == "__main__":
    generate_queue()
