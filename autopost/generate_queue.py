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

# Link produk Lynk.id
LYNKID_URL = "https://lynk.id/pinokioarab/mjz191d8871v"


def parse_hook_viral_promo():
    """Parse hook-viral-promo.md for single-post hooks."""
    filepath = MARKETING_DIR / "hook-viral-promo.md"
    if not filepath.exists():
        return []
    
    content = filepath.read_text(encoding="utf-8")
    hooks = []
    
    # Find numbered hooks (1. text, 2. text, etc.)
    pattern = r'^\d+\.\s+(.+)$'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    for match in matches:
        text = match.strip()
        if text and len(text) > 20 and not text.startswith("|") and not text.startswith("Hook"):
            hooks.append({
                "text": text,
                "category": "hook-viral-promo",
                "type": "single_post",
            })
    
    return hooks


def parse_caption_promosi():
    """Parse caption-promosi.md for ready-to-post captions."""
    filepath = MARKETING_DIR / "caption-promosi.md"
    if not filepath.exists():
        return []
    
    content = filepath.read_text(encoding="utf-8")
    captions = []
    
    # Extract content between ``` blocks
    code_blocks = re.findall(r'```\n(.*?)```', content, re.DOTALL)
    
    for block in code_blocks:
        text = block.strip()
        # Skip blocks that are clearly not captions (like story templates)
        if text and len(text) > 30 and "[Quote box]" not in text and "[Sticker]" not in text:
            # Clean up the text - remove hashtags at end if needed
            captions.append({
                "text": text,
                "category": "caption-promosi",
                "type": "caption",
            })
    
    return captions


def parse_thread_teaser_hooks():
    """
    Parse thread-teaser.md but only extract the HOOK posts (POST 1)
    since full threads need to be posted manually.
    Also extract CTA posts for single use.
    """
    filepath = MARKETING_DIR / "thread-teaser.md"
    if not filepath.exists():
        return []
    
    content = filepath.read_text(encoding="utf-8")
    hooks = []
    
    # Extract code blocks that contain [POST 1 - HOOK]
    code_blocks = re.findall(r'```\n(.*?)```', content, re.DOTALL)
    
    for block in code_blocks:
        if "[POST 1 - HOOK]" in block:
            # Extract just the text after the label
            text = block.replace("[POST 1 - HOOK]", "").strip()
            if text:
                hooks.append({
                    "text": text,
                    "category": "thread-teaser-hook",
                    "type": "single_post",
                })
    
    return hooks


def inject_link(text):
    """
    Replace all [link] placeholders and 'link/cek/klik di bio' mentions
    with the actual Lynk.id product URL.
    """
    # Replace [link] placeholder
    text = text.replace("[link]", LYNKID_URL)
    
    # Replace variations of "link di bio", "cek bio", "klik di bio" etc.
    # Match full phrases including trailing punctuation/words
    bio_replacements = [
        (r'Klik di bio buat checkout\.?', f'Grab di sini: {LYNKID_URL}'),
        (r'Klik di bio kalo siap\.?', f'Grab di sini: {LYNKID_URL}'),
        (r'Klik di bio sebelum kelewat\.?', f'Grab sekarang: {LYNKID_URL}'),
        (r'Klik di bio\.?', f'Grab di sini: {LYNKID_URL}'),
        (r'Cek bio sekarang\.?', f'Grab: {LYNKID_URL}'),
        (r'Cek bio kalo penasaran\.?', f'Cek di sini: {LYNKID_URL}'),
        (r'Cek bio\.?', f'Cek: {LYNKID_URL}'),
        (r'Link di bio\.?', LYNKID_URL),
        (r'link di bio\.?', LYNKID_URL),
    ]
    
    # Only inject bio link if post doesn't already contain the URL
    if LYNKID_URL not in text:
        for pattern, replacement in bio_replacements:
            if re.search(pattern, text):
                text = re.sub(pattern, replacement, text)
                break  # Only replace first match to avoid duplicates
    else:
        # URL already present from [link] replacement, just remove leftover "bio" refs
        for pattern, _ in bio_replacements:
            text = re.sub(pattern, '', text)
    
    # Clean up double newlines, trailing spaces, leading spaces on lines
    text = re.sub(r' +\n', '\n', text)
    text = re.sub(r'\n +', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


def generate_queue():
    """Generate the full content queue, mixed for variety."""
    print("Parsing marketing files...")
    print(f"  Lynk.id URL: {LYNKID_URL}")
    
    hooks = parse_hook_viral_promo()
    print(f"  hook-viral-promo.md: {len(hooks)} hooks")
    
    captions = parse_caption_promosi()
    print(f"  caption-promosi.md: {len(captions)} captions")
    
    teaser_hooks = parse_thread_teaser_hooks()
    print(f"  thread-teaser.md: {len(teaser_hooks)} teaser hooks")
    
    # Build queue: alternate between types for variety
    # Strategy: caption → hook → caption → hook → teaser → repeat
    queue = []
    h_idx, c_idx, t_idx = 0, 0, 0
    
    while h_idx < len(hooks) or c_idx < len(captions) or t_idx < len(teaser_hooks):
        # Add a caption
        if c_idx < len(captions):
            queue.append(captions[c_idx])
            c_idx += 1
        
        # Add a hook
        if h_idx < len(hooks):
            queue.append(hooks[h_idx])
            h_idx += 1
        
        # Add a teaser hook every 5 items
        if t_idx < len(teaser_hooks) and len(queue) % 5 == 0:
            queue.append(teaser_hooks[t_idx])
            t_idx += 1
    
    # Add remaining teaser hooks
    while t_idx < len(teaser_hooks):
        queue.append(teaser_hooks[t_idx])
        t_idx += 1
    
    # Inject Lynk.id link into all posts
    for item in queue:
        item["text"] = inject_link(item["text"])
    
    print(f"\nTotal queue: {len(queue)} posts")
    
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
