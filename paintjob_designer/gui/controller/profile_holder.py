# coding: utf-8

from paintjob_designer.models import Profile


class ProfileHolder:
    """Mutable cell carrying the active `Profile`."""

    def __init__(self) -> None:
        self._profile: Profile | None = None

    def get(self) -> Profile | None:
        return self._profile

    def set(self, profile: Profile | None) -> None:
        self._profile = profile

    def display_name_for(self, character_id: str | None) -> str:
        """Resolve a character id to its profile display name.

        Falls back to the id itself when no profile is loaded, the id is
        empty, or the id isn't in the active profile — that way labels
        always render *something* sensible.
        """
        if not character_id or self._profile is None:
            return character_id or ""

        for character in self._profile.characters:
            if character.id == character_id:
                return character.display_name or character.id

        return character_id
