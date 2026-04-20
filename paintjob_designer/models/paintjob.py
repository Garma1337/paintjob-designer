# coding: utf-8

import base64
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer

from paintjob_designer.models.color import PsxColor


CANONICAL_SLOT_NAMES = (
    "front", "back", "floor", "brown",
    "motorside", "motortop", "bridge", "exhaust",
)


class SlotRegionPixels(BaseModel):
    """4bpp pixel payload for one VRAM region of a slot.

    A slot can occupy multiple VRAM rects that share its CLUT (same
    palette, different pieces of geometry). When an artist imports a
    custom texture for a slot, each region needs its own pixel buffer
    — identified here by its VRAM position so the assignment survives
    re-parsing the character mesh in a different order.

    `pixels` is 4bpp packed: two pixels per byte, low nibble = left
    pixel, same layout the PSX GPU samples. Serializes as base64 in
    the JSON field `data`; round-trips cleanly to/from Python `bytes`.
    Python attribute stays `pixels` so call sites read naturally.
    """

    model_config = ConfigDict(frozen=False, populate_by_name=True)

    vram_x: int = 0
    vram_y: int = 0
    width: int = 0
    height: int = 0
    pixels: "_Base64Bytes" = Field(
        default=b"",
        alias="data",
        serialization_alias="data",
        json_schema_extra={"contentEncoding": "base64"},
    )

    @staticmethod
    def decode_base64(value: Any) -> bytes:
        """Accept raw bytes or a base64 string on input.

        Pydantic serializes bytes as base64 by default, so JSON brings a
        string; in-process construction (the importer building a fresh
        `SlotRegionPixels`) passes raw bytes. Both shapes must land on
        the same `bytes` field.
        """
        if isinstance(value, bytes):
            return value

        if isinstance(value, str):
            return base64.b64decode(value, validate=True)

        raise TypeError(
            f"Expected bytes or base64 string, got {type(value).__name__}",
        )

    @staticmethod
    def encode_base64(value: bytes) -> str:
        """Serialize raw bytes back to a base64 ASCII string for JSON."""
        return base64.b64encode(value).decode("ascii")


_Base64Bytes = Annotated[
    bytes,
    BeforeValidator(SlotRegionPixels.decode_base64),
    PlainSerializer(SlotRegionPixels.encode_base64, return_type=str),
]

SlotRegionPixels.model_rebuild(_types_namespace={"_Base64Bytes": _Base64Bytes})


class SlotColors(BaseModel):
    """One CLUT slot on a paintjob: 16 colors + optional per-region pixels.

    `colors` is always the 16-entry palette the slot's geometry samples
    through — CLUT-only paintjobs use this alone, with the character's
    vanilla texture pixels underneath.

    `pixels` is empty for CLUT-only slots and populated when the artist
    imports a custom texture — one `SlotRegionPixels` per VRAM region
    the slot occupies. Imported textures only carry across characters
    whose mesh UV rects for this slot match the stored dimensions; the
    designer restricts imports to slots whose dims are invariant across
    all profile characters so that portability is automatic.
    """

    model_config = ConfigDict(frozen=False)

    SIZE: ClassVar[int] = 16

    colors: list[PsxColor] = Field(default_factory=list)
    pixels: list[SlotRegionPixels] = Field(default_factory=list)


class Paintjob(BaseModel):
    """A single paintjob: 8 slots × 16 colors, optionally with custom textures.

    Paintjobs are character-agnostic. A CLUT-only paintjob applies to
    any character — palette swaps reuse each character's vanilla pixels.
    A paintjob that imports a custom texture for a slot also applies to
    any character, **as long as the slot's VRAM rect dimensions match
    across those characters**. The designer enforces this by only
    allowing texture imports on dim-invariant slots (currently 7 of 8 —
    all except `floor`, whose rect size differs per character).

    `base_character_id` is a soft, non-authoritative hint used for:
      - **Preview fallback** — slots the paintjob hasn't explicitly authored
        inherit colors from that character's VRAM so the 3D preview matches
        the character's unpainted look.
      - **Reopen context** — loading a saved paintjob restores the preview
        character the artist had active when they saved.

    Consumer tools should ignore it for dispatch decisions.
    """

    model_config = ConfigDict(frozen=False)

    SCHEMA_VERSION: ClassVar[int] = 1

    schema_version: int = SCHEMA_VERSION
    name: str = ""
    author: str = ""
    base_character_id: str | None = None
    slots: dict[str, SlotColors] = Field(default_factory=dict)

    def has_any_pixels(self) -> bool:
        """True when any slot carries imported pixel data.

        Used by the sidebar to show a "textured" marker next to paintjobs
        that ship custom pixels in addition to CLUT swaps.
        """
        return any(slot.pixels for slot in self.slots.values())


class PaintjobLibrary(BaseModel):
    """Ordered collection of paintjobs the session is working on.

    Not itself serialized to one JSON file — saved as a *directory* of
    `NN_<slug>.json` files, where the filename prefix encodes the
    library index. The library is still a proper pydantic model so
    in-memory operations (add/remove/move) benefit from validation and
    so test fixtures can instantiate cleanly.
    """

    model_config = ConfigDict(frozen=False)

    paintjobs: list[Paintjob] = Field(default_factory=list)

    def count(self) -> int:
        return len(self.paintjobs)

    def add(self, paintjob: Paintjob) -> int:
        """Append `paintjob` to the library and return its new index."""
        self.paintjobs.append(paintjob)
        return len(self.paintjobs) - 1

    def remove(self, index: int) -> Paintjob:
        """Pop the paintjob at `index` and return it.

        Raises `IndexError` on an out-of-range index — callers should guard
        on `count()` first rather than rely on exception handling for
        normal UI flow.
        """
        return self.paintjobs.pop(index)

    def move(self, from_index: int, to_index: int) -> None:
        """Reorder: move a paintjob to a new position.

        `to_index` is interpreted on the list state AFTER the source has
        been removed — same semantics as drag-and-drop in Qt's list views,
        so the sidebar can forward its indices verbatim.
        """
        pj = self.paintjobs.pop(from_index)
        to_index = max(0, min(to_index, len(self.paintjobs)))
        self.paintjobs.insert(to_index, pj)

    def find_by_base_character(self, character_id: str) -> Paintjob | None:
        """Return the paintjob whose `base_character_id` matches, or None."""
        for pj in self.paintjobs:
            if pj.base_character_id == character_id:
                return pj

        return None
