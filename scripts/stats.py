#!/usr/bin/env python3
"""Generate profile stat cards (public + private) as SVGs in assets/.

Only aggregate numbers and language names are written out; no repo names.
Needs GH_TOKEN with read access to your private repos.
"""
import datetime as dt
import json
import os
import urllib.request
from html import escape

TOKEN = os.environ["GH_TOKEN"]
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")
# Languages that are mostly generated bulk and would drown out real code.
EXCLUDE_LANGS = {"Jupyter Notebook"}
TOP_LANGS = 8

BG, BORDER, TITLE, TEXT, ICON, MUTED = "#1a1b27", "#1a1b27", "#70a5fd", "#38bdae", "#bf91f3", "#a9b1d6"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif"


def gql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if body.get("errors"):
        raise SystemExit(body["errors"])
    return body["data"]


def fetch():
    v = gql("""{ viewer { login name createdAt
        pullRequests { totalCount } issues { totalCount }
        contributionsCollection { contributionYears } } }""")["viewer"]

    repos, cursor = [], None
    while True:
        page = gql("""query($after: String) { viewer {
            repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
              pageInfo { hasNextPage endCursor }
              nodes { stargazerCount
                languages(first: 20) { edges { size node { name color } } } } } } }""",
                   after=cursor)["viewer"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    commits, days = 0, {}
    for year in v["contributionsCollection"]["contributionYears"]:
        c = gql("""query($from: DateTime!, $to: DateTime!) { viewer {
            contributionsCollection(from: $from, to: $to) {
              totalCommitContributions restrictedContributionsCount
              contributionCalendar { weeks { contributionDays { date contributionCount } } } } } }""",
                **{"from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})["viewer"]["contributionsCollection"]
        commits += c["totalCommitContributions"]
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    langs = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name in EXCLUDE_LANGS:
                continue
            size, color = langs.get(name, (0, e["node"]["color"] or "#888"))
            langs[name] = (size + e["size"], color)

    return {
        "name": v["name"] or v["login"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": len(repos),
        "commits": commits,
        "prs": v["pullRequests"]["totalCount"],
        "issues": v["issues"]["totalCount"],
        "langs": langs,
        "days": days,
    }


def streaks(days):
    today = dt.date.today()
    dates = sorted(d for d in days if dt.date.fromisoformat(d) <= today)
    total = sum(days[d] for d in dates)
    longest = (0, None, None)
    run, start = 0, None
    for d in dates:
        if days[d]:
            if run == 0:
                start = d
            run += 1
            if run > longest[0]:
                longest = (run, start, d)
        else:
            run = 0
    # Today with no activity yet doesn't break the current streak.
    cur, i = 0, len(dates) - 1
    if i >= 0 and days[dates[i]] == 0:
        i -= 1
    end = dates[i] if i >= 0 else None
    while i >= 0 and days[dates[i]]:
        cur, i = cur + 1, i - 1
    cur_start = dates[i + 1] if cur else None
    first = next((d for d in dates if days[d]), None)
    return total, first, (cur, cur_start, end if cur else None), longest


def fmt(d):
    return dt.date.fromisoformat(d).strftime("%b %-d, %Y") if d else "—"


def card(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<style>text{{font-family:{FONT}}} .fade{{opacity:0;animation:f .6s ease-in-out forwards}}'
            f'@keyframes f{{to{{opacity:1}}}}</style>'
            f'<rect x="0.5" y="0.5" rx="6" width="{w-1}" height="{h-1}" fill="{BG}" stroke="{BORDER}"/>{body}</svg>')


ICONS = {  # 16x16 octicon paths
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z",
    "commit": "M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z",
    "pr": "M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354Z",
    "issue": "M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z",
    "repo": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z",
}


def stats_card(s):
    rows = [("star", "Total Stars", s["stars"]), ("commit", "Total Commits", s["commits"]),
            ("pr", "Pull Requests", s["prs"]), ("issue", "Issues", s["issues"]),
            ("repo", "Repositories", s["repos"])]
    body = f'<text x="25" y="35" fill="{TITLE}" font-size="18" font-weight="600">{escape(s["name"])}\'s GitHub Stats</text>'
    for i, (icon, label, val) in enumerate(rows):
        y = 62 + i * 25
        body += (f'<g class="fade" style="animation-delay:{150 + i*150}ms" transform="translate(25,{y})">'
                 f'<path transform="translate(0,-12)" fill="{ICON}" d="{ICONS[icon]}"/>'
                 f'<text x="25" y="0" fill="{TEXT}" font-size="14" font-weight="600">{label}:</text>'
                 f'<text x="190" y="0" fill="{TEXT}" font-size="14" font-weight="700">{val:,}</text></g>')
    body += (f'<text x="25" y="186" fill="{MUTED}" font-size="10" opacity=".7">'
             f'Includes private repositories</text>')
    return card(400, 200, body)


def langs_card(langs):
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:TOP_LANGS]
    total = sum(v[0] for _, v in top) or 1
    body = f'<text x="25" y="35" fill="{TITLE}" font-size="18" font-weight="600">Most Used Languages</text>'
    body += '<mask id="m"><rect x="25" y="52" width="250" height="8" rx="4" fill="white"/></mask><g mask="url(#m)">'
    x = 25.0
    for name, (size, color) in top:
        w = 250 * size / total
        body += f'<rect x="{x:.2f}" y="52" width="{w + .5:.2f}" height="8" fill="{color}"/>'
        x += w
    body += "</g>"
    for i, (name, (size, color)) in enumerate(top):
        col, row = i % 2, i // 2
        gx, gy = 25 + col * 135, 85 + row * 25
        body += (f'<g class="fade" style="animation-delay:{150 + i*100}ms" transform="translate({gx},{gy})">'
                 f'<circle cx="5" cy="-4" r="5" fill="{color}"/>'
                 f'<text x="15" y="0" fill="{MUTED}" font-size="11">{escape(name)} {100*size/total:.1f}%</text></g>')
    return card(300, 200, body)


def streak_card(days):
    total, first, cur, longest = streaks(days)
    cols = [(total, "Total Contributions", f"{fmt(first)} – Present", TEXT),
            (cur[0], "Current Streak", f"{fmt(cur[1])} – {fmt(cur[2])}" if cur[0] else "Start one today!", ICON),
            (longest[0], "Longest Streak", f"{fmt(longest[1])} – {fmt(longest[2])}" if longest[0] else "—", TEXT)]
    body = ""
    for i, (n, label, sub, color) in enumerate(cols):
        cx = 117 + i * 233
        if i:
            body += f'<line x1="{cx-116}" y1="28" x2="{cx-116}" y2="172" stroke="{MUTED}" stroke-opacity=".25"/>'
        if i == 1:
            body += f'<circle cx="{cx}" cy="72" r="40" fill="none" stroke="{ICON}" stroke-width="5"/>'
        body += (f'<g class="fade" style="animation-delay:{200 + i*200}ms">'
                 f'<text x="{cx}" y="{84 if i == 1 else 84}" text-anchor="middle" fill="{color}" font-size="28" font-weight="700">{n:,}</text>'
                 f'<text x="{cx}" y="{140}" text-anchor="middle" fill="{color}" font-size="14" font-weight="600">{label}</text>'
                 f'<text x="{cx}" y="{162}" text-anchor="middle" fill="{MUTED}" font-size="11" opacity=".8">{sub}</text></g>')
    return card(700, 195, body)


def main():
    s = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, svg in [("stats.svg", stats_card(s)), ("languages.svg", langs_card(s["langs"])),
                      ("streak.svg", streak_card(s["days"]))]:
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg)
    print(json.dumps({k: v for k, v in s.items() if k not in ("days", "langs")}))
    top = sorted(s["langs"].items(), key=lambda kv: -kv[1][0])[:TOP_LANGS]
    print([n for n, _ in top])


if __name__ == "__main__":
    main()
