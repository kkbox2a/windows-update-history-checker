from __future__ import annotations

"""Resilient Windows 11 update-history fetcher.

Stable-channel parsing and JSON output remain implemented by fetch_updates_v2.
This wrapper improves Experimental/26H2 discovery and can build an entry from an
official Windows Insider Blog announcement when the matching Microsoft Learn
release-note page is temporarily missing, blocked, or not present in the
server-rendered index.
"""

import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

import requests

from scripts import fetch_updates_v2 as base

BLOG_INDEX_URL = "https://blogs.windows.com/windows-insider/tag/windows-insider-program/"
LEARN_BUILD_URL = (
    "https://learn.microsoft.com/en-us/windows-insider/release-notes/"
    "experimental/preview-build-{build}"
)

# Official Microsoft announcements used as resilient fallbacks. These are not
# synthetic records: every entry must point to an official Microsoft page.
OFFICIAL_BUILD_FALLBACKS = {
    "26300.8935": {
        "date": "July 20, 2026",
        "url": "https://blogs.windows.com/windows-insider/2026/07/20/announcing-new-builds-for-20-july-2026/",
    },
    "26300.8772": {
        "date": "July 6, 2026",
        "url": LEARN_BUILD_URL.format(build="26300-8772"),
    },
    "26300.8697": {
        "date": "June 19, 2026",
        "url": LEARN_BUILD_URL.format(build="26300-8697"),
    },
    "26300.8553": {
        "date": "May 29, 2026",
        "url": LEARN_BUILD_URL.format(build="26300-8553"),
    },
    "26300.8493": {
        "date": "May 15, 2026",
        "url": LEARN_BUILD_URL.format(build="26300-8493"),
    },
    "26300.8289": {
        "date": "April 24, 2026",
        "url": LEARN_BUILD_URL.format(build="26300-8289"),
    },
}

BUILD_RE = re.compile(r"\b26300[.-](\d{4,5})\b", re.IGNORECASE)
LEARN_LINK_RE = re.compile(
    r"https?://learn\.microsoft\.com/(?:[a-z]{2}-[a-z]{2}/)?"
    r"windows-insider/release-notes/experimental/preview-build-26300-(\d{4,5})",
    re.IGNORECASE,
)


def _build_sort_key(build: str) -> tuple[int, int]:
    major, revision = build.split(".", 1)
    return int(major), int(revision)


def _collect_builds(text: str, found: dict[str, str]) -> None:
    decoded = text.replace("\\/", "/").replace("\\u002F", "/")

    for match in LEARN_LINK_RE.finditer(decoded):
        build = f"26300.{match.group(1)}"
        found[build] = LEARN_BUILD_URL.format(build=build.replace(".", "-"))

    for match in BUILD_RE.finditer(decoded):
        revision = int(match.group(1))
        if revision < base.INSIDER_MIN_REVISION:
            continue
        build = f"26300.{revision}"
        found.setdefault(build, LEARN_BUILD_URL.format(build=build.replace(".", "-")))


def discover_insider_links(session: requests.Session) -> list[tuple[str, str]]:
    found: dict[str, str] = {}

    try:
        response = session.get(base.INSIDER_INDEX_URL, headers=base.HEADERS, timeout=40)
        response.raise_for_status()
        _collect_builds(response.text, found)
        for build, url in base.extract_insider_links(response.text, response.url):
            found[build] = url
    except Exception as exc:
        print(f"warning: Learn index discovery failed: {exc}", file=sys.stderr)

    try:
        blog = session.get(BLOG_INDEX_URL, headers=base.HEADERS, timeout=40)
        blog.raise_for_status()
        _collect_builds(blog.text, found)

        announcement_urls: list[str] = []
        for href in re.findall(r'href=["\']([^"\']+)["\']', blog.text, re.IGNORECASE):
            absolute = urljoin(blog.url, href)
            if "/windows-insider/2026/" in absolute and absolute not in announcement_urls:
                announcement_urls.append(absolute)

        for url in announcement_urls[:20]:
            try:
                page = session.get(url, headers=base.HEADERS, timeout=40)
                page.raise_for_status()
                _collect_builds(page.text, found)
            except Exception as exc:
                print(f"warning: Insider blog page skipped: {url}: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"warning: Insider blog discovery failed: {exc}", file=sys.stderr)

    for build, metadata in OFFICIAL_BUILD_FALLBACKS.items():
        found.setdefault(build, metadata["url"])

    return sorted(found.items(), key=lambda pair: _build_sort_key(pair[0]), reverse=True)


def _fallback_item(build: str) -> base.UpdateItem | None:
    metadata = OFFICIAL_BUILD_FALLBACKS.get(build)
    if not metadata:
        return None

    return base.UpdateItem(
        id=f"Build {build}",
        date=metadata["date"],
        kb="",
        builds=[build],
        update_type="Dev / Experimental",
        channel="Dev / Experimental",
        version=base.INSIDER_VERSION,
        title=f"Windows 11 Insider Experimental Preview Build {build}",
        support_url=metadata["url"],
        technical_url=metadata["url"],
        msu_x64_url="",
        msu_status="not_applicable",
    )


def fetch_insider_history(session: requests.Session) -> list[base.UpdateItem]:
    links = discover_insider_links(session)
    updates: list[base.UpdateItem] = []
    seen: set[str] = set()

    for index, (build, url) in enumerate(links[:30]):
        item: base.UpdateItem | None = None
        try:
            page = session.get(url, headers=base.HEADERS, timeout=40)
            page.raise_for_status()
            item = base.parse_insider_page(page.text, page.url, build)
        except Exception as exc:
            # The Learn page for a newly announced build may lag behind the
            # official blog or be inaccessible to the Actions runner. Preserve
            # the official announcement instead of silently falling back to an
            # older build.
            item = _fallback_item(build)
            if item:
                print(
                    f"warning: using official announcement fallback for {build}: {exc}",
                    file=sys.stderr,
                )
            else:
                print(f"warning: Insider build {build} skipped: {exc}", file=sys.stderr)

        if item and item.id not in seen:
            seen.add(item.id)
            updates.append(item)

        if index < min(len(links), 30) - 1:
            time.sleep(0.2)

    if not updates:
        raise RuntimeError("No Windows 11 26H2 Dev / Experimental pages could be parsed.")

    updates.sort(key=lambda item: _build_sort_key(item.builds[0]), reverse=True)
    return updates


base.fetch_insider_history = fetch_insider_history


if __name__ == "__main__":
    raise SystemExit(base.main())
