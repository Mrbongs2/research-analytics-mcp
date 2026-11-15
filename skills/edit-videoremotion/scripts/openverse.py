#!/usr/bin/env python3
"""Openverse helper for the edit-videoremotion skill — free Creative Commons / public-domain
images and audio (api.openverse.org, run by WordPress). No API key needed
(anonymous access is rate-limited, ~20 results per page).

Every file has its OWN license. Default search filter = licenses that allow
commercial use AND modification (cropping/editing in a video). Many still REQUIRE
attribution (CC BY / BY-SA): `download` appends the credit line to
<output-dir>/stock-credits.md automatically — put those credits in the video
description or end card.

Usage (run with python3 -I):
  openverse.py images "<query>" [-n 10] [--aspect wide|tall|square] [--size large|medium|small]
                      [--license commercial|any|pd] [--source flickr,wikimedia,...]
  openverse.py audio  "<query>" [-n 10] [--license commercial|any|pd]
  openverse.py download <image|audio> <openverse-id> <output-path>
  openverse.py check
"""
import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.openverse.org/v1"
UA = "research-analytics-mcp-media/1.0"
MAX_BYTES = 300 * 1024 * 1024
LICENSE_FILTERS = {
    # commercial use + modification allowed (CC0, PDM, BY, BY-SA)
    "commercial": {"license_type": "commercial,modification"},
    # public domain only — no attribution needed
    "pd": {"license": "cc0,pdm"},
    "any": {},
}


def call(path, params=None):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        if e.code == 429:
            sys.exit("Openverse: batas request anonim tercapai (HTTP 429). Tunggu beberapa menit lalu coba lagi.")
        sys.exit(f"Openverse API error {e.code}: {body}")


def license_label(r):
    lic = (r.get("license") or "").upper()
    ver = r.get("license_version") or ""
    if lic in ("CC0", "PDM"):
        return lic
    return f"CC {lic} {ver}".strip()


def needs_attribution(r):
    return (r.get("license") or "").lower() not in ("cc0", "pdm")


def summarize(r, kind):
    item = {
        "id": r["id"],
        "title": r.get("title"),
        "creator": r.get("creator"),
        "license": license_label(r),
        "attribution_required": needs_attribution(r),
        "source": r.get("source"),
        "page": r.get("foreign_landing_url"),
        "filetype": r.get("filetype"),
    }
    if kind == "image":
        item["res"] = f'{r.get("width") or "?"}x{r.get("height") or "?"}'
        item["preview"] = r.get("thumbnail")
    else:
        dur = r.get("duration")
        item["duration_s"] = round(dur / 1000, 1) if dur else None
    return item


def search(kind, a):
    params = {"q": a.query, "page_size": max(1, min(20, a.n)), "mature": "false"}
    params.update(LICENSE_FILTERS[a.license])
    if kind == "image":
        params.update({"aspect_ratio": a.aspect, "size": a.size, "source": a.source})
    data = call(f"/{'images' if kind == 'image' else 'audio'}/", params)
    out = [summarize(r, kind) for r in data.get("results", [])[: a.n]]
    print(json.dumps({"total": data.get("result_count", 0), "shown": len(out), "hits": out},
                     indent=2, ensure_ascii=False))


def download(a):
    kind = a.kind
    # Resolve the file URL from Openverse itself (never from user/page input).
    r = call(f"/{'images' if kind == 'image' else 'audio'}/{urllib.parse.quote(a.id)}/")
    url = r.get("url") or ""
    if urllib.parse.urlparse(url).scheme not in ("https", "http"):
        sys.exit(f"Menolak: URL file tidak valid ({url[:80]})")
    dest = pathlib.Path(a.output)
    if dest.exists():
        sys.exit(f"Sudah ada, tidak ditimpa: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if not ctype.startswith(("image/", "audio/", "application/octet-stream")):
                sys.exit(f"Menolak: tipe file tak terduga ({ctype})")
            total = 0
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                while chunk := resp.read(1 << 20):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        f.close()
                        tmp.unlink(missing_ok=True)
                        sys.exit("Menolak: file lebih dari 300 MB")
                    f.write(chunk)
            tmp.rename(dest)
    except urllib.error.HTTPError as e:
        sys.exit(f"Gagal mengunduh dari sumber asli ({e.code}). Coba hasil lain.")

    credit = r.get("attribution") or (
        f'"{r.get("title")}" by {r.get("creator")} — {license_label(r)} — {r.get("foreign_landing_url")}'
    )
    credits = dest.parent / "stock-credits.md"
    with open(credits, "a") as f:
        f.write(f"- `{dest.name}` — Openverse {kind} {r['id']} — {credit} "
                f"(halaman: {r.get('foreign_landing_url')})\n")
    print(f"OK {dest} ({dest.stat().st_size / 1_000_000:.1f} MB)")
    print(f"Lisensi: {license_label(r)}"
          + (" — WAJIB cantumkan kredit (sudah dicatat di stock-credits.md)" if needs_attribution(r) else " — tanpa atribusi wajib"))


def check(_):
    call("/images/", {"q": "wedding", "page_size": 1})
    print("Openverse bisa diakses (tanpa API key).")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("images")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=10)
    s.add_argument("--aspect", choices=["wide", "tall", "square"])
    s.add_argument("--size", choices=["large", "medium", "small"])
    s.add_argument("--license", default="commercial", choices=list(LICENSE_FILTERS))
    s.add_argument("--source", help="mis. flickr,wikimedia")
    s.set_defaults(fn=lambda a: search("image", a))
    s = sub.add_parser("audio")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=10)
    s.add_argument("--license", default="commercial", choices=list(LICENSE_FILTERS))
    s.set_defaults(fn=lambda a: search("audio", a))
    d = sub.add_parser("download")
    d.add_argument("kind", choices=["image", "audio"])
    d.add_argument("id")
    d.add_argument("output")
    d.set_defaults(fn=download)
    sub.add_parser("check").set_defaults(fn=check)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
