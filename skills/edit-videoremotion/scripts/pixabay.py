#!/usr/bin/env python3
"""Pixabay helper for the edit-videoremotion skill (fallback when the Pixabay MCP is not installed).

The API key is read from (in order):
  1. env var PIXABAY_API_KEY
  2. ~/.config/research-analytics-mcp/.env  (line: PIXABAY_API_KEY=xxxx)
It is never printed and never passed on the command line.

Usage (run with python3 -I):
  pixabay.py videos "<query>" [--orientation vertical|horizontal|all] [-n 10] [--min-height 1080]
  pixabay.py images "<query>" [--orientation vertical|horizontal|all] [-n 10]
  pixabay.py download <url> <output-path>
  pixabay.py check
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ENV_FILE = pathlib.Path.home() / ".config" / "research-analytics-mcp" / ".env"
UA = "research-analytics-mcp-media/1.0"


def load_key():
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("PIXABAY_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit(
        "PIXABAY_API_KEY tidak ditemukan. Set env var PIXABAY_API_KEY atau tulis\n"
        f"  PIXABAY_API_KEY=<kunci>\nke {ENV_FILE} (chmod 600). Lihat references/setup-mcp.md."
    )


def call(endpoint, params):
    params = dict(params, key=load_key())
    url = endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        sys.exit(f"Pixabay API error {e.code}: {body}")


def fmt_size(n):
    return f"{n / 1_000_000:.1f} MB" if n else "?"


def videos(a):
    data = call(
        "https://pixabay.com/api/videos/",
        {"q": a.query, "per_page": max(3, min(200, a.n * 3)), "safesearch": "true",
         "min_height": a.min_height, "order": "popular"},
    )
    out = []
    for h in data.get("hits", []):
        v = h["videos"]
        best = next((v[k] for k in ("large", "medium", "small") if v.get(k, {}).get("url")), None)
        if not best:
            continue
        w, ht = best["width"], best["height"]
        if a.orientation == "vertical" and ht <= w:
            continue
        if a.orientation == "horizontal" and w <= ht:
            continue
        out.append({"id": h["id"], "duration_s": h["duration"], "res": f"{w}x{ht}",
                    "size": fmt_size(best.get("size")), "tags": h["tags"], "user": h["user"],
                    "page": h["pageURL"], "download": best["url"],
                    "thumbnail": best.get("thumbnail", "")})
        if len(out) >= a.n:
            break
    print(json.dumps({"total": data.get("totalHits", 0), "shown": len(out), "hits": out},
                     indent=2, ensure_ascii=False))


def images(a):
    data = call(
        "https://pixabay.com/api/",
        {"q": a.query, "per_page": max(3, min(200, a.n)), "safesearch": "true",
         "image_type": "photo", "orientation": a.orientation, "order": "popular"},
    )
    out = [{"id": h["id"], "res": f'{h["imageWidth"]}x{h["imageHeight"]}', "tags": h["tags"],
            "user": h["user"], "page": h["pageURL"], "download": h["largeImageURL"],
            "preview": h["webformatURL"]} for h in data.get("hits", [])[: a.n]]
    print(json.dumps({"total": data.get("totalHits", 0), "shown": len(out), "hits": out},
                     indent=2, ensure_ascii=False))


def download(a):
    host = urllib.parse.urlparse(a.url).hostname or ""
    if not (host == "pixabay.com" or host.endswith(".pixabay.com")):
        sys.exit(f"Menolak: URL bukan dari pixabay.com ({host})")
    dest = pathlib.Path(a.output)
    if dest.exists():
        sys.exit(f"Sudah ada, tidak ditimpa: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(a.url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    print(f"OK {dest} ({fmt_size(dest.stat().st_size)})")


def check(_):
    call("https://pixabay.com/api/", {"q": "test", "per_page": 3})
    print("Kunci Pixabay valid.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("videos", videos), ("images", images)):
        s = sub.add_parser(name)
        s.add_argument("query")
        s.add_argument("--orientation", default="all", choices=["all", "vertical", "horizontal"])
        s.add_argument("-n", type=int, default=8)
        if name == "videos":
            s.add_argument("--min-height", type=int, default=0)
        s.set_defaults(fn=fn)
    d = sub.add_parser("download")
    d.add_argument("url")
    d.add_argument("output")
    d.set_defaults(fn=download)
    sub.add_parser("check").set_defaults(fn=check)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
