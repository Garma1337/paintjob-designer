# coding: utf-8

"""JSON field-name constants for the on-disk paintjob/skin/profile formats.

Centralized so a typo in `raw.get("schema_version", ...)` becomes an
`AttributeError` at import time instead of silently returning the
default. Pydantic models use these same names as their attribute names,
so model serialization stays in sync without further wiring.

Grouped by document type. Keys shared across documents (e.g. `name`,
`schema_version`) live on `CommonKey`.
"""


class CommonKey:
    SCHEMA_VERSION = "schema_version"
    NAME = "name"
    AUTHOR = "author"
    ID = "id"
    DISPLAY_NAME = "display_name"


class ProfileKey:
    VRAM_PAGE = "vram_page"
    WIDTH = "width"
    HEIGHT = "height"
    CHARACTERS = "characters"
    PAINTJOB_SLOTS = "paintjob_slots"
    DEFAULT_CHARACTER_ID = "default_character_id"
    MESH_SOURCE = "mesh_source"
    KART_TYPE = "kart_type"
    KART_SLOTS = "kart_slots"
    SKIN_SLOTS = "skin_slots"
    CLUT = "clut"
    CLUT_MENU = "clut_menu"
    CLUT_X = "x"
    CLUT_Y = "y"
    NON_PORTABLE = "non_portable"


class PaintjobKey:
    SLOTS = "slots"
    COLORS = "colors"
    BASE_CHARACTER_ID = "base_character_id"


class SkinKey:
    SLOTS = "slots"
    COLORS = "colors"
    CHARACTER_ID = "character_id"
    VERTEX_OVERRIDES = "vertex_overrides"
