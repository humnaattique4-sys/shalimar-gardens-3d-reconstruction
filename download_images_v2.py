# -*- coding: utf-8 -*-
"""
download_images_v2.py -- Charbagh Collective, PMW x TechRealm
===========================================================
Downloads tightly overlapping images of the Moorcroft Pavilion in Shalimar Gardens
using Wikipedia's imageinfo API to fetch 1280px thumbnail URLs, bypassing direct rate limits.
"""

import os, sys, time, json, re
import urllib.request, urllib.parse, urllib.error

BASE        = r"C:\Users\DELL\OneDrive\Desktop\New folder"
OUTPUT_DIR  = os.path.join(BASE, "images_v2")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

TITLES = [
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore- By @ibneazhar 2016 4.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore By @ibneazhar 2016 2.jpg",
    "File:Entrance of Moorcroft Pavilion, Shalimar Gardens, Lahore.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore- By @ibneazhar Sep 2016 2.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore- By @ibneazhar 2016 5.jpg",
    "File:Moorcroft Pavilion, Shalimar Gardens, Lahore.jpg",
    "File:Moorcroft Pavilion - Shalimar bagh.jpg",
    "File:Western Facade of Moorcroft Pavilion, Shalimar Gardens, Lahore.jpg",
    "File:Moorcroft Pavilion at Shalimar Gardens.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens By @ibneazhar 2016.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens By @ibneazhar 2016 8.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore- By @ibneazhar 2016.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore By @ibneazhar 2016 1.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore- By @ibneazhar 2016 7.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore- By @ibneazhar Sep 2016 (111).jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore By @ibneazhar 2016 3.jpg",
    "File:Moorcroft Pavilion - Shalimar Gardens Lahore By @ibneazhar 2016 5.jpg",
    "File:Moorcroft Pavilion - Shalamar Garden 2005 - A baradari on the first level.jpg",
    "File:Pakistan- Shalimar Gardens Lahore- By @ibneazhar Sep 2016 (102).jpg"
]

def wiki_api(params: dict) -> dict:
    params["format"] = "json"
    params["formatversion"] = "2"
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())

def get_thumbnail_urls(titles: list[str]) -> dict[str, str]:
    """Queries Wikimedia API for 1280px thumbnail URLs."""
    urls = {}
    # Process in batches of 10 to avoid URI too long
    for i in range(0, len(titles), 10):
        batch = titles[i:i+10]
        try:
            res = wiki_api({
                "action": "query",
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 1280,
                "titles": "|".join(batch)
            })
            pages = res.get("query", {}).get("pages", [])
            for page in pages:
                title = page.get("title")
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    # Prefer thumbnail URL (responsive to iiurlwidth), fallback to original url
                    thumb_url = imageinfo[0].get("thumburl") or imageinfo[0].get("url")
                    if thumb_url:
                        urls[title] = thumb_url
        except Exception as e:
            print(f"  [API Error] batch {i}: {e}")
    return urls

def safe_name(title: str) -> str:
    n = title.replace("File:","").replace(" ","_")
    n = n.strip("'\"")
    n = re.sub(r"[^\w.\-]","",n)
    if len(n) > 100:
        ext = n.rsplit(".",1)[-1] if "." in n else "jpg"
        n = n[:90]+"."+ext
    return n

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("="*65)
    print("  Moorcroft Pavilion Image Downloader - Shalimar Gardens V2")
    print("  PMW x TechRealm | Heritage Preservation, Lahore")
    print("  Mode   : Wikipedia Imageinfo API (1280px thumbnails)")
    print("="*65)

    print("\nFetching image metadata from Wikipedia API...")
    thumb_urls = get_thumbnail_urls(TITLES)
    print(f"Found metadata for {len(thumb_urls)} of {len(TITLES)} files.\n")

    downloaded = 0
    skipped = 0

    for title in TITLES:
        fname = safe_name(title)
        dest = os.path.join(OUTPUT_DIR, fname)

        if os.path.exists(dest):
            print(f"  [SKIP] {fname} (already downloaded)")
            skipped += 1
            continue

        url = thumb_urls.get(title)
        if not url:
            # Try cleaning title quotes
            alt_title = title.replace("'", "")
            url = thumb_urls.get(alt_title)
            if not url:
                print(f"  [FAIL] No metadata URL found for: {title}")
                skipped += 1
                continue

        disp = fname[:55] if len(fname) <= 55 else fname[:52]+"..."
        print(f"  [DL]  {disp:<55}", end=" ", flush=True)

        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            with open(dest, "wb") as f:
                f.write(raw)
            print(f"-> OK ({len(raw)//1024} KB)")
            downloaded += 1
            time.sleep(1.0) # Polite delay
        except Exception as e:
            print(f"-> FAIL: {e}")
            skipped += 1

    print("\n"+"="*65)
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped:    {skipped}")
    print(f"  Total:      {len(os.listdir(OUTPUT_DIR))}")
    print("="*65)

if __name__ == "__main__":
    main()
