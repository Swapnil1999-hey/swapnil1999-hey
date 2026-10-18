#!/usr/bin/env python3
"""Generate self-hosted profile SVGs (activity graph + highlights) from the GitHub GraphQL API.

Usage:
  GH_TOKEN=... python scripts/generate_profile_svgs.py --user Swapnil1999-hey
  python scripts/generate_profile_svgs.py --user Swapnil1999-hey --demo   # no network, placeholder data
"""
import argparse, datetime as dt, json, os, urllib.request

BG, BORDER, TEXT, MUTED, ACCENT = "#0D1117", "#30363d", "#c9d1d9", "#8b949e", "#58A6FF"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!){
  user(login:$login){
    followers{ totalCount }
    repositories(ownerAffiliation:OWNER, privacy:PUBLIC, isFork:false, first:100){
      totalCount
      nodes{ stargazerCount }
    }
    contributionsCollection(from:$from, to:$to){
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}
"""

def fetch(login, token):
    now = dt.datetime.utcnow().replace(microsecond=0)
    variables = {"login": login,
                 "from": (now - dt.timedelta(days=364)).isoformat() + "Z",
                 "to": now.isoformat() + "Z"}
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-svg-generator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    u = payload["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = sorted((d["date"], d["contributionCount"])
                  for w in cal["weeks"] for d in w["contributionDays"])
    today = dt.date.today().isoformat()
    days = [d for d in days if d[0] <= today]
    return {
        "days": days,
        "year_total": cal["totalContributions"],
        "repos": u["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "followers": u["followers"]["totalCount"],
    }

def demo():
    today = dt.date.today()
    days = [((today - dt.timedelta(days=i)).isoformat(), 0) for i in range(364, -1, -1)]
    return {"days": days, "year_total": 0, "repos": 0, "stars": 0, "followers": 0}

def streaks(days):
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    cur, i = 0, len(days) - 1
    if i >= 0 and days[i][1] == 0:  # today may not have commits yet
        i -= 1
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    return cur, longest

def activity_svg(data, placeholder):
    w, h = 900, 300
    left, right, top, bottom = 56, 30, 70, 50
    last = data["days"][-31:]
    vals = [c for _, c in last]
    ymax = max(max(vals, default=0), 4)
    ymax = ymax if ymax % 2 == 0 else ymax + 1
    pw, ph = w - left - right, h - top - bottom
    n = max(len(last) - 1, 1)
    pts = [(left + pw * i / n, top + ph - ph * v / ymax) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{left},{top+ph} " + line + f" {left+pw},{top+ph}"
    grid = ""
    for k in range(5):
        y = top + ph * k / 4
        label = int(ymax - ymax * k / 4)
        grid += (f'<line x1="{left}" y1="{y:.1f}" x2="{left+pw}" y2="{y:.1f}" stroke="{BORDER}" stroke-dasharray="3 4"/>'
                 f'<text x="{left-10}" y="{y+4:.1f}" fill="{MUTED}" font-size="11" text-anchor="end">{label}</text>')
    xl = ""
    for i in range(0, len(last), 5):
        d = dt.date.fromisoformat(last[i][0])
        x = left + pw * i / n
        xl += f'<text x="{x:.1f}" y="{h-bottom+22}" fill="{MUTED}" font-size="11" text-anchor="middle">{d.strftime("%b %d").replace(" 0", " ")}</text>'
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{BG}" stroke="{ACCENT}" stroke-width="2"/>' for x, y in pts)
    note = (f'<text x="{w/2}" y="{top+ph/2}" fill="{MUTED}" font-size="14" text-anchor="middle">'
            f'Waiting for first workflow run...</text>') if placeholder else ""
    total31 = sum(vals)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0.45"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0.02"/></linearGradient></defs>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text x="{left}" y="36" fill="{ACCENT}" font-size="18" font-weight="600">Contribution Activity Graph</text>
<text x="{left}" y="56" fill="{MUTED}" font-size="12">{total31} contributions in the last 31 days</text>
{grid}{xl}
<polygon points="{area}" fill="url(#g)"/>
<polyline points="{line}" fill="none" stroke="{ACCENT}" stroke-width="2.2" stroke-linejoin="round"/>
{dots}{note}
<text x="{left+pw}" y="{h-bottom+40}" fill="{MUTED}" font-size="10" text-anchor="end">Days</text>
</svg>'''

def highlights_svg(data):
    cur, longest = streaks(data["days"])
    items = [("Public Repos", data["repos"]), ("Stars Earned", data["stars"]),
             ("Followers", data["followers"]), ("Contributions (1 yr)", data["year_total"]),
             ("Current Streak", f"{cur}d"), ("Longest Streak", f"{longest}d")]
    w, h, gap = 900, 130, 12
    cw = (w - 2 * 20 - gap * (len(items) - 1)) / len(items)
    cards = ""
    for i, (label, val) in enumerate(items):
        x = 20 + i * (cw + gap)
        cx = x + cw / 2
        cards += (f'<rect x="{x:.1f}" y="30" width="{cw:.1f}" height="80" rx="8" fill="#161b22" stroke="{BORDER}"/>'
                  f'<text x="{cx:.1f}" y="68" fill="{ACCENT}" font-size="26" font-weight="700" text-anchor="middle">{val}</text>'
                  f'<text x="{cx:.1f}" y="92" fill="{MUTED}" font-size="11" text-anchor="middle">{label}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text x="20" y="22" fill="{TEXT}" font-size="13" font-weight="600">Highlights</text>
{cards}
</svg>'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", default="assets")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    data = demo() if a.demo else fetch(a.user, os.environ["GH_TOKEN"])
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, "activity-graph.svg"), "w").write(activity_svg(data, a.demo))
    open(os.path.join(a.out, "highlights.svg"), "w").write(highlights_svg(data))
    print("Wrote SVGs to", a.out)

if __name__ == "__main__":
    main()
