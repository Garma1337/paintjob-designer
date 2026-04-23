# coding: utf-8

import json
from pathlib import Path

from paintjob_designer.models import Skin


_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schema"
    / "skins_library_schema.json"
)


class TestSkinJsonSchema:
    """The committed `schema/skins_library_schema.json` is the on-the-wire
    contract external consumer tools validate against. It must stay in
    lockstep with the pydantic Skin model — if you change a field,
    regenerate the schema by running `tools/dump_schema.py` and commit
    the result.
    """

    def test_committed_schema_matches_model(self) -> None:
        generated = Skin.model_json_schema(by_alias=True)
        committed = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

        assert generated == committed, (
            "Committed schema/skins_library_schema.json is out of sync with "
            "the pydantic Skin model. Regenerate with "
            "`python tools/dump_schema.py`."
        )

    def test_character_id_is_required(self) -> None:
        # Skins are character-bound — `character_id` carries the binding
        # and must appear in the schema as a string field.
        schema = Skin.model_json_schema(by_alias=True)
        assert schema["properties"]["character_id"]["type"] == "string"

    def test_vertex_overrides_present(self) -> None:
        # Vertex overrides are a skin-only feature (paintjobs don't have
        # them); the schema must expose them so external consumers can
        # validate the field.
        schema = Skin.model_json_schema(by_alias=True)
        assert "vertex_overrides" in schema["properties"]
