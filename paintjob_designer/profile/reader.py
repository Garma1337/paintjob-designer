# coding: utf-8

import json

from paintjob_designer.models import (
    CharacterProfile,
    ClutCoord,
    PaintjobSlotProfile,
    Profile,
    SlotProfile,
    VramPageDimensions,
)


class ProfileReader:
    """Parses a target-profile JSON document into a `Profile`."""

    def read(self, data: str | bytes) -> Profile:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        return self._parse(json.loads(data))

    def _parse(self, raw: dict) -> Profile:
        if not isinstance(raw, dict):
            raise ValueError("Profile root must be a JSON object")

        schema_version = int(raw.get("schema_version", Profile.SCHEMA_VERSION))
        if schema_version != Profile.SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported profile schema_version {schema_version} "
                f"(expected {Profile.SCHEMA_VERSION})"
            )

        vram = raw.get("vram_page") or {}
        vram_page = VramPageDimensions(
            width=int(vram.get("width", 1024)),
            height=int(vram.get("height", 512)),
        )

        characters = [self._parse_character(c) for c in raw.get("characters", [])]
        paintjob_slots = [
            self._parse_paintjob_slot(s) for s in raw.get("paintjob_slots", [])
        ]

        return Profile(
            schema_version=schema_version,
            id=str(raw.get("id", "")),
            display_name=str(raw.get("display_name", "")),
            vram_page=vram_page,
            characters=characters,
            paintjob_slots=paintjob_slots,
        )

    def _parse_paintjob_slot(self, raw: dict) -> PaintjobSlotProfile:
        default_char_raw = raw.get("default_character_id")
        default_character_id: str | None = (
            str(default_char_raw) if default_char_raw else None
        )

        return PaintjobSlotProfile(
            name=str(raw.get("name", "")),
            default_character_id=default_character_id,
        )

    def _parse_character(self, raw: dict) -> CharacterProfile:
        return CharacterProfile(
            id=str(raw.get("id", "")),
            display_name=str(raw.get("display_name", "")),
            mesh_source=str(raw.get("mesh_source", "")),
            slots=[self._parse_slot(s) for s in raw.get("slots", [])],
        )

    def _parse_slot(self, raw: dict) -> SlotProfile:
        clut_raw = raw.get("clut") or {}
        clut_menu_raw = raw.get("clut_menu")

        clut_menu = None
        if clut_menu_raw is not None:
            clut_menu = ClutCoord(
                x=int(clut_menu_raw.get("x", 0)),
                y=int(clut_menu_raw.get("y", 0)),
            )

        return SlotProfile(
            name=str(raw.get("name", "")),
            clut=ClutCoord(
                x=int(clut_raw.get("x", 0)),
                y=int(clut_raw.get("y", 0)),
            ),
            clut_menu=clut_menu,
        )
