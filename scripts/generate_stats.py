#!/usr/bin/env python3
"""
Generates assets/stats.svg for the profile README.

Talks to the GitHub REST API directly (no third-party stats server, so nothing
to rate-limit or go down), then draws an SVG card in the README's palette.
Standard library only.
"""
import html
import json
import os
import sys
import time
import urllib.parse
import urllib.request

USER = os.environ.get("GH_USER", "Avleen2002")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_PATH", "assets/stats.svg")

# Languages left out of the bar chart (notebooks inflate byte counts a lot).
EXCLUDE_LANGS = {"Jupyter Notebook"}
TOP_N = 6

PALETTE = ["#E3DE7A", "#B9A9E6", "#E8743B", "#E8D5B7", "#6B7A9E", "#8A93B2"]


def api(path, params=None):
    url = "https://api.github.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats-card")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def search_count(kind, query):
    """total_count from a search endpoint; 0 if rate limited."""
    try:
        data = api(f"/search/{kind}", {"q": query, "per_page": 1})
        time.sleep(1.5)  # stay under the unauthenticated search limit
        return int(data.get("total_count", 0))
    except Exception as e:  # noqa: BLE001
        print(f"warning: search {kind} failed: {e}", file=sys.stderr)
        return 0


def fetch_repos():
    repos, page = [], 1
    while True:
        batch = api(f"/users/{USER}/repos", {"per_page": 100, "type": "owner", "page": page})
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def main():
    profile = api(f"/users/{USER}")
    name = (profile.get("name") or USER).split()[0]
    repos = [r for r in fetch_repos() if not r.get("fork")]

    stars = sum(r.get("stargazers_count", 0) for r in repos)
    commits = search_count("commits", f"author:{USER}")
    prs = search_count("issues", f"author:{USER} type:pr")

    langs = {}
    for r in repos:
        try:
            for lang, size in api(f"/repos/{USER}/{r['name']}/languages").items():
                if lang not in EXCLUDE_LANGS:
                    langs[lang] = langs.get(lang, 0) + size
        except Exception as e:  # noqa: BLE001
            print(f"warning: languages for {r['name']} failed: {e}", file=sys.stderr)

    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
    shown_total = sum(v for _, v in top) or 1  # percentages of what is displayed

    stats = [
        ("Public Repos", profile.get("public_repos", len(repos))),
        ("Stars Earned", stars),
        ("Commits (public)", commits),
        ("Pull Requests", prs),
        ("Followers", profile.get("followers", 0)),
    ]

    e = html.escape
    parts = []
    parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 320" width="840" height="320" role="img" aria-label="{e(name)}'s GitHub stats">
  <style>
    .t {{ font-family: Georgia, 'Times New Roman', serif; }}
    .m {{ font-family: 'Courier New', Consolas, monospace; }}
    .fade {{ animation: fade .9s ease-out both; }}
    @keyframes fade {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    .bar {{ transform-box: fill-box; transform-origin: left center; animation: grow 1.1s cubic-bezier(.2,.7,.2,1) both; }}
    @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  </style>
  <rect x="0.5" y="0.5" width="839" height="319" rx="16" fill="#0D1117" stroke="#E3DE7A" stroke-opacity=".2"/>
  <text class="t fade" x="40" y="56" font-size="24" fill="#E3DE7A">{e(name)}'s GitHub Stats</text>
  <text class="t fade" x="430" y="56" font-size="24" fill="#E3DE7A">Most Used Languages</text>
  <rect x="40" y="70" width="330" height="1.5" fill="#E3DE7A" opacity=".25"/>
  <rect x="430" y="70" width="370" height="1.5" fill="#E3DE7A" opacity=".25"/>''')

    for i, (label, value) in enumerate(stats):
        y = 112 + i * 42
        parts.append(
            f'  <text class="m fade" x="40" y="{y}" font-size="15" fill="#AEB6D6" style="animation-delay:{.1 + i * .08:.2f}s">{e(label)}</text>\n'
            f'  <text class="t fade" x="370" y="{y + 1}" font-size="22" font-weight="bold" fill="#F3E6CF" text-anchor="end" style="animation-delay:{.1 + i * .08:.2f}s">{value:,}</text>'
        )

    for i, (lang, size) in enumerate(top):
        y = 112 + i * 36
        pct = size / shown_total * 100
        color = PALETTE[i % len(PALETTE)]
        width = max(4, 170 * pct / 100 / (top[0][1] / shown_total))
        d = f"{.15 + i * .1:.2f}s"
        parts.append(
            f'  <text class="m fade" x="430" y="{y}" font-size="14" fill="#E8D5B7" style="animation-delay:{d}">{e(lang)}</text>\n'
            f'  <rect x="570" y="{y - 11}" width="170" height="10" rx="5" fill="#1A1E30"/>\n'
            f'  <rect class="bar" x="570" y="{y - 11}" width="{width:.1f}" height="10" rx="5" fill="{color}" style="animation-delay:{d}"/>\n'
            f'  <text class="m fade" x="800" y="{y}" font-size="13" fill="#AEB6D6" text-anchor="end" style="animation-delay:{d}">{pct:.1f}%</text>'
        )

    parts.append("</svg>\n")

    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"wrote {OUT}: repos={stats[0][1]} stars={stars} commits={commits} prs={prs} langs={[l for l, _ in top]}")


if __name__ == "__main__":
    main()
