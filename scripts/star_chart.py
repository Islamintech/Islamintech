#!/usr/bin/env python3
"""Generate profile/star-chart.svg: a GitHub profile drawn as a star chart.

Projects (pinned repos first, then recent pushes) are stars joined into a
constellation, newest push first,
colored by main language, sized by repo size, and glowing brighter the more
recently they were pushed. A side panel shows the language mix and activity.

Standard library only. Needs GITHUB_TOKEN (the Actions token is enough) and
GITHUB_USER. Run with --sample to render from built-in demo data offline.
"""
import json
import math
import os
import random
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape

API = "https://api.github.com"
OUT = os.environ.get("STAR_CHART_OUT", "profile/star-chart.svg")
HIDE_LANGS = {"Jupyter Notebook"}  # notebook outputs inflate byte counts
MAX_STARS = 8

LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5",
    "CSS": "#8a63d2", "SCSS": "#c6538c", "HTML": "#e34c26", "C++": "#f34b7d",
    "C": "#8f9aa8", "Jupyter Notebook": "#DA5B0B", "Dockerfile": "#5b7d8f",
    "Shell": "#89e051", "Go": "#00ADD8", "Java": "#b07219", "Kotlin": "#A97BFF",
    "Dart": "#00B4AB", "Rust": "#dea584", "PLpgSQL": "#336790",
}
DEFAULT_COLOR = "#9fb3c8"

W, H = 840, 430


# ── data ─────────────────────────────────────────────────────────────────────
def _req(url, token, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "star-chart"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch(user, token):
    profile = _req(f"{API}/users/{user}", token)
    repos = []
    page = 1
    while True:
        batch = _req(f"{API}/users/{user}/repos?per_page=100&type=owner&page={page}", token)
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    repos = [r for r in repos if not r["fork"] and not r["private"] and r["name"].lower() != user.lower()]

    lang_bytes = {}
    for r in repos:
        for lang, n in _req(r["languages_url"], token).items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + n

    year = datetime.now(timezone.utc).year
    commits = None
    pinned = []
    try:
        q = {"query": "query($u:String!,$f:DateTime!){user(login:$u){pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{name}}} contributionsCollection(from:$f){totalCommitContributions contributionCalendar{totalContributions}}}}",
             "variables": {"u": user, "f": f"{year}-01-01T00:00:00Z"}}
        gu = _req(f"{API}/graphql", token, q)["data"]["user"]
        pinned = [n["name"] for n in gu["pinnedItems"]["nodes"] if n]
        cc = gu["contributionsCollection"]
        commits = cc["totalCommitContributions"]
        contributions = cc["contributionCalendar"]["totalContributions"]
    except Exception as e:  # stats are a nice-to-have; never fail the card
        print("contributions lookup failed:", e, file=sys.stderr)
        contributions = None

    return {
        "login": profile["login"],
        "name": profile.get("name") or profile["login"],
        "location": profile.get("location") or "",
        "repos": [{"name": r["name"], "language": r.get("language"), "size": r.get("size", 0),
                   "pushed_at": r["pushed_at"], "stars": r.get("stargazers_count", 0)} for r in repos],
        "lang_bytes": lang_bytes,
        "pinned": pinned,
        "commits": commits,
        "contributions": contributions,
        "year": year,
    }


def sample():
    now = datetime.now(timezone.utc)
    def ago(d):
        return datetime.fromtimestamp(now.timestamp() - d * 86400, timezone.utc).isoformat()
    return {
        "login": "Islamintech", "name": "Islombek (Islam)", "location": "Seoul, South Korea",
        "repos": [
            {"name": "vivora", "language": "TypeScript", "size": 9000, "pushed_at": ago(1), "stars": 0},
            {"name": "qalqon", "language": "Python", "size": 2500, "pushed_at": ago(3), "stars": 0},
            {"name": "cake-hh", "language": "TypeScript", "size": 3100, "pushed_at": ago(12), "stars": 0},
            {"name": "auction-react", "language": "TypeScript", "size": 4000, "pushed_at": ago(30), "stars": 0},
            {"name": "visa-checker", "language": "JavaScript", "size": 600, "pushed_at": ago(60), "stars": 0},
            {"name": "computer_vision", "language": "Jupyter Notebook", "size": 12000, "pushed_at": ago(90), "stars": 0},
            {"name": "AI", "language": "Jupyter Notebook", "size": 3000, "pushed_at": ago(40), "stars": 0},
            {"name": "Snake-Game-C-", "language": "C++", "size": 400, "pushed_at": ago(150), "stars": 0},
            {"name": "zoo", "language": "TypeScript", "size": 300, "pushed_at": ago(200), "stars": 0},
        ],
        "pinned": ["vivora", "qalqon", "visa-checker", "auction-react", "cake-hh", "computer_vision"],
        "lang_bytes": {"TypeScript": 590, "Python": 265, "CSS": 82, "JavaScript": 42, "C++": 16, "Jupyter Notebook": 900},
        "commits": 324, "contributions": 1373, "year": now.year,
    }


# ── helpers ──────────────────────────────────────────────────────────────────
def days_since(iso):
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / 86400)


def rel(d):
    if d < 1:
        return "today"
    if d < 2:
        return "yesterday"
    if d < 31:
        return f"{int(d)}d ago"
    if d < 365:
        return f"{int(d // 30)}mo ago"
    return f"{int(d // 365)}y ago"


def color(lang):
    return LANG_COLORS.get(lang or "", DEFAULT_COLOR)


# Hand-placed anchor points inside the chart area so any 3-8 stars read as a
# constellation rather than a scatter. Order = most recent push first.
ANCHORS = [(150, 160), (268, 125), (378, 178), (478, 132),
           (430, 272), (300, 298), (172, 268), (78, 330)]


# ── render ───────────────────────────────────────────────────────────────────
def render(d):
    rnd = random.Random(d["login"])
    # pinned repos always shine; remaining slots go to the most recent pushes
    by_recent = sorted(d["repos"], key=lambda r: r["pushed_at"], reverse=True)
    pinned = set(d.get("pinned") or [])
    chosen = [r for r in by_recent if r["name"] in pinned]
    chosen += [r for r in by_recent if r["name"] not in pinned][:max(0, MAX_STARS - len(chosen))]
    repos = sorted(chosen, key=lambda r: r["pushed_at"], reverse=True)
    o = []
    add = o.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{escape(d["name"])} star chart">')
    add('<title>' + escape(d["name"]) + ' — projects as a constellation</title>')
    add("""<defs>
  <radialGradient id="sky" cx="30%" cy="35%" r="85%">
    <stop offset="0" stop-color="#1a1f4a"/><stop offset=".55" stop-color="#0c1030"/><stop offset="1" stop-color="#05060f"/>
  </radialGradient>
  <radialGradient id="neb" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="#7b5cff" stop-opacity=".22"/><stop offset="1" stop-color="#7b5cff" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="neb2" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="#22d3ee" stop-opacity=".14"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/>
  </radialGradient>
  <filter id="glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="4"/></filter>
  <linearGradient id="trail" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".9"/></linearGradient>
  <clipPath id="card"><rect width="840" height="430" rx="18"/></clipPath>
</defs>
<style>
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  .sans{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
  .tw{animation:tw 3.6s ease-in-out infinite}
  @keyframes tw{0%,100%{opacity:.25}50%{opacity:1}}
  .line{stroke-dasharray:6 7;animation:flow 14s linear infinite}
  @keyframes flow{to{stroke-dashoffset:-260}}
  .pulse{animation:pulse 2.8s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
  @keyframes pulse{0%,100%{transform:scale(1);opacity:.55}50%{transform:scale(1.35);opacity:1}}
  .comet{animation:comet 9s ease-in infinite}
  @keyframes comet{0%{transform:translate(0,0);opacity:0}4%{opacity:1}16%{transform:translate(420px,170px);opacity:0}100%{transform:translate(420px,170px);opacity:0}}
  .bar{animation:grow 1.4s ease-out both;transform-box:fill-box;transform-origin:left}
  @keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
</style>""")
    add('<g clip-path="url(#card)">')
    add(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')
    add('<ellipse cx="300" cy="215" rx="260" ry="150" fill="url(#neb)"/>')
    add('<ellipse cx="470" cy="300" rx="180" ry="110" fill="url(#neb2)"/>')

    # background stars
    for i in range(110):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.choice([0.5, 0.6, 0.8, 1.0, 1.3])
        delay = rnd.uniform(0, 3.6)
        cls = ' class="tw"' if i % 3 == 0 else ""
        add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#dfe7ff" opacity="{rnd.uniform(.25,.8):.2f}"{cls} '
            f'style="animation-delay:{delay:.2f}s"/>')

    # comet
    add('<g class="comet"><line x1="-90" y1="-36" x2="0" y2="0" stroke="url(#trail)" stroke-width="1.6" '
        'transform="translate(330,70)"/><circle cx="330" cy="70" r="1.8" fill="#fff"/></g>')

    # header
    add(f'<text x="28" y="40" class="mono" font-size="11" letter-spacing="2.5" fill="#8fa3d9">'
        f'STAR CHART · @{escape(d["login"].upper())}</text>')
    add(f'<text x="28" y="66" class="sans" font-size="22" font-weight="700" fill="#f4f6ff">{escape(d["name"])}</text>')

    # grid circles (chart feel)
    add('<g fill="none" stroke="#8fa3d9" stroke-opacity=".10">'
        '<circle cx="290" cy="225" r="90"/><circle cx="290" cy="225" r="160"/><circle cx="290" cy="225" r="230"/>'
        '<line x1="290" y1="80" x2="290" y2="410"/><line x1="40" y1="225" x2="540" y2="225"/></g>')

    pts = ANCHORS[:len(repos)]
    # constellation lines
    if len(pts) > 1:
        path = "M" + " L".join(f"{x},{y}" for x, y in pts)
        add(f'<path d="{path}" fill="none" stroke="#c9d6ff" stroke-opacity=".45" stroke-width="1.2" class="line"/>')

    max_size = max([r["size"] for r in repos] + [1])
    for i, (r, (x, y)) in enumerate(zip(repos, pts)):
        age = days_since(r["pushed_at"])
        bright = max(0.35, 1 - math.log10(1 + age) / 2.6)  # today≈1, ~1y≈0.35
        rad = 4.5 + 5 * math.sqrt(r["size"] / max_size)
        c = color(r["language"])
        add(f'<circle cx="{x}" cy="{y}" r="{rad*2.6:.1f}" fill="{c}" opacity="{bright*.55:.2f}" filter="url(#glow)"/>')
        cls = ' class="pulse"' if i == 0 else ""
        add(f'<circle cx="{x}" cy="{y}" r="{rad:.1f}" fill="{c}" stroke="#fff" stroke-opacity="{bright:.2f}" '
            f'stroke-width="1.2"{cls}/>')
        add(f'<circle cx="{x}" cy="{y}" r="{max(1.2, rad*.35):.1f}" fill="#fff" opacity="{bright:.2f}"/>')
        # name + meta both above the star in the top half, both below in the bottom half
        if y < 225:
            name_y, meta_y = y - rad - 20, y - rad - 8
        else:
            name_y, meta_y = y + rad + 18, y + rad + 30
        add(f'<text x="{x}" y="{name_y:.0f}" text-anchor="middle" class="mono" font-size="11.5" font-weight="600" '
            f'fill="#eef2ff" stroke="#070a1c" stroke-width="3" paint-order="stroke" '
            f'opacity="{0.6 + 0.4*bright:.2f}">{escape(r["name"])}</text>')
        add(f'<text x="{x}" y="{meta_y:.0f}" text-anchor="middle" class="mono" font-size="9" fill="{c}" '
            f'stroke="#070a1c" stroke-width="3" paint-order="stroke" '
            f'opacity="{0.55 + 0.45*bright:.2f}">{escape(r["language"] or "—")} · {rel(age)}</text>')

    # side panel
    px = 560
    add(f'<rect x="{px}" y="24" width="256" height="382" rx="14" fill="#0b0f2a" fill-opacity=".72" '
        f'stroke="#8fa3d9" stroke-opacity=".18"/>')
    add(f'<text x="{px+20}" y="54" class="mono" font-size="10" letter-spacing="2" fill="#8fa3d9">LANGUAGE MIX</text>')
    langs = {k: v for k, v in d["lang_bytes"].items() if k not in HIDE_LANGS}
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:5]
    y = 78
    for i, (lang, n) in enumerate(top):
        pct = 100 * n / total
        c = color(lang)
        add(f'<circle cx="{px+25}" cy="{y-4}" r="4" fill="{c}"/>')
        add(f'<text x="{px+36}" y="{y}" class="sans" font-size="12" fill="#e8edff">{escape(lang)}</text>')
        add(f'<text x="{px+236}" y="{y}" text-anchor="end" class="mono" font-size="11" fill="#aab6dd">{pct:.0f}%</text>')
        add(f'<rect x="{px+20}" y="{y+7}" width="216" height="5" rx="2.5" fill="#ffffff" fill-opacity=".07"/>')
        add(f'<rect x="{px+20}" y="{y+7}" width="{max(3, 216*pct/100):.1f}" height="5" rx="2.5" fill="{c}" '
            f'class="bar" style="animation-delay:{0.15*i:.2f}s"/>')
        y += 34

    # stats
    add(f'<line x1="{px+20}" y1="{y-4}" x2="{px+236}" y2="{y-4}" stroke="#8fa3d9" stroke-opacity=".18"/>')
    add(f'<text x="{px+20}" y="{y+20}" class="mono" font-size="10" letter-spacing="2" fill="#8fa3d9">FLIGHT LOG · {d["year"]}</text>')
    latest = repos[0] if repos else None
    stats = [
        ("Public projects", str(len(d["repos"]))),
        ("Commits this year", f'{d["commits"]:,}' if d.get("commits") is not None else "—"),
        ("Contributions", f'{d["contributions"]:,}' if d.get("contributions") is not None else "—"),
        ("Last launch", f'{latest["name"]} · {rel(days_since(latest["pushed_at"]))}' if latest else "—"),
    ]
    sy = y + 44
    for label, val in stats:
        add(f'<text x="{px+20}" y="{sy}" class="sans" font-size="12" fill="#aab6dd">{escape(label)}</text>')
        add(f'<text x="{px+236}" y="{sy}" text-anchor="end" class="sans" font-size="12" font-weight="600" '
            f'fill="#f4f6ff">{escape(val)}</text>')
        sy += 22

    # footer
    add(f'<text x="28" y="{H-18}" class="mono" font-size="9.5" fill="#6f7fae">'
        f'stars = projects · color = language · brightness = recent pushes · updated daily</text>')
    add('</g></svg>')
    return "\n".join(o)


def main():
    if "--sample" in sys.argv:
        d = sample()
    else:
        user = os.environ.get("GITHUB_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER")
        if not user:
            sys.exit("Set GITHUB_USER")
        d = fetch(user, os.environ.get("GITHUB_TOKEN"))
        if os.environ.get("DISPLAY_NAME"):
            d["name"] = os.environ["DISPLAY_NAME"]
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(d))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
