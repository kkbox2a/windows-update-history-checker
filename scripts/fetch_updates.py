from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "updates.json"
WEB_DATA_FILE = ROOT / "docs" / "data" / "updates.json"
SOURCE_URL = (
    "https://support.microsoft.com/en-US/servicing/os/windows-11/2025/07/"
    "windows-11-version-25h2-update-history"
)
TARGET_VERSION = "25H2"
CATALOG_SEARCH_URL = "https://www.catalog.update.microsoft.com/Search.aspx?q={}"
CATALOG_DOWNLOAD_URL = "https://www.catalog.update.microsoft.com/DownloadDialog.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/150 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

UPDATE_RE = re.compile(
    r"^(?P<date>[A-Z][a-z]+\s+\d{1,2},\s+\d{4})\s*[—-]\s*"
    r"(?P<kb>KB\d+)\s*\((?P<builds>OS Builds?\s+[^)]+)\)"
    r"(?P<suffix>.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class UpdateItem:
    date: str
    kb: str
    builds: list[str]
    update_type: str
    title: str
    support_url: str
    technical_url: str
    msu_x64_url: str = ""
    msu_status: str = "missing"

    @property
    def key(self) -> str:
        return f"{self.kb}|{'|'.join(self.builds)}|{self.date}"


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def classify_update(suffix: str) -> str:
    text = suffix.lower()
    if "out-of-band" in text:
        return "Out-of-band"
    if "preview" in text:
        return "Preview"
    return "Security / Cumulative"


def parse_update_anchor(text: str, href: str, base_url: str) -> UpdateItem | None:
    text = normalize_text(text)
    match = UPDATE_RE.match(text)
    if not match:
        return None
    builds_text = normalize_text(
        match.group("builds").replace("OS Builds", "").replace("OS Build", "")
    )
    builds = re.findall(r"\d+\.\d+", builds_text)
    if not builds:
        return None
    kb = match.group("kb").upper()
    return UpdateItem(
        date=match.group("date"),
        kb=kb,
        builds=builds,
        update_type=classify_update(match.group("suffix")),
        title=text,
        support_url=urljoin(base_url, href),
        technical_url=f"https://support.microsoft.com/en-us/help/{kb[2:]}",
    )


def extract_updates(html: str, base_url: str = SOURCE_URL) -> list[UpdateItem]:
    soup = BeautifulSoup(html, "html.parser")
    target_re = re.compile(rf"^Windows\s*11,?\s*version\s*{TARGET_VERSION}$", re.I)
    any_version_re = re.compile(r"^Windows\s*11,?\s*version\s*\d{2}H\d$", re.I)
    candidates: list[UpdateItem] = []
    collecting = False

    for node in soup.find_all(["h1", "h2", "h3", "h4", "a"]):
        text = normalize_text(node.get_text(" ", strip=True))
        if target_re.match(text):
            collecting = True
            continue
        if collecting and any_version_re.match(text) and not target_re.match(text):
            if candidates:
                break
            collecting = False
            continue
        if collecting and node.name == "a" and node.get("href"):
            item = parse_update_anchor(text, node["href"], base_url)
            if item:
                candidates.append(item)

    if not candidates:
        for anchor in soup.find_all("a", href=True):
            item = parse_update_anchor(anchor.get_text(" ", strip=True), anchor["href"], base_url)
            if item and any(build.startswith("26200.") for build in item.builds):
                candidates.append(item)

    unique: list[UpdateItem] = []
    seen: set[str] = set()
    for item in candidates:
        if item.key not in seen:
            seen.add(item.key)
            unique.append(item)
    return unique


def fetch_history(session: requests.Session) -> list[UpdateItem]:
    response = session.get(SOURCE_URL, headers=HEADERS, timeout=40)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    updates = extract_updates(response.text, response.url)
    if not updates:
        raise RuntimeError("No Windows 11 25H2 update entries were parsed.")
    return updates


def find_catalog_update_id(html: str, kb: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    preferred: list[tuple[int, str]] = []
    for row in soup.find_all("tr"):
        text = normalize_text(row.get_text(" ", strip=True))
        lower = text.lower()
        if kb.lower() not in lower or "x64-based systems" not in lower:
            continue
        score = 0
        if f"version {TARGET_VERSION.lower()}" in lower:
            score += 100
        if "cumulative update" in lower:
            score += 25
        if "dynamic update" in lower or "servicing stack" in lower or "arm64" in lower:
            score -= 80
        guids = re.findall(
            r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
            str(row),
        )
        preferred.extend((score, guid.lower()) for guid in guids)
    if not preferred:
        raise RuntimeError(f"Catalog entry not found for {kb}")
    preferred.sort(key=lambda value: value[0], reverse=True)
    return preferred[0][1]


def url_matches_kb(url: str, kb: str) -> bool:
    number = re.sub(r"\D", "", kb)
    return bool(re.search(rf"(?:^|[-_])kb{re.escape(number)}(?:[-_.]|$)", url, re.I))


def extract_msu_url(html: str, kb: str) -> str:
    decoded = html.replace(r"\/", "/").replace(r"\u0026", "&")
    urls = re.findall(r"https?://[^\"'<>\\\s]+?\.msu(?:\?[^\"'<>\\\s]*)?", decoded, re.I)
    clean = [url.replace("&amp;", "&") for url in urls]
    exact = [url for url in clean if url_matches_kb(url, kb)]
    for url in exact:
        lower = url.lower()
        if "x64" in lower and "arm64" not in lower:
            return url
    if exact:
        return exact[0]
    raise RuntimeError(f"Direct MSU URL for {kb} was not found in Catalog dialog")


def fetch_msu_url(session: requests.Session, kb: str) -> str:
    search = session.get(
        CATALOG_SEARCH_URL.format(kb), headers=HEADERS, timeout=40
    )
    search.raise_for_status()
    update_id = find_catalog_update_id(search.text, kb)
    dialog = session.post(
        CATALOG_DOWNLOAD_URL,
        headers={**HEADERS, "Referer": search.url},
        data={"updateIDs": json.dumps([{"size": 0, "updateID": update_id, "uidInfo": update_id}])},
        timeout=40,
    )
    dialog.raise_for_status()
    return extract_msu_url(dialog.text, kb)


def load_existing() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def canonical_updates(updates: list[dict[str, Any]]) -> str:
    return json.dumps(updates, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    session = requests.Session()
    existing = load_existing()
    old_by_kb = {item.get("kb"): item for item in existing.get("updates", [])}
    parsed = fetch_history(session)

    enriched: list[UpdateItem] = []
    for index, item in enumerate(parsed):
        old = old_by_kb.get(item.kb, {})
        cached_url = old.get("msu_x64_url", "")
        if cached_url and url_matches_kb(cached_url, item.kb):
            msu_url = cached_url
            status = "available"
        else:
            try:
                msu_url = fetch_msu_url(session, item.kb)
                status = "available"
            except Exception as exc:  # Keep history available even if Catalog is temporarily unavailable.
                print(f"warning: {item.kb}: {exc}", file=sys.stderr)
                msu_url = ""
                status = "unavailable"
            if index < len(parsed) - 1:
                time.sleep(0.7)
        enriched.append(
            UpdateItem(
                date=item.date,
                kb=item.kb,
                builds=item.builds,
                update_type=item.update_type,
                title=item.title,
                support_url=item.support_url,
                technical_url=item.technical_url,
                msu_x64_url=msu_url,
                msu_status=status,
            )
        )

    update_dicts = [asdict(item) for item in enriched]
    old_updates = existing.get("updates", [])
    changed = canonical_updates(update_dicts) != canonical_updates(old_updates)

    if changed or not DATA_FILE.exists():
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        digest = hashlib.sha256(canonical_updates(update_dicts).encode("utf-8")).hexdigest()
        payload = {
            "schema_version": 1,
            "product": "Windows 11",
            "version": TARGET_VERSION,
            "source_url": SOURCE_URL,
            "generated_at": generated_at,
            "content_sha256": digest,
            "count": len(update_dicts),
            "latest_kb": update_dicts[0]["kb"] if update_dicts else "",
            "updates": update_dicts,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        WEB_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(text, encoding="utf-8")
        WEB_DATA_FILE.write_text(text, encoding="utf-8")
        print(f"updated: {len(update_dicts)} records; latest={payload['latest_kb']}")
    else:
        # Ensure Pages copy exists without changing the canonical metadata.
        WEB_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        WEB_DATA_FILE.write_text(DATA_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"no change: {len(update_dicts)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
