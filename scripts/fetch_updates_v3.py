from __future__ import annotations

"""Resilient Windows 11 update-history fetcher.

Stable-channel parsing and JSON output remain implemented by fetch_updates_v2.
This wrapper discovers the current Windows Insider Experimental builds from
Microsoft Learn and the Windows Insider Blog without assuming a fixed build
prefix such as 26300. This allows the tracker to follow Experimental as it
moves to newer build series such as 26340.
"""

import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scripts import fetch_updates_v2 as base

BLOG_INDEX_URL = "https://blogs.windows.com/windows-insider/tag/windows-insider-program/"
LEARN_BUILD_URL = (
    "https://learn.microsoft.com/en-us/windows-insider/release-notes/"
    "experimental/preview-build-{build}"
)

# Verified official pages used only when discovery temporarily fails.
OFFICIAL_BUILD_FALLBACKS = {
    "26340.9233": {
        "date": "August 21, 2026",
        "url": LEARN_BUILD_URL.format(build="26340-9233"),
    },
    "26340.9212": {
        "date": "August 17, 2026",
        "url": LEARN_BUILD_URL.format(build="26340-9212"),
    },
    "26300.9032": {
        "date": "July 31, 2026",
        "url": LEARN_BUILD_URL.format(build="26300-9032"),
    },
    "26300.8935": {
        "date": "July 20, 2026",
        "url": "https://blogs.windows.com/windows-insider/2026/07/20/announcing-new-builds-for-20-july-2026/",
    },
}

LEARN_LINK_RE = re.compile(
    r"https?://learn\.microsoft\.com/(?:[a-z]{2}-[a-z]{2}/)?"
    r"windows-insider/release-notes/experimental/preview-build-(\d{5})-(\d{4,5})",
    re.IGNORECASE,
)
EXPERIMENTAL_TEXT_RE = re.compile(
    r"\bExperimental\s*:\s*Build\s+(\d{5})[.-](\d{4,5})\b",
    re.IGNORECASE,
)


def _build_sort_key(build: str) -> tuple[int, int]:
    major, revision = build.split(".", 1)
    return int(major), int(revision)


def _learn_url(build: str) -> str:
    return LEARN_BUILD_URL.format(build=build.replace(".", "-"))


def _collect_learn_links(text: str, found: dict[str, str]) -> None:
    decoded = text.replace("\\/", "/").replace("\\u002F", "/")
    for match in LEARN_LINK_RE.finditer(decoded):
        build = f"{match.group(1)}.{match.group(2)}"
        found[build] = _learn_url(build)


def _collect_experimental_from_blog(text: str, found: dict[str, str]) -> None:
    # Parse rendered text so Beta / Experimental (26H1) / Future Platforms are
    # not accidentally collected as the main Experimental channel.
    plain = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    for match in EXPERIMENTAL_TEXT_RE.finditer(plain):
        build = f"{match.group(1)}.{match.group(2)}"
        found.setdefault(build, _learn_url(build))


def discover_insider_links(session: requests.Session) -> list[tuple[str, str]]:
    found: dict[str, str] = {}

    try:
        response = session.get(base.legacy.INSIDER_INDEX_URL, headers=base.legacy.HEADERS, timeout=40)
        response.raise_for_status()
        _collect_learn_links(response.text, found)
    except Exception as exc:
        print(f"warning: Learn Experimental discovery failed: {exc}", file=sys.stderr)

    try:
        blog = session.get(BLOG_INDEX_URL, headers=base.legacy.HEADERS, timeout=40)
        blog.raise_for_status()
        _collect_learn_links(blog.text, found)
        _collect_experimental_from_blog(blog.text, found)

        announcement_urls: list[str] = []
        for href in re.findall(r'href=["\']([^"\']+)["\']', blog.text, re.IGNORECASE):
            absolute = urljoin(blog.url, href)
            if "/windows-insider/2026/" in absolute and absolute not in announcement_urls:
                announcement_urls.append(absolute)

        for url in announcement_urls[:20]:
            try:
                page = session.get(url, headers=base.legacy.HEADERS, timeout=40)
                page.raise_for_status()
                _collect_learn_links(page.text, found)
                _collect_experimental_from_blog(page.text, found)
            except Exception as exc:
                print(f"warning: Insider blog page skipped: {url}: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"warning: Insider blog discovery failed: {exc}", file=sys.stderr)

    for build, metadata in OFFICIAL_BUILD_FALLBACKS.items():
        found.setdefault(build, metadata["url"])

    return sorted(found.items(), key=lambda pair: _build_sort_key(pair[0]), reverse=True)


def _as_experimental(item: base.legacy.UpdateItem) -> base.legacy.UpdateItem:
    values = asdict(item)
    values["update_type"] = "Experimental"
    values["channel"] = "Experimental"
    values["version"] = "26H2"
    return base.legacy.UpdateItem(**values)


def _fallback_item(build: str) -> base.legacy.UpdateItem | None:
    metadata = OFFICIAL_BUILD_FALLBACKS.get(build)
    if not metadata:
        return None

    return base.legacy.UpdateItem(
        id=f"Build {build}",
        date=metadata["date"],
        kb="",
        builds=[build],
        update_type="Experimental",
        channel="Experimental",
        version="26H2",
        title=f"Windows 11 Insider Experimental Preview Build {build}",
        support_url=metadata["url"],
        technical_url=metadata["url"],
        msu_x64_url="",
        msu_status="not_applicable",
    )


def fetch_insider_history(session: requests.Session) -> list[base.legacy.UpdateItem]:
    links = discover_insider_links(session)
    updates: list[base.legacy.UpdateItem] = []
    seen_builds: set[str] = set()

    for index, (build, url) in enumerate(links[:30]):
        item: base.legacy.UpdateItem | None = None
        try:
            page = session.get(url, headers=base.legacy.HEADERS, timeout=40)
            page.raise_for_status()
            item = _as_experimental(base.legacy.parse_insider_page(page.text, page.url, build))
        except Exception as exc:
            item = _fallback_item(build)
            if item:
                print(
                    f"warning: using official announcement fallback for {build}: {exc}",
                    file=sys.stderr,
                )
            else:
                print(f"warning: Experimental build {build} skipped: {exc}", file=sys.stderr)

        if item and build not in seen_builds:
            seen_builds.add(build)
            updates.append(item)

        if index < min(len(links), 30) - 1:
            time.sleep(0.2)

    for build in OFFICIAL_BUILD_FALLBACKS:
        if build in seen_builds:
            continue
        item = _fallback_item(build)
        if item:
            seen_builds.add(build)
            updates.append(item)
            print(f"info: appended verified official fallback for {build}", file=sys.stderr)

    if not updates:
        raise RuntimeError("No Windows Insider Experimental pages could be parsed.")

    updates.sort(key=lambda item: _build_sort_key(item.builds[0]), reverse=True)
    return updates


def fetch_msu_url_with_retry(session: requests.Session, kb: str) -> str:
    """Retry Catalog lookup because a new KB can appear before its download dialog is ready."""
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return base.legacy.fetch_msu_url_original(session, kb)
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                delay = 5 * attempt
                print(
                    f"warning: {kb} MSU lookup attempt {attempt}/3 failed; retrying in {delay}s: {exc}",
                    file=sys.stderr,
                )
                time.sleep(delay)
    raise RuntimeError(f"MSU lookup failed after 3 attempts for {kb}: {last_error}")


def _persist_experimental_metadata() -> None:
    # The legacy writer compares update arrays only, so a label-only change would
    # otherwise not be written. Normalize metadata after the fetch completes.
    for path in (base.legacy.DATA_FILE, base.legacy.WEB_DATA_FILE):
        file_path = Path(path)
        data = json.loads(file_path.read_text(encoding="utf-8"))
        dev = data.get("channels", {}).get("dev")
        if dev:
            dev["label"] = "Windows Insider Experimental"
            dev["channel"] = "Experimental"
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    base.fetch_insider_history_resilient = fetch_insider_history
    base.legacy.fetch_insider_history = fetch_insider_history

    if not hasattr(base.legacy, "fetch_msu_url_original"):
        base.legacy.fetch_msu_url_original = base.legacy.fetch_msu_url
    base.legacy.fetch_msu_url = fetch_msu_url_with_retry

    result = base.legacy.main()
    _persist_experimental_metadata()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
