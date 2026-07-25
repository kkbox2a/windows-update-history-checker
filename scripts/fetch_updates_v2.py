from __future__ import annotations

import html as html_module
import re
import time
from urllib.parse import urljoin

import requests

import scripts.fetch_updates as legacy

# Microsoft Learn's release-notes index can return a shell page whose links are
# embedded in JSON instead of normal <a> elements. These verified fallback pages
# keep the first 26H2 deployment working even when the index is not directly
# parsable by a non-browser client.
KNOWN_26H2_BUILDS = (
    "26300.8772",
    "26300.8697",
)


def build_url(build: str) -> str:
    major, revision = build.split(".", 1)
    return (
        "https://learn.microsoft.com/en-us/windows-insider/release-notes/"
        f"experimental/preview-build-{major}-{revision}"
    )


def extract_insider_links_resilient(
    raw_html: str,
    base_url: str = legacy.INSIDER_INDEX_URL,
) -> list[tuple[str, str]]:
    found = dict(legacy.extract_insider_links(raw_html, base_url))

    # Also inspect the raw response because Learn can serialize navigation links
    # inside JSON/script data rather than rendering them as anchors.
    decoded = html_module.unescape(raw_html).replace(r"\/", "/").replace(r"\u002F", "/")
    pattern = re.compile(
        r"(?:https?://learn\.microsoft\.com/(?:[a-z]{2}-[a-z]{2}/)?)?"
        r"windows-insider/release-notes/experimental/preview-build-(26300)-(\d+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(decoded):
        revision = int(match.group(2))
        if revision < legacy.INSIDER_MIN_REVISION:
            continue
        build = f"26300.{revision}"
        found[build] = build_url(build)

    for build in KNOWN_26H2_BUILDS:
        found.setdefault(build, build_url(build))

    return sorted(
        found.items(),
        key=lambda pair: tuple(map(int, pair[0].split("."))),
        reverse=True,
    )


def fetch_insider_history_resilient(session: requests.Session) -> list[legacy.UpdateItem]:
    links: list[tuple[str, str]] = []
    try:
        response = session.get(legacy.INSIDER_INDEX_URL, headers=legacy.HEADERS, timeout=40)
        response.raise_for_status()
        links = extract_insider_links_resilient(response.text, response.url)
    except Exception as exc:
        print(f"warning: Insider index unavailable; using verified fallback pages: {exc}")
        links = extract_insider_links_resilient("")

    updates: list[legacy.UpdateItem] = []
    failures: list[str] = []
    for index, (build, url) in enumerate(links[:30]):
        try:
            page = session.get(url, headers=legacy.HEADERS, timeout=40)
            page.raise_for_status()
            updates.append(legacy.parse_insider_page(page.text, page.url, build))
        except Exception as exc:
            failures.append(f"{build}: {exc}")
        if index < min(len(links), 30) - 1:
            time.sleep(0.2)

    if not updates:
        detail = "; ".join(failures[:5]) or "no candidate pages"
        raise RuntimeError(f"No Windows 11 26H2 Dev / Experimental pages were parsed ({detail}).")

    updates.sort(
        key=lambda item: tuple(map(int, item.builds[0].split("."))),
        reverse=True,
    )
    return updates


def main() -> int:
    legacy.fetch_insider_history = fetch_insider_history_resilient
    return legacy.main()


if __name__ == "__main__":
    raise SystemExit(main())
