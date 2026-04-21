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
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.color.gradient import GradientGenerator
from paintjob_designer.color.transform import ColorTransformer
from paintjob_designer.config.iso_root_validator import IsoRootValidator
from paintjob_designer.config.store import AppConfig, ConfigStore
from paintjob_designer.core import Slugifier
from paintjob_designer.ctr.vertex_assembler import VertexAssembler
from paintjob_designer.gui.command.apply_palette_command import ApplyPaletteCommand
from paintjob_designer.gui.command.bulk_transform_command import (
    BulkColorEdit,
    BulkTransformCommand,
)
from paintjob_designer.gui.command.reset_slot_command import ResetSlotCommand
from paintjob_designer.gui.command.set_slot_color_command import SetSlotColorCommand
from paintjob_designer.gui.dialog.gradient_fill_dialog import GradientFillDialog
from paintjob_designer.gui.dialog.palette_apply_dialog import PaletteApplyDialog
from paintjob_designer.gui.dialog.palette_edit_dialog import PaletteEditDialog
from paintjob_designer.gui.dialog.profile_picker_dialog import (
    ProfilePickerDialog,
)
from paintjob_designer.gui.handler.character_handler import (
    BroughtUpCharacter,
    CharacterHandler,
)
from paintjob_designer.gui.handler.color_handler import ColorHandler
from paintjob_designer.gui.handler.project_handler import ProjectHandler
from paintjob_designer.gui.widget.color_picker import PsxColorPicker
from paintjob_designer.gui.widget.kart_viewer import KartViewer
from paintjob_designer.gui.widget.paintjob_library_sidebar import PaintjobLibrarySidebar
from paintjob_designer.gui.widget.palette_sidebar import PaletteSidebar
from paintjob_designer.gui.widget.slot_editor import SlotEditor
from paintjob_designer.gui.widget.transform_panel import (
    TransformCandidate,
    TransformColorsPanel,
)
from paintjob_designer.models import (
    CANONICAL_SLOT_NAMES,
    CharacterProfile,
    Paintjob,
    PaintjobLibrary,
    Palette,
    PaletteLibrary,
    Profile,
    PsxColor,
    SlotColors,
    SlotRegionPixels,
)
from paintjob_designer.profile.registry import ProfileRegistry
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from paintjob_designer.render.atlas_uv_mapper import AtlasUvMapper
from paintjob_designer.render.ray_picker import RayTrianglePicker
from paintjob_designer.texture.importer import SizeMismatchMode, TextureImporter

_PAINTJOB_EXT = ".json"

_PAINTJOB_FILTER = f"Paintjob (*{_PAINTJOB_EXT})"


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
        color_converter: ColorConverter,
        color_picker: PsxColorPicker,
        vertex_assembler: VertexAssembler,
        atlas_uv_mapper: AtlasUvMapper,
        color_transformer: ColorTransformer,
        gradient_generator: GradientGenerator,
        ray_picker: RayTrianglePicker,
        slugifier: Slugifier,
        texture_importer: TextureImporter,
    ) -> None:
        super().__init__()
        self._config_store = config_store
        self._validator = iso_root_validator
        self._profile_registry = profile_registry
        self._character_handler = character_handler
        self._color_handler = color_handler
        self._project_handler = project_handler
        self._color_converter = color_converter
        self._color_picker = color_picker
        self._vertex_assembler = vertex_assembler
        self._atlas_uv_mapper = atlas_uv_mapper
        self._color_transformer = color_transformer
        self._gradient_generator = gradient_generator
        self._ray_picker = ray_picker
        self._slugifier = slugifier
        self._texture_importer = texture_importer

        self._config: AppConfig = self._config_store.load()
        self._profile: Profile | None = None

        # Paintjob library — ordered list of all paintjobs the user is
        # editing. Restored from the persisted config so a restart doesn't
        # lose in-progress work; the saved state rehydrates before the
        # sidebar is built so the first paint shows it.
        self._library = self._restore_library_from_config()
        self._palette_library = self._restore_palette_library_from_config()
        self._current_paintjob: Paintjob | None = None

        # Debounced autosave — mutation sites call `_schedule_autosave()`;
        # the timer collapses the bursts that a live transform-slider drag
        # produces into one disk write instead of hundreds.
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(500)
        self._autosave_timer.timeout.connect(self._flush_autosave)

        # `_current_character` is the PREVIEW character — the mesh the 3D
        # viewer shows and the VRAM we sample defaults from. It's driven by
        # the preview-character combo at the top of the viewer pane, NOT
        # the sidebar (which lists paintjobs now).
        self._current_character: CharacterProfile | None = None
        self._current_bundle: BroughtUpCharacter | None = None

        # Slot → triangle indices lookup for focus-highlight in the 3D view.
        self._slot_triangle_mask: dict[str, list[int]] = {}

        # One undo stack for the whole session. Clicking between characters
        # doesn't clear it — Ctrl+Z still unwinds edits across character
        # boundaries, which matches what users expect from a single-editor app.
        self._undo_stack = QUndoStack(self)

        # Every undo-routed edit (color set, reset, bulk transform, palette
        # apply) advances the stack index. Hook that for autosave so the
        # color-edit path doesn't need an explicit `_schedule_autosave()`
        # at each mutation site.
        self._undo_stack.indexChanged.connect(self._schedule_autosave)

        # Transform panel lifecycle fields — lazy-constructed on first
        # open, but the snapshot / dirty-keys pair needs to exist from
        # the start because paintjob-selected / preview-character-changed
        # hooks call `_on_transform_panel_closing` before the panel may
        # have been opened for the first time.
        self._transform_panel: TransformColorsPanel | None = None
        self._transform_snapshot: dict | None = None
        self._transform_dirty_keys: set = set()

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
        # Palettes aren't profile-bound; seed the sidebar from the restored
        # state here so the tab is populated even before / without an ISO.
        self._palette_sidebar.set_palettes(self._palette_library.palettes)
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

        self._apply_paintjob_file_to_library(path)

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
            file_menu, "Export &Library As...", self._on_save_library_as,
            shortcut=QKeySequence("Ctrl+Shift+S"),
        )

        self._add_action(
            file_menu, "&Import Paintjobs...", self._on_import_paintjob,
            shortcut=QKeySequence("Ctrl+O"),
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

        # The library toolbar is built after the menu bar, so this method
        # gets called once before the actions exist — guard accordingly.
        if hasattr(self, "_action_save_library"):
            self._action_save_library.setEnabled(has_iso)

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)

        self._sidebar = PaintjobLibrarySidebar()
        self._sidebar.paintjob_selected.connect(self._on_paintjob_selected)
        self._sidebar.paintjob_context_requested.connect(self._on_sidebar_context)
        self._sidebar.new_paintjob_requested.connect(self._on_new_paintjob)
        self._sidebar.delete_paintjob_requested.connect(self._on_delete_paintjob)
        self._sidebar.paintjobs_reordered.connect(self._on_paintjobs_reordered)

        self._palette_sidebar = PaletteSidebar(self._color_converter)
        self._palette_sidebar.new_palette_requested.connect(self._on_new_palette)
        self._palette_sidebar.save_from_slot_requested.connect(
            self._on_save_palette_from_slot,
        )
        self._palette_sidebar.delete_palette_requested.connect(
            self._on_delete_palette,
        )
        self._palette_sidebar.edit_palette_requested.connect(
            self._on_edit_palette,
        )
        self._palette_sidebar.rename_palette_requested.connect(
            self._on_rename_palette,
        )

        self._sidebar_tabs = QTabWidget()
        self._sidebar_tabs.addTab(self._sidebar, "Paintjobs")
        self._sidebar_tabs.addTab(self._palette_sidebar, "Color Palettes")
        sidebar_layout.addWidget(self._sidebar_tabs, 1)
        sidebar_layout.addWidget(self._build_animation_panel())

        viewer_container = QWidget()
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)

        # Preview-character selector sits above the 3D viewer so the
        # "which mesh am I seeing this paintjob on?" question is
        # answered at a glance. Paintjobs themselves are character-
        # agnostic in the new model; this dropdown just picks the
        # preview context (mesh + VRAM defaults).
        preview_strip = QWidget()
        preview_strip_layout = QHBoxLayout(preview_strip)
        preview_strip_layout.setContentsMargins(8, 4, 8, 4)
        preview_strip_layout.addWidget(QLabel("Preview on:"))
        self._preview_character_combo = QComboBox()
        self._preview_character_combo.currentIndexChanged.connect(
            self._on_preview_character_changed,
        )
        preview_strip_layout.addWidget(self._preview_character_combo, 1)
        viewer_layout.addWidget(preview_strip)

        self._kart_viewer = KartViewer(self._atlas_uv_mapper, self._ray_picker)
        self._kart_viewer.gl_init_failed.connect(self._on_gl_init_failed)
        self._kart_viewer.eyedropper_picked.connect(self._on_eyedropper_picked)
        viewer_layout.addWidget(self._kart_viewer, 1)

        self._slot_editor = SlotEditor(self._color_converter)
        self._slot_editor.color_edit_requested.connect(self._on_color_edit_requested)
        self._slot_editor.slot_reset_requested.connect(self._on_slot_reset_requested)
        self._slot_editor.slot_focus_changed.connect(self._on_slot_focus_changed)
        self._slot_editor.context_requested.connect(self._on_slot_editor_context)

        splitter.addWidget(sidebar_container)
        splitter.addWidget(viewer_container)
        splitter.addWidget(self._slot_editor)

        # Stored so `_on_gl_init_failed` can swap the viewer for a placeholder
        # without having to re-walk the splitter hierarchy. The viewer lives
        # inside the viewer-container widget now (so the preview-character
        # combo can sit above it), so the placeholder replaces the inner
        # widget rather than a splitter pane.
        self._splitter = splitter
        self._viewer_container = viewer_container
        self._viewer_container_layout = viewer_layout
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 600, 600])

        self.setCentralWidget(splitter)
        self._build_library_toolbar()

        # Permanent status-bar widget so the active profile is always visible
        # regardless of what transient message `showMessage` is showing.
        self._profile_status_label = QLabel()
        self.statusBar().addPermanentWidget(self._profile_status_label)
        self._update_window_title()

        self.statusBar().showMessage("Ready.")
        self._refresh_action_state()

    def _build_library_toolbar(self) -> None:
        """Top toolbar — library I/O + bulk-edit shortcut."""
        toolbar = self.addToolBar("Library")
        toolbar.setMovable(False)

        self._action_save_library = toolbar.addAction(
            "Export Library", self._on_save_library_as,
        )

        toolbar.addSeparator()

        self._action_transform_all = toolbar.addAction(
            "Transform Colors...",
            self._show_transform_panel,
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

        # Populate the preview-character combo from the profile. Setting the
        # first item fires currentIndexChanged, which triggers the initial
        # mesh/VRAM/atlas load.
        self._populate_preview_character_combo()

        # Rebuild the sidebar from the library. If the library was restored
        # from the autosave blob (first boot after a prior session), select
        # the first paintjob so the editor reopens where the artist left
        # off; fresh sessions with an empty library land with no selection.
        initial = 0 if self._library.count() > 0 else None
        self._sidebar.set_library(self._library, selected_index=initial)
        self._refresh_action_state()

    def _populate_preview_character_combo(self) -> None:
        """Fill the preview-character combo from the active profile.

        Signals are blocked during the rebuild so clearing + adding doesn't
        spam `_on_preview_character_changed`; we fire it once explicitly
        after the combo is populated so the first character loads.
        """
        self._preview_character_combo.blockSignals(True)
        self._preview_character_combo.clear()

        if self._profile is not None:
            for character in self._profile.characters:
                self._preview_character_combo.addItem(
                    character.display_name or character.id,
                    character.id,
                )

        self._preview_character_combo.blockSignals(False)

        if self._preview_character_combo.count() > 0:
            self._preview_character_combo.setCurrentIndex(0)
        else:
            self._current_character = None
            self._current_bundle = None

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

    def _require_active_paintjob(self) -> bool:
        """Gate for actions that need a selected paintjob in the library.

        Creating a new paintjob / loading one from JSON both satisfy this —
        the user just has to pick one before they can edit slots.
        """
        if self._current_paintjob is not None:
            return True

        QMessageBox.information(
            self, "No paintjob selected",
            "Create a paintjob (sidebar → New) or import one from JSON "
            "before performing this action.",
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

        # A fresh ISO wipes any in-flight edits — they were keyed to
        # characters from the previous ISO's profile and wouldn't make
        # sense against the new one. Undo history goes with them.
        self._library = PaintjobLibrary()
        self._current_paintjob = None
        self._current_character = None
        self._current_bundle = None
        self._undo_stack.clear()
        self._schedule_autosave()

        self._load_profile(self._config.last_profile_id)
        self.statusBar().showMessage(
            "ISO loaded. Create a paintjob (sidebar → New) or import one to begin.",
        )

    def _apply_paintjob_file_to_library(self, path: Path) -> None:
        """Load a paintjob JSON from disk and add it as a new library entry."""
        try:
            loaded = self._project_handler.load(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        new_index = self._library.add(loaded)

        # Imports clear undo — the commands' captured paintjob refs point
        # at pre-import objects that may no longer be in the library.
        self._undo_stack.clear()

        self._sidebar.set_library(self._library, selected_index=new_index)
        self._schedule_autosave()
        self.statusBar().showMessage(f"Imported {path.name}")

    def _replace_paintjob_from_file(self, index: int, path: Path) -> None:
        """Replace the paintjob at `index` with one loaded from `path`."""
        if index < 0 or index >= self._library.count():
            return

        try:
            loaded = self._project_handler.load(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        self._library.paintjobs[index] = loaded
        self._undo_stack.clear()
        self._sidebar.set_library(self._library, selected_index=index)
        self._schedule_autosave()
        self.statusBar().showMessage(f"Replaced with {path.name}")

    def _on_sidebar_context(self, index: int, global_pos: QPoint) -> None:
        """Per-paintjob context menu (sidebar right-click)."""
        if index < 0 or index >= self._library.count():
            return

        paintjob = self._library.paintjobs[index]

        menu = QMenu(self)
        menu.addAction(
            "Rename...",
            lambda: self._on_rename_paintjob(index),
        )
        menu.addAction(
            "Set author...",
            lambda: self._on_set_author(index),
        )
        menu.addAction(
            "Change base character...",
            lambda: self._on_change_base_character(index),
        )
        menu.addSeparator()
        menu.addAction(
            "Export as JSON...",
            lambda: self._on_export_json_for_paintjob(paintjob),
        )
        menu.addAction(
            "Replace from JSON...",
            lambda: self._on_replace_paintjob_from_file(index),
        )
        menu.addSeparator()
        menu.addAction(
            "Delete",
            lambda: self._on_delete_paintjob(index),
        )
        menu.exec(global_pos)

    def _on_import_paintjob(self) -> None:
        """Load one or more paintjob JSONs and append them to the library.

        Multi-select is the entry point artists use to mass-restore a
        previously-exported library directory (pick every `NN_*.json` at
        once); picking a single file is still the single-paintjob import
        case. Files load in selection order.
        """
        if self._profile is None:
            return

        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import paintjobs",
            self._config.iso_root or str(Path.home()),
            f"{_PAINTJOB_FILTER};;All files (*)",
        )

        if not paths:
            return

        for path_str in paths:
            self._apply_paintjob_file_to_library(Path(path_str))

    def _on_replace_paintjob_from_file(self, index: int) -> None:
        if index < 0 or index >= self._library.count():
            return

        path_str, _ = QFileDialog.getOpenFileName(
            self, "Replace paintjob from JSON",
            self._config.iso_root or str(Path.home()),
            f"{_PAINTJOB_FILTER};;All files (*)",
        )

        if not path_str:
            return

        self._replace_paintjob_from_file(index, Path(path_str))

    def _on_rename_paintjob(self, index: int) -> None:
        if index < 0 or index >= self._library.count():
            return

        from PySide6.QtWidgets import QInputDialog
        paintjob = self._library.paintjobs[index]
        new_name, ok = QInputDialog.getText(
            self, "Rename paintjob",
            "Name:", text=paintjob.name,
        )
        if not ok:
            return

        paintjob.name = new_name.strip()
        # Preserve selection across the rebuild so the user stays on the
        # paintjob they just renamed.
        self._sidebar.set_library(self._library, selected_index=index)
        self._schedule_autosave()

    def _on_set_author(self, index: int) -> None:
        """Edit the paintjob's `author` metadata field.

        Round-trips through the library JSON as-is — the designer does
        nothing with the value itself; consumers may show it (credits
        screen, mod log) if they want.
        """
        if index < 0 or index >= self._library.count():
            return

        paintjob = self._library.paintjobs[index]
        new_author, ok = QInputDialog.getText(
            self, "Set paintjob author",
            "Author:", text=paintjob.author,
        )

        if not ok:
            return

        paintjob.author = new_author.strip()
        self._sidebar.set_library(self._library, selected_index=index)
        self._schedule_autosave()

    def _on_change_base_character(self, index: int) -> None:
        if self._profile is None or index < 0 or index >= self._library.count():
            return

        paintjob = self._library.paintjobs[index]

        none_label = "(none — unbound)"
        options = [none_label] + [c.id for c in self._profile.characters]

        current = paintjob.base_character_id or none_label
        current_index = options.index(current) if current in options else 0

        chosen, ok = QInputDialog.getItem(
            self, "Change base character",
            "Base character for this paintjob:",
            options, current_index, editable=False,
        )

        if not ok:
            return

        paintjob.base_character_id = None if chosen == none_label else chosen
        self._sidebar.set_library(self._library, selected_index=index)
        self._schedule_autosave()

        if paintjob is self._current_paintjob:
            self._reload_preview()

    def _on_export_json_for_paintjob(self, paintjob: Paintjob) -> None:
        """Save one paintjob as a standalone JSON file.

        Writes the paintjob as-authored: only the slots / colors / pixels
        the artist explicitly set. Unedited slots are *not* backfilled
        from VRAM — that's a mod-consumer concern (it owns the decision
        about which character's vanilla CLUT stands in for an unedited
        slot), and keeping the designer's output to "just what the
        artist authored" makes the JSON format a clean interface.
        """
        default_name = (
            self._paintjob_filename(paintjob, self._library.paintjobs.index(paintjob))
            + _PAINTJOB_EXT
        )

        path_str, _ = QFileDialog.getSaveFileName(
            self, "Export paintjob as JSON",
            default_name, _PAINTJOB_FILTER,
        )

        if not path_str:
            return

        try:
            self._project_handler.save(Path(path_str), paintjob)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return

        self.statusBar().showMessage(f"Exported {Path(path_str).name}")

    def _on_save_library_as(self) -> None:
        """Write every paintjob in the library to a chosen folder."""
        if self._profile is None:
            return

        if self._library.count() == 0:
            QMessageBox.information(
                self, "Nothing to save",
                "The paintjob library is empty — create or import at "
                "least one paintjob before saving.",
            )

            return

        dir_str = QFileDialog.getExistingDirectory(
            self, "Save paintjob library",
            str(Path.home()),
        )

        if not dir_str:
            return

        try:
            written = self._project_handler.save_library(
                Path(dir_str), self._library, self._paintjob_library_filename,
            )
        except OSError as exc:
            QMessageBox.critical(self, "Save library failed", str(exc))
            return

        self.statusBar().showMessage(
            f"Saved {len(written)} paintjob(s) to {dir_str}",
        )

    def _paintjob_library_filename(
        self, paintjob: Paintjob, index: int,
    ) -> str:
        """Filename used when saving a paintjob as part of a library.

        The `NN_` prefix pins the filesystem sort order to the library
        index so `load_library` round-trips the ordering. The slug part
        prefers the authored paintjob name so the file is recognisable
        at a glance, falling back to `base_character_id` and then a
        numbered placeholder only when the artist hasn't named it.
        """
        slug = self._slugifier.slugify(paintjob.name) or paintjob.base_character_id or "paintjob"
        return f"{index:02d}_{slug}{_PAINTJOB_EXT}"


    def _paintjob_filename(self, paintjob: Paintjob, index: int) -> str:
        """Filesystem-safe slug for one library paintjob.

        The authored paintjob name wins; the home-character binding is
        only the fallback for unnamed entries. Used by the single-paintjob
        JSON save dialog.
        """
        return self._slugifier.slugify(paintjob.name) or paintjob.base_character_id or f"paintjob_{index:02d}"

    def _restore_library_from_config(self) -> PaintjobLibrary:
        """Rehydrate the persisted library from the config blob.

        Returns a fresh empty library when the config has no saved library
        yet or the saved shape fails validation — we never want a corrupt
        autosave payload to prevent the app from starting. Corrupt blobs
        get logged to the status bar after `_build_ui` runs via the
        deferred warning list.
        """
        raw = self._config.library
        if not isinstance(raw, dict):
            return PaintjobLibrary()

        try:
            return PaintjobLibrary.model_validate(raw)
        except Exception:
            return PaintjobLibrary()

    def _restore_palette_library_from_config(self) -> PaletteLibrary:
        """Rehydrate the persisted palette library from the config list."""
        raw = self._config.palettes
        if not isinstance(raw, list):
            return PaletteLibrary()

        palettes: list[Palette] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue

            try:
                palettes.append(Palette.model_validate(entry))
            except Exception:
                continue

        return PaletteLibrary(palettes=palettes)

    def _schedule_autosave(self) -> None:
        """Kick the debounced autosave; coalesces bursty mutation sequences.

        Idempotent within the debounce window — calling it 100 times in
        500ms still results in one save.
        """
        self._autosave_timer.start()

    def _flush_autosave(self) -> None:
        """Serialize the current library + palette library into the config."""
        try:
            self._config.library = self._library.model_dump(by_alias=True)
            self._config.palettes = [
                p.model_dump() for p in self._palette_library.palettes
            ]
            self._config_store.save(self._config)
        except OSError:
            self.statusBar().showMessage(
                "Autosave failed — check disk space / permissions.", 4000,
            )

    def closeEvent(self, event) -> None:
        """Confirm on close, then flush a final autosave before exiting.

        Unconditional confirm (not tied to a dirty flag) because autosave
        covers persistence — the dialog's job is just to stop an accidental
        window-close click from ending the session.
        """
        confirm = QMessageBox.question(
            self, "Exit Paintjob Designer?",
            "Exit Paintjob Designer?\n\n"
            "Your library is autosaved and will reopen the way you left it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            event.ignore()
            return

        # Rewind any live transform preview so the autosaved state is the
        # last committed one, not the in-flight slider preview.
        self._on_transform_panel_closing()

        self._autosave_timer.stop()
        self._flush_autosave()

        event.accept()

    def _on_new_palette(self) -> None:
        """Create a blank palette and open the edit dialog to fill it."""
        palette = Palette(name=f"Palette {len(self._palette_library.palettes) + 1}")
        dialog = PaletteEditDialog(palette, self._color_converter, parent=self)
        if dialog.exec() != PaletteEditDialog.DialogCode.Accepted:
            return

        new_palette = dialog.resulting_palette()
        self._palette_library.palettes.append(new_palette)
        self._palette_sidebar.set_palettes(
            self._palette_library.palettes,
            selected_index=len(self._palette_library.palettes) - 1,
        )
        self._schedule_autosave()

    def _on_save_palette_from_slot(self) -> None:
        """Seed a new palette from the currently-focused slot's 16 colors.

        Uses the slot editor's `focused_slot()` — the same "current slot"
        the Transform Colors panel targets for its This-Slot scope. No
        focused slot → informational message; we deliberately don't guess.
        """
        if self._current_bundle is None or self._current_paintjob is None:
            QMessageBox.information(
                self, "No slot to capture",
                "Select a paintjob and highlight a slot row first — the "
                "palette captures that slot's 16 colors.",
            )

            return

        slot_name = self._slot_editor.focused_slot()
        if slot_name is None:
            QMessageBox.information(
                self, "No focused slot",
                "Click a slot row in the editor to highlight it; the "
                "palette captures the highlighted slot's colors.",
            )

            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        colors = [
            PsxColor(value=self._current_color(slot, i).value)
            for i in range(SlotColors.SIZE)
        ]

        palette = Palette(name=f"{slot_name} palette", colors=colors)

        dialog = PaletteEditDialog(palette, self._color_converter, parent=self)
        if dialog.exec() != PaletteEditDialog.DialogCode.Accepted:
            return

        new_palette = dialog.resulting_palette()
        self._palette_library.palettes.append(new_palette)
        self._palette_sidebar.set_palettes(
            self._palette_library.palettes,
            selected_index=len(self._palette_library.palettes) - 1,
        )
        self._schedule_autosave()

    def _on_delete_palette(self, index: int) -> None:
        if index < 0 or index >= len(self._palette_library.palettes):
            return

        palette = self._palette_library.palettes[index]
        label = palette.name.strip() or f"Palette {index + 1}"
        confirm = QMessageBox.question(
            self, "Delete palette",
            f"Delete '{label}'? This can't be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._palette_library.palettes.pop(index)
        next_selection = None

        if self._palette_library.palettes:
            next_selection = min(index, len(self._palette_library.palettes) - 1)

        self._palette_sidebar.set_palettes(
            self._palette_library.palettes, selected_index=next_selection,
        )
        self._schedule_autosave()

    def _on_edit_palette(self, index: int) -> None:
        if index < 0 or index >= len(self._palette_library.palettes):
            return

        palette = self._palette_library.palettes[index]
        dialog = PaletteEditDialog(palette, self._color_converter, parent=self)
        if dialog.exec() != PaletteEditDialog.DialogCode.Accepted:
            return

        self._palette_library.palettes[index] = dialog.resulting_palette()
        self._palette_sidebar.set_palettes(
            self._palette_library.palettes, selected_index=index,
        )
        self._schedule_autosave()

    def _on_rename_palette(self, index: int) -> None:
        if index < 0 or index >= len(self._palette_library.palettes):
            return

        palette = self._palette_library.palettes[index]
        new_name, ok = QInputDialog.getText(
            self, "Rename palette",
            "Name:", text=palette.name,
        )

        if not ok:
            return

        palette.name = new_name.strip()
        self._palette_sidebar.set_palettes(
            self._palette_library.palettes, selected_index=index,
        )
        self._schedule_autosave()

    def _on_apply_palette_to_slot(self, palette_index: int, slot_name: str) -> None:
        """Open the mapping dialog for `palette_index` targeting `slot_name`.

        Invoked from the slot row's right-click "Apply Color Palette" submenu
        so the artist picks palette + target slot in one gesture. The dialog's
        row order IS the slot-index mapping; trailing slot colors beyond the
        palette's length are left untouched.
        """
        if palette_index < 0 or palette_index >= len(self._palette_library.palettes):
            return

        if (
            self._current_bundle is None
            or not self._require_active_paintjob()
        ):
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        palette = self._palette_library.palettes[palette_index]
        paintjob = self._current_paintjob

        dialog = PaletteApplyDialog(
            palette=palette,
            paintjob_name=paintjob.name,
            slot_name=slot_name,
            color_converter=self._color_converter,
            parent=self,
        )

        if dialog.exec() != PaletteApplyDialog.DialogCode.Accepted:
            return

        ordered = dialog.ordered_colors()
        if not ordered:
            return

        edits: list[BulkColorEdit] = []
        for color_index, new_color in enumerate(ordered[:SlotColors.SIZE]):
            old = PsxColor(value=self._current_color(slot, color_index).value)

            if old.value == new_color.value:
                continue

            edits.append(BulkColorEdit(
                paintjob=paintjob,
                slot=slot,
                color_index=color_index,
                old_color=old,
                new_color=PsxColor(value=new_color.value),
            ))

        if not edits:
            self.statusBar().showMessage(
                f"Palette '{palette.name}' already matches {slot_name}.",
            )

            return

        self.apply_bulk_edits_from_command(
            [(e.paintjob, e.slot, e.color_index, e.new_color) for e in edits],
        )

        label = f"Apply palette '{palette.name or '(unnamed)'}' to {slot_name}"
        self._undo_stack.push(ApplyPaletteCommand(self, label, edits))

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
        self._library = PaintjobLibrary()
        self._current_character = None
        self._current_bundle = None
        self._undo_stack.clear()
        self._schedule_autosave()

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

        # The viewer is wrapped in a container that also holds the preview-
        # character combo above it. Replace just the viewer, not the whole
        # container, so the combo stays visible and functional.
        self._viewer_container_layout.replaceWidget(self._kart_viewer, placeholder)
        self._kart_viewer.deleteLater()

        # Calls that used to land on the viewer (highlight, set_atlas, ...)
        # would now crash; swap in a no-op stand-in that silently absorbs
        # them so the rest of the loading path doesn't need to know.
        self._kart_viewer = _NullKartViewer()
        self.statusBar().showMessage("3D preview disabled (GL init failed).")

    def _on_preview_character_changed(self, index: int) -> None:
        """Driven by the preview-character combo above the 3D viewer."""
        if self._profile is None or index < 0:
            return

        character_id = self._preview_character_combo.itemData(index)
        character = next(
            (c for c in self._profile.characters if c.id == character_id),
            None,
        )
        if character is None:
            return

        # Revert any in-flight transform preview — it was built against
        # the old character's candidates and would misapply otherwise.
        self._on_transform_panel_closing()

        self._current_character = character
        self._reload_preview()

        if (
            getattr(self, "_transform_panel", None) is not None
            and self._transform_panel.isVisible()
        ):
            self._take_transform_snapshot()
            self._refresh_transform_panel()

    def _reload_preview(self) -> None:
        """Load the current preview character's mesh + VRAM + atlas.

        Applies `_current_paintjob` on top — or an empty paintjob when the
        library has nothing selected, so the 3D viewer still shows the
        character's vanilla look.
        """
        if self._current_character is None:
            return

        render_paintjob = self._current_paintjob or Paintjob()
        try:
            bundle = self._character_handler.load_character(
                self._config.iso_root, self._current_character, render_paintjob,
            )
        except FileNotFoundError as exc:
            self.statusBar().showMessage(f"Load failed: {exc}")
            return

        self._current_bundle = bundle

        self._kart_viewer.set_atlas(
            bundle.atlas_rgba, AtlasRenderer.ATLAS_WIDTH, AtlasRenderer.ATLAS_HEIGHT,
        )

        assembled = self._vertex_assembler.assemble(bundle.mesh)
        self._kart_viewer.set_mesh(assembled, bundle.mesh.texture_layouts)

        self._slot_triangle_mask = self._build_slot_triangle_mask(assembled, bundle)

        self._populate_animations()
        self._populate_slot_editor()
        self._refresh_action_state()

        self.statusBar().showMessage(
            f"{self._current_character.display_name}: "
            f"{len(bundle.slot_regions.slots)} slots, "
            f"{len(bundle.slot_regions.unmatched_palettes)} unmatched palettes, "
            f"{assembled.triangle_count} triangles",
        )

    def _on_paintjob_selected(self, index: int) -> None:
        """Sidebar click — switch the active paintjob and refresh preview."""
        # The transform panel holds onto candidates built against the OLD
        # paintjob. Revert any in-flight preview first, so the slot
        # editor / 3D viewer show the old paintjob's committed state
        # (not a stranded preview from before the switch).
        self._on_transform_panel_closing()

        if index < 0 or index >= self._library.count():
            self._current_paintjob = None
        else:
            self._current_paintjob = self._library.paintjobs[index]

        # Re-render the atlas with the new paintjob on the current preview
        # character; slot editor repopulates from the paintjob's colors
        # (or VRAM defaults for untouched slots).
        self._reload_preview()

        # If the transform panel is open, re-seed it against the new paintjob.
        if (
            getattr(self, "_transform_panel", None) is not None
            and self._transform_panel.isVisible()
        ):
            self._take_transform_snapshot()
            self._refresh_transform_panel()

    def _on_new_paintjob(self) -> None:
        """Create a paintjob seeded from the current preview character's VRAM CLUTs.

        Every slot's 16 colors are baked in at creation time (read from the
        character's vanilla VRAM via `default_slot_colors_at`) and stored
        on the paintjob. Switching the preview character later doesn't
        change the paintjob's colors — the paintjob is now "authored"
        against its base character, matching how an artist thinks about
        "a Crash-themed paintjob" vs. "whatever the preview happens to
        be showing".
        """
        if self._profile is None:
            return

        base_character = self._current_character
        base_character_id = base_character.id if base_character is not None else None

        slots: dict[str, SlotColors] = {}
        if base_character is not None:
            slots = self._seed_slots_from_character(base_character)

        paintjob = Paintjob(
            name=f"Paintjob {self._library.count() + 1}",
            base_character_id=base_character_id,
            slots=slots,
        )

        index = self._library.add(paintjob)
        self._sidebar.set_library(self._library, selected_index=index)
        self._schedule_autosave()
        # The sidebar's selection change fires `_on_paintjob_selected`
        # which loads the preview.

    def _seed_slots_from_character(self, character) -> dict[str, SlotColors]:
        """Read the character's vanilla VRAM CLUTs into a full 8-slot paintjob dict.

        Missing profile slots (e.g. Papu has no `floor` entry) are left out
        — downstream code (atlas render, slot editor) already handles
        absent slots gracefully by falling back to the preview character's
        VRAM for rendering. No slot gets emitted unless its profile-level
        `clut` coords were defined.
        """
        slots: dict[str, SlotColors] = {}
        for slot_profile in character.slots:
            if slot_profile.name not in CANONICAL_SLOT_NAMES:
                continue

            defaults = self._color_handler.default_slot_colors_at(
                self._config.iso_root,
                slot_profile.clut.x,
                slot_profile.clut.y,
            )

            slots[slot_profile.name] = SlotColors(colors=list(defaults))

        return slots

    def _on_delete_paintjob(self, index: int) -> None:
        if index < 0 or index >= self._library.count():
            return

        paintjob = self._library.paintjobs[index]
        label = paintjob.name.strip() or f"Paintjob {index + 1}"
        confirm = QMessageBox.question(
            self, "Delete paintjob",
            f"Delete '{label}'? This can't be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        removed = self._library.remove(index)

        # Undo history can still reference the removed paintjob via its
        # stored ref; those entries would mutate a paintjob that's no
        # longer visible. Safer to clear the stack.
        self._undo_stack.clear()

        if self._current_paintjob is removed:
            self._current_paintjob = None

        next_selection = None
        if self._library.count() > 0:
            next_selection = min(index, self._library.count() - 1)
            self._current_paintjob = self._library.paintjobs[next_selection]

        self._sidebar.set_library(self._library, selected_index=next_selection)
        self._reload_preview()
        self._schedule_autosave()

    def _on_paintjobs_reordered(self, from_index: int, to_index: int) -> None:
        """Qt reordered the list view; mirror the move into the library.

        `_current_paintjob` holds an object reference, not an index, so the
        "which paintjob is selected" state naturally survives the move.
        We just need to translate the visible selection index.
        """
        self._library.move(from_index, to_index)
        # The view already moved; keep sidebar selection on the dragged row.
        self._sidebar.set_selected_index(to_index)
        self._schedule_autosave()

    def _build_slot_triangle_mask(
        self, assembled, bundle: BroughtUpCharacter,
    ) -> dict[str, list[int]]:
        """Group triangles by the slot they belong to for highlight focus.

        `SlotRegion.texture_layout_indices` stores **0-based** positions
        (from `enumerate(mesh.texture_layouts)`), but `AssembledMesh.
        texture_layout_indices[tri]` is **1-based** with `0 = untextured`
        — same convention as `atlas_uv_mapper`, which subtracts 1 before
        indexing. We convert on the triangle side and skip `0`, mapping
        each textured triangle through the correct region entry.
        """
        layout_to_slot: dict[int, str] = {}
        for slot_name, regions in bundle.slot_regions.slots.items():
            for region in regions.regions:
                for layout_idx in region.texture_layout_indices:
                    layout_to_slot[layout_idx] = slot_name

        mask: dict[str, list[int]] = {}
        for tri_idx, one_based in enumerate(assembled.texture_layout_indices):
            if one_based == 0:
                continue   # Untextured triangle — no slot ownership.

            slot = layout_to_slot.get(one_based - 1)
            if slot is not None:
                mask.setdefault(slot, []).append(tri_idx)

        return mask

    def _on_slot_focus_changed(self, slot_name) -> None:
        # `slot_name` is either a `str` (focus on that slot) or `None`
        # (clear focus). Declared as `object` on the signal.
        if slot_name is None:
            self._kart_viewer.set_highlighted_triangles(None)
        else:
            self._kart_viewer.set_highlighted_triangles(
                self._slot_triangle_mask.get(slot_name, []),
            )

        # Focus changes pick which slot "This slot" scope targets in the
        # transform panel, so re-push candidates whenever it shifts.
        if (
            getattr(self, "_transform_panel", None) is not None
            and self._transform_panel.isVisible()
        ):
            self._refresh_transform_panel()

    def _populate_slot_editor(self) -> None:
        """Refresh the slot-editor swatches for the current paintjob + preview character.

        Shows either the paintjob's authored colors or VRAM defaults for
        slots it hasn't touched. Called on preview-character change,
        paintjob-selection change, and after any edit that mutates slot
        state.
        """
        if self._current_bundle is None:
            self._slot_editor.set_slots([])
            return

        slot_names = self._ordered_slot_names(
            self._current_bundle.slot_regions.slots.keys(),
        )

        dimensions = {
            name: self._slot_dimension_hint(
                self._current_bundle.slot_regions.slots[name],
            )
            for name in slot_names
        }

        self._slot_editor.set_slots(slot_names, dimensions=dimensions)

        for slot_name, slot in self._current_bundle.slot_regions.slots.items():
            if (
                self._current_paintjob is not None
                and slot_name in self._current_paintjob.slots
            ):
                colors = list(self._current_paintjob.slots[slot_name].colors)
            else:
                colors = self._color_handler.default_slot_colors(
                    self._config.iso_root, slot,
                )

            self._slot_editor.set_slot_colors(slot_name, colors)

    def _slot_dimension_hint(self, slot_regions) -> str:
        """Pixel-space size hint shown next to a slot label in the editor.

        Each `SlotRegions` may hold multiple `SlotRegion` rects (same CLUT,
        different geometry sampling it). `vram_width` is in 16bpp VRAM units;
        at 4bpp each VRAM unit holds 4 pixels, so pixel width = vram_width x
        stretch (4 for Bit4, 2 for Bit8, 1 otherwise). Height is 1:1.

        Single region renders as "WxH"; multi-region slots fold into
        "WxH + WxH" so artists see they'll need one texture per region when
        importing custom pixels.
        """
        if not slot_regions.regions:
            return ""

        sizes: list[str] = []
        for region in slot_regions.regions:
            stretch = {0: 4, 1: 2}.get(int(region.bpp), 1)
            pixel_w = region.vram_width * stretch
            pixel_h = region.vram_height
            sizes.append(f"{pixel_w}x{pixel_h}")

        return " + ".join(sizes)

    def _ordered_slot_names(self, names) -> list[str]:
        """Sort slot names into canonical order so the sidebar stays stable across characters.

        Different characters' CTR files can list slots in different orders, so
        following the bundle's natural iteration makes the sidebar reshuffle
        every time the preview character changes. Canonical first (the shared
        slot order the interface contract pins down), anything unrecognized
        appended alphabetically.
        """
        name_set = set(names)

        ordered = [n for n in CANONICAL_SLOT_NAMES if n in name_set]
        extras = sorted(name_set - set(CANONICAL_SLOT_NAMES))
        return ordered + extras

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
        if (
            self._current_bundle is None
            or not self._require_active_paintjob()
        ):
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        old_color = self._current_color(slot, color_index)
        new_color = self._color_picker.pick(old_color, parent=self)
        if new_color is None or new_color.value == old_color.value:
            return

        paintjob = self._current_paintjob
        # Apply immediately so the user sees the change without waiting for
        # the undo stack; then push a command that represents the same
        # operation so it can be reversed. SetSlotColorCommand's first redo
        # is a no-op.
        self.apply_color_edit_from_command(paintjob, slot, color_index, new_color)

        self._undo_stack.push(SetSlotColorCommand(
            self, paintjob, slot, color_index, old_color, new_color,
        ))

    def _on_slot_reset_requested(self, slot_name: str) -> None:
        if (
            self._current_bundle is None
            or not self._require_active_paintjob()
        ):
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        paintjob = self._current_paintjob
        old_colors = self._snapshot_slot_colors(paintjob, slot.slot_name)
        self.apply_slot_reset_from_command(paintjob, slot)
        self._undo_stack.push(ResetSlotCommand(
            self, paintjob, slot, old_colors,
        ))

    def _on_eyedropper_picked(
        self, tex_layout_index: int, byte_u: float, byte_v: float,
    ) -> None:
        """Resolve an Alt+Click 3D pick to a (slot, color_index) and reveal it.

        The viewer gives us a 1-based texture_layout index + the interpolated
        byte-space UV at the hit. We map that to:
          * a paintjob slot — by finding which `SlotRegions` has this layout
            index in its `texture_layout_indices` list,
          * a color_index — by sampling the atlas at the hit's pixel and
            matching the RGB back to one of the slot's 16 PsxColors.

        On success we open the color picker pre-loaded with the hit color so
        Alt+Click → pick-new-color is a two-click flow. On "this isn't on a
        paintjob-editable slot" we post a status-bar message rather than a
        dialog; the tool already has enough modal popups.
        """
        if self._current_bundle is None or self._current_character is None:
            return

        mesh = self._current_bundle.mesh
        layout_index = tex_layout_index - 1
        if layout_index < 0 or layout_index >= len(mesh.texture_layouts):
            return

        slot_name = self._find_slot_for_texture_layout(layout_index)
        if slot_name is None:
            self.statusBar().showMessage(
                "Eyedropper: this face isn't assigned to a paintjob slot "
                "(shared asset, wheel, or other non-editable region).",
                4000,
            )
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        tl = mesh.texture_layouts[layout_index]
        atlas_x = int(round(tl.page_x * 256 + byte_u))
        atlas_y = int(round(tl.page_y * 256 + byte_v))
        atlas_w = AtlasRenderer.ATLAS_WIDTH
        atlas_h = AtlasRenderer.ATLAS_HEIGHT
        if not (0 <= atlas_x < atlas_w and 0 <= atlas_y < atlas_h):
            return

        offset = (atlas_y * atlas_w + atlas_x) * 4
        if offset + 4 > len(self._current_bundle.atlas_rgba):
            return

        hit_r = self._current_bundle.atlas_rgba[offset + 0]
        hit_g = self._current_bundle.atlas_rgba[offset + 1]
        hit_b = self._current_bundle.atlas_rgba[offset + 2]
        hit_a = self._current_bundle.atlas_rgba[offset + 3]

        color_index = self._match_atlas_pixel_to_slot_color(
            slot, hit_r, hit_g, hit_b, hit_a,
        )

        if color_index is None:
            self.statusBar().showMessage(
                f"Eyedropper: sampled ({hit_r},{hit_g},{hit_b}) in "
                f"slot '{slot_name}' but couldn't match it to any of the 16 CLUT entries.",
                4000,
            )
            return

        hex_text = self._color_converter.psx_to_u16_hex(
            self._current_color(slot, color_index),
        )

        self.statusBar().showMessage(
            f"Eyedropper: {slot_name}[{color_index}] = {hex_text}. "
            f"Opening color picker — Cancel to leave unchanged.",
            5000,
        )

        # Pop the color picker pre-loaded with the picked color. If the user
        # changes it, that's a normal slot edit (goes through the regular
        # undo path); Cancel leaves everything alone.
        self._edit_color_at(slot, color_index)

    def _edit_color_at(self, slot, color_index: int) -> None:
        """Programmatic equivalent of the user clicking that slot's swatch.

        Centralizes the color-picker → apply → undo-push flow so both the
        swatch-click handler and the eyedropper drive the same pipeline.
        """
        if (
            self._current_bundle is None
            or not self._require_active_paintjob()
        ):
            return

        old_color = self._current_color(slot, color_index)
        new_color = self._color_picker.pick(old_color, parent=self)
        if new_color is None or new_color.value == old_color.value:
            return

        paintjob = self._current_paintjob
        self.apply_color_edit_from_command(paintjob, slot, color_index, new_color)

        self._undo_stack.push(SetSlotColorCommand(
            self, paintjob, slot, color_index, old_color, new_color,
        ))

    def _find_slot_for_texture_layout(self, layout_index: int) -> str | None:
        """Reverse-lookup: which paintjob slot owns this 0-based texture layout?

        `SlotRegionDeriver` stores layout indices per region when it groups
        layouts by CLUT; iterating the map is fast enough for the per-click
        path (slots are ~8, regions per slot rarely > 3).
        """
        if self._current_bundle is None:
            return None

        for slot_name, slot in self._current_bundle.slot_regions.slots.items():
            for region in slot.regions:
                if layout_index in region.texture_layout_indices:
                    return slot_name

        return None

    def _match_atlas_pixel_to_slot_color(
        self, slot, r: int, g: int, b: int, a: int,
    ) -> int | None:
        """Find which of a slot's 16 CLUT entries was sampled at the hit pixel.

        PSX CLUT value 0 is the transparency sentinel — it renders with alpha
        zero, so a zero-alpha pixel means that sentinel (usually index 0).
        Opaque pixels are compared against each non-sentinel entry's
        snapped-RGB representation, which is how the atlas renderer produced
        them in the first place (no fuzzy matching needed).
        """
        for i in range(SlotColors.SIZE):
            color = self._current_color(slot, i)
            if color.value == 0:
                if a == 0:
                    return i

                continue

            rgb = self._color_converter.psx_to_rgb(color)
            if rgb.r == r and rgb.g == g and rgb.b == b:
                return i

        return None

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

        menu = QMenu(self)
        menu.addAction(
            "Transform colors...",
            lambda: self._show_transform_panel(slot_override=slot_name),
        )

        # Gradient fill only makes sense on a whole slot — offer it from the
        # row-chrome context menu, not individual swatches.
        if color_index < 0:
            menu.addAction(
                "Gradient fill...",
                lambda: self._open_gradient_fill_dialog(slot_name),
            )

            self._add_apply_palette_submenu(menu, slot_name)

            # Texture import is only offered on slots whose VRAM rect is
            # dim-invariant across characters. Hiding the action on
            # non-portable slots (like `floor`) is cleaner than showing
            # it and erroring out on click.
            if slot_name not in self._NON_PORTABLE_TEXTURE_SLOTS:
                menu.addSeparator()
                menu.addAction(
                    "Import texture...",
                    lambda: self._on_import_slot_texture(slot_name),
                )

                if (
                    self._current_paintjob is not None
                    and self._current_paintjob.slots.get(slot_name) is not None
                    and self._current_paintjob.slots[slot_name].pixels
                ):
                    menu.addAction(
                        "Remove imported texture",
                        lambda: self._on_remove_slot_texture(slot_name),
                    )

        menu.exec(global_pos)

    def _add_apply_palette_submenu(self, menu: QMenu, slot_name: str) -> None:
        """Append an "Apply Color Palette" submenu listing every saved palette.

        Each palette entry is a leaf action that opens the apply-mapping
        dialog pre-targeted at `slot_name`. When no palettes exist, the
        submenu shows one disabled hint row instead of being empty (empty
        submenus render as unclickable dead space and confuse users).
        """
        submenu = menu.addMenu("Apply Color Palette")
        palettes = self._palette_library.palettes

        if not palettes:
            hint = submenu.addAction(
                "(no palettes saved — create one in the Color Palettes tab)",
            )
            hint.setEnabled(False)
            return

        for i, palette in enumerate(palettes):
            label = palette.name.strip() or f"Palette {i + 1}"
            submenu.addAction(
                label,
                lambda _=False, pi=i, sn=slot_name: self._on_apply_palette_to_slot(pi, sn),
            )

    def _open_gradient_fill_dialog(self, slot_name: str) -> None:
        if (
            self._current_bundle is None
            or not self._require_active_paintjob()
        ):
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        current_colors = [
            self._current_color(slot, i) for i in range(SlotColors.SIZE)
        ]

        dialog = GradientFillDialog(
            slot_name=slot_name,
            current_colors=current_colors,
            color_converter=self._color_converter,
            gradient_generator=self._gradient_generator,
            parent=self,
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        replacements = dialog.resulting_replacements()
        if not replacements:
            return

        paintjob = self._current_paintjob
        edits = [
            BulkColorEdit(
                paintjob=paintjob,
                slot=slot,
                color_index=ci,
                old_color=current_colors[ci],
                new_color=new_color,
            )
            for ci, new_color in replacements
        ]

        self.apply_bulk_edits_from_command(
            [(e.paintjob, e.slot, e.color_index, e.new_color) for e in edits],
        )

        lo = replacements[0][0]
        hi = replacements[-1][0]
        label = f"Gradient fill {slot_name}[{lo}..{hi}]"
        self._undo_stack.push(BulkTransformCommand(self, label, edits))

    # Slots whose VRAM rect dimensions aren't invariant across the 15
    # profile characters. Texture import is refused for these so the
    # resulting paintjob stays portable across every character — the
    # one exception today is `floor` (4 distinct sizes + Papu missing
    # it entirely), which is CLUT-editable but not textureable.
    _NON_PORTABLE_TEXTURE_SLOTS = frozenset({"floor"})

    def _on_import_slot_texture(self, slot_name: str) -> None:
        """Import a PNG as the slot's 4bpp pixel + CLUT payload.

        The paintjob stays character-agnostic: a slot's VRAM rect is
        dim-invariant across the 15 characters for every slot we allow
        import on, so the same pixel buffer uploads cleanly wherever the
        paintjob is applied. The import is refused on slots whose rect
        dims vary by character (see `_NON_PORTABLE_TEXTURE_SLOTS`).

        Multi-region slots are also rejected — the paintjob format can
        hold per-region pixel payloads, but the import UX for picking
        one PNG per region isn't built yet.
        """
        if (
            self._current_bundle is None
            or self._current_character is None
            or not self._require_active_paintjob()
        ):
            return

        if slot_name in self._NON_PORTABLE_TEXTURE_SLOTS:
            QMessageBox.information(
                self, "Slot not textureable",
                f"'{slot_name}' has different VRAM rect dimensions per character "
                f"(e.g. 8x8 on Crash, 16x8 on Cortex, 4x8 on Tiny), so an imported "
                f"texture can't upload cleanly across all characters. Edit its "
                f"CLUT colors instead — those stay portable.",
            )

            return

        slot_regions = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot_regions is None or not slot_regions.regions:
            return

        if len(slot_regions.regions) != 1:
            QMessageBox.information(
                self, "Multi-region slot",
                f"'{slot_name}' occupies {len(slot_regions.regions)} separate "
                f"VRAM regions on this character. Texture import for "
                f"multi-region slots isn't supported yet — edit the CLUT "
                f"instead, or use a single-region slot.",
            )
            return

        region = slot_regions.regions[0]
        stretch = {0: 4, 1: 2}.get(int(region.bpp), 1)
        width = region.vram_width * stretch
        height = region.vram_height

        path_str, _ = QFileDialog.getOpenFileName(
            self, f"Import texture for {slot_name} ({width}x{height})",
            self._config.iso_root or str(Path.home()),
            "PNG images (*.png);;All files (*)",
        )

        if not path_str:
            return

        path = Path(path_str)

        texture = self._import_png_with_prompt(path, width, height)
        if texture is None:
            return

        # Replace the slot's CLUT with the quantized palette and stash
        # pixels keyed by VRAM position so re-parsing the mesh doesn't
        # invalidate the assignment.
        paintjob = self._current_paintjob
        paintjob.slots[slot_name] = SlotColors(
            colors=list(texture.palette),
            pixels=[
                SlotRegionPixels(
                    vram_x=region.vram_x,
                    vram_y=region.vram_y,
                    width=texture.width,
                    height=texture.height,
                    pixels=texture.pixels,
                ),
            ],
        )

        self._undo_stack.clear()
        self._sidebar.set_library(
            self._library,
            selected_index=self._library.paintjobs.index(paintjob),
        )
        self._populate_slot_editor()
        self._schedule_autosave()
        self.statusBar().showMessage(
            f"Imported {path.name} → {slot_name}",
        )

    def _import_png_with_prompt(self, path: Path, width: int, height: int):
        """Try REJECT mode first; on size mismatch, ask the artist whether to scale/crop."""
        try:
            return self._texture_importer.import_from_path(path, width, height)
        except ValueError as exc:
            # Size mismatch — offer Scale / Crop / Cancel.
            msg = QMessageBox(self)
            msg.setWindowTitle("Size mismatch")
            msg.setText(str(exc))
            msg.setInformativeText(
                "Choose how to fit the source image into the slot:",
            )
            scale = msg.addButton("Scale", QMessageBox.ButtonRole.AcceptRole)
            crop = msg.addButton("Center crop", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton(QMessageBox.StandardButton.Cancel)
            msg.exec()

            chosen = msg.clickedButton()

            if chosen is scale:
                mode = SizeMismatchMode.SCALE
            elif chosen is crop:
                mode = SizeMismatchMode.CENTER_CROP
            else:
                return None

            try:
                return self._texture_importer.import_from_path(
                    path, width, height, mode=mode,
                )
            except ValueError as exc2:
                QMessageBox.critical(self, "Import failed", str(exc2))
                return None
        except OSError as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return None

    def _on_remove_slot_texture(self, slot_name: str) -> None:
        """Drop a slot's pixel payload; CLUT colors stay as-is."""
        if not self._require_active_paintjob():
            return

        paintjob = self._current_paintjob
        slot = paintjob.slots.get(slot_name)
        if slot is None or not slot.pixels:
            return

        paintjob.slots[slot_name] = SlotColors(colors=list(slot.colors), pixels=[])

        self._undo_stack.clear()
        self._sidebar.set_library(
            self._library,
            selected_index=self._library.paintjobs.index(paintjob),
        )
        self._populate_slot_editor()
        self._schedule_autosave()
        self.statusBar().showMessage(f"Removed imported texture on {slot_name}")

    def _show_transform_panel(self, slot_override: str | None = None) -> None:
        """Open or focus the modeless Transform Colors panel.

        `slot_override` pins the panel's "Just this slot" scope to a
        specific slot — used when the user opens the panel from a slot
        row's right-click menu, where the clicked slot is the implicit
        target but it may not be the currently-highlighted one. `None`
        falls back to whatever slot the editor is highlighting.

        The panel stays live across paintjob / preview-character /
        slot-focus changes — `_refresh_transform_panel` rebuilds its
        candidate list whenever the current state changes underneath.
        Snapshot for live preview is taken on show and restored on hide,
        so closing the panel always reverts to the last committed state.
        """
        if (
            self._current_bundle is None
            or not self._require_active_paintjob()
        ):
            return

        self._ensure_transform_panel()
        self._refresh_transform_panel(slot_override=slot_override)

        # When the user opened the panel from a slot's right-click menu,
        # default the scope to THIS_SLOT so the scope combo reflects
        # their intent. They can still flip it to ENTIRE_KART via the
        # combo if they want.
        if slot_override is not None:
            self._transform_panel.select_slot_scope()

        if not self._transform_panel.isVisible():
            self._take_transform_snapshot()
            self._transform_panel.show()
        else:
            self._transform_panel.raise_()
            self._transform_panel.activateWindow()

    def _ensure_transform_panel(self) -> None:
        if self._transform_panel is not None:
            return

        panel = TransformColorsPanel(
            color_transformer=self._color_transformer,
            color_converter=self._color_converter,
            parent=self,
        )
        panel.preview_changed.connect(self._on_transform_preview)
        panel.commit_requested.connect(self._on_transform_commit)
        panel.closing.connect(self._on_transform_panel_closing)

        self._transform_panel = panel

    def _refresh_transform_panel(
        self, slot_override: str | None = None,
    ) -> None:
        """Rebuild the panel's candidate list against current paintjob state.

        `slot_override` pins the "Just this slot" scope to that slot
        name. Used by the slot-row right-click menu where the clicked
        slot is the intended target. Without an override we fall back
        to the slot-editor's Highlight-focused slot.
        """
        if self._transform_panel is None:
            return
        if self._current_bundle is None or self._current_paintjob is None:
            return

        slot_name = slot_override or self._slot_editor.focused_slot()
        slot_candidates: list[TransformCandidate] = []
        if slot_name is not None:
            target_slot = self._current_bundle.slot_regions.slots.get(slot_name)
            if target_slot is not None:
                slot_candidates = self._build_transform_candidates([target_slot])

        kart_candidates = self._build_transform_candidates(
            list(self._current_bundle.slot_regions.slots.values()),
        )

        self._transform_panel.set_candidates(
            slot_candidates, kart_candidates, slot_name or "",
        )

    def _take_transform_snapshot(self) -> None:
        """Capture paintjob state for live-preview rollback."""
        if self._current_bundle is None:
            return

        candidates = self._build_transform_candidates(
            list(self._current_bundle.slot_regions.slots.values()),
        )

        self._transform_snapshot = self._snapshot_slots_for_preview(candidates)
        self._transform_dirty_keys = set()

    def _on_transform_preview(self, edits: list) -> None:
        """Slider tick → rewind preview residue, paint the new in-flight transform."""
        if self._transform_snapshot is None:
            return

        self._apply_transform_preview(
            self._transform_snapshot, self._transform_dirty_keys, edits,
        )

    def _on_transform_commit(self, edits: list) -> None:
        """Commit button → rewind preview, apply + push undo, take fresh snapshot."""
        if self._current_bundle is None or not edits or self._transform_snapshot is None:
            return

        self._restore_transform_snapshot(
            self._transform_snapshot, self._transform_dirty_keys,
        )

        self._commit_transform_edits(edits)

        # New baseline: the committed edits are now the "current" state,
        # and any further preview in the panel should rewind to here.
        self._take_transform_snapshot()
        self._transform_panel.commit_finished()

    def _on_transform_panel_closing(self) -> None:
        """Panel closed → restore any pending preview, drop the snapshot."""
        if self._transform_snapshot is None:
            return

        self._restore_transform_snapshot(
            self._transform_snapshot, self._transform_dirty_keys,
        )

        self._transform_snapshot = None
        self._transform_dirty_keys = set()

    def _commit_transform_edits(self, edits: list) -> None:
        """Apply edits + push a single `BulkTransformCommand` onto the undo stack."""
        self.apply_bulk_edits_from_command(
            [(e.paintjob, e.slot, e.color_index, e.new_color) for e in edits],
        )

        label = f"Transform {len(edits)} color{'s' if len(edits) != 1 else ''}"
        self._undo_stack.push(BulkTransformCommand(self, label, edits))

    def _snapshot_slots_for_preview(
        self, candidates: list[TransformCandidate],
    ) -> dict[tuple[int, str], tuple[object, object, SlotColors | None]]:
        """Capture per-slot paintjob state for every unique slot in `candidates`.

        Keyed by `(id(paintjob), slot_name)` — `id()` on the paintjob
        object makes the key hashable and stable across the preview
        session without leaking the reference into Python's dict-equality
        machinery (paintjobs aren't `@dataclass(eq=False)` so two distinct
        instances with matching fields would otherwise hash equal).
        The value carries the paintjob back so the revert path can find
        it without re-scanning the library.
        """
        snapshot: dict[tuple[int, str], tuple[object, object, SlotColors | None]] = {}
        for cand in candidates:
            key = (id(cand.paintjob), cand.slot.slot_name)
            if key in snapshot:
                continue

            snapshot[key] = (
                cand.paintjob,
                cand.slot,
                self._snapshot_slot_colors(cand.paintjob, cand.slot.slot_name),
            )

        return snapshot

    def _apply_transform_preview(
        self,
        snapshot: dict[tuple[int, str], tuple[object, object, SlotColors | None]],
        dirty_keys: set[tuple[int, str]],
        edits: list,
    ) -> None:
        """Push a preview edit set into the paintjob + 3D view.

        Reverts everything to snapshot first (clearing residue from a
        prior Preview click that might have touched different
        slots/indices), then applies the new edits grouped by slot, then
        does one full-atlas GL upload. Per-slot `set_atlas_region` can't
        be used here — the viewer's pending-region field is a single
        tuple, so multiple region uploads within one paintGL cycle would
        drop all but the last one.
        """
        if self._current_bundle is None:
            return

        new_dirty = {(id(e.paintjob), e.slot.slot_name) for e in edits}

        for key in dirty_keys | new_dirty:
            paintjob, slot, colors = snapshot[key]
            restored = self._color_handler.restore_slot(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                paintjob,
                slot,
                colors,
            )
            self._slot_editor.set_slot_colors(slot.slot_name, restored)

        by_slot: dict[tuple[int, str], list] = {}
        slot_for_key: dict[tuple[int, str], object] = {}
        paintjob_for_key: dict[tuple[int, str], object] = {}

        for edit in edits:
            key = (id(edit.paintjob), edit.slot.slot_name)
            by_slot.setdefault(key, []).append(edit)
            slot_for_key[key] = edit.slot
            paintjob_for_key[key] = edit.paintjob

        for key, slot_edits in by_slot.items():
            slot = slot_for_key[key]
            paintjob = paintjob_for_key[key]
            self._color_handler.apply_edits(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                paintjob,
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

        dirty_keys.clear()
        dirty_keys.update(new_dirty)

    def _restore_transform_snapshot(
        self,
        snapshot: dict[tuple[int, str], tuple[object, object, SlotColors | None]],
        dirty_keys: set[tuple[int, str]],
    ) -> None:
        """Revert every slot that diverged during preview back to snapshot."""
        if self._current_bundle is None or not dirty_keys:
            dirty_keys.clear()
            return

        for key in dirty_keys:
            paintjob, slot, colors = snapshot[key]
            restored = self._color_handler.restore_slot(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                paintjob,
                slot,
                colors,
            )
            self._slot_editor.set_slot_colors(slot.slot_name, restored)

        self._kart_viewer.set_atlas(
            self._current_bundle.atlas_rgba,
            AtlasRenderer.ATLAS_WIDTH,
            AtlasRenderer.ATLAS_HEIGHT,
        )

        dirty_keys.clear()

    def apply_bulk_edits_from_command(
        self,
        operations: list[tuple[object, object, int, PsxColor]],
    ) -> None:
        """Apply N `(paintjob, slot, color_index, color)` changes in one batch.

        Used by the Transform Colors Accept path AND by
        `BulkTransformCommand` redo/undo. Groups by
        `(id(paintjob), slot_name)` so each slot takes one paintjob
        mutation + one atlas render, and finishes with a single full-atlas
        GL upload. Per-edit `apply_color_edit_from_command` would queue
        one `set_atlas_region` per edit, but the viewer keeps only the
        latest pending region — all earlier uploads get dropped before
        `paintGL` runs, so a multi-slot transform would leave most slots
        un-updated on the GPU.
        """
        if self._current_bundle is None or not operations:
            return

        # If every edit targets a single paintjob that's NOT the currently
        # selected one, switch selection — a Ctrl+Z on hidden state is
        # confusing.
        paintjobs = {id(op[0]) for op in operations}
        if len(paintjobs) == 1:
            self._switch_to_paintjob_if_needed(operations[0][0])

        by_slot: dict[tuple[int, str], list[tuple[int, PsxColor]]] = {}
        slot_for_key: dict[tuple[int, str], object] = {}
        paintjob_for_key: dict[tuple[int, str], object] = {}
        for paintjob, slot, color_index, color in operations:
            key = (id(paintjob), slot.slot_name)
            by_slot.setdefault(key, []).append((color_index, color))
            slot_for_key[key] = slot
            paintjob_for_key[key] = paintjob

        for key, slot_ops in by_slot.items():
            slot = slot_for_key[key]
            paintjob = paintjob_for_key[key]
            self._color_handler.apply_edits(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                paintjob,
                slot,
                slot_ops,
            )

            if paintjob is self._current_paintjob:
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
        """Resolve `(slot, color_index)` → effective color for every color in `slots`.

        "Effective" = current paintjob override if present, else the
        preview character's VRAM default. That matches what the swatches
        visually show and what Replace-matches uses as its before value.
        """
        if self._current_paintjob is None:
            return []

        paintjob = self._current_paintjob

        result: list[TransformCandidate] = []
        for slot in slots:
            if slot.slot_name in paintjob.slots:
                colors = paintjob.slots[slot.slot_name].colors
            else:
                colors = self._color_handler.default_slot_colors(
                    self._config.iso_root, slot,
                )

            for i, color in enumerate(colors):
                result.append(TransformCandidate(
                    paintjob=paintjob,
                    slot=slot,
                    color_index=i,
                    current_color=PsxColor(value=color.value),
                ))

        return result

    def _switch_to_paintjob_if_needed(self, paintjob: Paintjob) -> None:
        """Make `paintjob` the currently-selected one (for undo across paintjobs).

        Commands hold paintjob refs — a Ctrl+Z on an edit to paintjob A
        while paintjob B is selected needs to visually show the unwound
        change on A. Select it in the sidebar so the user sees what just
        reverted.
        """
        if self._current_paintjob is paintjob:
            return

        try:
            index = self._library.paintjobs.index(paintjob)
        except ValueError:
            # Paintjob is no longer in the library (e.g. command targets a
            # deleted entry). Fail quietly — deletion clears the undo
            # stack, so this should only happen if an earlier path missed
            # that cleanup.
            return

        self._current_paintjob = paintjob
        self._sidebar.set_selected_index(index)
        self._reload_preview()

    def apply_color_edit_from_command(
        self,
        paintjob: Paintjob,
        slot,
        color_index: int,
        new_color: PsxColor,
    ) -> None:
        """Apply a color change without going through the undo stack.

        Called from `SetSlotColorCommand.redo` / `undo` and from the
        initial edit path to keep all three mutate-state / re-render /
        refresh-swatch steps in one place.
        """
        if self._current_bundle is None:
            return

        self._switch_to_paintjob_if_needed(paintjob)

        self._color_handler.apply_edit(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            paintjob,
            slot,
            color_index,
            new_color,
        )

        self._push_slot_region_to_viewer(slot)
        self._slot_editor.update_color(slot.slot_name, color_index, new_color)

    def apply_slot_reset_from_command(self, paintjob: Paintjob, slot) -> None:
        if self._current_bundle is None:
            return

        self._switch_to_paintjob_if_needed(paintjob)

        # Reset pulls colors from the paintjob's base character, not the
        # preview character. An artist editing "Crash's racing stripes"
        # while previewing on Cortex still wants Reset to restore the
        # Crash vanilla CLUT — otherwise every slot reset would drift
        # toward whichever character was in the preview dropdown.
        base_x, base_y = self._base_clut_coord_for(paintjob, slot.slot_name)

        defaults = self._color_handler.reset_slot(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            paintjob,
            slot,
            base_x,
            base_y,
        )

        self._push_slot_region_to_viewer(slot)
        self._slot_editor.set_slot_colors(slot.slot_name, defaults)

    def _base_clut_coord_for(
        self, paintjob: Paintjob, slot_name: str,
    ) -> tuple[int, int]:
        """Resolve the paintjob's base-character CLUT coords for a given slot.

        Falls back to the preview character's coords when the paintjob
        has no `base_character_id` (e.g. free-floating "wildcard"
        paintjobs) — there's no other character to anchor against in
        that case.
        """
        base_char = self._find_character(paintjob.base_character_id)
        if base_char is None:
            base_char = self._current_character

        if base_char is None:
            return 0, 0

        for slot_profile in base_char.slots:
            if slot_profile.name == slot_name:
                return slot_profile.clut.x, slot_profile.clut.y

        return 0, 0

    def _find_character(self, character_id: str | None):
        """Profile-character lookup by id. Returns `None` when not found or id is None."""
        if character_id is None or self._profile is None:
            return None
        
        for character in self._profile.characters:
            if character.id == character_id:
                return character

        return None

    def apply_slot_restore_from_command(
        self,
        paintjob: Paintjob,
        slot,
        old_colors: SlotColors | None,
    ) -> None:
        if self._current_bundle is None:
            return

        self._switch_to_paintjob_if_needed(paintjob)

        colors = self._color_handler.restore_slot(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            paintjob,
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

    def _snapshot_slot_colors(
        self, paintjob: Paintjob, slot_name: str,
    ) -> SlotColors | None:
        """Deep-copy a slot's entire state (colors + imported pixels).

        Used by the Transform Colors preview loop to revert a drag-driven
        preview back to pre-transform state. Pixels are passed through by
        reference — the pixel bytes are immutable, and the transform
        preview only mutates CLUT entries, so sharing the refs is safe
        and saves a copy on every slider tick.
        """
        slot = paintjob.slots.get(slot_name)
        if slot is None:
            return None

        return SlotColors(
            colors=[PsxColor(value=c.value) for c in slot.colors],
            pixels=list(slot.pixels),
        )

    def _current_color(self, slot, color_index: int) -> PsxColor:
        """Effective color for `(slot, color_index)` in the editor right now.

        Paintjob override if the slot has been authored; otherwise the
        VRAM default from the preview character's CLUT.
        """
        if (
            self._current_paintjob is not None
            and slot.slot_name in self._current_paintjob.slots
        ):
            return self._current_paintjob.slots[slot.slot_name].colors[color_index]

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
