"""
Analyze performance of published Threads posts using the Meta Threads API.
Fetches metrics (likes, replies, reposts, quotes), updates tracker.json,
and generates a performance report.

Usage:
    python autopost/analyze_performance.py

Environment Variables:
    THREADS_ACCESS_TOKEN - API token with threads_manage_insights permission.
    MOCK_MODE           - Set to 'true' to simulate API calls for testing.
"""

import os
import json
import time
import requests
import random
from pathlib import Path

TRACKER_FILE = Path(__file__).parent / "tracker.json"
REPORT_FILE = Path(__file__).parent / "performance_report.md"

THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
MOCK_MODE = os.environ.get("MOCK_MODE", "").lower() == "true"
GRAPH_API_BASE = "https://graph.threads.net/v1.0"


def load_tracker():
    if TRACKER_FILE.exists():
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"threads_index": 0, "x_index": 0, "posted": []}


def save_tracker(tracker):
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)


def fetch_metrics_from_api(post_id):
    """Fetch metrics from Meta Threads API."""
    if MOCK_MODE:
        # Simulate API response for testing
        time.sleep(0.1)
        return {
            "likes": random.randint(0, 50),
            "replies": random.randint(0, 15),
            "reposts": random.randint(0, 8),
            "quotes": random.randint(0, 5),
        }

    url = f"{GRAPH_API_BASE}/{post_id}/insights"
    params = {
        "metric": "likes,replies,reposts,quotes",
        "access_token": THREADS_ACCESS_TOKEN,
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        # Handle case where post/media is deleted or not found
        if response.status_code == 400 or response.status_code == 404:
            print(f"Post {post_id} not found or deleted (Status {response.status_code}). Skipping.")
            return None
            
        response.raise_for_status()
        data = response.json()
        
        metrics = {"likes": 0, "replies": 0, "reposts": 0, "quotes": 0}
        for item in data.get("data", []):
            name = item.get("name")
            if name in metrics:
                # Value is in the first element of 'values' array
                values = item.get("values", [{}])
                if values:
                    metrics[name] = values[0].get("value", 0)
        return metrics
        
    except Exception as e:
        print(f"Error fetching metrics for post {post_id}: {e}")
        return None


def generate_report(posted_items):
    """Generate a Markdown report of post performance."""
    analyzed_posts = [p for p in posted_items if "metrics" in p]
    if not analyzed_posts:
        return "Belum ada data metrik yang dianalisis."

    # Sort by total engagement (likes + replies + reposts + quotes) descending
    for post in analyzed_posts:
        m = post["metrics"]
        post["total_engagement"] = m["likes"] + m["replies"] + m["reposts"] + m["quotes"]

    analyzed_posts.sort(key=lambda x: x["total_engagement"], reverse=True)

    # Calculate aggregate stats
    total_likes = sum(p["metrics"]["likes"] for p in analyzed_posts)
    total_replies = sum(p["metrics"]["replies"] for p in analyzed_posts)
    total_reposts = sum(p["metrics"]["reposts"] for p in analyzed_posts)
    total_quotes = sum(p["metrics"]["quotes"] for p in analyzed_posts)
    total_engagement = total_likes + total_replies + total_reposts + total_quotes

    # Group by category
    category_stats = {}
    for p in analyzed_posts:
        cat = p.get("category", "unknown")
        if cat not in category_stats:
            category_stats[cat] = {"count": 0, "engagement": 0}
        category_stats[cat]["count"] += 1
        category_stats[cat]["engagement"] += p["total_engagement"]

    # Build report content
    lines = [
        "# Laporan Performa Postingan Threads 📈",
        f"Terakhir diperbarui: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "",
        "## Ringkasan Performa (Total)",
        "| Metrik | Jumlah |",
        "|---|---|",
        f"| **Likes** | {total_likes} |",
        f"| **Replies** | {total_replies} |",
        f"| **Reposts** | {total_reposts} |",
        f"| **Quotes** | {total_quotes} |",
        f"| **Total Engagement** | **{total_engagement}** |",
        "",
        "## Performa Berdasarkan Kategori",
        "| Kategori | Jumlah Post | Total Engagement | Rata-rata per Post |",
        "|---|---|---|---|",
    ]

    for cat, stats in sorted(category_stats.items(), key=lambda x: x[1]["engagement"], reverse=True):
        avg = stats["engagement"] / stats["count"] if stats["count"] > 0 else 0
        lines.append(f"| `{cat}` | {stats['count']} | {stats['engagement']} | {avg:.1f} |")

    lines.extend([
        "",
        "## Postingan Terbaik (Top Posts)",
        "Daftar postingan diurutkan berdasarkan interaksi tertinggi:",
        "",
        "| Rank | Post ID | Kategori | Tanggal | Likes | Replies | Reposts | Total |",
        "|---|---|---|---|---|---|---|---|",
    ])

    for i, post in enumerate(analyzed_posts[:15], 1):
        m = post["metrics"]
        # Format date for readability
        date = post["timestamp"].split(" ")[0]
        # Make post ID a link to threads if valid
        post_link = f"[{post['post_id']}](https://www.threads.net/post/{post['post_id']})" if post['post_id'].isdigit() else post['post_id']
        lines.append(
            f"| {i} | {post_link} | `{post['category']}` | {date} | {m['likes']} | {m['replies']} | {m['reposts']} | **{post['total_engagement']}** |"
        )

    report_content = "\n".join(lines)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"Laporan performa disimpan di: {REPORT_FILE}")


def main():
    if not THREADS_ACCESS_TOKEN and not MOCK_MODE:
        print("ERROR: THREADS_ACCESS_TOKEN environment variable is not set.")
        print("Jika ingin menjalankan simulasi pengujian, jalankan dengan MOCK_MODE=true.")
        exit(1)

    print(f"Memulai analisis performa... {'(MOCK MODE AKTIF)' if MOCK_MODE else ''}")
    tracker = load_tracker()
    posted_items = tracker.get("posted", [])

    if not posted_items:
        print("Belum ada postingan yang tercatat di tracker.json.")
        return

    # Find posts to analyze (must have a valid digit-only post_id)
    threads_posts = [p for p in posted_items if p.get("platform") == "threads" and p.get("post_id", "").isdigit()]
    print(f"Menemukan {len(threads_posts)} postingan Threads untuk dianalisis.")

    updated_count = 0
    for idx, post in enumerate(threads_posts, 1):
        post_id = post["post_id"]
        category = post.get("category", "unknown")
        print(f"[{idx}/{len(threads_posts)}] Mengambil data post {post_id} ({category})...")
        
        metrics = fetch_metrics_from_api(post_id)
        if metrics:
            metrics["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            post["metrics"] = metrics
            updated_count += 1
        
        # Sleep to avoid rate limiting (only in real mode)
        if not MOCK_MODE:
            time.sleep(0.5)

    if updated_count > 0:
        save_tracker(tracker)
        print(f"Berhasil memperbarui tracker.json dengan {updated_count} postingan.")

    # Generate Markdown report
    generate_report(posted_items)
    print("Analisis performa selesai.")


if __name__ == "__main__":
    main()
