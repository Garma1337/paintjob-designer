# coding: utf-8

import json

from paintjob_designer.models import (
    CharacterProfile,
    ClutCoord,
    KartType,
    PaintjobSlotProfile,
    Profile,
    SlotProfile,
    VramPageDimensions,
)
from paintjob_designer.schema_keys import CommonKey, ProfileKey


class ProfileReader:
    """Parses a target-profile JSON document into a `Profile`."""

    def read(self, data: str | bytes) -> Profile:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        return self._parse(json.loads(data))

    def _parse(self, raw: dict) -> Profile:
        if not isinstance(raw, dict):
            raise ValueError("Profile root must be a JSON object")

        schema_version = int(
            raw.get(CommonKey.SCHEMA_VERSION, Profile.SCHEMA_VERSION),
        )
        if schema_version != Profile.SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported profile schema_version {schema_version} "
                f"(expected {Profile.SCHEMA_VERSION})"
            )

        vram = raw.get(ProfileKey.VRAM_PAGE) or {}
        vram_page = VramPageDimensions(
            width=int(vram.get(ProfileKey.WIDTH, 1024)),
            height=int(vram.get(ProfileKey.HEIGHT, 512)),
        )

        characters = [
            self._parse_character(c) for c in raw.get(ProfileKey.CHARACTERS, [])
        ]
        paintjob_slots = [
            self._parse_paintjob_slot(s)
            for s in raw.get(ProfileKey.PAINTJOB_SLOTS, [])
        ]

        return Profile(
            schema_version=schema_version,
            id=str(raw.get(CommonKey.ID, "")),
            display_name=str(raw.get(CommonKey.DISPLAY_NAME, "")),
            vram_page=vram_page,
            characters=characters,
            paintjob_slots=paintjob_slots,
        )

    def _parse_paintjob_slot(self, raw: dict) -> PaintjobSlotProfile:
        default_char_raw = raw.get(ProfileKey.DEFAULT_CHARACTER_ID)
        default_character_id: str | None = (
            str(default_char_raw) if default_char_raw else None
        )

        return PaintjobSlotProfile(
            name=str(raw.get(CommonKey.NAME, "")),
            default_character_id=default_character_id,
        )

    def _parse_character(self, raw: dict) -> CharacterProfile:
        kart_type_raw = str(raw.get(ProfileKey.KART_TYPE, KartType.KART.value))

        try:
            kart_type = KartType(kart_type_raw)
        except ValueError as exc:
            raise ValueError(
                f"Unknown kart_type {kart_type_raw!r} for character "
                f"{raw.get(CommonKey.ID, '?')!r}"
            ) from exc

        return CharacterProfile(
            id=str(raw.get(CommonKey.ID, "")),
            display_name=str(raw.get(CommonKey.DISPLAY_NAME, "")),
            mesh_source=str(raw.get(ProfileKey.MESH_SOURCE, "")),
            kart_type=kart_type,
            kart_slots=[
                self._parse_slot(s) for s in raw.get(ProfileKey.KART_SLOTS, [])
            ],
            skin_slots=[
                self._parse_slot(s) for s in raw.get(ProfileKey.SKIN_SLOTS, [])
            ],
        )

    def _parse_slot(self, raw: dict) -> SlotProfile:
        clut_raw = raw.get(ProfileKey.CLUT) or {}
        clut_menu_raw = raw.get(ProfileKey.CLUT_MENU)

        clut_menu = None
        if clut_menu_raw is not None:
            clut_menu = ClutCoord(
                x=int(clut_menu_raw.get(ProfileKey.CLUT_X, 0)),
                y=int(clut_menu_raw.get(ProfileKey.CLUT_Y, 0)),
            )

        return SlotProfile(
            name=str(raw.get(CommonKey.NAME, "")),
            clut=ClutCoord(
                x=int(clut_raw.get(ProfileKey.CLUT_X, 0)),
                y=int(clut_raw.get(ProfileKey.CLUT_Y, 0)),
            ),
            clut_menu=clut_menu,
            non_portable=bool(raw.get(ProfileKey.NON_PORTABLE, False)),
        )
