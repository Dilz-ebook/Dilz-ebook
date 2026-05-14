"""
Auto-post to Threads via Meta's Threads API.
Reads content from marketing files and posts sequentially.

Usage:
    python autopost/post_threads.py

Environment Variables Required:
    THREADS_USER_ID     - Your Threads user ID
    THREADS_ACCESS_TOKEN - Long-lived access token from Meta Developer Portal
"""

import os
import json
import time
import requests
from pathlib import Path

# === CONFIG ===
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
TRACKER_FILE = Path(__file__).parent / "tracker.json"
CONTENT_FILE = Path(__file__).parent / "content_queue.json"

GRAPH_API_BASE = "https://graph.threads.net/v1.0"


def load_tracker():
    """Load the post tracker to know what's been posted."""
    if TRACKER_FILE.exists():
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"threads_index": 0, "x_index": 0, "posted": []}


def save_tracker(tracker):
    """Save the tracker state."""
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)


def load_content_queue():
    """Load the content queue."""
    if not CONTENT_FILE.exists():
        print("ERROR: content_queue.json not found. Run generate_queue.py first.")
        return []
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def create_threads_container(text):
    """
    Step 1: Create a media container on Threads.
    Returns the container ID.
    """
    # Threads has a 500 character limit per post
    if len(text) > 500:
        text = text[:497] + "..."
    
    url = f"{GRAPH_API_BASE}/{THREADS_USER_ID}/threads"
    payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    print(f"POST {url}")
    print(f"Text length: {len(text)} chars")
    response = requests.post(url, data=payload)
    
    # Log response for debugging
    print(f"Status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    response.raise_for_status()
    data = response.json()
    return data["id"]


def publish_threads_container(container_id):
    """
    Step 2: Publish the media container.
    Returns the published post ID.
    """
    url = f"{GRAPH_API_BASE}/{THREADS_USER_ID}/threads_publish"
    payload = {
        "creation_id": container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    data = response.json()
    return data["id"]


def post_to_threads(text):
    """Full flow: create container → wait → publish."""
    print(f"Creating Threads container...")
    container_id = create_threads_container(text)
    
    # Wait for container to be ready (Meta recommends checking status)
    print(f"Waiting for container to be ready...")
    time.sleep(5)
    
    print(f"Publishing to Threads...")
    post_id = publish_threads_container(container_id)
    print(f"Published! Post ID: {post_id}")
    return post_id


def main():
    # Validate environment
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("ERROR: Missing THREADS_USER_ID or THREADS_ACCESS_TOKEN environment variables.")
        print("Set them in GitHub Secrets or export locally.")
        exit(1)

    # Load content and tracker
    content_queue = load_content_queue()
    if not content_queue:
        exit(1)

    tracker = load_tracker()
    current_index = tracker["threads_index"]

    # Check if we've posted everything
    if current_index >= len(content_queue):
        print("All content has been posted! Resetting queue...")
        tracker["threads_index"] = 0
        current_index = 0

    # Get next post
    post_content = content_queue[current_index]
    text = post_content["text"]
    category = post_content.get("category", "unknown")
    
    print(f"--- Posting #{current_index + 1}/{len(content_queue)} ---")
    print(f"Category: {category}")
    print(f"Text: {text[:100]}...")
    print()

    # Post to Threads
    try:
        post_id = post_to_threads(text)
        
        # Update tracker
        tracker["threads_index"] = current_index + 1
        tracker["posted"].append({
            "platform": "threads",
            "index": current_index,
            "post_id": post_id,
            "category": category,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        })
        save_tracker(tracker)
        print(f"\nSuccess! Tracker updated. Next post index: {current_index + 1}")
        
    except requests.exceptions.HTTPError as e:
        print(f"ERROR posting to Threads: {e}")
        if e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        else:
            print("Response: No response object")
        exit(1)


if __name__ == "__main__":
    main()
