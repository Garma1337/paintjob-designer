#!/usr/bin/env python

"""Regenerate `schema/library.json` from the pydantic model.

Run whenever the library schema changes:

    python tools/dump_schema.py

The test `tests/paintjob/test_schema.py::test_committed_schema_matches_model`
asserts that the committed file equals this script's output, so CI fails if
someone changes the model without also updating the schema.
"""

import json
from pathlib import Path

from paintjob_designer.models import Paintjob


_REPO_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT = _REPO_ROOT / "schema" / "library.json"


def main() -> None:
    schema = Paintjob.model_json_schema(by_alias=True)
    _OUTPUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {_OUTPUT}")


if __name__ == "__main__":
    main()
