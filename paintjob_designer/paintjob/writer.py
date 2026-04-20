# coding: utf-8

from paintjob_designer.models import Paintjob


class PaintjobWriter:
    """Serializes a `Paintjob` to JSON.

    A thin wrapper around `Paintjob.model_dump_json(by_alias=True)` —
    pydantic handles the CLUT-hex serialization, base64 pixel encoding,
    and field ordering; the `by_alias=True` flag routes the pixel bytes
    through the public `data` JSON key.

    Kept as a class (rather than a module-level function) so it stays
    consistent with the reader's DI pattern and so future format
    variants (e.g. a compact single-file library dump) can be other
    methods on the same class.
    """

    def serialize(self, paintjob: Paintjob, indent: int = 2) -> str:
        return paintjob.model_dump_json(indent=indent, by_alias=True)
