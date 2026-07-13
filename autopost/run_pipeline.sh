#!/bin/bash
# Daily Threads feed scrape → queue regen → push (copas, no Gemini).
# Run by cron at 21:00 UTC (04:00 WIB), 3h before GitHub 00:00 UTC post.
set -euo pipefail
cd /root/sosmedauto/Dilz-ebook || exit 1
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="/root"
export DISPLAY=":10.0"
VENV="autopost/venv/bin/python"
LOG="autopost/pipeline.log"

echo "=== PIPELINE $(date -u) ===" >> "$LOG"
# 1. Scrape For-You feed → append hooks directly to organik-viral-hooks.md
$VENV -u autopost/scrape_threads_feed.py >> "$LOG" 2>&1
# 2. Generate + validate queue → content_queue.json, x_export.txt
$VENV -u autopost/generate_queue.py >> "$LOG" 2>&1
# 3. Commit + push so GitHub 00:00 UTC post picks up new queue
git add marketing/organik-viral-hooks.md autopost/content_queue.json autopost/x_export.txt
git diff --staged --quiet || git commit -m "chore: daily feed scrape + queue regen [skip ci]" >> "$LOG" 2>&1
git push >> "$LOG" 2>&1
echo "=== DONE ===" >> "$LOG"
