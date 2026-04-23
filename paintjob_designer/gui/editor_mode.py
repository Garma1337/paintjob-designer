# coding: utf-8

from enum import Enum


class EditorMode(str, Enum):
    """Which side of the app the main window is currently editing.

    `PAINTJOB` / `SKIN` edit a single asset in their respective tab;
    `PREVIEW` composites an existing paintjob + skin and is read-only.
    The string values persist in the per-tab `remembered_character_id`
    dict, so they're part of an in-memory contract, not just labels.
    """

    PAINTJOB = "paintjob"
    SKIN = "skin"
    PREVIEW = "preview"
