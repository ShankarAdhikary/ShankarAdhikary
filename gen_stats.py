#!/usr/bin/env python3
"""Render assets/stats.svg from live GitHub API data.

Self-hosted replacement for third-party stats widgets: no external service,
no rate-limited public instance, and the card matches the profile's palette.

Usage:  GITHUB_TOKEN=<token> python scripts/gen_stats.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

USER = os.environ.get("STATS_USER", "adhikaryshankar04")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "stats.svg")
CONTRIB_OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "contributions.svg")

ACID, CYAN, AMBER, VIOLET, RED = "#00ff9f", "#22d3ee", "#ffb020", "#a78bfa", "#ff2e5b"
TEXT, MUTED, DIM = "#eafff6", "#7f9aa8", "#37604f"
MONO = "ui-monospace,'SF Mono','Cascadia Code',Menlo,Consolas,monospace"

QUERY = """
query($login:String!) {
  user(login:$login) {
    followers { totalCount }
    following { totalCount }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false,
                 orderBy:{field:STARGAZERS, direction:DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first:12, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""


def fetch(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": USER + "-profile-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise RuntimeError("GraphQL error: %s" % body["errors"])
    return body["data"]["user"]


def collect(u):
    repos = u["repositories"]["nodes"]
    langs = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = langs.setdefault(name, {"size": 0, "color": edge["node"]["color"] or MUTED})
            entry["size"] += edge["size"]
    total = sum(v["size"] for v in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1]["size"])[:6]
    c = u["contributionsCollection"]
    return {
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": u["followers"]["totalCount"],
        "commits": c["totalCommitContributions"] + c["restrictedContributionsCount"],
        "prs": c["totalPullRequestContributions"],
        "issues": c["totalIssueContributions"],
        "langs": [(n, v["color"], v["size"] * 100.0 / total) for n, v in top],
        "weeks": c["contributionCalendar"]["weeks"],
        "contributions": c["contributionCalendar"]["totalContributions"],
    }


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tile(x, y, label, value, accent):
    return f"""  <g>
    <rect x="{x}" y="{y}" width="180" height="88" rx="8" fill="#08111a" stroke="#14324a"/>
    <rect x="{x}" y="{y}" width="180" height="2.5" rx="1.25" fill="{accent}" opacity="0.8"/>
    <text x="{x + 16}" y="{y + 32}" font-family="{MONO}" font-size="9.5"
          letter-spacing="1.9" fill="{DIM}">{label}</text>
    <text x="{x + 16}" y="{y + 68}" font-family="{MONO}" font-size="28"
          font-weight="700" fill="{TEXT}">{value}</text>
  </g>
"""


def render(d):
    n = lambda v: f"{v:,}"
    tiles = (
        tile(30, 74, "REPOSITORIES", n(d["repos"]), ACID)
        + tile(220, 74, "STARS EARNED", n(d["stars"]), AMBER)
        + tile(410, 74, "FOLLOWERS", n(d["followers"]), CYAN)
        + tile(30, 172, "COMMITS / YR", n(d["commits"]), ACID)
        + tile(220, 172, "PULL REQUESTS", n(d["prs"]), VIOLET)
        + tile(410, 172, "ISSUES", n(d["issues"]), RED)
    )

    bar, legend, cursor = [], [], 640.0
    span = 510.0
    for i, (name, color, pct) in enumerate(d["langs"]):
        w = max(span * pct / 100.0, 2.0)
        bar.append(
            f'    <rect x="{cursor:.1f}" y="118" width="{w:.1f}" height="18" fill="{color}"/>'
        )
        cursor += w
        col, row = i % 2, i // 2
        lx, ly = 640 + col * 262, 176 + row * 26
        legend.append(
            f'  <g><circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>'
            f'<text x="{lx + 18}" y="{ly}" font-family="{MONO}" font-size="11.5" '
            f'fill="{MUTED}">{esc(name)}</text>'
            f'<text x="{lx + 232}" y="{ly}" font-family="{MONO}" font-size="11.5" '
            f'font-weight="700" fill="{TEXT}" text-anchor="end">{pct:.1f}%</text></g>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 290" width="1200" height="290" role="img" aria-label="GitHub statistics for {USER}: {d['repos']} repositories, {d['stars']} stars earned, {d['followers']} followers, {d['commits']} commits in the last year">
<title>{USER} &#183; github telemetry</title>
<defs>
  <linearGradient id="st-bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#060c13"/><stop offset="1" stop-color="#03070c"/>
  </linearGradient>
  <pattern id="st-grid" width="30" height="30" patternUnits="userSpaceOnUse">
    <path d="M30 0 V30 M0 30 H30" stroke="#0a1720" stroke-width="1" fill="none"/>
  </pattern>
  <clipPath id="st-reveal">
    <rect x="640" y="118" width="0" height="18">
      <animate attributeName="width" values="0;{span:.0f};{span:.0f}" keyTimes="0;0.45;1" dur="5s" repeatCount="indefinite"/>
    </rect>
  </clipPath>
</defs>

<rect width="1200" height="290" rx="10" fill="url(#st-bg)" stroke="#132433"/>
<rect width="1200" height="290" rx="10" fill="url(#st-grid)" opacity="0.55"/>

<rect x="30" y="26" width="4" height="16" fill="{ACID}"/>
<text x="46" y="39" font-family="{MONO}" font-size="13" font-weight="700"
      letter-spacing="3.4" fill="{TEXT}">GITHUB TELEMETRY</text>
<text x="266" y="39" font-family="{MONO}" font-size="9.5" letter-spacing="2"
      fill="{DIM}">PULLED LIVE FROM THE GITHUB API</text>
<circle cx="1150" cy="34" r="4" fill="{ACID}">
  <animate attributeName="opacity" values="1;0.2;1" dur="1.8s" repeatCount="indefinite"/>
</circle>
<text x="1136" y="38" font-family="{MONO}" font-size="9.5" letter-spacing="1.8"
      fill="{DIM}" text-anchor="end">SYNCED</text>
<path d="M30 54 H1170" stroke="#123528"/>

{tiles}
<path d="M600 74 V260" stroke="#123528" opacity="0.7"/>

<text x="640" y="98" font-family="{MONO}" font-size="9.5" letter-spacing="1.9"
      fill="{DIM}">LANGUAGE DISTRIBUTION</text>
<rect x="640" y="118" width="{span:.0f}" height="18" rx="4" fill="#0f2229"/>
<g clip-path="url(#st-reveal)">
{chr(10).join(bar)}
</g>
<rect x="640" y="118" width="{span:.0f}" height="18" rx="4" fill="none" stroke="#0a1720"/>

{chr(10).join(legend)}
</svg>
"""


HEAT = ["#0d1a17", "#0b4f37", "#0f8a5c", "#00c97e", "#00ff9f"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

CELL, GAP = 14, 3
STEP = CELL + GAP
GRID_X, GRID_Y = 76, 86


def heat_level(count, peak):
    if count <= 0:
        return 0
    if peak <= 1:
        return 4
    for i, cut in enumerate((0.25, 0.50, 0.75), start=1):
        if count <= peak * cut:
            return i
    return 4


def render_contributions(d):
    weeks = d["weeks"]
    peak = max((day["contributionCount"] for w in weeks for day in w["contributionDays"]), default=0)
    grid_w = len(weeks) * STEP - GAP

    cells, months, last_month, last_label_x = [], [], None, -999
    for wi, week in enumerate(weeks):
        x = GRID_X + wi * STEP
        for day in week["contributionDays"]:
            y = GRID_Y + day["weekday"] * STEP
            fill = HEAT[heat_level(day["contributionCount"], peak)]
            cells.append(
                f'    <rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="3" fill="{fill}"/>'
            )
        first = week["contributionDays"][0]["date"]
        month = int(first[5:7])
        if month != last_month and x - last_label_x >= 46:
            months.append(
                f'  <text x="{x}" y="78" font-family="{MONO}" font-size="9.5" '
                f'letter-spacing="1.4" fill="{DIM}">{MONTHS[month - 1]}</text>'
            )
            last_month, last_label_x = month, x

    day_labels = "".join(
        f'  <text x="66" y="{GRID_Y + wd * STEP + 11}" font-family="{MONO}" font-size="9" '
        f'fill="{DIM}" text-anchor="end">{name}</text>\n'
        for wd, name in ((1, "MON"), (3, "WED"), (5, "FRI"))
    )

    legend_x = GRID_X + grid_w - 168
    legend = "".join(
        f'  <rect x="{legend_x + 46 + i * 18}" y="216" width="{CELL}" height="{CELL}" rx="3" fill="{c}"/>\n'
        for i, c in enumerate(HEAT)
    )

    tile_x, total = 1000, d["contributions"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 250" width="1200" height="250" role="img" aria-label="Contribution grid for {USER}: {total} contributions in the last 12 months">
<title>{USER} &#183; contribution grid</title>
<defs>
  <linearGradient id="cg-bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#060c13"/><stop offset="1" stop-color="#03070c"/>
  </linearGradient>
  <pattern id="cg-grid" width="30" height="30" patternUnits="userSpaceOnUse">
    <path d="M30 0 V30 M0 30 H30" stroke="#0a1720" stroke-width="1" fill="none"/>
  </pattern>
  <clipPath id="cg-reveal">
    <rect x="{GRID_X}" y="{GRID_Y}" width="0" height="{7 * STEP}">
      <animate attributeName="width" values="0;{grid_w};{grid_w}" keyTimes="0;0.42;1" dur="7s" repeatCount="indefinite"/>
    </rect>
  </clipPath>
</defs>

<rect width="1200" height="250" rx="10" fill="url(#cg-bg)" stroke="#132433"/>
<rect width="1200" height="250" rx="10" fill="url(#cg-grid)" opacity="0.55"/>

<rect x="30" y="26" width="4" height="16" fill="{ACID}"/>
<text x="46" y="39" font-family="{MONO}" font-size="13" font-weight="700"
      letter-spacing="3.4" fill="{TEXT}">CONTRIBUTION GRID</text>
<text x="288" y="39" font-family="{MONO}" font-size="9.5" letter-spacing="2"
      fill="{DIM}">ROLLING 12-MONTH WINDOW</text>
<circle cx="1150" cy="34" r="4" fill="{ACID}">
  <animate attributeName="opacity" values="1;0.2;1" dur="1.8s" repeatCount="indefinite"/>
</circle>
<text x="1136" y="38" font-family="{MONO}" font-size="9.5" letter-spacing="1.8"
      fill="{DIM}" text-anchor="end">SYNCED</text>
<path d="M30 54 H1170" stroke="#123528"/>

{chr(10).join(months)}
{day_labels}
<g clip-path="url(#cg-reveal)">
{chr(10).join(cells)}
</g>

<text x="{legend_x}" y="227" font-family="{MONO}" font-size="9.5" letter-spacing="1.4"
      fill="{DIM}">LESS</text>
{legend}<text x="{legend_x + 142}" y="227" font-family="{MONO}" font-size="9.5"
      letter-spacing="1.4" fill="{DIM}">MORE</text>

<rect x="{tile_x}" y="{GRID_Y}" width="170" height="{7 * STEP - GAP}" rx="8"
      fill="#08111a" stroke="#14324a"/>
<rect x="{tile_x}" y="{GRID_Y}" width="170" height="2.5" rx="1.25" fill="{ACID}" opacity="0.8"/>
<text x="{tile_x + 16}" y="{GRID_Y + 30}" font-family="{MONO}" font-size="9.5"
      letter-spacing="1.9" fill="{DIM}">CONTRIBUTIONS</text>
<text x="{tile_x + 16}" y="{GRID_Y + 74}" font-family="{MONO}" font-size="34"
      font-weight="700" fill="{TEXT}">{total:,}</text>
<text x="{tile_x + 16}" y="{GRID_Y + 98}" font-family="{MONO}" font-size="9.5"
      letter-spacing="1.6" fill="{DIM}">LAST 12 MONTHS</text>
</svg>
"""


def write(path, body):
    full = os.path.abspath(path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    print("wrote %s" % full)


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    try:
        data = collect(fetch(token))
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, KeyError) as exc:
        sys.exit("failed to fetch stats: %s" % exc)

    write(OUT, render(data))
    write(CONTRIB_OUT, render_contributions(data))
    print("  repos=%(repos)d stars=%(stars)d followers=%(followers)d "
          "commits=%(commits)d prs=%(prs)d issues=%(issues)d "
          "contributions=%(contributions)d" % data)
    print("  langs=%s" % ", ".join("%s %.1f%%" % (n, p) for n, _, p in data["langs"]))


if __name__ == "__main__":
    main()
