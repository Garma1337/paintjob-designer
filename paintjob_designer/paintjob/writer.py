# coding: utf-8

from paintjob_designer.models import Paintjob


class PaintjobWriter:
    """Serializes a `Paintjob` to JSON."""

    def serialize(self, paintjob: Paintjob, indent: int = 2) -> str:
        return paintjob.model_dump_json(indent=indent, by_alias=True)
