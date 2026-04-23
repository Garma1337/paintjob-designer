# coding: utf-8

from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QWidget

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.color.transform import ColorTransformer
from paintjob_designer.gui.command.bulk_transform_command import BulkColorEdit, BulkTransformCommand
from paintjob_designer.gui.handler.color_handler import ColorHandler
from paintjob_designer.gui.widget.slot_editor import SlotEditor
from paintjob_designer.gui.widget.transform_panel import TransformCandidate, TransformColorsPanel
from paintjob_designer.models import CharacterProfile, Paintjob, PsxColor, Skin, SlotColors
from paintjob_designer.render.atlas_renderer import AtlasRenderer

# (asset_id, slot_name) — id() because Paintjob/Skin aren't hashable.
SnapshotKey = tuple[int, str]
# (asset, slot, snapshotted SlotColors | None)
SnapshotEntry = tuple[object, object, SlotColors | None]


class TransformPanelCoordinator(QObject):
    """Owns the modeless Transform Colors panel + its snapshot/preview/commit
    lifecycle.

    Operates on the *active asset* (Paintjob in paintjob mode, Skin in
    skin mode). Both have the same `.slots[name] -> SlotColors` shape so
    the apply path duck-types on it.
    """

    def __init__(
        self,
        color_transformer: ColorTransformer,
        color_converter: ColorConverter,
        color_handler: ColorHandler,
        slot_editor_provider: Callable[[], SlotEditor],
        kart_viewer_provider: Callable[[], object],
        bundle_provider: Callable[[], object | None],
        asset_provider: Callable[[], Paintjob | Skin | None],
        character_provider: Callable[[], CharacterProfile | None],
        editor_mode_provider: Callable[[], str],
        iso_root_provider: Callable[[], str],
        undo_stack: QUndoStack,
        parent_widget: QWidget | None = None,
    ) -> None:
        super().__init__(parent_widget)
        self._transformer = color_transformer
        self._converter = color_converter
        self._color_handler = color_handler
        self._slot_editor_provider = slot_editor_provider
        self._kart_viewer_provider = kart_viewer_provider
        self._bundle_provider = bundle_provider
        self._asset_provider = asset_provider
        self._character_provider = character_provider
        self._editor_mode_provider = editor_mode_provider
        self._iso_root_provider = iso_root_provider
        self._undo_stack = undo_stack
        self._parent_widget = parent_widget

        self._panel: TransformColorsPanel | None = None
        self._snapshot: dict[SnapshotKey, SnapshotEntry] | None = None
        self._dirty_keys: set[SnapshotKey] = set()

    def show(self, slot_override: str | None = None) -> None:
        # Refuse to open in preview mode (read-only) or when there's no
        # active asset / bundle to mutate.
        if self._editor_mode_provider() not in ("paintjob", "skin"):
            return
        if self._bundle_provider() is None or self._asset_provider() is None:
            return

        self._ensure_panel()
        self.refresh(slot_override=slot_override)

        if slot_override is not None:
            self._panel.select_slot_scope()

        if not self._panel.isVisible():
            self._take_snapshot()
            self._panel.show()
        else:
            self._panel.raise_()
            self._panel.activateWindow()

    def refresh(self, slot_override: str | None = None) -> None:
        """Rebuild candidate lists for the panel against current state."""
        if self._panel is None:
            return

        bundle = self._bundle_provider()
        asset = self._asset_provider()
        if bundle is None or asset is None:
            return

        slot_name = slot_override or self._slot_editor_provider().focused_slot()
        slot_candidates: list[TransformCandidate] = []
        if slot_name is not None:
            target_slot = bundle.slot_regions.slots.get(slot_name)
            if target_slot is not None:
                slot_candidates = self._build_candidates([target_slot])

        # Strict separation: the panel only exposes the scope that
        # matches the active asset's owning side. Off-mode lists are
        # empty so the panel disables those scope options.
        mode = self._editor_mode_provider()
        kart_slot_candidates = (
            self._build_candidates(self._slots_in_group("kart"))
            if mode == "paintjob" else []
        )
        skin_slot_candidates = (
            self._build_candidates(self._slots_in_group("skin"))
            if mode == "skin" else []
        )

        self._panel.set_candidates(
            slot_candidates,
            kart_slot_candidates,
            skin_slot_candidates,
            slot_name or "",
        )

    def close_pending_preview(self) -> None:
        """Restore any in-flight preview and drop the snapshot."""
        if self._snapshot is None:
            return

        self._restore_snapshot()
        self._snapshot = None
        self._dirty_keys = set()

    def is_visible(self) -> bool:
        return self._panel is not None and self._panel.isVisible()

    def _ensure_panel(self) -> None:
        if self._panel is not None:
            return

        panel = TransformColorsPanel(
            color_transformer=self._transformer,
            color_converter=self._converter,
            parent=self._parent_widget,
        )

        panel.preview_changed.connect(self._on_preview)
        panel.commit_requested.connect(self._on_commit)
        panel.closing.connect(self.close_pending_preview)
        self._panel = panel

    def _slots_in_group(self, group: str) -> list:
        bundle = self._bundle_provider()
        character = self._character_provider()
        if bundle is None or character is None:
            return []

        if group == "kart":
            slot_names = {s.name for s in character.kart_slots}
        else:
            slot_names = {s.name for s in character.skin_slots}

        return [
            slot for name, slot in bundle.slot_regions.slots.items()
            if name in slot_names
        ]

    def _take_snapshot(self) -> None:
        bundle = self._bundle_provider()
        if bundle is None:
            return

        candidates = self._build_candidates(
            list(bundle.slot_regions.slots.values()),
        )

        snapshot: dict[SnapshotKey, SnapshotEntry] = {}
        for cand in candidates:
            key = (id(cand.asset), cand.slot.slot_name)
            if key in snapshot:
                continue
            snapshot[key] = (
                cand.asset, cand.slot,
                self._snapshot_slot_colors(cand.asset, cand.slot.slot_name),
            )

        self._snapshot = snapshot
        self._dirty_keys = set()

    def _on_preview(self, edits: list[BulkColorEdit]) -> None:
        """Live preview: revert previous-pass residue, apply new edits, upload."""
        if self._snapshot is None or self._bundle_provider() is None:
            return

        bundle = self._bundle_provider()
        new_dirty = {(id(e.asset), e.slot.slot_name) for e in edits}

        # Revert union of old + new dirty so cross-slot drift cleans up.
        for key in self._dirty_keys | new_dirty:
            asset, slot, colors = self._snapshot[key]
            restored = self._color_handler.restore_slot(
                self._iso_root_provider(),
                bundle.atlas_rgba, asset, slot, colors,
            )
            self._slot_editor_provider().set_slot_colors(slot.slot_name, restored)

        # Apply grouped by slot, then a single full-atlas upload — the
        # viewer's pending-region tuple holds only the latest, so per-region
        # uploads would drop all but one within a paintGL cycle.
        by_slot: dict[SnapshotKey, list[BulkColorEdit]] = {}
        for edit in edits:
            by_slot.setdefault(
                (id(edit.asset), edit.slot.slot_name), [],
            ).append(edit)

        for key, slot_edits in by_slot.items():
            asset, slot, _ = self._snapshot[key]
            self._color_handler.apply_edits(
                self._iso_root_provider(),
                bundle.atlas_rgba, asset, slot,
                [(e.color_index, e.new_color) for e in slot_edits],
            )

            for e in slot_edits:
                self._slot_editor_provider().update_color(
                    slot.slot_name, e.color_index, e.new_color,
                )

        self._kart_viewer_provider().set_atlas(
            bundle.atlas_rgba, AtlasRenderer.ATLAS_WIDTH, AtlasRenderer.ATLAS_HEIGHT,
        )

        self._dirty_keys = new_dirty

    def _on_commit(self, edits: list[BulkColorEdit]) -> None:
        if self._bundle_provider() is None or not edits or self._snapshot is None:
            return

        # Rewind preview so the undo command sees the pre-preview state
        # as its base, then apply the committed edits and push undo.
        self._restore_snapshot()
        self._apply_committed_edits(edits)
        self._undo_stack.push(BulkTransformCommand(
            self._parent_widget,
            f"Transform {len(edits)} color{'s' if len(edits) != 1 else ''}",
            edits,
        ))

        self._take_snapshot()
        self._panel.commit_finished()

    def _restore_snapshot(self) -> None:
        if self._snapshot is None or not self._dirty_keys:
            self._dirty_keys.clear()
            return

        bundle = self._bundle_provider()
        if bundle is None:
            self._dirty_keys.clear()
            return

        for key in self._dirty_keys:
            asset, slot, colors = self._snapshot[key]
            restored = self._color_handler.restore_slot(
                self._iso_root_provider(),
                bundle.atlas_rgba, asset, slot, colors,
            )
            self._slot_editor_provider().set_slot_colors(slot.slot_name, restored)

        self._kart_viewer_provider().set_atlas(
            bundle.atlas_rgba, AtlasRenderer.ATLAS_WIDTH, AtlasRenderer.ATLAS_HEIGHT,
        )
        self._dirty_keys.clear()

    def _apply_committed_edits(self, edits: list[BulkColorEdit]) -> None:
        """Apply committed transform edits without going through the undo
        stack — used by the commit path before the undo command is pushed."""
        bundle = self._bundle_provider()
        if bundle is None:
            return

        by_slot: dict[SnapshotKey, list[BulkColorEdit]] = {}
        for e in edits:
            by_slot.setdefault((id(e.asset), e.slot.slot_name), []).append(e)

        for key, slot_edits in by_slot.items():
            asset = slot_edits[0].asset
            slot = slot_edits[0].slot
            self._color_handler.apply_edits(
                self._iso_root_provider(),
                bundle.atlas_rgba, asset, slot,
                [(e.color_index, e.new_color) for e in slot_edits],
            )

            if asset is self._asset_provider():
                for e in slot_edits:
                    self._slot_editor_provider().update_color(
                        slot.slot_name, e.color_index, e.new_color,
                    )

        self._kart_viewer_provider().set_atlas(
            bundle.atlas_rgba, AtlasRenderer.ATLAS_WIDTH, AtlasRenderer.ATLAS_HEIGHT,
        )

    def _build_candidates(self, slots) -> list[TransformCandidate]:
        asset = self._asset_provider()
        if asset is None:
            return []

        result: list[TransformCandidate] = []
        for slot in slots:
            if slot.slot_name in asset.slots:
                colors = asset.slots[slot.slot_name].colors
            else:
                colors = self._color_handler.default_slot_colors(
                    self._iso_root_provider(), slot,
                )

            for i, color in enumerate(colors):
                result.append(TransformCandidate(
                    asset=asset,
                    slot=slot,
                    color_index=i,
                    current_color=PsxColor(value=color.value),
                ))

        return result

    def _snapshot_slot_colors(
        self, asset: Paintjob | Skin, slot_name: str,
    ) -> SlotColors | None:
        slot = asset.slots.get(slot_name)
        if slot is None:
            return None

        return SlotColors(
            colors=[PsxColor(value=c.value) for c in slot.colors],
            pixels=list(slot.pixels),
        )
