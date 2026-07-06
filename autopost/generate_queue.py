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
    
    # Find numbered hooks (1. text, 2. text, etc.)
    pattern = r'^\d+\.\s+(.+)$'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    for match in matches:
        text = match.strip()
        if text and len(text) > 20 and not text.startswith("|") and not text.startswith("Hook"):
            hooks.append({
                "text": text,
                "category": "organik-viral-hook",
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
    """Generate the full content queue, mixed for variety."""
    print("Parsing marketing files...")
    
    hooks = parse_hook_viral_promo()
    print(f"  organik-viral-hooks.md: {len(hooks)} hooks")
    
    captions = []
    teaser_hooks = []
    
    # Separate posts with link vs without link (links are not used anymore)
    all_posts = hooks + captions + teaser_hooks
    posts_with_link = []
    posts_without_link = all_posts
    
    print(f"  Total organic posts: {len(posts_without_link)}")
    
    # Build queue: 3 posts per day
    # Rule: minimal 1, maksimal 2 link per hari
    # With 26 link posts and 38 no-link posts = 64 total = ~21 days
    # 26 links / 21 days = ~1.2 per day → mostly 1, sometimes 2
    queue = []
    link_idx = 0
    no_link_idx = 0
    day = 0
    
    while link_idx < len(posts_with_link) or no_link_idx < len(posts_without_link):
        day += 1
        day_posts = []
        
        # Calculate: should this day have 1 or 2 links?
        remaining_links = len(posts_with_link) - link_idx
        remaining_no_links = len(posts_without_link) - no_link_idx
        remaining_days = max(1, (remaining_links + remaining_no_links + 2) // 3)
        
        # If we have enough links for 2 per day for remaining days, use 2
        # Otherwise use 1 to spread them out
        links_today = 2 if remaining_links > remaining_days else 1
        # But max 2
        links_today = min(links_today, 2, remaining_links)
        # Ensure at least 1 if available
        links_today = max(links_today, min(1, remaining_links))
        
        no_links_today = 3 - links_today
        
        # Build day: start with no-link, then link in middle/end (more natural)
        # Pattern: no-link first, then links
        added_no_link = 0
        added_link = 0
        
        # First slot: no-link (if available)
        if added_no_link < no_links_today and no_link_idx < len(posts_without_link):
            day_posts.append(posts_without_link[no_link_idx])
            no_link_idx += 1
            added_no_link += 1
        elif link_idx < len(posts_with_link):
            day_posts.append(posts_with_link[link_idx])
            link_idx += 1
            added_link += 1
        
        # Second slot: link (if needed) or no-link
        if added_link < links_today and link_idx < len(posts_with_link):
            day_posts.append(posts_with_link[link_idx])
            link_idx += 1
            added_link += 1
        elif no_link_idx < len(posts_without_link):
            day_posts.append(posts_without_link[no_link_idx])
            no_link_idx += 1
            added_no_link += 1
        
        # Third slot: fill remaining
        if added_link < links_today and link_idx < len(posts_with_link):
            day_posts.append(posts_with_link[link_idx])
            link_idx += 1
            added_link += 1
        elif no_link_idx < len(posts_without_link):
            day_posts.append(posts_without_link[no_link_idx])
            no_link_idx += 1
            added_no_link += 1
        
        if not day_posts:
            break
        
        queue.extend(day_posts)
    
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
