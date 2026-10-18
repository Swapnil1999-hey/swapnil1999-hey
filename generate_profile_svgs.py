#!/usr/bin/env python3
"""Self-hosted GitHub profile images: github-stats.svg, activity-graph.svg, highlights.svg.

  GH_TOKEN=... python generate_profile_svgs.py --user Swapnil1999-hey
  python generate_profile_svgs.py --user Swapnil1999-hey --demo      # offline placeholders
"""
import argparse, base64, datetime as dt, json, os, urllib.request
from xml.sax.saxutils import escape

BG, CARD, BORDER, TEXT, MUTED, ACCENT = "#0D1117", "#161b22", "#30363d", "#c9d1d9", "#8b949e", "#58A6FF"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
HERE = os.path.dirname(os.path.abspath(__file__))

def gql(query, variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-svg-generator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]

BASE_Q = """
query($login:String!, $from:DateTime!, $to:DateTime!){
  user(login:$login){
    name createdAt
    followers{ totalCount }
    repositories(ownerAffiliations:[OWNER], privacy:PUBLIC, isFork:false, first:100){
      totalCount
      nodes{ stargazerCount }
    }
    contributionsCollection(from:$from, to:$to){
      contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } }
      commitContributionsByRepository(maxRepositories:100){ repository{ nameWithOwner } }
      pullRequestContributionsByRepository(maxRepositories:100){ repository{ nameWithOwner } }
      issueContributionsByRepository(maxRepositories:100){ repository{ nameWithOwner } }
    }
  }
}"""

def fetch(login, token):
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None)
    frm = (now - dt.timedelta(days=364)).isoformat() + "Z"
    to = now.isoformat() + "Z"
    u = gql(BASE_Q, {"login": login, "from": frm, "to": to}, token)["user"]
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = sorted((d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"])
    days = [d for d in days if d[0] <= dt.date.today().isoformat()]
    repos_touched = {x["repository"]["nameWithOwner"]
                     for key in ("commitContributionsByRepository", "pullRequestContributionsByRepository",
                                 "issueContributionsByRepository") for x in cc[key]}

    # all-time commits / PRs / issues, one aliased query over 364-day windows since account creation
    created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", ""))
    windows, start = [], created
    while start < now:
        end = min(start + dt.timedelta(days=364), now)
        windows.append((start, end))
        start = end
    parts = "".join(
        f'w{i}: contributionsCollection(from:"{a.isoformat()}Z", to:"{b.isoformat()}Z")'
        f'{{ totalCommitContributions totalPullRequestContributions totalIssueContributions }} '
        for i, (a, b) in enumerate(windows))
    tot = gql("query($login:String!){ user(login:$login){ %s } }" % parts, {"login": login}, token)["user"]
    commits = sum(v["totalCommitContributions"] for v in tot.values())
    prs = sum(v["totalPullRequestContributions"] for v in tot.values())
    issues = sum(v["totalIssueContributions"] for v in tot.values())
    return {"name": u["name"] or login, "days": days, "year_total": cal["totalContributions"],
            "repos": u["repositories"]["totalCount"],
            "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
            "followers": u["followers"]["totalCount"], "commits": commits, "prs": prs,
            "issues": issues, "contributed_to": len(repos_touched)}

def demo(login):
    today = dt.date.today()
    days = [((today - dt.timedelta(days=i)).isoformat(), 0) for i in range(364, -1, -1)]
    return {"name": login, "days": days, "year_total": 0, "repos": 0, "stars": 0, "followers": 0,
            "commits": 0, "prs": 0, "issues": 0, "contributed_to": 0}

def streaks(days):
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    cur, i = 0, len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    return cur, longest

def avatar_data_uri():
    p = os.path.join(HERE, "octocat.png")
    if not os.path.exists(p):
        return None
    return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()

def stats_svg(d):
    w, h = 495, 195
    rows = [("Total Stars Earned", d["stars"]), ("Total Commits", d["commits"]), ("Total PRs", d["prs"]),
            ("Total Issues", d["issues"]), ("Contributed to (last year)", d["contributed_to"])]
    body = ""
    for i, (label, val) in enumerate(rows):
        y = 78 + i * 25
        body += (f'<circle cx="32" cy="{y-5}" r="4" fill="{ACCENT}"/>'
                 f'<text x="46" y="{y}" fill="#2dd4bf" font-size="13" font-weight="600">{label}:</text>'
                 f'<text x="232" y="{y}" fill="{TEXT}" font-size="13" font-weight="700">{val}</text>')
    uri = avatar_data_uri()
    img = (f'<image x="364" y="62" width="92" height="92" href="{uri}"/>' if uri else "")
    title = escape(f"{d['name']}'s GitHub Stats")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<defs><linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="#a78bfa"/></linearGradient></defs>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="8" fill="{BG}" stroke="{BORDER}"/>
<text x="25" y="38" fill="{ACCENT}" font-size="17" font-weight="600">{title}</text>
{body}
<circle cx="410" cy="108" r="52" fill="none" stroke="url(#ring)" stroke-width="4"/>
{img}
</svg>'''

def activity_svg(d, placeholder):
    w, h = 900, 300
    left, right, top, bottom = 56, 30, 70, 50
    last = d["days"][-31:]
    vals = [c for _, c in last]
    ymax = max(max(vals, default=0), 4)
    ymax += ymax % 2
    pw, ph = w - left - right, h - top - bottom
    n = max(len(last) - 1, 1)
    pts = [(left + pw * i / n, top + ph - ph * v / ymax) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{left},{top+ph} " + line + f" {left+pw},{top+ph}"
    grid = ""
    for k in range(5):
        y = top + ph * k / 4
        grid += (f'<line x1="{left}" y1="{y:.1f}" x2="{left+pw}" y2="{y:.1f}" stroke="{BORDER}" stroke-dasharray="3 4"/>'
                 f'<text x="{left-10}" y="{y+4:.1f}" fill="{MUTED}" font-size="11" text-anchor="end">{int(ymax - ymax*k/4)}</text>')
    xl = ""
    for i in range(0, len(last), 5):
        day = dt.date.fromisoformat(last[i][0])
        xl += (f'<text x="{left + pw*i/n:.1f}" y="{h-bottom+22}" fill="{MUTED}" font-size="11" text-anchor="middle">'
               f'{day.strftime("%b")} {day.day}</text>')
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{BG}" stroke="{ACCENT}" stroke-width="2"/>' for x, y in pts)
    note = (f'<text x="{w/2}" y="{top+ph/2}" fill="{MUTED}" font-size="14" text-anchor="middle">'
            f'Waiting for first workflow run...</text>') if placeholder else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0.45"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0.02"/></linearGradient></defs>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text x="{left}" y="36" fill="{ACCENT}" font-size="18" font-weight="600">Contribution Activity Graph</text>
<text x="{left}" y="56" fill="{MUTED}" font-size="12">{sum(vals)} contributions in the last 31 days</text>
{grid}{xl}
<polygon points="{area}" fill="url(#g)"/>
<polyline points="{line}" fill="none" stroke="{ACCENT}" stroke-width="2.2" stroke-linejoin="round"/>
{dots}{note}
</svg>'''

def highlights_svg(d):
    cur, longest = streaks(d["days"])
    items = [("Public Repos", d["repos"]), ("Stars Earned", d["stars"]), ("Followers", d["followers"]),
             ("Contributions (1 yr)", d["year_total"]), ("Current Streak", f"{cur}d"), ("Longest Streak", f"{longest}d")]
    w, h, gap = 900, 130, 12
    cw = (w - 40 - gap * (len(items) - 1)) / len(items)
    cards = ""
    for i, (label, val) in enumerate(items):
        x = 20 + i * (cw + gap); cx = x + cw / 2
        cards += (f'<rect x="{x:.1f}" y="30" width="{cw:.1f}" height="80" rx="8" fill="{CARD}" stroke="{BORDER}"/>'
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
    ap.add_argument("--out", default=".")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    d = demo(a.user) if a.demo else fetch(a.user, os.environ["GH_TOKEN"])
    os.makedirs(a.out, exist_ok=True)
    for name, svg in (("github-stats.svg", stats_svg(d)), ("activity-graph.svg", activity_svg(d, a.demo)),
                      ("highlights.svg", highlights_svg(d))):
        open(os.path.join(a.out, name), "w", encoding="utf-8").write(svg)
    print("Wrote SVGs to", a.out)

if __name__ == "__main__":
    main()
