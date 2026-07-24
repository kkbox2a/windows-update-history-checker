from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data" / "updates.json"
data = json.loads(path.read_text(encoding="utf-8"))
assert data["schema_version"] == 1
assert data["version"] == "25H2"
assert data["count"] == len(data["updates"])
seen = set()
for item in data["updates"]:
    assert re.fullmatch(r"KB\d+", item["kb"])
    assert item["builds"]
    assert item["kb"] not in seen
    seen.add(item["kb"])
    if item["msu_x64_url"]:
        assert item["kb"].lower() in item["msu_x64_url"].lower()
print(f"validated {len(seen)} records")
