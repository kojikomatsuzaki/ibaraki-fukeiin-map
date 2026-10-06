"""One-time, lossless migration. Office IDs are internal IDs, not Japan Post codes."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
destination = root / "source/catalog.json"
if destination.exists():
    raise SystemExit("The master catalog already exists; refusing to overwrite it.")
original = json.loads((root / "data.json").read_text())
office_ids = {}
offices = []
stamps = []
for record in original["records"]:
    key = (record["name"], record["city"], record["region"])
    if key not in office_ids:
        office_id = f"office-{len(offices) + 1:04d}"
        office_ids[key] = office_id
        offices.append(dict(id=office_id, name=key[0], city=key[1], region=key[2]))
    stamps.append({"officeId": office_ids[key], **{k: v for k, v in record.items() if k not in ("name", "city", "region")}})
catalog = {"schemaVersion": 2, "verifiedAt": original["verifiedAt"], "sourceUrl": original["sourceUrl"], "partial": original["partial"], "offices": offices, "stamps": stamps}
destination.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
print(f"Migrated {len(offices)} offices and {len(stamps)} stamps; original fields preserved.")
