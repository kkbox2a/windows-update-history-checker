from __future__ import annotations

"""Resilient Windows 11 update-history fetcher.

The stable channel is discovered dynamically from Microsoft Support instead of
being tied to Windows 11 25H2 / build 26200. This lets the tracker move to the
next mainstream H2 release (for example 26H2 / build 26300) when Microsoft
publishes its update-history page.

The Windows Insider Experimental channel is also discovered without assuming a
fixed build prefix, so it can move between build families such as 26300 and
26340.
"""

import json
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
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
SUPPORT_HISTORY_URL = (
    "https://support.microsoft.com/en-US/servicing/os/windows-11/"
    "{year}/{month:02d}/windows-11-version-{version_slug}-update-history"
)
KNOWN_STABLE_SOURCES = {
    "25H2": (
        "https://support.microsoft.com/en-US/servicing/os/windows-11/2025/07/"
        "windows-11-version-25h2-update-history"
    ),
}

CURRENT_STABLE_VERSION = base.legacy.STABLE_VERSION
CURRENT_STABLE_SOURCE_URL = base.legacy.STABLE_SOURCE_URL

# Verified official pages used only when Experimental discovery temporarily fails.
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
WINDOWS_VERSION_HEADING_RE = re.compile(
    r"^Windows\s*11,?\s*version\s*(\d{2}H\d)$",
    re.IGNORECASE,
)


def _build_sort_key(build: str) -> tuple[int, int]:
    major, revision = build.split(".", 1)
    return int(major), int(revision)


def _version_sort_key(version: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{2})H(\d)", version, re.IGNORECASE)
    if not match:
        return (0, 0)
    return int(match.group(1)), int(match.group(2))


def _stable_candidate_urls() -> list[tuple[str, str]]:
    """Return newest plausible mainstream H2 Support pages first.

    H2 releases are probed only around the second half of the year. Known URLs
    are preferred when available, keeping normal checks inexpensive while still
    allowing a future H2 page to be discovered automatically.
    """
    now = datetime.now(timezone.utc)
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    for year in range(now.year, now.year - 3, -1):
        version = f"{year % 100:02d}H2"
        known = KNOWN_STABLE_SOURCES.get(version)
        if known and known not in seen:
            candidates.append((version, known))
            seen.add(known)

        max_month = 12
        if year == now.year:
            max_month = min(12, max(6, now.month + 1))
        for month in range(max_month, 5, -1):
            url = SUPPORT_HISTORY_URL.format(
                year=year,
                month=month,
                version_slug=version.lower(),
            )
            if url not in seen:
                candidates.append((version, url))
                seen.add(url)

    candidates.sort(key=lambda pair: _version_sort_key(pair[0]), reverse=True)
    return candidates


def _looks_like_stable_history(html: str, version: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    text = base.legacy.normalize_text(soup.get_text(" ", strip=True))
    return bool(
        re.search(
            rf"Windows\s*11,?\s*version\s*{re.escape(version)}\s*update\s*history",
            text,
            re.IGNORECASE,
        )
        or re.search(
            rf"Windows\s*11.*version\s*{re.escape(version)}",
            text,
            re.IGNORECASE,
        )
    )


def discover_stable_source(
    session: requests.Session,
) -> tuple[str, str, requests.Response]:
    errors: list[str] = []
    for version, url in _stable_candidate_urls():
        try:
            response = session.get(url, headers=base.legacy.HEADERS, timeout=15)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            if _looks_like_stable_history(response.text, version):
                return version, response.url, response
        except Exception as exc:
            errors.append(f"{version}: {exc}")

    raise RuntimeError(
        "No current Windows 11 H2 update-history page could be discovered."
        + (f" Last error: {errors[-1]}" if errors else "")
    )


def _stable_item_with_version(
    text: str,
    href: str,
    base_url: str,
    version: str,
) -> base.legacy.UpdateItem | None:
    item = base.legacy.parse_update_anchor(text, href, base_url)
    if not item:
        return None
    values = asdict(item)
    values["version"] = version
    values["channel"] = "General Availability"
    return base.legacy.UpdateItem(**values)


def extract_stable_updates(
    html: str,
    base_url: str,
    version: str,
) -> list[base.legacy.UpdateItem]:
    soup = BeautifulSoup(html, "html.parser")
    target_re = re.compile(
        rf"^Windows\s*11,?\s*version\s*{re.escape(version)}$",
        re.IGNORECASE,
    )
    any_version_re = re.compile(
        r"^Windows\s*11,?\s*version\s*\d{2}H\d$",
        re.IGNORECASE,
    )
    candidates: list[base.legacy.UpdateItem] = []
    collecting = False

    for node in soup.find_all(["h1", "h2", "h3", "h4", "a"]):
        text = base.legacy.normalize_text(node.get_text(" ", strip=True))
        if target_re.match(text):
            collecting = True
            continue
        if collecting and any_version_re.match(text) and not target_re.match(text):
            if candidates:
                break
            collecting = False
            continue
        if collecting and node.name == "a" and node.get("href"):
            item = _stable_item_with_version(text, node["href"], base_url, version)
            if item:
                candidates.append(item)

    # A version-specific Support page is already isolated to one release. If
    # Microsoft changes its heading markup, fall back to KB links on that page
    # instead of checking for a hard-coded build prefix such as 26200.
    if not candidates:
        for anchor in soup.find_all("a", href=True):
            item = _stable_item_with_version(
                anchor.get_text(" ", strip=True),
                anchor["href"],
                base_url,
                version,
            )
            if item:
                candidates.append(item)

    unique: list[base.legacy.UpdateItem] = []
    seen: set[str] = set()
    for item in candidates:
        if item.key not in seen:
            seen.add(item.key)
            unique.append(item)
    return unique


def fetch_stable_history(session: requests.Session) -> list[base.legacy.UpdateItem]:
    global CURRENT_STABLE_VERSION, CURRENT_STABLE_SOURCE_URL

    version, source_url, response = discover_stable_source(session)
    updates = extract_stable_updates(response.text, source_url, version)
    if not updates:
        raise RuntimeError(f"No Windows 11 {version} update entries were parsed.")

    CURRENT_STABLE_VERSION = version
    CURRENT_STABLE_SOURCE_URL = source_url
    print(f"info: current stable release discovered as Windows 11 {version}", file=sys.stderr)
    return updates


def _learn_url(build: str) -> str:
    return LEARN_BUILD_URL.format(build=build.replace(".", "-"))


def _collect_learn_links(text: str, found: dict[str, str]) -> None:
    decoded = text.replace("\\/", "/").replace("\\u002F", "/")
    for match in LEARN_LINK_RE.finditer(decoded):
        build = f"{match.group(1)}.{match.group(2)}"
        found[build] = _learn_url(build)


def _collect_experimental_from_blog(text: str, found: dict[str, str]) -> None:
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


def find_catalog_update_id_dynamic(
    html: str,
    kb: str,
    target_version: str | None = None,
) -> str:
    return base.legacy.find_catalog_update_id_original(
        html,
        kb,
        target_version or CURRENT_STABLE_VERSION,
    )


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


def _persist_channel_metadata() -> None:
    # The legacy writer compares update arrays only, so metadata-only changes
    # must be normalized after the fetch completes.
    for path in (base.legacy.DATA_FILE, base.legacy.WEB_DATA_FILE):
        file_path = Path(path)
        data = json.loads(file_path.read_text(encoding="utf-8"))
        channels = data.get("channels", {})

        stable = channels.get("stable")
        if stable:
            stable["label"] = f"Windows 11 {CURRENT_STABLE_VERSION}"
            stable["version"] = CURRENT_STABLE_VERSION
            stable["channel"] = "General Availability"
            stable["source_url"] = CURRENT_STABLE_SOURCE_URL

        dev = channels.get("dev")
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
    base.legacy.fetch_stable_history = fetch_stable_history

    if not hasattr(base.legacy, "find_catalog_update_id_original"):
        base.legacy.find_catalog_update_id_original = base.legacy.find_catalog_update_id
    base.legacy.find_catalog_update_id = find_catalog_update_id_dynamic

    if not hasattr(base.legacy, "fetch_msu_url_original"):
        base.legacy.fetch_msu_url_original = base.legacy.fetch_msu_url
    base.legacy.fetch_msu_url = fetch_msu_url_with_retry

    result = base.legacy.main()
    _persist_channel_metadata()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
