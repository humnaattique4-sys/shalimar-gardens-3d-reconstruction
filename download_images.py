# -*- coding: utf-8 -*-
"""
download_images.py -- Charbagh Collective, PMW x TechRealm
===========================================================
Downloads Shalimar Gardens images using:
  - en.wikipedia.org API (not blocked) for file discovery
  - images.weserv.nl proxy to bypass CDN 429/403 rate limits on upload.wikimedia.org
  - Automatic resizing to 1280px via weserv proxy (&w=1280)
  - Super fast downloads with no rate-limiting!
"""

import os, sys, time, hashlib, re, io, json
import urllib.request, urllib.parse, urllib.error

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Config ─────────────────────────────────────────────────────────────────
BASE        = r"C:\Users\DELL\OneDrive\Desktop\New folder"
OUTPUT_DIR  = os.path.join(BASE, "images")
MIN_DIM     = 600       # px minimum shortest side
TARGET      = 42        # total images to collect
THUMB_W     = 1280      # Target width to request from weserv proxy
BASE_DELAY  = 0.5       # Fast delay since proxy handles rate limiting!
EXCLUDED    = {"logo.png", "Logo.png", "logo.PNG"}
HASH_THRESH = 6

# User-Agent representing a modern browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/jpeg,image/png,image/*",
}

# Search queries
SEARCH_QUERIES = [
    "Shalimar Gardens Lahore",
    "Shalimar Bagh Lahore",
    "Shalamar garden Lahore terrace",
    "Shalimar fountain Lahore",
    "Shalimar pavilion Lahore",
    "Shalimar garden walkway",
    "Faiz Bakhsh terrace Shalimar",
    "Hayat Baksh terrace Shalimar",
    "Farah Bakhsh Shalimar",
    "Moorcroft Pavilion Shalimar",
    "Shalimar Bagh entrance Lahore",
    "Lahore Mughal garden UNESCO",
]

# ── Helpers ────────────────────────────────────────────────────────────────

def wiki_api(params: dict) -> dict:
    params["format"] = "json"
    params["formatversion"] = "2"
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def search_file_ns(query: str) -> list[str]:
    try:
        data = wiki_api({"action":"query","list":"search",
                          "srnamespace":"6","srsearch":query,"srlimit":"50"})
        return [h["title"] for h in data.get("query",{}).get("search", [])]
    except Exception as e:
        print(f"  [WARN] Search '{query}': {e}"); return []


def make_original_url(title: str) -> str:
    """Construct original file CDN URL."""
    fname  = title.replace("File:","").replace(" ","_")
    md5    = hashlib.md5(fname.encode("utf-8")).hexdigest()
    enc    = urllib.parse.quote(fname, safe="")
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[:2]}/{enc}"


def make_proxy_url(title: str, width: int = THUMB_W) -> str:
    """Construct a weserv proxy URL that fetches the original and resizes to standard width."""
    orig = make_original_url(title)
    # weserv proxy automatically resizes and caches
    return f"https://images.weserv.nl/?url={urllib.parse.quote(orig)}&w={width}"

# ── Filters ────────────────────────────────────────────────────────────────

def ok_title(title: str) -> bool:
    t = title.lower()
    bad = ("logo","icon","seal","emblem","flag","coat","arms","signature",
           "map","plan","diagram","sketch","drawing","djvu",".svg",".gif",
           ".ogv",".pdf",".webm",".ogg",".djvu")
    return not any(b in t for b in bad)


def ok_pixels(data: bytes) -> bool:
    if not HAS_PIL: return True
    try:
        img = Image.open(io.BytesIO(data))
        return min(img.size) >= MIN_DIM
    except Exception: return False


def safe_name(title: str) -> str:
    n = title.replace("File:","").replace(" ","_")
    n = re.sub(r"[^\w.\-]","",n)
    if len(n) > 100:
        ext = n.rsplit(".",1)[-1] if "." in n else "jpg"
        n = n[:90]+"."+ext
    return n

# ── Download via Proxy ─────────────────────────────────────────────────────

def fetch_via_proxy(title: str, width: int = THUMB_W) -> bytes | None:
    proxy_url = make_proxy_url(title, width)
    try:
        req = urllib.request.Request(proxy_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except Exception as e:
        print(f"  [Proxy Fail] trying direct...", end=" ", flush=True)
        # Try direct fallback
        orig_url = make_original_url(title)
        try:
            req = urllib.request.Request(orig_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e2:
            print(f"  [Direct Fail] {e2}")
            return None

# ── Dedup ──────────────────────────────────────────────────────────────────

def avg_hash(data: bytes, size=8) -> int | None:
    if not HAS_PIL: return None
    try:
        img = Image.open(io.BytesIO(data)).convert("L").resize((size,size),Image.LANCZOS)
        px  = list(img.getdata())
        avg = sum(px)/len(px)
        h = 0
        for p in px: h = (h<<1)|(1 if p>=avg else 0)
        return h
    except Exception: return None

def hamming(a,b):
    x=a^b; d=0
    while x: d+=x&1; x>>=1
    return d

def is_dup(data, hashes, md5s):
    m = hashlib.md5(data).hexdigest()
    if m in md5s: return True
    md5s.add(m)
    h = avg_hash(data)
    if h is not None:
        for sh in hashes:
            if hamming(h,sh)<=HASH_THRESH: return True
        hashes.append(h)
    return False

# ── Main ───────────────────────────────────────────────────────────────────

def count_imgs():
    return sum(1 for f in os.listdir(OUTPUT_DIR)
               if f not in EXCLUDED
               and os.path.splitext(f)[1].lower() in (".jpg",".jpeg",".png",".tif",".tiff",".webp"))

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("="*65)
    print("  Charbagh Collective -- Shalimar Gardens Image Downloader")
    print("  PMW x TechRealm | Heritage Preservation, Lahore")
    print(f"  Output : {OUTPUT_DIR}")
    print(f"  Mode   : images.weserv.nl Proxy + {BASE_DELAY}s delay")
    print("="*65)

    hashes: list[int] = []
    md5s:   set[str]  = set()

    print("\n[PRE-SEED] Hashing existing images in ./images/ ...")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f in EXCLUDED: continue
        if os.path.splitext(f)[1].lower() not in (".jpg",".jpeg",".png",".tif",".tiff",".webp"):
            continue
        fp = os.path.join(OUTPUT_DIR, f)
        try:
            with open(fp,"rb") as fh: raw=fh.read()
            is_dup(raw, hashes, md5s)
            print(f"  Seeded: {f}")
        except Exception: pass

    existing = count_imgs()
    need = max(0, TARGET - existing)
    print(f"\n  Existing images : {existing}")
    print(f"  Need to get     : {need}")
    if need == 0:
        print("  Already at target. Done.")
        return existing

    # ── Step 1: Collect titles ─────────────────────────────────────────
    print("\n[STEP 1] Searching Wikipedia File namespace ...")
    all_titles: set[str] = set()
    for q in SEARCH_QUERIES:
        print(f"  -> {q}")
        for t in search_file_ns(q):
            if ok_title(t):
                all_titles.add(t)
        time.sleep(0.5)

    # Prioritise: put Shalimar-specific titles first
    def priority(t):
        tl = t.lower()
        if "shalimar" in tl or "shalamar" in tl: return 0
        if "lahore" in tl: return 1
        if "mughal" in tl: return 2
        return 3

    title_list = sorted(all_titles, key=priority)
    print(f"\n  Unique file titles found : {len(title_list)}")

    # ── Step 2: Download ───────────────────────────────────────────────
    print(f"\n[STEP 2] Downloading (target: {TARGET} total) ...")
    print(f"  Delay: {BASE_DELAY}s between downloads\n")
    downloaded = 0; skipped = 0

    for title in title_list:
        if count_imgs() >= TARGET:
            print(f"\n  Target of {TARGET} reached."); break

        fname = safe_name(title)
        dest  = os.path.join(OUTPUT_DIR, fname)

        if os.path.exists(dest):
            skipped += 1; continue

        # Shorten display name
        disp = fname[:55] if len(fname) <= 55 else fname[:52]+"..."
        print(f"  [DL]  {disp:<55}", end=" ", flush=True)

        raw = fetch_via_proxy(title)

        if raw is None:
            skipped += 1; continue

        if not ok_pixels(raw):
            print("-> low-res"); skipped += 1; continue

        if is_dup(raw, hashes, md5s):
            print("-> duplicate"); skipped += 1; continue

        with open(dest,"wb") as f: f.write(raw)
        print(f"-> OK ({len(raw)//1024} KB)")
        downloaded += 1
        time.sleep(BASE_DELAY)

    total = count_imgs()
    print("\n"+"="*65)
    print(f"  Downloaded this run : {downloaded}")
    print(f"  Skipped             : {skipped}")
    print(f"  Total in ./images   : {total}  (excl. logo.png)")
    print("="*65)
    return total

if __name__ == "__main__":
    main()
