"""Henter de nyeste videoene fra YouTube-kanalen og lagrer dem i videos.json.
Kjøres automatisk hver dag av GitHub Actions (se .github/workflows/oppdater-videoer.yml),
eller for hånd med:  python3 oppdater_videoer.py
"""
import json
import re
import html
import urllib.request

CHANNEL_ID = "UC_PqG28Sm1SOlMm27SRq1rQ"
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"

with urllib.request.urlopen(FEED, timeout=30) as r:
    xml = r.read().decode("utf-8")

videos = []
for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
    vid = re.search(r"<yt:videoId>(.*?)</yt:videoId>", entry).group(1)
    title = html.unescape(re.search(r"<title>(.*?)</title>", entry).group(1))
    published = re.search(r"<published>(.*?)</published>", entry).group(1)
    if "/shorts/" in entry:
        continue
    videos.append({"id": vid, "title": title, "published": published})

with open("videos.json", "w", encoding="utf-8") as f:
    json.dump(videos, f, ensure_ascii=False, indent=2)

print(f"Lagret {len(videos)} videoer i videos.json")
