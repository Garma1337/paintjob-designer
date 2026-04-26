# coding: utf-8

from dataclasses import dataclass


@dataclass
class MetadataEdit:
    """Values returned by the Edit Metadata dialog. `base_character_id` is
    `None` when the dialog was opened without the base-character field
    (skin mode) and when the user picked the unbound option (paintjob).
    The controller knows from context which it expects.
    """
    name: str
    author: str
    base_character_id: str | None
