import json
from pathlib import Path

for p in sorted(Path("data/processed").glob("*.json")):
    r = json.loads(p.read_text(encoding="utf-8"))
    if r["outcome"] == "unknown":
        tail = r["judgment_text"][-600:]
        print(f"\n=== {r['case_id']} ===")
        print(tail[-400:])
        print("---")
