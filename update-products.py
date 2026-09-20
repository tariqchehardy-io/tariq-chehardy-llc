#!/usr/bin/env python3
"""Auto-generate products.json — the public product/release index for the
official Tariq Chehardy LLC site.

Runs inside GitHub Actions. Reads every PUBLIC repo under the account owner,
skips anything listed in products.config.json -> ignore, pulls the latest
release for each repo, and writes products.json. The site renders this file
client-side, so every new confirmed product or code release appears on the
official site automatically once its repo is public.
"""
import json
import os
import sys
import urllib.request

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "tariqchehardy-io")
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HDRS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "tariq-chehardy-llc-product-index",
}
if TOKEN:
    HDRS["Authorization"] = f"Bearer {TOKEN}"


def get(path, optional=False):
    req = urllib.request.Request(API + path, headers=HDRS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if optional and e.code == 404:
            return None
        raise


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "products.config.json"), encoding="utf-8") as f:
        config = json.load(f)
    ignore = set(config.get("ignore", []))
    featured = config.get("featured", [])

    sources = [OWNER, "pokedot-ai"]
    repos = []
    for src in sources:
        page = 1
        while True:
            batch = get(f"/users/{src}/repos?per_page=100&page={page}")
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1

    products = []
    seen = set()
    for repo in repos:
        name = repo.get("name", "")
        full = repo.get("full_name", name)
        if name in ignore or repo.get("fork") or full in seen:
            continue
        seen.add(full)
        release = None
        rel = get(f"/repos/{full}/releases/latest", optional=True)
        if rel:
            release = {
                "tag": rel.get("tag_name", ""),
                "name": rel.get("name") or rel.get("tag_name", ""),
                "published": (rel.get("published_at") or "")[:10],
                "url": rel.get("html_url", ""),
            }
        products.append(
            {
                "name": name,
                "description": (repo.get("description") or "").strip(),
                "url": repo.get("html_url", ""),
                "language": repo.get("language") or "",
                "stars": repo.get("stargazers_count", 0),
                "pushed": (repo.get("pushed_at") or "")[:10],
                "featured": name in featured,
                "release": release,
            }
        )

    # featured first, then most recently active (stable two-pass sort)
    products.sort(key=lambda p: p["pushed"] or "", reverse=True)
    products.sort(key=lambda p: not p["featured"])

    out = {"generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), "products": products}
    with open(os.path.join(base, "products.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote products.json with {len(products)} product(s): " + ", ".join(p["name"] for p in products))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
