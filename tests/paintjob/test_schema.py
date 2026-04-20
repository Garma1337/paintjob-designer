# coding: utf-8

import json
from pathlib import Path

from paintjob_designer.models import Paintjob


_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schema"
    / "library.json"
)


class TestLibraryJsonSchema:
    """The committed `schema/library.json` is the on-the-wire contract
    external consumer tools validate against. It must stay in lockstep with
    the pydantic models — if you change a field, regenerate the schema by
    running `tools/dump_schema.py` and commit the result.
    """

    def test_committed_schema_matches_model(self) -> None:
        # Regenerate from the model and compare to the committed file. If
        # this ever fails, the model changed without an accompanying schema
        # update — run tools/dump_schema.py to refresh it.
        generated = Paintjob.model_json_schema(by_alias=True)
        committed = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

        assert generated == committed, (
            "Committed schema/library.json is out of sync with the pydantic "
            "Paintjob model. Regenerate with `python tools/dump_schema.py`."
        )

    def test_psx_color_serializes_as_hex_string(self) -> None:
        # The schema describes PsxColor as a string (not the inner int).
        # This protects the on-the-wire contract against accidental
        # regressions (e.g. removing @model_serializer from PsxColor).
        schema = Paintjob.model_json_schema(by_alias=True)
        psx_color = schema["$defs"]["PsxColor"]

        assert psx_color["type"] == "string"
        assert psx_color["pattern"].startswith("^#")

    def test_pixel_payload_uses_data_key_not_pixels(self) -> None:
        # SlotRegionPixels' Python attribute is `pixels` but JSON key is
        # `data`. The schema must expose `data` so external consumers
        # look in the right place.
        schema = Paintjob.model_json_schema(by_alias=True)
        region_props = schema["$defs"]["SlotRegionPixels"]["properties"]

        assert "data" in region_props
        assert "pixels" not in region_props
