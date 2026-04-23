# coding: utf-8

from typing import Callable

from PySide6.QtWidgets import QWidget

from paintjob_designer.gui.dialog.pick_character_dialog import PickCharacterDialog
from paintjob_designer.models import CharacterProfile, KartType, Profile


class CharacterPicker:
    """Opens the modal character picker and returns the chosen `CharacterProfile`."""

    def __init__(self, profile_provider: Callable[[], Profile | None]) -> None:
        self._profile_provider = profile_provider

    def current_profile(self) -> Profile | None:
        return self._profile_provider()

    def pick(
        self,
        title: str,
        kart_type_filter: KartType | None = None,
        parent: QWidget | None = None,
    ) -> CharacterProfile | None:
        profile = self._profile_provider()
        if profile is None or not profile.characters:
            return None

        dialog = PickCharacterDialog(
            profile.characters,
            title=title,
            kart_type_filter=kart_type_filter,
            parent=parent,
        )
        if dialog.exec() != PickCharacterDialog.DialogCode.Accepted:
            return None

        chosen_id = dialog.selected_character_id()
        if chosen_id is None:
            return None

        return next(
            (c for c in profile.characters if c.id == chosen_id), None,
        )
