# coding: utf-8

from paintjob_designer.models import Skin


class SkinWriter:
    """Serializes a `Skin` to JSON."""

    def serialize(self, skin: Skin, indent: int = 2) -> str:
        return skin.model_dump_json(indent=indent, by_alias=True)
