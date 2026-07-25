from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data" / "updates.json"
data = json.loads(path.read_text(encoding="utf-8"))

assert data["schema_version"] == 2
assert data["product"] == "Windows 11"
assert set(data["channels"]) >= {"stable", "dev"}

stable = data["channels"]["stable"]
dev = data["channels"]["dev"]

assert stable["version"] == "25H2"
assert stable["count"] == len(stable["updates"])
assert stable["updates"]
assert stable["latest_id"] == stable["updates"][0]["id"]

stable_seen = set()
for item in stable["updates"]:
    assert re.fullmatch(r"KB\d+", item["kb"])
    assert item["id"] == item["kb"]
    assert item["builds"]
    assert item["version"] == "25H2"
    assert item["id"] not in stable_seen
    stable_seen.add(item["id"])
    if item["msu_x64_url"]:
        assert item["kb"].lower() in item["msu_x64_url"].lower()

assert dev["version"] == "26H2"
assert dev["count"] == len(dev["updates"])
assert dev["updates"]
assert dev["latest_id"] == dev["updates"][0]["id"]

dev_seen = set()
for item in dev["updates"]:
    assert item["builds"]
    assert all(build.startswith("26300.") for build in item["builds"])
    assert item["version"] == "26H2"
    assert item["update_type"] == "Dev / Experimental"
    assert item["technical_url"].startswith((
        "https://learn.microsoft.com/",
        "https://blogs.windows.com/windows-insider/",
    ))
    assert not item["msu_x64_url"]
    assert item["id"] not in dev_seen
    dev_seen.add(item["id"])

assert data["latest_dev_build"] == dev["latest_id"]
print(
    f"validated stable={len(stable_seen)} and dev={len(dev_seen)} records; "
    f"latest_dev={data['latest_dev_build']}"
)
