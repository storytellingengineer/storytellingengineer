import json
import os
import urllib.request
from datetime import date, timedelta
from html import escape

USERNAME = "storytellingengineer"
OUTPUT = "asset/github-contributions.svg"

QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      totalContributions
      contributionCalendar {
        weeks {
          contributionDays { date contributionCount contributionLevel }
        }
      }
    }
  }
}
"""

def github_graphql():
    token = os.environ["GITHUB_TOKEN"]
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=365)
    payload = json.dumps({
        "query": QUERY,
        "variables": {
            "login": USERNAME,
            "from": f"{start.isoformat()}T00:00:00Z",
            "to": f"{end.isoformat()}T00:00:00Z",
        },
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "github-contribution-card"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        body = json.load(response)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]["user"]["contributionsCollection"]


def streaks(days):
    counts = {d["date"]: d["contributionCount"] for d in days}
    ordered = sorted(date.fromisoformat(d) for d in counts)
    longest = current = 0
    run = 0
    for d in ordered:
        if counts[d.isoformat()] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    today = date.today()
    cursor = today if counts.get(today.isoformat(), 0) > 0 else today - timedelta(days=1)
    while counts.get(cursor.isoformat(), 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def make_svg(data):
    days = [d for w in data["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    weeks = data["contributionCalendar"]["weeks"]
    total = data["totalContributions"]
    current, longest = streaks(days)

    bg, panel, grid0 = "#0d1117", "#161b22", "#21262d"
    greens = ["#21262d", "#12351f", "#196c2e", "#2ea043", "#56d364"]
    width, height = 920, 250
    left, top = 48, 76
    cell, gap = 12, 3
    chart_w = 53 * (cell + gap) - gap
    divider_x = 735

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="GitHub contributions">',
             f'<rect width="{width}" height="{height}" rx="10" fill="{bg}"/>',
             f'<text x="20" y="28" fill="#f0f6fc" font-family="Arial,sans-serif" font-size="18" font-weight="700">GitHub Contributions</text>',
             f'<text x="20" y="46" fill="#8b949e" font-family="Arial,sans-serif" font-size="11">Building consistently, one commit at a time</text>']

    # Month labels, based on the first day represented by each week.
    seen_months = set()
    for i, week in enumerate(weeks[-53:]):
        first = date.fromisoformat(week["contributionDays"][0]["date"])
        label = first.strftime("%b")
        if first.month not in seen_months and i > 0:
            x = left + i * (cell + gap)
            parts.append(f'<text x="{x}" y="65" fill="#8b949e" font-family="Arial,sans-serif" font-size="9">{label}</text>')
            seen_months.add(first.month)

    for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = top + row * (cell + gap) + 9
        parts.append(f'<text x="5" y="{y}" fill="#8b949e" font-family="Arial,sans-serif" font-size="9">{label}</text>')

    for col, week in enumerate(weeks[-53:]):
        by_week = {date.fromisoformat(d["date"]): d for d in week["contributionDays"]}
        for row in range(7):
            target = next((d for d in by_week if d.weekday() == row), None)
            # GraphQL weeks are Sunday-first; convert Sunday=0 through Saturday=6.
            target = next((d for d in by_week if (d.weekday() + 1) % 7 == row), None)
            if target is None:
                continue
            day = by_week[target]
            level = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}.get(day["contributionLevel"], 0)
            x = left + col * (cell + gap)
            y = top + row * (cell + gap)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{greens[level]}"/>')

    parts += [f'<line x1="{divider_x}" y1="56" x2="{divider_x}" y2="218" stroke="#30363d"/>',
              f'<text x="758" y="84" fill="#8b949e" font-family="Arial,sans-serif" font-size="10">TOTAL CONTRIBUTIONS</text>',
              f'<text x="758" y="109" fill="#56d364" font-family="Arial,sans-serif" font-size="24" font-weight="700">{total}</text>',
              f'<text x="758" y="124" fill="#8b949e" font-family="Arial,sans-serif" font-size="9">in the last year</text>',
              f'<text x="758" y="157" fill="#8b949e" font-family="Arial,sans-serif" font-size="10">CURRENT STREAK</text>',
              f'<text x="758" y="181" fill="#f2cc60" font-family="Arial,sans-serif" font-size="20" font-weight="700">{current} days</text>',
              f'<text x="758" y="196" fill="#8b949e" font-family="Arial,sans-serif" font-size="9">Keep it going</text>',
              f'<text x="758" y="218" fill="#8b949e" font-family="Arial,sans-serif" font-size="10">LONGEST STREAK  <tspan fill="#58a6ff" font-size="18" font-weight="700">{longest} days</tspan></text>',
              '<text x="48" y="223" fill="#8b949e" font-family="Arial,sans-serif" font-size="9">Less</text>']

    for i, color in enumerate(greens):
        x = 82 + i * 15
        parts.append(f'<rect x="{x}" y="215" width="11" height="11" rx="2" fill="{color}"/>')
    parts.append('<text x="160" y="223" fill="#8b949e" font-family="Arial,sans-serif" font-size="9">More</text></svg>')
    return "".join(parts)


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(make_svg(github_graphql()))
