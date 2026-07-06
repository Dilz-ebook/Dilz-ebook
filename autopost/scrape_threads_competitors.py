#!/usr/bin/env python3
"""
Scrape Threads Competitors.
Visits public profiles defined in competitors.json, extracts their latest posts,
filters them by interaction threshold (likes), and appends new viral posts to viral_inputs.txt.

Usage:
    python3 autopost/scrape_threads_competitors.py
"""

import os
import re
import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

# Paths
CONFIG_FILE = Path(__file__).parent / "competitors.json"
INPUT_FILE = Path(__file__).parent / "viral_inputs.txt"


def load_config():
    """Load config from competitors.json."""
    if not CONFIG_FILE.exists():
        # Create a default configuration if it doesn't exist
        default_config = {
            "competitors": ["siauwandreas", "rahardjapoetra", "humphrey_rusli", "zuck"],
            "viral_threshold_likes": 50,
            "max_posts_per_creator": 3
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        return default_config
        
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def read_existing_inputs():
    """Read existing posts in viral_inputs.txt to avoid duplicates."""
    if not INPUT_FILE.exists():
        return set()
        
    content = INPUT_FILE.read_text(encoding="utf-8")
    blocks = content.split("\n---")
    existing_texts = set()
    
    for block in blocks:
        # Clean comment lines starting with #
        lines = [line.strip() for line in block.split("\n") if line.strip() and not line.strip().startswith("#")]
        text = "\n".join(lines).strip()
        if text:
            # Store normalized version (lowercased, whitespace-stripped)
            normalized = re.sub(r'\s+', '', text).lower()
            existing_texts.add(normalized)
            
    return existing_texts


def parse_metric_value(text):
    """Parse metric text (e.g. '3.4K', '17.9K', '885') to integer."""
    text = text.replace(" ", "").replace(",", "").lower().strip()
    if not text:
        return 0
        
    match = re.search(r'([0-9.]+)([km]?)', text)
    if not match:
        return 0
        
    val, suffix = match.groups()
    try:
        val = float(val)
        if suffix == 'k':
            val *= 1000
        elif suffix == 'm':
            val *= 1000000
        return int(val)
    except ValueError:
        return 0


def scrape_profile(driver, username, config, existing_normalized_posts):
    """Scrape a single profile and return list of new viral posts."""
    url = f"https://www.threads.net/@{username}"
    print(f"Mengunjungi profil: {url} ...")
    
    try:
        try:
            driver.get(url)
        except TimeoutException:
            print(f"  ⚠️ Timeout saat memuat halaman {url}, mencoba memproses DOM yang ada...")
            
        time.sleep(3) # Wait slightly for DOM to settle
        
        # Scroll down slightly to trigger loading more posts if needed
        driver.execute_script("window.scrollTo(0, 600);")
        time.sleep(2)
        
        post_elements = driver.find_elements(By.CSS_SELECTOR, "div.xrvj5dj.xd0jker")
        print(f"  Ditemukan {len(post_elements)} kontainer postingan di halaman.")
        
        viral_posts = []
        
        for idx, post_el in enumerate(post_elements):
            # Extract post text
            try:
                text_el = post_el.find_element(By.CSS_SELECTOR, ".x1a6qonq.x6ikm8r.x10wlt62.xj0a0fe.x126k92a.x6prxxf.x7r5mf7")
                post_text = text_el.text.strip()
            except Exception:
                # If there's no text (e.g., image-only post), skip it
                continue
                
            if not post_text or len(post_text) < 25:
                continue
                
            # Extract metrics (likes, replies)
            likes = 0
            replies = 0
            try:
                metric_el = post_el.find_element(By.CSS_SELECTOR, ".x4vbgl9.x1qfufaz.x1k70j0n")
                buttons = metric_el.find_elements(By.CSS_SELECTOR, "div[role='button']")
                
                # Button 1 is Likes, Button 2 is Replies
                if len(buttons) >= 1:
                    likes = parse_metric_value(buttons[0].text)
                if len(buttons) >= 2:
                    replies = parse_metric_value(buttons[1].text)
            except Exception:
                pass
                
            # Skip if likes is below threshold
            if likes < config["viral_threshold_likes"]:
                continue
                
            # Check for duplicates
            normalized_text = re.sub(r'\s+', '', post_text).lower()
            if normalized_text in existing_normalized_posts:
                continue
                
            viral_posts.append({
                "username": username,
                "text": post_text,
                "likes": likes,
                "replies": replies
            })
            
            # Stop if we hit the maximum limit per creator
            if len(viral_posts) >= config["max_posts_per_creator"]:
                break
                
        print(f"  -> Berhasil mendapatkan {len(viral_posts)} postingan viral baru dari @{username}.")
        return viral_posts
        
    except Exception as e:
        print(f"  ❌ Eror saat memproses @{username}: {e}")
        return []


def append_to_inputs_file(new_posts):
    """Append new viral posts to viral_inputs.txt."""
    if not new_posts:
        return
        
    # Check if we need to add a separator first
    needs_separator = INPUT_FILE.exists() and INPUT_FILE.stat().st_size > 0
    
    with open(INPUT_FILE, "a", encoding="utf-8") as f:
        for post in new_posts:
            if needs_separator:
                f.write("\n---\n")
            else:
                needs_separator = True
                
            f.write(f"# Source: threads.net/@{post['username']} (Likes: {post['likes']}, Replies: {post['replies']})\n")
            f.write(f"{post['text']}\n")
            
    print(f"✅ Sukses menambahkan {len(new_posts)} postingan baru ke {INPUT_FILE.name}")


def main():
    config = load_config()
    print("=== MULTI-COMPETITOR THREADS SCRAPER ===")
    print(f"Konfigurasi:")
    print(f"  - Target Kreator: {', '.join(config['competitors'])}")
    print(f"  - Batas Minimum Likes: {config['viral_threshold_likes']}")
    print(f"  - Max Posts per Kreator: {config['max_posts_per_creator']}\n")
    
    existing_normalized = read_existing_inputs()
    print(f"Membaca {len(existing_normalized)} postingan unik yang sudah ada di {INPUT_FILE.name}.\n")
    
    # Setup Chrome options
    options = Options()
    options.page_load_strategy = 'eager'
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(20)
    all_new_posts = []
    
    try:
        for competitor in config["competitors"]:
            new_posts = scrape_profile(driver, competitor, config, existing_normalized)
            all_new_posts.extend(new_posts)
            # Short sleep between profiles to avoid aggressive request behavior
            time.sleep(3)
            
        # Write to file
        if all_new_posts:
            append_to_inputs_file(all_new_posts)
        else:
            print("Tidak ditemukan postingan viral baru yang belum terdaftar.")
            
    finally:
        driver.quit()
        print("\nProses selesai.")


if __name__ == "__main__":
    main()
