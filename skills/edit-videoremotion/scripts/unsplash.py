#!/usr/bin/env python3
"""Unsplash helper for the edit-videoremotion skill — free HD photos (fallback / scriptable
alternative to the official Unsplash connector at https://mcp.unsplash.com/mcp).

The Access Key is read from (in order):
  1. env var UNSPLASH_ACCESS_KEY
  2. ~/.config/research-analytics-mcp/.env  (line: UNSPLASH_ACCESS_KEY=xxxx)
It is never printed and never passed on the command line.

Unsplash API rules this script follows:
  - downloads go through the photo's `download_location` endpoint (required),
  - files come only from images.unsplash.com,
  - a credit line "Photo by <name> on Unsplash" is appended to
    <output-dir>/stock-credits.md (credit is expected, not legally required).
Demo apps get 50 requests/hour.

Usage (run with python3 -I):
  unsplash.py search "<query>" [-n 10] [--orientation landscape|portrait|squarish]
  unsplash.py download <photo-id> <output-path> [--width 2400]
  unsplash.py check
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.unsplash.com"
UA = "research-analytics-mcp-media/1.0"
KEY_FILES = [
    pathlib.Path.home() / ".config" / "research-analytics-mcp" / ".env",
]
UTM = "utm_source=research_analytics_mcp&utm_medium=referral"


def load_key():
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if key:
        return key
    for f in KEY_FILES:
        if f.exists():
            for line in f.read_text().splitlines():
                line = line.strip()
                if line.startswith("UNSPLASH_ACCESS_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit(
        "UNSPLASH_ACCESS_KEY tidak ditemukan. Jalankan di Terminal:\n"
        "  export UNSPLASH_ACCESS_KEY=... (atau tulis ke ~/.config/research-analytics-mcp/.env, chmod 600)\n"
        "Lihat references/setup-mcp.md bagian Unsplash."
    )


def call(path_or_url, params=None):
    url = path_or_url if path_or_url.startswith("https://") else API + path_or_url
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    host = urllib.parse.urlparse(url).hostname
    if host != "api.unsplash.com":
        sys.exit(f"Menolak: bukan api.unsplash.com ({host})")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Version": "v1",
        "Authorization": f"Client-ID {load_key()}",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            sys.exit("Unsplash menolak Access Key (HTTP 401). Cek lagi key-nya.")
        if e.code == 403:
            sys.exit("Unsplash: batas request per jam tercapai atau akses ditolak (HTTP 403). Coba lagi nanti.")
        sys.exit(f"Unsplash API error {e.code}: {e.read().decode(errors='replace')[:200]}")


def search(a):
    params = {"query": a.query, "per_page": max(1, min(30, a.n)), "content_filter": "high"}
    if a.orientation:
        params["orientation"] = a.orientation
    data = call("/search/photos", params)
    out = [{
        "id": p["id"],
        "res": f'{p["width"]}x{p["height"]}',
        "description": p.get("alt_description") or p.get("description"),
        "photographer": p["user"]["name"],
        "page": p["links"]["html"],
        "preview": p["urls"]["small"],
    } for p in data.get("results", [])[: a.n]]
    print(json.dumps({"total": data.get("total", 0), "shown": len(out), "hits": out},
                     indent=2, ensure_ascii=False))


def download(a):
    photo = call(f"/photos/{urllib.parse.quote(a.id)}")
    # Required by the Unsplash API guidelines: register the download.
    call(photo["links"]["download_location"])
    raw = photo["urls"]["raw"]
    url = raw + ("&" if "?" in raw else "?") + urllib.parse.urlencode(
        {"w": a.width, "q": 90, "fm": "jpg", "fit": "max"})
    host = urllib.parse.urlparse(url).hostname
    if host != "images.unsplash.com":
        sys.exit(f"Menolak: file bukan dari images.unsplash.com ({host})")
    dest = pathlib.Path(a.output)
    if dest.exists():
        sys.exit(f"Sudah ada, tidak ditimpa: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    name = photo["user"]["name"]
    profile = f'{photo["user"]["links"]["html"]}?{UTM}'
    with open(dest.parent / "stock-credits.md", "a") as f:
        f.write(f"- `{dest.name}` — Photo by [{name}]({profile}) on "
                f"[Unsplash](https://unsplash.com/?{UTM}) — {photo['links']['html']}\n")
    print(f"OK {dest} ({dest.stat().st_size / 1_000_000:.1f} MB) — Photo by {name} on Unsplash")


def check(_):
    call("/search/photos", {"query": "wedding", "per_page": 1})
    print("Access Key Unsplash valid.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=10)
    s.add_argument("--orientation", choices=["landscape", "portrait", "squarish"])
    s.set_defaults(fn=search)
    d = sub.add_parser("download")
    d.add_argument("id")
    d.add_argument("output")
    d.add_argument("--width", type=int, default=2400)
    d.set_defaults(fn=download)
    sub.add_parser("check").set_defaults(fn=check)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
