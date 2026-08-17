#!/usr/bin/env python3
"""Generate self-hosted GitHub profile cards for the profile README."""

from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
LOGIN = os.environ.get("GITHUB_USERNAME", "arixbit")
API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
TOKEN = os.environ.get("GITHUB_TOKEN")
USER_AGENT = "arixbit-profile-assets"


def fetch_text(url: str) -> str:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> object:
    return json.loads(fetch_text(url))


def fetch_repositories() -> list[dict[str, object]]:
    repositories: list[dict[str, object]] = []
    for page in range(1, 11):
        query = urlencode({"type": "owner", "per_page": 100, "page": page})
        page_repositories = fetch_json(
            f"{API_URL}/users/{quote(LOGIN, safe='')}/repos?{query}"
        )
        if not isinstance(page_repositories, list):
            raise RuntimeError("GitHub returned an unexpected repository response")
        repositories.extend(
            repository
            for repository in page_repositories
            if isinstance(repository, dict)
        )
        if len(page_repositories) < 100:
            break
    return repositories


class ContributionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_heading = False
        self._heading_parts: list[str] = []
        self.days: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h2" and attributes.get("id") == "js-contribution-activity-description":
            self._in_heading = True
        if tag != "td" or "ContributionCalendar-day" not in attributes.get("class", ""):
            return
        contribution_date = attributes.get("data-date")
        level = attributes.get("data-level")
        if contribution_date and level and level.isdigit():
            self.days[contribution_date] = min(int(level), 4)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self._in_heading = False

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_parts.append(data)

    @property
    def total(self) -> int:
        heading = " ".join(self._heading_parts)
        match = re.search(r"([0-9][0-9,]*)\s+contributions?", heading)
        return int(match.group(1).replace(",", "")) if match else 0


def fetch_contributions(year: int) -> tuple[int, dict[str, int]]:
    query = urlencode({"from": f"{year}-01-01", "to": f"{year}-12-31"})
    parser = ContributionParser()
    parser.feed(fetch_text(f"https://github.com/users/{quote(LOGIN)}/contributions?{query}"))
    if not parser.days:
        raise RuntimeError("GitHub returned no contribution calendar days")
    return parser.total, parser.days


def svg_text(x: int, y: int, value: object, size: int = 14, color: str = "#c9d1d9", weight: str = "400") -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="{size}px" font-weight="{weight}">{escape(str(value))}</text>'
    )


def format_number(value: object) -> str:
    return f"{int(value):,}"


def render_profile_stats(profile: dict[str, object], repositories: list[dict[str, object]]) -> str:
    languages = Counter(
        str(repository["language"])
        for repository in repositories
        if repository.get("language") and not repository.get("fork")
    )
    language_summary = " · ".join(language for language, _ in languages.most_common(5))
    if not language_summary:
        language_summary = "No public language data"
    stars = sum(int(repository.get("stargazers_count", 0)) for repository in repositories)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d UTC")
    cards = [
        ("Public repos", profile.get("public_repos", len(repositories))),
        ("Followers", profile.get("followers", 0)),
        ("Following", profile.get("following", 0)),
        ("Total stars", stars),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="820" height="148" viewBox="0 0 820 148">',
        f'<title>GitHub profile statistics for {escape(LOGIN)}</title>',
        '<rect width="820" height="148" rx="12" fill="#f6f8fa" stroke="#d0d7de"/>',
        svg_text(28, 29, "GitHub snapshot", 18, "#24292f", "600"),
        svg_text(28, 49, f"{LOGIN} · public profile", 11, "#57606a"),
    ]
    for index, (label, value) in enumerate(cards):
        x = 28 + index * 192
        parts.extend(
            [
                f'<rect x="{x}" y="64" width="176" height="48" rx="8" fill="#ffffff" stroke="#d8dee4"/>',
                svg_text(x + 14, 83, label, 10, "#57606a"),
                svg_text(x + 14, 103, format_number(value), 19, "#0969da", "600"),
            ]
        )
    parts.extend(
        [
            svg_text(28, 133, f"Languages: {language_summary}", 11, "#57606a"),
            svg_text(650, 133, f"Updated {updated}", 10, "#57606a"),
            "</svg>",
        ]
    )
    return "\n".join(parts) + "\n"


def render_contributions(year: int, total: int, days: dict[str, int]) -> str:
    width = 820
    grid_x = 74
    grid_y = 62
    cell = 10
    gap = 3
    first_day = date(year, 1, 1)
    grid_start = first_day - timedelta(days=first_day.weekday())
    colors = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="180" viewBox="0 0 {width} 180">',
        f'<title>{LOGIN} GitHub contributions in {year}</title>',
        f'<rect width="{width}" height="180" rx="12" fill="#f6f8fa" stroke="#d0d7de"/>',
        svg_text(28, 30, f"Contribution activity · {year}", 18, "#24292f", "600"),
        svg_text(670, 30, f"{format_number(total)} total", 12, "#0969da", "600"),
        svg_text(28, 76, "Mon", 10, "#57606a"),
        svg_text(28, 102, "Wed", 10, "#57606a"),
        svg_text(28, 128, "Fri", 10, "#57606a"),
    ]
    for month in range(1, 13):
        month_start = date(year, month, 1)
        column = (month_start - grid_start).days // 7
        parts.append(
            svg_text(grid_x + column * (cell + gap), 51, calendar.month_abbr[month], 10, "#57606a")
        )
    for column in range(53):
        for weekday in range(7):
            current = grid_start + timedelta(days=column * 7 + weekday)
            if current.year != year:
                continue
            level = days.get(current.isoformat(), 0)
            x = grid_x + column * (cell + gap)
            y = grid_y + weekday * (cell + gap)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{colors[level]}"/>'
            )
    legend_x = 610
    parts.extend(
        [
            svg_text(28, 169, "GitHub contribution calendar", 10, "#57606a"),
            svg_text(552, 169, "Less", 10, "#57606a"),
        ]
    )
    for index, color in enumerate(colors):
        parts.append(
            f'<rect x="{legend_x + index * 13}" y="161" width="10" height="10" rx="2" fill="{color}"/>'
        )
    parts.append(svg_text(legend_x + len(colors) * 13 + 4, 169, "More", 10, "#57606a"))
    parts.append(
        "</svg>"
    )
    return "\n".join(parts) + "\n"


def main() -> None:
    profile = fetch_json(f"{API_URL}/users/{quote(LOGIN, safe='')}")
    if not isinstance(profile, dict):
        raise RuntimeError("GitHub returned an unexpected profile response")
    repositories = fetch_repositories()
    year = datetime.now(timezone.utc).year
    total, days = fetch_contributions(year)
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "profile-stats.svg").write_text(
        render_profile_stats(profile, repositories), encoding="utf-8"
    )
    (assets / "contributions.svg").write_text(
        render_contributions(year, total, days), encoding="utf-8"
    )
    print(
        f"Generated profile assets for {LOGIN}: {len(repositories)} repositories, "
        f"{total:,} contributions in {year}."
    )


if __name__ == "__main__":
    main()
