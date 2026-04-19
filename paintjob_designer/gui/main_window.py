# coding: utf-8

from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.color.transform import ColorTransformer
from paintjob_designer.config.iso_root_validator import IsoRootValidator
from paintjob_designer.config.store import AppConfig, ConfigStore
from paintjob_designer.ctr.vertex_assembler import VertexAssembler
from paintjob_designer.exporters.binary_exporter import BinaryExporter
from paintjob_designer.exporters.source_code_exporter import SourceCodeExporter
from paintjob_designer.gui.command.bulk_transform_command import (
    BulkTransformCommand,
)
from paintjob_designer.gui.command.reset_slot_command import ResetSlotCommand
from paintjob_designer.gui.command.set_slot_color_command import SetSlotColorCommand
from paintjob_designer.gui.dialog.profile_picker_dialog import (
    ProfilePickerDialog,
)
from paintjob_designer.gui.dialog.source_code_export_options_dialog import (
    SourceCodeExportOptionsDialog,
)
from paintjob_designer.gui.dialog.transform_colors_dialog import (
    TransformCandidate,
    TransformColorsDialog,
    TransformScope,
)
from paintjob_designer.gui.handler.character_handler import (
    BroughtUpCharacter,
    CharacterHandler,
)
from paintjob_designer.gui.handler.color_handler import ColorHandler
from paintjob_designer.gui.handler.project_handler import ProjectHandler
from paintjob_designer.gui.widget.character_sidebar import CharacterSidebar
from paintjob_designer.gui.widget.color_picker import PsxColorPicker
from paintjob_designer.gui.widget.kart_viewer import KartViewer
from paintjob_designer.gui.widget.slot_editor import SlotEditor
from paintjob_designer.models import (
    CharacterProfile,
    Paintjob,
    Profile,
    PsxColor,
    SlotColors,
)
from paintjob_designer.profile.registry import ProfileRegistry
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from paintjob_designer.render.atlas_uv_mapper import AtlasUvMapper

_PAINTJOB_EXT = ".json"
_SOURCE_CODE_EXT = ".c"
_BINARY_EXT = ".bin"

_PAINTJOB_FILTER = f"Paintjob (*{_PAINTJOB_EXT})"
_SOURCE_CODE_FILTER = f"Source code (*{_SOURCE_CODE_EXT})"
_BINARY_FILTER = f"Paintjob binary (*{_BINARY_EXT})"


class MainWindow(QMainWindow):
    """Single-editor window: pick a character, edit its CLUT slots, save/export.

    There's no "project" concept — every character the user touches keeps its
    edits in an in-memory `Paintjob` until the app closes. Saving produces a
    character-agnostic JSON file for the *current* character; opening a
    paintjob applies it to the current character (it doesn't carry its own
    binding). Batch exports handle the "whole roster" case separately.
    """

    def __init__(
        self,
        config_store: ConfigStore,
        iso_root_validator: IsoRootValidator,
        profile_registry: ProfileRegistry,
        character_handler: CharacterHandler,
        color_handler: ColorHandler,
        project_handler: ProjectHandler,
        source_code_exporter: SourceCodeExporter,
        binary_exporter: BinaryExporter,
        color_converter: ColorConverter,
        color_picker: PsxColorPicker,
        vertex_assembler: VertexAssembler,
        atlas_uv_mapper: AtlasUvMapper,
        color_transformer: ColorTransformer,
    ) -> None:
        super().__init__()
        self._config_store = config_store
        self._validator = iso_root_validator
        self._profile_registry = profile_registry
        self._character_handler = character_handler
        self._color_handler = color_handler
        self._project_handler = project_handler
        self._source_code_exporter = source_code_exporter
        self._binary_exporter = binary_exporter
        self._color_converter = color_converter
        self._color_picker = color_picker
        self._vertex_assembler = vertex_assembler
        self._atlas_uv_mapper = atlas_uv_mapper
        self._color_transformer = color_transformer

        self._config: AppConfig = self._config_store.load()
        self._profile: Profile | None = None

        # Session edits keyed by character id.
        self._paintjob = Paintjob()

        self._current_character: CharacterProfile | None = None
        self._current_bundle: BroughtUpCharacter | None = None

        # Slot → triangle indices lookup for focus-highlight in the 3D view.
        self._slot_triangle_mask: dict[str, list[int]] = {}

        # One undo stack for the whole session. Clicking between characters
        # doesn't clear it — Ctrl+Z still unwinds edits across character
        # boundaries, which matches what users expect from a single-editor app.
        self._undo_stack = QUndoStack(self)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_index: int = -1
        self._anim_frame_index: int = 0

        self.resize(1440, 900)
        self.setAcceptDrops(True)
        self.setWindowTitle("Paintjob Designer")

        self._build_menu_bar()
        self._build_ui()
        self._bootstrap()

    def dragEnterEvent(self, event) -> None:
        if self._drop_path(event) is not None:
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if self._drop_path(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        path = self._drop_path(event)
        if path is None:
            return

        event.acceptProposedAction()

        if not self._require_character():
            return

        self._apply_paintjob_file_to(self._current_character, path)

    def _drop_path(self, event) -> Path | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None

        urls = [u for u in mime.urls() if u.isLocalFile()]
        if len(urls) != 1:
            return None

        path = Path(urls[0].toLocalFile())
        if not path.name.lower().endswith(_PAINTJOB_EXT):
            return None

        return path

    def _build_menu_bar(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        self._add_action(
            file_menu, "&Load ISO...", self._on_load_iso,
            shortcut=QKeySequence("Ctrl+L"),
        )

        self._add_action(
            file_menu, "Switch &Profile...", self._on_switch_profile,
        )

        file_menu.addSeparator()
        self._add_action(
            file_menu, "E&xit", self.close,
            shortcut=QKeySequence.StandardKey.Quit,
        )

        edit_menu = menubar.addMenu("&Edit")
        undo_action = self._undo_stack.createUndoAction(self, "&Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)
        redo_action = self._undo_stack.createRedoAction(self, "&Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)

        view_menu = menubar.addMenu("&View")
        self._add_action(
            view_menu, "Reset &Camera", self._on_reset_camera,
            shortcut=QKeySequence("R"),
        )

        self._refresh_action_state()

    def _add_action(
        self,
        menu: QMenu,
        text: str,
        slot,
        shortcut: QKeySequence | None = None,
    ) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)

        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _refresh_action_state(self) -> None:
        has_iso = self._is_iso_ready()

        # The export-all toolbar is built after the menu bar, so this method
        # gets called once before the actions exist — guard accordingly.
        if hasattr(self, "_action_export_all_json"):
            self._action_export_all_json.setEnabled(has_iso)
            self._action_export_all_code.setEnabled(has_iso)
            self._action_export_all_binary.setEnabled(has_iso)

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.addWidget(QLabel("Characters"))
        self._sidebar = CharacterSidebar()
        self._sidebar.character_selected.connect(self._on_character_selected)
        self._sidebar.character_context_requested.connect(self._on_sidebar_context)
        sidebar_layout.addWidget(self._sidebar)
        sidebar_layout.addWidget(self._build_animation_panel())

        self._kart_viewer = KartViewer(self._atlas_uv_mapper)
        self._kart_viewer.gl_init_failed.connect(self._on_gl_init_failed)

        self._slot_editor = SlotEditor(self._color_converter)
        self._slot_editor.color_edit_requested.connect(self._on_color_edit_requested)
        self._slot_editor.slot_reset_requested.connect(self._on_slot_reset_requested)
        self._slot_editor.slot_focus_changed.connect(self._on_slot_focus_changed)
        self._slot_editor.context_requested.connect(self._on_slot_editor_context)

        splitter.addWidget(sidebar_container)
        splitter.addWidget(self._kart_viewer)
        splitter.addWidget(self._slot_editor)

        # Stored so `_on_gl_init_failed` can swap the viewer for a placeholder
        # without having to re-walk the splitter hierarchy.
        self._splitter = splitter
        self._kart_viewer_index = 1
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 600, 600])

        self.setCentralWidget(splitter)
        self._build_export_all_toolbar()

        # Permanent status-bar widget so the active profile is always visible
        # regardless of what transient message `showMessage` is showing.
        self._profile_status_label = QLabel()
        self.statusBar().addPermanentWidget(self._profile_status_label)
        self._update_window_title()

        self.statusBar().showMessage("Ready.")
        self._refresh_action_state()

    def _build_export_all_toolbar(self) -> None:
        """Top toolbar with the batch-export actions.

        Per-character exports live on the sidebar context menu (right-click a
        character) — the distinction is: toolbar = "everything I've edited",
        context menu = "this one character".
        """
        toolbar = self.addToolBar("Export All")
        toolbar.setMovable(False)

        self._action_export_all_json = toolbar.addAction(
            "Export as JSON", self._on_export_all_json,
        )

        self._action_export_all_code = toolbar.addAction(
            "Export as Code", self._on_export_all_code,
        )

        self._action_export_all_binary = toolbar.addAction(
            "Export as Binary", self._on_export_all_binary,
        )

        toolbar.addSeparator()

        self._action_transform_all = toolbar.addAction(
            "Transform Colors...",
            lambda: self._open_transform_dialog(
                scope=TransformScope.ENTIRE_KART,
                slot_name=None,
                match_color=None,
            ),
        )

        toolbar.addSeparator()
        toolbar.addAction("Switch Profile...", self._on_switch_profile)

        self.addToolBarBreak()

    def _build_animation_panel(self) -> QWidget:
        """Inline animation controls shown below the character list.

        Kept compact (grouped in a QGroupBox) because the sidebar is narrow —
        larger layouts would push the character list off-screen.
        """
        group = QGroupBox("Animation")
        layout = QFormLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._anim_combo = QComboBox()
        self._anim_combo.currentIndexChanged.connect(self._on_anim_selected)
        layout.addRow("Clip:", self._anim_combo)

        play_row = QWidget()
        play_layout = QHBoxLayout(play_row)
        play_layout.setContentsMargins(0, 0, 0, 0)
        play_layout.setSpacing(6)
        self._anim_play_button = QPushButton("Play")
        self._anim_play_button.clicked.connect(self._on_anim_play_clicked)
        play_layout.addWidget(self._anim_play_button)
        self._anim_frame_label = QLabel("—")
        self._anim_frame_label.setMinimumWidth(60)
        play_layout.addWidget(self._anim_frame_label, 1)
        layout.addRow("Frame:", play_row)

        self._anim_fps_spin = QSpinBox()
        self._anim_fps_spin.setRange(1, 60)
        self._anim_fps_spin.setValue(30)
        self._anim_fps_spin.setToolTip(
            "Playback speed in frames/second. PS1 animations don't carry an "
            "intended frame rate so this is just a preview control.",
        )
        self._anim_fps_spin.valueChanged.connect(self._on_anim_fps_changed)
        layout.addRow("FPS:", self._anim_fps_spin)

        self._set_animation_controls_enabled(False)
        return group

    def _on_anim_fps_changed(self, fps: int) -> None:
        self._anim_timer.setInterval(max(1, int(1000 / max(1, fps))))

    def _bootstrap(self) -> None:
        if self._validator.validate(self._config.iso_root).ok:
            self._load_profile(self._config.last_profile_id)
            return

        self.statusBar().showMessage(
            "No ISO loaded — use File → Load ISO... to pick your extracted CTR directory.",
        )

    def _load_profile(self, profile_id: str) -> None:
        try:
            self._profile = self._profile_registry.load(profile_id)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Profile not found", str(exc))
            return

        self._update_window_title()

        # Populating the sidebar auto-selects row 0 and emits the signal, so
        # the first character loads immediately without a second click.
        self._sidebar.set_profile(self._profile)
        self._refresh_action_state()

    def _profile_display_name(self) -> str:
        """Human-readable label for the active profile, or `"(none)"`."""
        if self._profile is None:
            return "(none)"

        return self._profile.display_name or self._profile.id

    def _update_window_title(self) -> None:
        """Bake the active profile into the window title so it's always visible."""
        self.setWindowTitle(f"Paintjob Designer — {self._profile_display_name()}")

        # Mirror the profile into the status bar as a permanent widget so it
        # stays visible even when the transient message area shows other info.
        label = getattr(self, "_profile_status_label", None)
        if label is not None:
            label.setText(f"Profile: {self._profile_display_name()}")

    def _is_iso_ready(self) -> bool:
        return self._validator.validate(self._config.iso_root).ok and self._profile is not None

    def _require_character(self) -> bool:
        if self._current_character is not None:
            return True

        QMessageBox.information(
            self, "Pick a character first",
            "Select a character on the left before performing this action.",
        )

        return False

    def _on_load_iso(self) -> None:
        start = self._config.iso_root or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(
            self, "Select extracted CTR ISO root", start,
        )

        if not chosen:
            return

        result = self._validator.validate(chosen)
        if not result.ok:
            QMessageBox.warning(
                self, "Not a valid CTR ISO",
                "The selected directory is missing required files:\n\n"
                + "\n".join(f"  • {p}" for p in result.missing),
            )

            return

        self._config.iso_root = chosen
        self._config_store.save(self._config)
        self._character_handler.invalidate_vram_cache()

        # A fresh ISO wipes any in-flight edits — they were keyed to characters
        # from the previous ISO's profile and wouldn't make sense against the new
        # one. Undo history goes with them.
        self._paintjob = Paintjob()
        self._current_character = None
        self._current_bundle = None
        self._undo_stack.clear()

        self._load_profile(self._config.last_profile_id)
        self.statusBar().showMessage("ISO loaded. Pick a character to begin.")

    def _apply_paintjob_file_to(self, character: CharacterProfile, path: Path) -> None:
        try:
            standalone = self._project_handler.open_standalone(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        self._project_handler.apply_standalone_to_character(
            self._paintjob, character.id, standalone,
        )

        # Opening from file isn't reversible through the existing edit
        # commands (their captured state refers to the pre-open slots), so
        # clear the stack rather than leaving stale entries in it.
        self._undo_stack.clear()

        # Reload so the atlas/3D/slot-editor all pick up the new slots.
        self._on_character_selected(character.id)
        self.statusBar().showMessage(
            f"Imported {path.name} onto {character.display_name}",
        )

    def _on_sidebar_context(self, character_id: str, global_pos: QPoint) -> None:
        """Show the per-character import/export menu next to the right-clicked row."""
        character = self._find_character(character_id)
        if character is None:
            return

        menu = QMenu(self)
        menu.addAction(
            "Import Paintjob from JSON...",
            lambda: self._on_import_json_for(character),
        )
        menu.addSeparator()
        menu.addAction(
            "Export Paintjob as JSON...",
            lambda: self._on_export_json_for(character),
        )
        menu.addAction(
            "Export Paintjob as Code...",
            lambda: self._on_export_code_for(character),
        )
        menu.exec(global_pos)

    def _on_import_json_for(self, character: CharacterProfile) -> None:
        """Load a paintjob JSON from disk and apply it to `character`."""
        if not self._ensure_character_loaded(character):
            return

        path_str, _ = QFileDialog.getOpenFileName(
            self, f"Import paintjob for {character.display_name}",
            self._config.iso_root or str(Path.home()),
            f"{_PAINTJOB_FILTER};;All files (*)",
        )

        if not path_str:
            return

        self._apply_paintjob_file_to(character, Path(path_str))

    def _find_character(self, character_id: str) -> CharacterProfile | None:
        if self._profile is None:
            return None

        for c in self._profile.characters:
            if c.id == character_id:
                return c

        return None

    def _ensure_character_loaded(self, character: CharacterProfile) -> bool:
        """Load the given character's bundle if it isn't the current one.

        The slot-default backfill used by exports reads from `_current_bundle`,
        so per-character exports via right-click need to warp the sidebar to
        that row first. Returns True if the bundle is usable afterwards.
        """
        if self._current_character is not None and self._current_character.id == character.id:
            return self._current_bundle is not None

        self._on_character_selected(character.id)
        return self._current_bundle is not None

    def _on_export_json_for(self, character: CharacterProfile) -> None:
        if not self._ensure_character_loaded(character):
            return

        default_name = f"{character.id}{_PAINTJOB_EXT}"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Export paintjob as JSON",
            default_name, _PAINTJOB_FILTER,
        )

        if not path_str:
            return

        path = Path(path_str)
        single = self._project_handler.extract_character_as_standalone(
            self._paintjob, character.id,
            defaults_by_slot=self._defaults_by_slot_for_current(),
        )

        try:
            self._project_handler.save_standalone(path, single)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return

        self.statusBar().showMessage(f"Exported {path.name}")

    def _on_export_code_for(self, character: CharacterProfile) -> None:
        if not self._ensure_character_loaded(character):
            return

        dialog = SourceCodeExportOptionsDialog(
            default_identifier=character.id,
            default_paint_index=self._character_paint_index(character.id),
            parent=self,
        )

        if dialog.exec() != SourceCodeExportOptionsDialog.DialogCode.Accepted:
            return

        options = dialog.options()
        if not options.identifier:
            QMessageBox.warning(self, "Identifier required", "Identifier can't be empty.")
            return

        default_name = f"{options.identifier}{_SOURCE_CODE_EXT}"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Export paintjob as code",
            default_name, _SOURCE_CODE_FILTER,
        )

        if not path_str:
            return

        single = self._project_handler.extract_character_as_standalone(
            self._paintjob, character.id,
            defaults_by_slot=self._defaults_by_slot_for_current(),
        )

        try:
            self._source_code_exporter.export_single(
                single, Path(path_str),
                identifier=options.identifier,
                paint_index=options.paint_index,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return

        self.statusBar().showMessage(f"Exported {Path(path_str).name}")

    def _on_export_all_json(self) -> None:
        if self._profile is None:
            return

        if not self._paintjob.characters:
            QMessageBox.information(
                self, "Nothing to export",
                "No characters have been edited yet. Pick a character and "
                "change at least one color before running a batch export.",
            )
            return

        dir_str = QFileDialog.getExistingDirectory(
            self, "Export all paintjobs (JSON)",
            str(Path.home()),
        )

        if not dir_str:
            return

        dest = Path(dir_str)
        saved = 0
        for character_id in self._paintjob.characters:
            single = self._project_handler.extract_character_as_standalone(
                self._paintjob, character_id,
            )

            try:
                self._project_handler.save_standalone(
                    dest / f"{character_id}{_PAINTJOB_EXT}", single,
                )
            except OSError as exc:
                QMessageBox.critical(self, "Export failed", str(exc))
                return

            saved += 1

        self.statusBar().showMessage(f"Exported {saved} paintjob(s) to {dir_str}")

    def _on_export_all_code(self) -> None:
        if self._profile is None:
            return

        if not self._paintjob.characters:
            QMessageBox.information(
                self, "Nothing to export",
                "No characters have been edited yet. Pick a character and "
                "change at least one color before running a batch export.",
            )
            return

        dir_str = QFileDialog.getExistingDirectory(
            self, "Export all paintjobs (source code)",
            str(Path.home()),
        )

        if not dir_str:
            return

        paint_index_by_character = {
            c.id: i + 1 for i, c in enumerate(self._profile.characters)
        }

        try:
            self._source_code_exporter.export_set(
                self._paintjob, Path(dir_str),
                paint_index_by_character=paint_index_by_character,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return

        self.statusBar().showMessage(
            f"Exported {len(self._paintjob.characters)} paintjob(s) to {dir_str}",
        )

    def _on_export_all_binary(self) -> None:
        if self._profile is None:
            return

        default_name = f"paintjobs{_BINARY_EXT}"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Export all paintjobs (binary)",
            default_name, _BINARY_FILTER,
        )

        if not path_str:
            return

        try:
            self._binary_exporter.export(
                self._paintjob, self._profile, Path(path_str),
            )
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return

        self.statusBar().showMessage(f"Exported {Path(path_str).name}")

    def _on_reset_camera(self) -> None:
        self._kart_viewer.reset_camera()

    def _on_switch_profile(self) -> None:
        """Let the user pick a different target profile.

        Switching profiles clears the in-memory session (character IDs differ
        between profiles, so old edits can't be trusted to map cleanly) and
        reloads the sidebar. The choice is persisted to `last_profile_id` so
        the next launch picks it up.
        """
        available = self._profile_registry.available()
        if not available:
            QMessageBox.warning(
                self, "No profiles available",
                "No profiles found under config/profiles/.",
            )

            return

        dialog = ProfilePickerDialog(
            available, self._config.last_profile_id, parent=self,
        )
        if dialog.exec() != ProfilePickerDialog.DialogCode.Accepted:
            return

        chosen = dialog.selected_profile_id()
        if chosen == self._config.last_profile_id and self._profile is not None:
            return

        self._config.last_profile_id = chosen
        self._config_store.save(self._config)

        # Reset session; character IDs / slot names / CLUT coords may all
        # differ between profiles. Safer to start clean than to silently drop
        # incompatible entries.
        self._paintjob = Paintjob()
        self._current_character = None
        self._current_bundle = None
        self._undo_stack.clear()

        self._load_profile(chosen)
        self._update_window_title()
        self.statusBar().showMessage(f"Switched to profile: {self._profile_display_name()}")

    def _on_gl_init_failed(self, reason: str) -> None:
        """Replace the 3D viewer with a placeholder when the GL context fails.

        Triggered by `KartViewer.gl_init_failed` — the usual cause is a driver
        without OpenGL 3.3 core support. The rest of the app (slot editor,
        sidebar, export menus) stays fully functional.
        """
        placeholder = QLabel(
            "3D preview unavailable.\n\n"
            "Your system's OpenGL support is insufficient for the kart viewer "
            "(requires OpenGL 3.3 core profile). You can still edit and export "
            "paintjobs — only the live 3D render is disabled.\n\n"
            f"Details: {reason}"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setStyleSheet("QLabel { background: #1f2024; color: #cccccc; padding: 24px; }")

        old = self._splitter.replaceWidget(self._kart_viewer_index, placeholder)
        if old is not None:
            old.deleteLater()

        # Calls that used to land on the viewer (highlight, set_atlas, ...)
        # would now crash; swap in a no-op stand-in that silently absorbs
        # them so the rest of the loading path doesn't need to know.
        self._kart_viewer = _NullKartViewer()
        self.statusBar().showMessage("3D preview disabled (GL init failed).")

    def _character_paint_index(self, character_id: str) -> int:
        """1-based position of a character in the active profile.

        Used as the default `PAINT<N>` aggregator index when exporting a single
        source file — the vanilla profile order matches CTR's own paintjob
        numbering, so this is almost always what the user wants.
        """
        if self._profile is None:
            return 1

        for i, c in enumerate(self._profile.characters):
            if c.id == character_id:
                return i + 1

        return 1

    def _on_character_selected(self, character_id: str) -> None:
        if self._profile is None:
            return

        character = next(
            (c for c in self._profile.characters if c.id == character_id),
            None,
        )

        if character is None:
            return

        try:
            bundle = self._character_handler.load_character(
                self._config.iso_root, character, self._paintjob,
            )
        except FileNotFoundError as exc:
            self.statusBar().showMessage(f"Load failed: {exc}")
            return

        self._current_character = character
        self._current_bundle = bundle

        self._kart_viewer.set_atlas(
            bundle.atlas_rgba, AtlasRenderer.ATLAS_WIDTH, AtlasRenderer.ATLAS_HEIGHT,
        )

        assembled = self._vertex_assembler.assemble(bundle.mesh)
        self._kart_viewer.set_mesh(assembled, bundle.mesh.texture_layouts)

        self._slot_triangle_mask = self._build_slot_triangle_mask(assembled, bundle)

        self._populate_animations()
        self._populate_slot_editor(character_id, bundle)
        self._refresh_action_state()

        self.statusBar().showMessage(
            f"{character.display_name}: {len(bundle.slot_regions.slots)} slots, "
            f"{len(bundle.slot_regions.unmatched_palettes)} unmatched palettes, "
            f"{assembled.triangle_count} triangles",
        )

    def _build_slot_triangle_mask(
        self, assembled, bundle: BroughtUpCharacter,
    ) -> dict[str, list[int]]:
        layout_to_slot: dict[int, str] = {}
        for slot_name, regions in bundle.slot_regions.slots.items():
            for region in regions.regions:
                for layout_idx in region.texture_layout_indices:
                    layout_to_slot[layout_idx] = slot_name

        mask: dict[str, list[int]] = {}
        for tri_idx, layout_idx in enumerate(assembled.texture_layout_indices):
            slot = layout_to_slot.get(layout_idx)
            if slot is not None:
                mask.setdefault(slot, []).append(tri_idx)

        return mask

    def _on_slot_focus_changed(self, slot_name) -> None:
        # `slot_name` is either a `str` (focus on that slot) or `None`
        # (clear focus). Declared as `object` on the signal.
        if slot_name is None:
            self._kart_viewer.set_highlighted_triangles(None)
            return

        self._kart_viewer.set_highlighted_triangles(
            self._slot_triangle_mask.get(slot_name, []),
        )

    def _populate_slot_editor(self, character_id: str, bundle: BroughtUpCharacter) -> None:
        slot_names = list(bundle.slot_regions.slots.keys())
        self._slot_editor.set_slots(slot_names)

        character_paintjob = self._paintjob.characters.get(character_id)

        for slot_name, slot in bundle.slot_regions.slots.items():
            if character_paintjob is not None and slot_name in character_paintjob.slots:
                colors = list(character_paintjob.slots[slot_name].colors)
            else:
                colors = self._color_handler.default_slot_colors(
                    self._config.iso_root, slot,
                )

            self._slot_editor.set_slot_colors(slot_name, colors)

    def _defaults_by_slot_for_current(self) -> dict[str, list[PsxColor]]:
        """VRAM-default CLUT for every slot the current character owns.

        Used to backfill slot entries on export so unedited slots still land
        in the output file. Empty when no character is loaded.
        """
        if self._current_bundle is None:
            return {}

        return {
            slot_name: self._color_handler.default_slot_colors(
                self._config.iso_root, slot,
            )
            for slot_name, slot in self._current_bundle.slot_regions.slots.items()
        }

    def _on_color_edit_requested(self, slot_name: str, color_index: int) -> None:
        if self._current_bundle is None or self._current_character is None:
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        old_color = self._current_color(slot, color_index)
        new_color = self._color_picker.pick(old_color, parent=self)
        if new_color is None or new_color.value == old_color.value:
            return

        # Apply immediately so the user sees the change without waiting for the
        # undo stack; then push a command that represents the same operation so
        # it can be reversed. SetSlotColorCommand's first redo is a no-op.
        self.apply_color_edit_from_command(
            self._current_character.id, slot, color_index, new_color,
        )
        self._undo_stack.push(SetSlotColorCommand(
            self,
            self._current_character.id,
            slot,
            color_index,
            old_color,
            new_color,
        ))

    def _on_slot_reset_requested(self, slot_name: str) -> None:
        if self._current_bundle is None or self._current_character is None:
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        old_colors = self._snapshot_slot_colors(self._current_character.id, slot.slot_name)
        self.apply_slot_reset_from_command(self._current_character.id, slot)
        self._undo_stack.push(ResetSlotCommand(
            self,
            self._current_character.id,
            slot,
            old_colors,
        ))

    def _on_slot_editor_context(self, slot_name: str, color_index: int, global_pos) -> None:
        """Right-click on a swatch (color_index >= 0) or slot-row chrome (color_index == -1).

        Pops a small menu whose only entry today is "Transform colors..." — but
        keeping it as a menu rather than a bare action leaves room for future
        per-swatch extras (copy hex, paste hex, etc.) without yanking the
        primary entry elsewhere.
        """
        if self._current_bundle is None or self._current_character is None:
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        match_color: PsxColor | None = None
        if color_index >= 0:
            match_color = self._current_color(slot, color_index)

        menu = QMenu(self)
        menu.addAction(
            "Transform colors...",
            lambda: self._open_transform_dialog(
                scope=TransformScope.THIS_SLOT,
                slot_name=slot_name,
                match_color=match_color,
            ),
        )
        menu.exec(global_pos)

    def _open_transform_dialog(
        self,
        scope: TransformScope,
        slot_name: str | None,
        match_color: PsxColor | None,
    ) -> None:
        if self._current_bundle is None or self._current_character is None:
            QMessageBox.information(
                self,
                "Transform Colors",
                "Load a character before running a bulk color transform.",
            )
            return

        slot_candidates: list[TransformCandidate] = []
        if slot_name is not None:
            target_slot = self._current_bundle.slot_regions.slots.get(slot_name)
            if target_slot is not None:
                slot_candidates = self._build_transform_candidates([target_slot])

        kart_candidates = self._build_transform_candidates(
            list(self._current_bundle.slot_regions.slots.values()),
        )

        # Snapshot every slot the dialog could touch. Needed because the
        # Preview button pushes the current transform into the paintjob + 3D
        # view — on Cancel we roll back to snapshot, on Apply we roll back
        # then re-apply the final edit set so the committed state matches
        # what Apply's `resulting_edits` describes (user may have tweaked
        # sliders between the last Preview and Apply).
        preview_snapshot = self._snapshot_slots_for_preview(kart_candidates)
        dirty_slots: set[tuple[str, str]] = set()

        dialog = TransformColorsDialog(
            slot_candidates=slot_candidates,
            kart_candidates=kart_candidates,
            color_transformer=self._color_transformer,
            color_converter=self._color_converter,
            initial_scope=scope,
            initial_match_color=match_color,
            initial_slot_label=slot_name or "",
            parent=self,
        )
        dialog.preview_requested.connect(
            lambda edits: self._apply_transform_preview(
                preview_snapshot, dirty_slots, edits,
            ),
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            self._restore_transform_snapshot(preview_snapshot, dirty_slots)
            return

        edits = dialog.resulting_edits()
        if not edits:
            self._restore_transform_snapshot(preview_snapshot, dirty_slots)
            return

        # Roll back any preview state first, then apply the final edit set
        # from a clean baseline. Without the restore, residue from an earlier
        # preview that touched different slots/indices than the final Apply
        # would stay in the paintjob (applying new edits only overwrites the
        # colors they touch; earlier preview colors at other indices would
        # stick around).
        self._restore_transform_snapshot(preview_snapshot, dirty_slots)
        self.apply_bulk_edits_from_command(
            [(e.character_id, e.slot, e.color_index, e.new_color) for e in edits],
        )

        label = (
            f"Transform {len(edits)} color{'s' if len(edits) != 1 else ''} "
            f"({'slot ' + slot_name if scope == TransformScope.THIS_SLOT and slot_name else 'entire kart'})"
        )
        self._undo_stack.push(BulkTransformCommand(self, label, edits))

    def _snapshot_slots_for_preview(
        self, candidates: list[TransformCandidate],
    ) -> dict[tuple[str, str], tuple[object, SlotColors | None]]:
        """Capture per-slot paintjob state for every unique slot in `candidates`.

        Value is (slot, colors). `colors` is None when the slot hadn't been
        touched yet, so revert deletes the paintjob entry — same semantics as
        `ResetSlotCommand.undo`'s None-means-untouched branch.
        """
        snapshot: dict[tuple[str, str], tuple[object, SlotColors | None]] = {}
        for cand in candidates:
            key = (cand.character_id, cand.slot.slot_name)
            if key in snapshot:
                continue

            snapshot[key] = (
                cand.slot,
                self._snapshot_slot_colors(cand.character_id, cand.slot.slot_name),
            )

        return snapshot

    def _apply_transform_preview(
        self,
        snapshot: dict[tuple[str, str], tuple[object, SlotColors | None]],
        dirty_slots: set[tuple[str, str]],
        edits: list,
    ) -> None:
        """Push a preview edit set into the paintjob + 3D view.

        Reverts everything to snapshot first (clearing residue from a prior
        Preview click that might have touched different slots/indices), then
        applies the new edits grouped by slot, then does one full-atlas GL
        upload. Per-slot `set_atlas_region` can't be used here — the viewer's
        pending-region field is a single tuple, so multiple region uploads
        within one paintGL cycle would drop all but the last one.
        """
        if self._current_bundle is None:
            return

        new_dirty = {(e.character_id, e.slot.slot_name) for e in edits}

        for key in dirty_slots | new_dirty:
            slot, colors = snapshot[key]
            restored = self._color_handler.restore_slot(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                self._paintjob,
                key[0],
                slot,
                colors,
            )
            self._slot_editor.set_slot_colors(slot.slot_name, restored)

        by_slot: dict[tuple[str, str], list] = {}
        slot_for_key: dict[tuple[str, str], object] = {}

        for edit in edits:
            key = (edit.character_id, edit.slot.slot_name)
            by_slot.setdefault(key, []).append(edit)
            slot_for_key[key] = edit.slot

        for key, slot_edits in by_slot.items():
            slot = slot_for_key[key]
            self._color_handler.apply_edits(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                self._paintjob,
                key[0],
                slot,
                [(e.color_index, e.new_color) for e in slot_edits],
            )

            for e in slot_edits:
                self._slot_editor.update_color(
                    slot.slot_name, e.color_index, e.new_color,
                )

        self._kart_viewer.set_atlas(
            self._current_bundle.atlas_rgba,
            AtlasRenderer.ATLAS_WIDTH,
            AtlasRenderer.ATLAS_HEIGHT,
        )

        dirty_slots.clear()
        dirty_slots.update(new_dirty)

    def _restore_transform_snapshot(
        self,
        snapshot: dict[tuple[str, str], tuple[object, SlotColors | None]],
        dirty_slots: set[tuple[str, str]],
    ) -> None:
        """Revert every slot that diverged during preview back to snapshot state."""
        if self._current_bundle is None or not dirty_slots:
            dirty_slots.clear()
            return

        for key in dirty_slots:
            slot, colors = snapshot[key]
            restored = self._color_handler.restore_slot(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                self._paintjob,
                key[0],
                slot,
                colors,
            )
            self._slot_editor.set_slot_colors(slot.slot_name, restored)

        self._kart_viewer.set_atlas(
            self._current_bundle.atlas_rgba,
            AtlasRenderer.ATLAS_WIDTH,
            AtlasRenderer.ATLAS_HEIGHT,
        )

        dirty_slots.clear()

    def apply_bulk_edits_from_command(
        self,
        operations: list[tuple[str, object, int, PsxColor]],
    ) -> None:
        """Apply N (character, slot, color_index, color) changes as one batch.

        Used by the Transform Colors Accept path AND by `BulkTransformCommand`
        redo/undo. Groups by slot so each slot takes one paintjob mutation +
        one atlas render, and finishes with a single full-atlas GL upload.
        Per-edit `apply_color_edit_from_command` would queue one
        `set_atlas_region` per edit, but the viewer keeps only the latest
        pending region — all earlier uploads get dropped before `paintGL`
        runs, so a multi-slot transform would leave most slots un-updated on
        the GPU.
        """
        if self._current_bundle is None or not operations:
            return

        by_slot: dict[tuple[str, str], list[tuple[int, PsxColor]]] = {}
        slot_for_key: dict[tuple[str, str], object] = {}
        for character_id, slot, color_index, color in operations:
            key = (character_id, slot.slot_name)
            by_slot.setdefault(key, []).append((color_index, color))
            slot_for_key[key] = slot

        for key, slot_ops in by_slot.items():
            slot = slot_for_key[key]
            self._color_handler.apply_edits(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                self._paintjob,
                key[0],
                slot,
                slot_ops,
            )

            for color_index, new_color in slot_ops:
                self._slot_editor.update_color(
                    slot.slot_name, color_index, new_color,
                )

        self._kart_viewer.set_atlas(
            self._current_bundle.atlas_rgba,
            AtlasRenderer.ATLAS_WIDTH,
            AtlasRenderer.ATLAS_HEIGHT,
        )

    def _build_transform_candidates(self, slots) -> list[TransformCandidate]:
        """Resolve (slot, color_index) → effective color for every color in `slots`.

        "Effective" = paintjob override if the user has touched this slot,
        else the VRAM default. That matches what the swatches visually show
        and what Replace-matches uses as its before value.
        """
        if self._current_character is None:
            return []

        character_id = self._current_character.id
        character_paintjob = self._paintjob.characters.get(character_id)

        result: list[TransformCandidate] = []
        for slot in slots:
            if character_paintjob is not None and slot.slot_name in character_paintjob.slots:
                colors = character_paintjob.slots[slot.slot_name].colors
            else:
                colors = self._color_handler.default_slot_colors(
                    self._config.iso_root, slot,
                )

            for i, color in enumerate(colors):
                result.append(TransformCandidate(
                    character_id=character_id,
                    slot=slot,
                    color_index=i,
                    current_color=PsxColor(value=color.value),
                ))

        return result

    def apply_color_edit_from_command(
        self,
        character_id: str,
        slot,
        color_index: int,
        new_color: PsxColor,
    ) -> None:
        """Apply a color change without going through the undo stack.

        Called from `SetSlotColorCommand.redo` / `undo` and from the initial
        edit path to keep all three mutate-state / re-render / refresh-swatch
        steps in one place.
        """
        if self._current_bundle is None:
            return

        self._color_handler.apply_edit(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            self._paintjob,
            character_id,
            slot,
            color_index,
            new_color,
        )

        self._push_slot_region_to_viewer(slot)
        self._slot_editor.update_color(slot.slot_name, color_index, new_color)

    def apply_slot_reset_from_command(self, character_id: str, slot) -> None:
        if self._current_bundle is None:
            return

        defaults = self._color_handler.reset_slot(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            self._paintjob,
            character_id,
            slot,
        )

        self._push_slot_region_to_viewer(slot)
        self._slot_editor.set_slot_colors(slot.slot_name, defaults)

    def apply_slot_restore_from_command(
        self,
        character_id: str,
        slot,
        old_colors: SlotColors | None,
    ) -> None:
        if self._current_bundle is None:
            return

        colors = self._color_handler.restore_slot(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            self._paintjob,
            character_id,
            slot,
            old_colors,
        )

        self._push_slot_region_to_viewer(slot)
        self._slot_editor.set_slot_colors(slot.slot_name, colors)

    def _push_slot_region_to_viewer(self, slot) -> None:
        """Upload just the dirty rectangle of the atlas after a slot edit.

        Uses `glTexSubImage2D` under the hood — re-uploading the full 4096×512
        atlas on every color-picker dismissal was wasteful. Falls back to a
        full upload if we can't compute a bounding box (e.g. slot has no
        regions, which shouldn't happen but is cheap to guard).
        """
        if self._current_bundle is None:
            return

        atlas_w = AtlasRenderer.ATLAS_WIDTH
        atlas_h = AtlasRenderer.ATLAS_HEIGHT
        bbox = self._atlas_bbox_for_slot(slot)

        if bbox is None:
            self._kart_viewer.set_atlas(
                self._current_bundle.atlas_rgba, atlas_w, atlas_h,
            )
            return

        x, y, w, h = bbox
        self._kart_viewer.set_atlas_region(
            self._current_bundle.atlas_rgba, atlas_w, atlas_h, x, y, w, h,
        )

    def _atlas_bbox_for_slot(self, slot) -> tuple[int, int, int, int] | None:
        """Atlas-pixel bounding box enclosing every VRAM region of `slot`.

        Multiple disjoint regions are merged into one rectangle — if a slot's
        regions are far apart we upload a bit more than strictly needed, but
        still orders of magnitude less than the whole atlas.
        """
        if not slot.regions:
            return None

        # AtlasRenderer stretches VRAM X by 4 for 4bpp texel visibility.
        stretch_x = 4
        min_x = min_y = None
        max_x = max_y = None

        for region in slot.regions:
            ax = region.vram_x * stretch_x
            ay = region.vram_y
            aw = region.vram_width * stretch_x
            ah = region.vram_height

            if min_x is None:
                min_x, min_y = ax, ay
                max_x, max_y = ax + aw, ay + ah
            else:
                min_x = min(min_x, ax)
                min_y = min(min_y, ay)
                max_x = max(max_x, ax + aw)
                max_y = max(max_y, ay + ah)

        return min_x, min_y, max_x - min_x, max_y - min_y

    def _snapshot_slot_colors(self, character_id: str, slot_name: str) -> SlotColors | None:
        character = self._paintjob.characters.get(character_id)
        if character is None:
            return None

        slot = character.slots.get(slot_name)
        if slot is None:
            return None

        return SlotColors(colors=[PsxColor(value=c.value) for c in slot.colors])

    def _current_color(self, slot, color_index: int) -> PsxColor:
        if self._current_character is None:
            return PsxColor()

        character_paintjob = self._paintjob.characters.get(self._current_character.id)
        if character_paintjob is not None and slot.slot_name in character_paintjob.slots:
            return character_paintjob.slots[slot.slot_name].colors[color_index]

        defaults = self._color_handler.default_slot_colors(self._config.iso_root, slot)
        return defaults[color_index]

    def _set_animation_controls_enabled(self, enabled: bool) -> None:
        self._anim_combo.setEnabled(enabled)
        self._anim_play_button.setEnabled(enabled)

    def _populate_animations(self) -> None:
        self._anim_timer.stop()
        self._anim_play_button.setText("Play")
        self._anim_index = -1
        self._anim_frame_index = 0
        self._anim_frame_label.setText("—")

        self._anim_combo.blockSignals(True)
        self._anim_combo.clear()
        self._anim_combo.addItem("(static pose)")

        anims = self._current_bundle.mesh.anims if self._current_bundle else []
        for anim in anims:
            label = anim.name or f"anim {self._anim_combo.count()}"
            frames = len(anim.frames)
            self._anim_combo.addItem(f"{label} ({frames} frames)")

        self._anim_combo.setCurrentIndex(0)
        self._anim_combo.blockSignals(False)

        self._set_animation_controls_enabled(bool(anims))

    def _on_anim_selected(self, combo_index: int) -> None:
        # Combo index 0 is the static pose; anim indices are shifted by 1.
        self._anim_timer.stop()
        self._anim_play_button.setText("Play")
        self._anim_frame_index = 0

        if combo_index <= 0:
            self._anim_index = -1
            self._anim_frame_label.setText("—")
            self._render_static_pose()
            return

        self._anim_index = combo_index - 1
        self._update_frame_label()
        self._render_current_frame()

    def _on_anim_play_clicked(self) -> None:
        if self._anim_index < 0:
            return

        if self._anim_timer.isActive():
            self._anim_timer.stop()
            self._anim_play_button.setText("Play")
        else:
            self._anim_timer.start()
            self._anim_play_button.setText("Pause")

    def _on_anim_tick(self) -> None:
        frames = self._current_frames()
        if not frames:
            self._anim_timer.stop()
            return

        self._anim_frame_index = (self._anim_frame_index + 1) % len(frames)
        self._update_frame_label()
        self._render_current_frame()

    def _current_frames(self) -> list:
        if self._current_bundle is None or self._anim_index < 0:
            return []

        anims = self._current_bundle.mesh.anims
        if self._anim_index >= len(anims):
            return []

        return anims[self._anim_index].frames

    def _update_frame_label(self) -> None:
        frames = self._current_frames()
        if not frames:
            self._anim_frame_label.setText("—")
            return

        self._anim_frame_label.setText(
            f"{self._anim_frame_index + 1}/{len(frames)}",
        )

    def _render_static_pose(self) -> None:
        if self._current_bundle is None:
            return

        assembled = self._vertex_assembler.assemble(self._current_bundle.mesh)
        positions = np.asarray(assembled.positions, dtype=np.float32)
        self._kart_viewer.set_frame_positions(positions)

    def _render_current_frame(self) -> None:
        frames = self._current_frames()
        if not frames:
            return

        frame = frames[self._anim_frame_index]
        assembled = self._vertex_assembler.assemble(
            self._current_bundle.mesh, frame=frame,
        )
        positions = np.asarray(assembled.positions, dtype=np.float32)
        self._kart_viewer.set_frame_positions(positions)


class _NullKartViewer:
    """Drop-in replacement for `KartViewer` after a GL init failure.

    Absorbs every method the main window calls (set_mesh, set_atlas,
    set_highlighted_triangles, reset_camera, ...) as no-ops. Having this stub
    means the rest of the app's character-load / color-edit / animation code
    doesn't have to check "is 3D available?" at every call site.
    """

    def __getattr__(self, _name):
        def _noop(*_args, **_kwargs):
            return None

        return _noop
