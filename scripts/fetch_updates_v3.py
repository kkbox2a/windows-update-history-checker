from __future__ import annotations

"""Resilient Windows 11 update-history fetcher.

This wrapper keeps the stable-channel implementation from fetch_updates_v2 and
replaces only the Insider/Experimental discovery logic. Microsoft Learn's
release-notes index does not always expose every build link in server-rendered
HTML, so discovery also scans the Windows Insider Blog and uses verified Learn
URLs as a final fallback.
"""

import re
import sys
import time
from urllib.parse import urljoin

import requests

from scripts import fetch_updates_v2 as base

BLOG_INDEX_URL = "https://blogs.windows.com/windows-insider/tag/windows-insider-program/"
LEARN_BUILD_URL = (
    "https://learn.microsoft.com/en-us/windows-insider/release-notes/"
    "experimental/preview-build-{build}"
)

# Verified official Microsoft Learn pages. This fallback prevents a temporary
# index-page rendering change from hiding the newest known Experimental build.
VERIFIED_BUILDS = (
    "26300.8935",
    "26300.8772",
    "26300.8697",
    "26300.8553",
    "26300.8493",
    "26300.8289",
)

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
        build = f"26300.{match.group(1)}"
        revision = int(match.group(1))
        if revision >= base.INSIDER_MIN_REVISION:
            found.setdefault(
                build,
                LEARN_BUILD_URL.format(build=build.replace(".", "-")),
            )


def discover_insider_links(session: requests.Session) -> list[tuple[str, str]]:
    found: dict[str, str] = {}

    # 1. Microsoft Learn release-notes index.
    try:
        response = session.get(base.INSIDER_INDEX_URL, headers=base.HEADERS, timeout=40)
        response.raise_for_status()
        _collect_builds(response.text, found)
        for build, url in base.extract_insider_links(response.text, response.url):
            found[build] = url
    except Exception as exc:
        print(f"warning: Learn index discovery failed: {exc}", file=sys.stderr)

    # 2. Windows Insider Blog index and its recent announcement pages.
    try:
        blog = session.get(BLOG_INDEX_URL, headers=base.HEADERS, timeout=40)
        blog.raise_for_status()
        _collect_builds(blog.text, found)

        announcement_urls = []
        for href in re.findall(r'href=["\']([^"\']+)["\']', blog.text, re.IGNORECASE):
            absolute = urljoin(blog.url, href)
            if "/windows-insider/2026/" in absolute and absolute not in announcement_urls:
                announcement_urls.append(absolute)

        for url in announcement_urls[:12]:
            try:
                page = session.get(url, headers=base.HEADERS, timeout=40)
                page.raise_for_status()
                _collect_builds(page.text, found)
            except Exception as exc:
                print(f"warning: Insider blog page skipped: {url}: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"warning: Insider blog discovery failed: {exc}", file=sys.stderr)

    # 3. Official verified fallback pages.
    for build in VERIFIED_BUILDS:
        found.setdefault(build, LEARN_BUILD_URL.format(build=build.replace(".", "-")))

    return sorted(found.items(), key=lambda pair: _build_sort_key(pair[0]), reverse=True)


def fetch_insider_history(session: requests.Session) -> list[base.UpdateItem]:
    links = discover_insider_links(session)
    updates: list[base.UpdateItem] = []

    for index, (build, url) in enumerate(links[:30]):
        try:
            page = session.get(url, headers=base.HEADERS, timeout=40)
            page.raise_for_status()
            item = base.parse_insider_page(page.text, page.url, build)
            updates.append(item)
        except Exception as exc:
            print(f"warning: Insider build {build} skipped: {exc}", file=sys.stderr)

        if index < min(len(links), 30) - 1:
            time.sleep(0.2)

    if not updates:
        raise RuntimeError("No Windows 11 26H2 Dev / Experimental pages could be parsed.")

    updates.sort(key=lambda item: _build_sort_key(item.builds[0]), reverse=True)
    return updates


# Patch only the Insider fetcher; stable updates, JSON schema, Catalog matching,
# caching, validation metadata, and output paths remain implemented by v2.
base.fetch_insider_history = fetch_insider_history


if __name__ == "__main__":
    raise SystemExit(base.main())
