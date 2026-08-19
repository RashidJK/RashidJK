#!/usr/bin/env python3
"""
Generate streak + stats SVG cards from the GitHub API.

Usage:
    GH_TOKEN=xxx GH_USER=yourname python3 scripts/gen_cards.py
    python3 scripts/gen_cards.py --demo      # sample data, no network

Writes assets/streak.svg and assets/stats.svg
"""
import os
import sys
import json
import datetime as dt
import urllib.request

API = "https://api.github.com/graphql"
OUT = "assets"

# ---------------------------------------------------------------- theme
BG_STOPS = [("0%", "#050505"), ("38%", "#141416"),
            ("68%", "#1d1d20"), ("100%", "#0a0a0b")]
ACCENT_A = "#12d6c4"
ACCENT_B = "#49e6d4"
TEXT = "#eafffb"
MUTED = "#43dfcf"
DIM = "#7d8c8a"
BORDER = 0.13
RADIUS = 26
W, H = 494, 195
FONT = "Arial, Helvetica, sans-serif"


# ---------------------------------------------------------------- api
def gql(query, variables, token):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "readme-cards"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


PROFILE_Q = """
query($login:String!){
  user(login:$login){
    createdAt
    followers{totalCount}
    repositories(first:100, ownerAffiliations:OWNER, isFork:false,
                 orderBy:{field:STARGAZERS, direction:DESC}){
      totalCount
      nodes{ stargazerCount }
    }
    pullRequests{totalCount}
    issues{totalCount}
    repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){
      totalCount
    }
  }
}"""

CALENDAR_Q = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from,to:$to){
      totalCommitContributions
      contributionCalendar{
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}"""


def fetch(user, token):
    """Pull profile totals plus a day-by-day contribution history."""
    prof = gql(PROFILE_Q, {"login": user}, token)["user"]
    created = dt.datetime.fromisoformat(prof["createdAt"].replace("Z", "+00:00"))
    today = dt.datetime.now(dt.timezone.utc)

    days, commits = {}, 0
    year = created.year
    while year <= today.year:
        start = max(created, dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc))
        end = min(today, dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
        cc = gql(CALENDAR_Q, {"login": user,
                              "from": start.isoformat(),
                              "to": end.isoformat()}, token)
        cc = cc["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"]
        for wk in cc["contributionCalendar"]["weeks"]:
            for d in wk["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        year += 1

    stars = sum(n["stargazerCount"] for n in prof["repositories"]["nodes"])
    return {
        "days": days,
        "stars": stars,
        "commits": commits,
        "prs": prof["pullRequests"]["totalCount"],
        "issues": prof["issues"]["totalCount"],
        "followers": prof["followers"]["totalCount"],
        "repos": prof["repositories"]["totalCount"],
        "contributed": prof["repositoriesContributedTo"]["totalCount"],
    }


# ---------------------------------------------------------------- streaks
def streaks(days):
    """Return totals plus current and longest run of consecutive active days."""
    if not days:
        return {"total": 0, "current": 0, "longest": 0,
                "first": "", "cur_range": "", "long_range": ""}

    dates = sorted(days)
    total = sum(days.values())

    best = cur = 0
    best_span = cur_span = (None, None)
    prev = None
    for d in dates:
        if days[d] > 0:
            if prev and (dt.date.fromisoformat(d) - dt.date.fromisoformat(prev)).days == 1:
                cur += 1
                cur_span = (cur_span[0], d)
            else:
                cur = 1
                cur_span = (d, d)
            if cur > best:
                best, best_span = cur, cur_span
            prev = d
        else:
            prev = None
            cur = 0
            cur_span = (None, None)

    # A streak stays alive if today is blank but yesterday was not.
    today = dt.date.today()
    last = dt.date.fromisoformat(dates[-1])
    if days.get(dates[-1], 0) == 0 or (today - last).days > 1:
        gap = today - dt.date.fromisoformat(cur_span[1]) if cur_span[1] else None
        if gap is None or gap.days > 1:
            cur, cur_span = 0, (None, None)

    def pretty(iso):
        return dt.date.fromisoformat(iso).strftime("%b %d, %Y").replace(" 0", " ")

    def span(a, b):
        if not a:
            return "—"
        return pretty(a) if a == b else f"{pretty(a)} – {pretty(b)}"

    return {"total": total, "current": cur, "longest": best,
            "first": pretty(dates[0]),
            "cur_range": span(*cur_span),
            "long_range": span(*best_span)}


# ---------------------------------------------------------------- svg
def commas(n):
    return f"{n:,}"


def shell(inner, title):
    stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in BG_STOPS)
    return f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">{stops}</linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{ACCENT_A}"/>
      <stop offset="100%" stop-color="{ACCENT_B}"/>
    </linearGradient>
    <radialGradient id="glow">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.09"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="card"><rect width="{W}" height="{H}" rx="{RADIUS}"/></clipPath>
  </defs>
  <rect width="{W}" height="{H}" rx="{RADIUS}" fill="url(#bg)"/>
  <g clip-path="url(#card)">
    <ellipse cx="{W*0.62}" cy="40" rx="300" ry="150" fill="url(#glow)"/>
  </g>
  <rect x="0.75" y="0.75" width="{W-1.5}" height="{H-1.5}" rx="{RADIUS-0.75}"
        fill="none" stroke="#ffffff" stroke-opacity="{BORDER}"/>
  <g font-family="{FONT}">{inner}</g>
</svg>
'''


def streak_card(s):
    cols = [(82, commas(s["total"]), "TOTAL CONTRIBUTIONS", f"Since {s['first']}"),
            (412, commas(s["longest"]), "LONGEST STREAK", s["long_range"])]
    out = []
    for cx, big, label, sub in cols:
        out.append(f'''
    <text x="{cx}" y="86" fill="{TEXT}" font-size="34" font-weight="800"
          text-anchor="middle">{big}</text>
    <text x="{cx}" y="112" fill="{MUTED}" font-size="9.5" font-weight="700"
          letter-spacing="1.6" text-anchor="middle">{label}</text>
    <text x="{cx}" y="132" fill="{DIM}" font-size="9.5"
          text-anchor="middle">{sub}</text>''')

    for x in (166, 328):
        out.append(f'<path d="M{x} 36 L{x} 159" stroke="#ffffff" '
                   f'stroke-opacity="0.10" stroke-width="1"/>')

    ring_gap = 30  # degrees of arc left open for the flame
    circ = 2 * 3.14159265 * 46
    dash = circ * (1 - ring_gap / 360.0)
    out.append(f'''
    <circle cx="247" cy="82" r="46" fill="none" stroke="url(#accent)"
            stroke-width="3" stroke-linecap="round"
            stroke-dasharray="{dash:.1f} {circ:.1f}"
            transform="rotate(-75 247 82)" opacity="0.9"/>
    <g transform="translate(240,22)">
      <path d="M7 0c1.6 3.1.3 5-1.2 6.6C4 8.4 2.4 10.1 2.4 12.6
               c0 2.9 2.4 5.2 5.2 5.2s5.2-2.3 5.2-5.2c0-1.6-.7-3-1.7-4.2
               .3 1.6-.9 2.6-1.9 2.1C8 9.9 9.4 7.3 8.7 4.6 8.3 2.7 7.4 1.1 7 0Z"
            fill="url(#accent)"/>
    </g>
    <text x="247" y="94" fill="{TEXT}" font-size="36" font-weight="800"
          text-anchor="middle">{s['current']}</text>
    <text x="247" y="150" fill="{MUTED}" font-size="9.5" font-weight="700"
          letter-spacing="1.6" text-anchor="middle">CURRENT STREAK</text>
    <text x="247" y="169" fill="{DIM}" font-size="9.5"
          text-anchor="middle">{s['cur_range']}</text>''')
    return shell("".join(out), "Contribution streak")


ICONS = {
    "star": "M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8z",
    "commit": "M12 7a5 5 0 100 10 5 5 0 000-10zm0-3a8 8 0 017.8 6.5H24v3h-4.2A8 8 0 014.2 13.5H0v-3h4.2A8 8 0 0112 4z",
    "pr": "M6 3a3 3 0 00-1.5 5.6v6.8a3 3 0 101.5.1V8.6A3 3 0 006 3zm12 12.4V9a4 4 0 00-4-4h-1.6l1.8-1.8-1.1-1.1L9.7 5.7l3.4 3.4 1.1-1.1-1.8-1.5H14a2.5 2.5 0 012.5 2.5v6.4a3 3 0 101.5 0z",
    "issue": "M12 2a10 10 0 100 20 10 10 0 000-20zm0 3a1.6 1.6 0 110 3.2A1.6 1.6 0 0112 5zm1.4 13h-2.8v-8h2.8z",
    "people": "M8.5 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zm7 0a3 3 0 100-6 3 3 0 000 6zM8.5 13C4.9 13 2 14.8 2 17v2h13v-2c0-2.2-2.9-4-6.5-4zm7 .5c-.8 0-1.6.1-2.3.3 1.7 1 2.8 2.5 2.8 4.2v1H22v-1.8c0-2.1-2.9-3.7-6.5-3.7z",
    "repo": "M4 2h14a2 2 0 012 2v18l-4-2-4 2-4-2-4 2V4a2 2 0 012-2zm2 4v2h10V6z",
}


def stats_card(d, user):
    rows = [("star", "Total Stars", d["stars"]),
            ("commit", "Total Commits", d["commits"]),
            ("pr", "Pull Requests", d["prs"]),
            ("issue", "Issues Opened", d["issues"]),
            ("repo", "Public Repos", d["repos"]),
            ("people", "Followers", d["followers"])]

    out = [f'''
    <text x="28" y="42" fill="{MUTED}" font-size="13" font-weight="700"
          letter-spacing="2.4">@{user.upper()}</text>
    <text x="28" y="42" fill="{TEXT}" font-size="13" font-weight="700"
          letter-spacing="2.4" opacity="0"> </text>
    <path d="M28 56 H{W-28}" stroke="#ffffff" stroke-opacity="0.10"/>''']

    col_x = [28, 262]
    col_w = 204
    for i, (icon, label, val) in enumerate(rows):
        x = col_x[i % 2]
        y = 88 + (i // 2) * 34
        out.append(f'''
    <g transform="translate({x},{y-12}) scale(0.62)">
      <path d="{ICONS[icon]}" fill="{ACCENT_B}" opacity="0.85"/>
    </g>
    <text x="{x+24}" y="{y}" fill="{DIM}" font-size="12.5">{label}</text>
    <text x="{x+col_w}" y="{y}" fill="{TEXT}" font-size="14" font-weight="700"
          text-anchor="end">{commas(val)}</text>''')
    return shell("".join(out), "GitHub stats")


# ---------------------------------------------------------------- main
DEMO = {"days": {}, "stars": 1284, "commits": 4317, "prs": 268,
        "issues": 143, "followers": 892, "repos": 47, "contributed": 31}


def main():
    demo = "--demo" in sys.argv
    user = os.environ.get("GH_USER", "USERNAME")

    if demo:
        data = dict(DEMO)
        s = {"total": 5210, "current": 46, "longest": 118,
             "first": "Mar 4, 2021",
             "cur_range": "Jul 5 – Aug 19, 2026",
             "long_range": "Jan 9 – May 6, 2024"}
    else:
        token = os.environ.get("GH_TOKEN")
        if not token:
            sys.exit("GH_TOKEN is not set")
        data = fetch(user, token)
        s = streaks(data["days"])

    os.makedirs(OUT, exist_ok=True)
    open(f"{OUT}/streak.svg", "w").write(streak_card(s))
    open(f"{OUT}/stats.svg", "w").write(stats_card(data, user))
    print(f"wrote {OUT}/streak.svg and {OUT}/stats.svg")


if __name__ == "__main__":
    main()
