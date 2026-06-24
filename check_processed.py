import json
from pathlib import Path

for p in sorted(Path("data/processed").glob("*.json")):
    r = json.loads(p.read_text(encoding="utf-8"))
    print(r["case_id"], "|", r["outcome"], "|", r["case_type"], "|", r["judge_name"][:30])
