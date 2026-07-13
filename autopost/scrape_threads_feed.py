#!/usr/bin/env python3
"""
Scrape Threads For-You feed (home timeline) via persistent Chrome profile.

Requires a one-time login:
    DISPLAY=:10.0 python3 autopost/scrape_threads_feed.py --login

Cron mode (no flag) reuses the logged-in profile headless-ish (non-headless
under Xvfb to dodge anti-bot detection), scrolls the feed, filters posts by
likes threshold, appends viral ones to viral_inputs.txt.

Usage:
    python3 autopost/scrape_threads_feed.py            # scrape feed
    python3 autopost/scrape_threads_feed.py --login    # interactive login

Reuses read_existing_inputs / parse_metric_value / append_to_inputs_file /
load_config from scrape_threads_competitors.py.
"""

import argparse
import re
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

# Reuse generic helpers from the profile scraper
sys.path.insert(0, str(Path(__file__).parent))
from scrape_threads_competitors import (  # noqa: E402
    read_existing_inputs, parse_metric_value, append_to_inputs_file, load_config,
)

# Paths
PROFILE_DIR = Path(__file__).parent / ".chrome-profile"
FEED_URL = "https://www.threads.net/"

# ponytail: selectors are Threads feed DOM classes, obfuscated & change per deploy.
# Verify live via DevTools on first --login run; fallback to structural role=article.
CONTAINER_SELECTORS = [
    "div.xrvj5dj.xd0jker",            # primary (profile-page class, may not match feed)
    'div[role="article"]',            # structural fallback
    "article",
]
TEXT_SELECTORS = [
    ".x1a6qonq.x6ikm8r.x10wlt62.xj0a0fe.x126k92a.x6prxxf.x7r5mf7",
    'div[data-pressable-container] [data-ad-comet-preview]',
    'div[dir="auto"]',
]
METRIC_SELECTORS = [
    ".x4vbgl9.x1qfufaz.x1k70j0n",
    'div[role="button"]',
]


def find_first(parent, selectors, by=By.CSS_SELECTOR):
    """Return first matching element from a list of selectors, or None."""
    for sel in selectors:
        try:
            el = parent.find_element(by, sel)
            if el:
                return el
        except Exception:
            continue
    return None


def make_driver(headless=False):
    options = Options()
    options.page_load_strategy = 'eager'
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument(f'--user-data-dir={PROFILE_DIR}')
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(25)
    return driver


def login_mode():
    """Launch visible Chrome, wait for manual login, persist profile."""
    print("=== THREADS LOGIN (one-time) ===")
    print(f"Profile dir: {PROFILE_DIR}")
    print("Browser akan terbuka. Login Threads manual, selesaiin 2FA/captcha.")
    driver = make_driver(headless=False)
    try:
        driver.get(FEED_URL)
        print("\nTekan ENTER di sini setelah login sukses & feed kebuka...")
        input()
        print(f"Profile tersimpan di {PROFILE_DIR}. Browser ditutup.")
    finally:
        driver.quit()


def detect_login_wall(driver):
    """Heuristic: feed not loaded -> likely login expired."""
    try:
        # login wall usually has email/password inputs or a 'Log in' heading
        driver.find_elements(By.CSS_SELECTOR, 'input[type="text"], input[type="email"]')
        inputs = driver.find_elements(By.CSS_SELECTOR, 'input')
        return len(inputs) >= 2
    except Exception:
        return False


def is_indonesian(text):
    """Heuristic: keep only Indonesian (casual) posts.

    Reject non-Latin scripts (Cyrillic/CJK/Arabic) and English-dominant text.
    Indonesian detected by common ID markers / informal words.
    """
    if not text:
        return False
    # Reject non-Latin-heavy text (Cyrillic, CJK, Arabic, emoji-only)
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    letters = sum(1 for c in text if c.isalpha())
    if letters and latin / letters < 0.7:
        return False
    low = text.lower()
    # Strong Indonesian / informal-ID markers
    id_markers = [
        " gua", " gue", " lu", " lo ", " kamu", " kita", " aja", " kalo", " kalau",
        " gak", " nggak", " udah", " bikin", " banget", " yang", " di ", " ke ",
        " sama", " tapi", " jadi", " ini ", " itu ", " mau", " bisa", " ada",
        " untuk", " dari", " dengan", " saya", " mereka",
    ]
    hits = sum(1 for m in id_markers if m in low)
    return hits >= 2


def extract_post(post_el, existing_normalized):
    """Extract text + likes + handle from one feed container. Returns dict or None."""
    # ponytail: Threads feed has no stable class for post text. Post body = the
    # span[dir=auto] that is multiline or >30 chars (handle/badge/time spans are short).
    spans = post_el.find_elements(By.CSS_SELECTOR, 'span[dir="auto"]')
    post_text = ""
    for s in spans:
        t = s.text.strip()
        if "\n" in t or len(t) > 30:
            post_text = t
            break
    if not post_text or len(post_text) < 25:
        return None
    if not is_indonesian(post_text):
        return None

    # Author handle: first /@handle link
    handle = "feed"
    try:
        for link in post_el.find_elements(By.CSS_SELECTOR, 'a[href]'):
            href = link.get_attribute("href") or ""
            m = re.search(r'/@([^/?#]+)', href)
            if m:
                handle = m.group(1)
                break
    except Exception:
        pass

    # Metrics: numeric role=button texts -> [likes, replies, reposts, ...]
    likes = replies = 0
    try:
        nums = []
        for b in post_el.find_elements(By.CSS_SELECTOR, 'div[role="button"]'):
            bt = b.text.strip()
            if bt and re.match(r'^[0-9.,KkMm]+$', bt):
                nums.append(parse_metric_value(bt))
        if len(nums) >= 1:
            likes = nums[0]
        if len(nums) >= 2:
            replies = nums[1]
    except Exception:
        pass

    normalized = re.sub(r'\s+', '', post_text).lower()
    if normalized in existing_normalized:
        return None

    return {
        "username": handle,
        "text": post_text,
        "likes": likes,
        "replies": replies,
        "normalized": normalized,
    }


def scrape_feed(driver, config, existing_normalized):
    """Scroll feed, collect viral posts above threshold."""
    threshold = config.get("feed_threshold_likes", 100)
    max_posts = config.get("feed_max_posts", 20)
    scroll_limit = config.get("feed_scroll_limit", 15)

    try:
        driver.get(FEED_URL)
    except TimeoutException:
        print("⚠️ Timeout muat feed, proses DOM yang ada...")

    time.sleep(4)

    viral_posts = []
    seen_texts = set(existing_normalized)
    stale_count = 0

    for i in range(scroll_limit):
        # collect containers across all candidate selectors
        containers = []
        for sel in CONTAINER_SELECTORS:
            containers.extend(driver.find_elements(By.CSS_SELECTOR, sel))
        # dedup containers by element id
        seen_ids = set()
        unique_containers = []
        for c in containers:
            cid = c.id
            if cid not in seen_ids:
                seen_ids.add(cid)
                unique_containers.append(c)

        new_this_scroll = 0
        for post_el in unique_containers:
            post = extract_post(post_el, seen_texts)
            if not post:
                continue
            if post["likes"] < threshold:
                continue
            seen_texts.add(post["normalized"])
            viral_posts.append(post)
            new_this_scroll += 1
            if len(viral_posts) >= max_posts:
                break

        print(f"  scroll {i+1}/{scroll_limit}: {len(unique_containers)} containers, "
              f"{new_this_scroll} viral baru, total {len(viral_posts)}")

        if len(viral_posts) >= max_posts:
            break

        if new_this_scroll == 0:
            stale_count += 1
            if stale_count >= 2:
                print("  2 scroll berturut-turut gak ada post baru. Stop.")
                break
        else:
            stale_count = 0

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2.5)

    # drop the helper 'normalized' key before append
    for p in viral_posts:
        p.pop("normalized", None)
    return viral_posts


def main():
    parser = argparse.ArgumentParser(description="Scrape Threads For-You feed.")
    parser.add_argument("--login", action="store_true", help="Interactive one-time login.")
    args = parser.parse_args()

    if args.login:
        login_mode()
        return

    config = load_config()
    print("=== THREADS FEED SCRAPER ===")
    print(f"  Threshold likes: {config.get('feed_threshold_likes', 100)}")
    print(f"  Max posts: {config.get('feed_max_posts', 20)}")
    print(f"  Scroll limit: {config.get('feed_scroll_limit', 15)}")

    if not PROFILE_DIR.exists():
        print(f"❌ Profile belum ada di {PROFILE_DIR}.")
        print("   Jalankan dulu: DISPLAY=:10.0 python3 autopost/scrape_threads_feed.py --login")
        sys.exit(1)

    existing = read_existing_inputs()
    print(f"  {len(existing)} post unik sudah ada di viral_inputs.txt.\n")

    driver = make_driver(headless=False)
    try:
        if detect_login_wall(driver):
            print("❌ Login wall terdeteksi. Session expired.")
            print("   Re-login: DISPLAY=:10.0 python3 autopost/scrape_threads_feed.py --login")
            sys.exit(1)

        new_posts = scrape_feed(driver, config, existing)
        if not new_posts:
            print("Tidak ada post viral baru di feed.")
            sys.exit(0)

        append_to_inputs_file(new_posts)
        print(f"\n✅ {len(new_posts)} post viral feed ditambahkan ke viral_inputs.txt")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
