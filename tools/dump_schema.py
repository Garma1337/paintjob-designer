#!/usr/bin/env python

"""Regenerate the JSON schema files under `schema/` from the pydantic models.

Run whenever an exported model's shape changes:

    python tools/dump_schema.py

Outputs one file per model — currently `schema/paintjobs_library_schema.json`
(Paintjob) and `schema/skins_library_schema.json` (Skin). The matching tests
in `tests/paintjob/test_schema.py` and `tests/skin/test_schema.py` assert the
committed files equal this script's output, so CI fails if someone changes a
model without also updating the committed schema.
"""

import json
from pathlib import Path

from paintjob_designer.models import Paintjob, Skin

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_DIR = _REPO_ROOT / "schema"

# (model, output filename) — keep `library.json` as the paintjob filename
# since external consumers already read from that path.
_TARGETS = [
    (Paintjob, "paintjobs_library_schema.json"),
    (Skin, "skins_library_schema.json"),
]

def main() -> None:
    _SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

    for model, filename in _TARGETS:
        path = _SCHEMA_DIR / filename
        schema = model.model_json_schema(by_alias=True)
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
