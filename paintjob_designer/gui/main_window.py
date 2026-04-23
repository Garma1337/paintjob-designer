# coding: utf-8

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.color.gradient import GradientGenerator
from paintjob_designer.color.transform import ColorTransformer
from paintjob_designer.config.iso_root_validator import IsoRootValidator
from paintjob_designer.config.store import AppConfig, ConfigStore
from paintjob_designer.core import Slugifier
from paintjob_designer.ctr.vertex_assembler import VertexAssembler
from paintjob_designer.gui.command.bulk_transform_command import BulkColorEdit, BulkTransformCommand
from paintjob_designer.gui.command.reset_slot_command import ResetSlotCommand
from paintjob_designer.gui.command.set_slot_color_command import SetSlotColorCommand
from paintjob_designer.gui.controller.animation_controller import AnimationController
from paintjob_designer.gui.controller.paintjob_library_controller import PaintjobLibraryController
from paintjob_designer.gui.controller.palette_library_controller import PaletteLibraryController
from paintjob_designer.gui.controller.profile_holder import ProfileHolder
from paintjob_designer.gui.controller.skin_library_controller import SkinLibraryController
from paintjob_designer.gui.controller.transform_panel_coordinator import TransformPanelCoordinator
from paintjob_designer.gui.dialog.gradient_fill_dialog import GradientFillDialog
from paintjob_designer.gui.dialog.palette_apply_dialog import PaletteApplyDialog
from paintjob_designer.gui.dialog.profile_picker_dialog import ProfilePickerDialog
from paintjob_designer.gui.editor_mode import EditorMode
from paintjob_designer.gui.handler.character_handler import BroughtUpCharacter, CharacterHandler
from paintjob_designer.gui.handler.color_handler import ColorHandler
from paintjob_designer.gui.handler.project_handler import ProjectHandler
from paintjob_designer.gui.util.dialogs import FilePicker, MessageDialog
from paintjob_designer.gui.widget.color_picker import PsxColorPicker
from paintjob_designer.gui.widget.kart_viewer import KartViewer, NullKartViewer
from paintjob_designer.gui.widget.preview_sidebar import PreviewSidebar
from paintjob_designer.gui.widget.slot_editor import SlotEditor
from paintjob_designer.gui.widget.vertex_slot_editor import VertexSlotEditor
from paintjob_designer.models import (
    CharacterProfile,
    KartType,
    Paintjob,
    PaintjobLibrary,
    Palette,
    PaletteLibrary,
    Profile,
    PsxColor,
    Rgb888,
    Skin,
    SkinLibrary,
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
    """Top-level window. Owns the editor surface and orchestrates the
    library / palette / skin / preview controllers."""

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
        skin_writer,
        message: MessageDialog,
        files: FilePicker,
        profile_holder: ProfileHolder,
        paintjob_library_controller: PaintjobLibraryController,
        skin_library_controller: SkinLibraryController,
        palette_library_controller: PaletteLibraryController,
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
        self._skin_writer = skin_writer
        self._message = message
        self._files = files
        self._profile_holder = profile_holder

        self._paintjob_controller = paintjob_library_controller
        self._skin_controller = skin_library_controller
        self._palette_controller = palette_library_controller

        # Make sidebars discoverable via short aliases — most editor
        # logic still asks for them by name. Controllers own the actual
        # sidebar widgets and wire their internal signals.
        self._sidebar = self._paintjob_controller._sidebar
        self._skin_sidebar = self._skin_controller._sidebar
        self._palette_sidebar = self._palette_controller._sidebar

        # Sidebar row labels resolve raw character ids to display names
        # via the profile holder. Installed once here; the holder is a
        # mutable cell so the resolver picks up new profiles without
        # being re-wired.
        self._sidebar.set_character_resolver(self._profile_holder.display_name_for)
        self._skin_sidebar.set_character_resolver(self._profile_holder.display_name_for)

        self._config: AppConfig = self._config_store.load()
        self._profile: Profile | None = None

        # Hydrate library state from the persisted config and hand it
        # to the controllers — they own all read/write access from here
        # on.
        self._paintjob_controller.replace_library(
            self._restore_library_from_config(),
        )
        self._skin_controller.replace_library(
            self._restore_skin_library_from_config(),
        )
        self._palette_controller.replace_library(
            self._restore_palette_library_from_config(),
        )

        self._editor_mode: EditorMode = EditorMode.PAINTJOB
        self._preview_paintjob: Paintjob | None = None
        self._preview_skin: Skin | None = None

        self._wire_controller_signals()

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

        # Per-tab preview-character memory: keyed by editor mode
        # (EditorMode.PAINTJOB / SKIN), value is the last character_id the user
        # picked while that tab was active. On tab change we restore that
        # character if it's still in the new combo's list, falling back
        # to the first compatible character when not.
        self._remembered_character_id: dict[EditorMode, str] = {}

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

        self._transform = TransformPanelCoordinator(
            color_transformer=self._color_transformer,
            color_converter=self._color_converter,
            color_handler=self._color_handler,
            slot_editor_provider=lambda: self._slot_editor,
            kart_viewer_provider=lambda: self._kart_viewer,
            bundle_provider=lambda: self._current_bundle,
            asset_provider=self._active_asset,
            character_provider=lambda: self._current_character,
            editor_mode_provider=lambda: self._editor_mode,
            iso_root_provider=lambda: self._config.iso_root,
            undo_stack=self._undo_stack,
            parent_widget=self,
        )

        self._animation = AnimationController(
            vertex_assembler=self._vertex_assembler,
            bundle_provider=lambda: self._current_bundle,
            on_positions=lambda pos: self._kart_viewer.set_frame_positions(pos),
            parent=self,
        )

        self.resize(1440, 900)
        self.setAcceptDrops(True)
        self.setWindowTitle("Paintjob Designer")

        self._build_menu_bar()
        self._build_ui()
        self._palette_controller.show_initial()
        self._bootstrap()

    @property
    def _library(self) -> PaintjobLibrary:
        return self._paintjob_controller.library

    @property
    def _skin_library(self) -> SkinLibrary:
        return self._skin_controller.library

    @property
    def _palette_library(self) -> PaletteLibrary:
        return self._palette_controller.library

    @property
    def _current_paintjob(self) -> Paintjob | None:
        return self._paintjob_controller.current

    @property
    def _current_skin(self) -> Skin | None:
        return self._skin_controller.current

    def _wire_controller_signals(self) -> None:
        """Forward controller events to the editor-side handlers."""
        pjc = self._paintjob_controller
        pjc.selection_changed.connect(self._on_paintjob_selection_changed)
        pjc.transform_requested.connect(self._on_transform_paintjob_requested)
        pjc.library_changed.connect(self._on_paintjob_library_changed)
        pjc.library_reset.connect(self._undo_stack_clear_safely)
        pjc.mutated.connect(self._schedule_autosave)

        skc = self._skin_controller
        skc.selection_changed.connect(self._on_skin_selection_changed)
        skc.transform_requested.connect(self._on_transform_skin_requested)
        skc.library_changed.connect(self._on_skin_library_changed)
        skc.library_reset.connect(self._undo_stack_clear_safely)
        skc.mutated.connect(self._schedule_autosave)

        plc = self._palette_controller
        plc.save_from_slot_requested.connect(self._on_save_palette_from_slot)
        plc.mutated.connect(self._schedule_autosave)

    def _undo_stack_clear_safely(self) -> None:
        """Drop the undo stack — used when controllers reset their library."""
        if hasattr(self, "_undo_stack"):
            self._undo_stack.clear()

    def _on_paintjob_library_changed(self) -> None:
        if hasattr(self, "_preview_sidebar"):
            self._sync_preview_sidebar_sources()

    def _on_skin_library_changed(self) -> None:
        if hasattr(self, "_preview_sidebar"):
            self._sync_preview_sidebar_sources()

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

        self._paintjob_controller.import_file(path)

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
            file_menu, "Export Paintjob &Library As...",
            self._paintjob_controller.export_library,
            shortcut=QKeySequence("Ctrl+Shift+S"),
        )
        self._add_action(
            file_menu, "&Import Paintjobs...",
            lambda: self._paintjob_controller.import_files(
                self._config.iso_root or None,
            ),
            shortcut=QKeySequence("Ctrl+O"),
        )

        file_menu.addSeparator()
        self._add_action(
            file_menu, "Export &Skin Library As...",
            self._skin_controller.export_library,
        )
        self._add_action(
            file_menu, "Import S&kins...",
            lambda: self._skin_controller.import_files(
                self._config.iso_root or None,
            ),
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

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)

        self._preview_sidebar = PreviewSidebar()
        self._preview_sidebar.composition_changed.connect(
            self._on_preview_composition_changed,
        )

        # Palettes are paintjob-only (vertex/skin slots don't draw from
        # them), so they live nested inside the Paintjobs tab as a second
        # vertically-stacked section rather than as their own top-level
        # tab. Splitter so the artist can grow the palette area when
        # they're palette-heavy and shrink it otherwise.
        paintjobs_tab = QWidget()
        paintjobs_tab_layout = QVBoxLayout(paintjobs_tab)
        paintjobs_tab_layout.setContentsMargins(0, 0, 0, 0)
        paintjobs_tab_layout.setSpacing(4)

        paintjobs_inner_split = QSplitter(Qt.Orientation.Vertical)
        paintjobs_inner_split.addWidget(self._sidebar)

        palette_section = QWidget()
        palette_section_layout = QVBoxLayout(palette_section)
        palette_section_layout.setContentsMargins(0, 0, 0, 0)
        palette_section_layout.setSpacing(2)
        palette_header = QLabel("Color Palettes")
        palette_header.setStyleSheet("color: #aaa; padding: 2px 4px;")
        palette_section_layout.addWidget(palette_header)
        palette_section_layout.addWidget(self._palette_sidebar, 1)
        paintjobs_inner_split.addWidget(palette_section)

        paintjobs_inner_split.setStretchFactor(0, 3)
        paintjobs_inner_split.setStretchFactor(1, 2)
        paintjobs_tab_layout.addWidget(paintjobs_inner_split, 1)

        self._sidebar_tabs = QTabWidget()
        self._sidebar_tabs.addTab(paintjobs_tab, "Paintjobs")
        self._sidebar_tabs.addTab(self._skin_sidebar, "Skins")
        self._sidebar_tabs.addTab(self._preview_sidebar, "Preview")
        self._sidebar_tabs.currentChanged.connect(self._on_sidebar_tab_changed)
        sidebar_layout.addWidget(self._sidebar_tabs, 1)
        sidebar_layout.addWidget(self._animation.panel)

        # Stash for tab-change identity checks — the inner widget hosting
        # the paintjob list is no longer the tab's root widget.
        self._paintjobs_tab = paintjobs_tab
        self._preview_tab = self._preview_sidebar

        viewer_container = QWidget()
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)

        # Preview-character selector sits above the 3D viewer so the
        # "which mesh am I seeing this paintjob on?" question is
        # answered at a glance. Paintjobs themselves are character-
        # agnostic in the new model; this dropdown just picks the
        # preview context (mesh + VRAM defaults). Hidden in Preview
        # mode where the sidebar's own character combo drives.
        self._preview_strip = QWidget()
        preview_strip_layout = QHBoxLayout(self._preview_strip)
        preview_strip_layout.setContentsMargins(8, 4, 8, 4)
        preview_strip_layout.addWidget(QLabel("Preview on:"))
        self._preview_character_combo = QComboBox()
        self._preview_character_combo.setPlaceholderText("Pick a character to preview…")
        self._preview_character_combo.currentIndexChanged.connect(
            self._on_preview_character_changed,
        )
        preview_strip_layout.addWidget(self._preview_character_combo, 1)
        viewer_layout.addWidget(self._preview_strip)

        self._kart_viewer = KartViewer(self._atlas_uv_mapper, self._ray_picker)
        self._kart_viewer.gl_init_failed.connect(self._on_gl_init_failed)
        self._kart_viewer.eyedropper_picked.connect(self._on_eyedropper_picked)
        viewer_layout.addWidget(self._kart_viewer, 1)

        self._slot_editor = SlotEditor(self._color_converter)
        self._slot_editor.color_edit_requested.connect(self._on_color_edit_requested)
        self._slot_editor.slot_reset_requested.connect(self._on_slot_reset_requested)
        self._slot_editor.slot_focus_changed.connect(self._on_slot_focus_changed)
        self._slot_editor.context_requested.connect(self._on_slot_editor_context)

        # Vertex-color editor for the gouraud table; only meaningful in
        # skin mode (paintjobs don't carry vertex overrides). Lives next
        # to the CLUT slot editor in a tab widget so the right pane stays
        # one column wide regardless of which mode is active.
        self._vertex_editor = VertexSlotEditor()
        self._vertex_editor.color_edited.connect(self._on_vertex_color_edited)
        self._vertex_editor.transform_requested.connect(
            self._on_vertex_transform_requested,
        )

        self._right_tabs = QTabWidget()
        self._right_tabs.addTab(self._slot_editor, "CLUT slots")
        self._right_tabs.addTab(self._vertex_editor, "Vertex slots")

        splitter.addWidget(sidebar_container)
        splitter.addWidget(viewer_container)
        splitter.addWidget(self._right_tabs)

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

    def _build_library_toolbar(self) -> None:
        """Top toolbar — only the things that aren't asset-scoped."""
        toolbar = self.addToolBar("Library")
        toolbar.setMovable(False)

        toolbar.addAction("Switch Profile...", self._on_switch_profile)

        self.addToolBarBreak()

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
            self._message.error(self, "Profile not found", str(exc))
            return

        self._update_window_title()

        # Push the active profile + iso into the shared holder + controllers
        # so the new-asset flows can pick characters and seed slots.
        self._profile_holder.set(self._profile)
        self._paintjob_controller.set_iso_root(self._config.iso_root)
        self._skin_controller.set_iso_root(self._config.iso_root)

        # Fresh profile = fresh context. Drop any per-tab memory from
        # the previous profile (character ids may differ).
        self._remembered_character_id.clear()
        self._clear_preview_render()
        self._populate_preview_character_combo([])
        if hasattr(self, "_preview_sidebar"):
            self._sync_preview_sidebar_sources()

        # Auto-select the first paintjob in the active tab (Paintjobs is
        # the default). The selection_changed handler will populate the
        # combo and auto-pick a preview character. The skin controller
        # waits — its first item only auto-selects when the user
        # actually switches to the Skins tab.
        self._paintjob_controller.show_initial_selection()
    def _populate_preview_character_combo(
        self,
        characters: list[CharacterProfile],
    ) -> None:
        self._preview_character_combo.blockSignals(True)
        self._preview_character_combo.clear()

        for character in characters:
            self._preview_character_combo.addItem(
                character.display_name or character.id, character.id,
            )

        # Force "no selection" — without this Qt sets currentIndex to 0
        # automatically as items are added.
        self._preview_character_combo.setCurrentIndex(-1)
        self._preview_character_combo.blockSignals(False)
        self._preview_character_combo.setEnabled(bool(characters))

    def _clear_preview_render(self) -> None:
        self._current_character = None
        self._current_bundle = None
        self._slot_triangle_mask = {}
        self._slot_editor.set_slots([])
        self._vertex_editor.set_colors([])
        self._kart_viewer.clear()

    def _restore_preview_character(
        self, characters: list[CharacterProfile],
    ) -> None:
        if not characters:
            return

        target_index = 0
        remembered = self._remembered_character_id.get(self._editor_mode)
        if remembered:
            for i in range(self._preview_character_combo.count()):
                if self._preview_character_combo.itemData(i) == remembered:
                    target_index = i
                    break

        # Combo is at -1 from `_populate_preview_character_combo`; setting
        # to a valid index always emits and triggers `_reload_preview`.
        self._preview_character_combo.setCurrentIndex(target_index)

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
        """Gate for actions that need a selected paintjob in the library."""
        if self._current_paintjob is not None:
            return True

        QMessageBox.information(
            self, "No paintjob selected",
            "Create a paintjob (sidebar → New) or import one from JSON "
            "before performing this action.",
        )

        return False

    def _require_active_asset(self) -> bool:
        """Gate for actions that edit whatever the active mode exposes."""
        if self._editor_mode == EditorMode.PREVIEW:
            QMessageBox.information(
                self, "Preview mode is read-only",
                "The Preview tab combines existing paintjobs and skins to "
                "show how they look together — it can't be edited. Switch "
                "to the Paintjobs or Skins tab to make changes.",
            )

            return False

        if self._active_asset() is not None:
            return True

        if self._editor_mode == EditorMode.SKIN:
            QMessageBox.information(
                self, "No skin selected",
                "Create a skin (Skins tab → New) or pick one from the list "
                "before performing this action.",
            )
        else:
            QMessageBox.information(
                self, "No paintjob selected",
                "Create a paintjob (sidebar → New) or import one from JSON "
                "before performing this action.",
            )

        return False

    def _on_load_iso(self) -> None:
        chosen = self._files.pick_directory(
            self, "Select extracted CTR ISO root",
            self._config.iso_root or None,
        )

        if chosen is None:
            return

        chosen = str(chosen)

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

        # A fresh ISO invalidates every in-flight asset (character IDs may
        # change between profiles). Reset all three libraries via their
        # controllers — undo history clears via the library_reset signal.
        self._paintjob_controller.replace_library(PaintjobLibrary())
        self._skin_controller.replace_library(SkinLibrary())
        self._current_character = None
        self._current_bundle = None
        self._schedule_autosave()

        self._load_profile(self._config.last_profile_id)
        self.statusBar().showMessage(
            "ISO loaded. Create a paintjob (sidebar → New) or import one to begin.",
        )

    def _on_transform_paintjob_requested(self, index: int) -> None:
        """Paintjob sidebar Transform button — select + open panel."""
        if index < 0 or index >= self._library.count():
            return

        self._sidebar_tabs.setCurrentWidget(self._paintjobs_tab)
        self._paintjob_controller.select_index(index)
        self._editor_mode = EditorMode.PAINTJOB
        self._transform.show()

    def _on_transform_skin_requested(self, index: int) -> None:
        """Skin sidebar Transform button — select + open panel."""
        if index < 0 or index >= self._skin_library.count():
            return

        self._sidebar_tabs.setCurrentWidget(self._skin_sidebar)
        self._skin_controller.select_index(index)
        self._editor_mode = EditorMode.SKIN
        self._transform.show()

    def _restore_library_from_config(self) -> PaintjobLibrary:
        """Rehydrate the persisted library from the config blob."""
        raw = self._config.library
        if not isinstance(raw, dict):
            return PaintjobLibrary()

        try:
            return PaintjobLibrary.model_validate(raw)
        except Exception:
            return PaintjobLibrary()

    def _restore_skin_library_from_config(self) -> SkinLibrary:
        """Rehydrate the persisted skin library from the config blob."""
        raw = self._config.skins
        if not isinstance(raw, dict):
            return SkinLibrary()

        try:
            return SkinLibrary.model_validate(raw)
        except Exception:
            return SkinLibrary()

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
        """Kick the debounced autosave; coalesces bursty mutation sequences."""
        self._autosave_timer.start()

    def _flush_autosave(self) -> None:
        """Serialize the current library + palette library + skin library
        into the config."""
        try:
            self._config.library = self._library.model_dump(by_alias=True)
            self._config.palettes = [
                p.model_dump() for p in self._palette_library.palettes
            ]
            self._config.skins = self._skin_library.model_dump(by_alias=True)
            self._config_store.save(self._config)
        except OSError:
            self.statusBar().showMessage(
                "Autosave failed — check disk space / permissions.", 4000,
            )

    def closeEvent(self, event) -> None:
        """Confirm on close, then flush a final autosave before exiting."""
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
        self._transform.close_pending_preview()

        self._autosave_timer.stop()
        self._flush_autosave()

        event.accept()

    def _on_save_palette_from_slot(self) -> None:
        """Capture the focused slot's 16 colors and hand them to the palette controller."""
        if self._current_bundle is None or self._current_paintjob is None:
            self._message.info(
                self, "No slot to capture",
                "Select a paintjob and highlight a slot row first — the "
                "palette captures that slot's 16 colors.",
            )

            return

        slot_name = self._slot_editor.focused_slot()
        if slot_name is None:
            self._message.info(
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

        self._palette_controller.add_from_colors(colors, f"{slot_name} palette")

    def _on_apply_palette_to_slot(self, palette_index: int, slot_name: str) -> None:
        """Open the mapping dialog for `palette_index` targeting `slot_name`."""
        if palette_index < 0 or palette_index >= len(self._palette_library.palettes):
            return

        if self._current_bundle is None or not self._require_active_asset():
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        palette = self._palette_library.palettes[palette_index]
        asset = self._active_asset()

        dialog = PaletteApplyDialog(
            palette=palette,
            paintjob_name=asset.name,
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
                asset=asset,
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
            [(e.asset, e.slot, e.color_index, e.new_color) for e in edits],
        )

        label = f"Apply palette '{palette.name or '(unnamed)'}' to {slot_name}"
        self._undo_stack.push(BulkTransformCommand(self, label, edits))

    def _on_reset_camera(self) -> None:
        self._kart_viewer.reset_camera()

    def _on_switch_profile(self) -> None:
        """Let the user pick a different target profile."""
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

        # Profile change invalidates every in-flight asset since character IDs
        # / slot names may differ. Reset both libraries via their controllers.
        self._paintjob_controller.replace_library(PaintjobLibrary())
        self._skin_controller.replace_library(SkinLibrary())
        self._current_character = None
        self._current_bundle = None
        self._schedule_autosave()

        self._load_profile(chosen)
        self._update_window_title()
        self.statusBar().showMessage(f"Switched to profile: {self._profile_display_name()}")

    def _on_gl_init_failed(self, reason: str) -> None:
        """Replace the 3D viewer with a placeholder when the GL context fails."""
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
        self._kart_viewer = NullKartViewer()
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
        self._transform.close_pending_preview()

        self._current_character = character
        # Per-tab memory: this is now the character to restore next time
        # the user comes back to this tab.
        if self._editor_mode in (EditorMode.PAINTJOB, EditorMode.SKIN):
            self._remembered_character_id[self._editor_mode] = character.id

        self._reload_preview()

        if self._transform.is_visible():
            self._transform._take_snapshot()
            self._transform.refresh()

    def _reload_preview(self) -> None:
        """Re-render the current preview character with the active asset."""
        if self._current_character is None:
            return

        active = self._active_asset()
        render_asset = active if active is not None else Paintjob()
        try:
            bundle = self._character_handler.load_character(
                self._config.iso_root, self._current_character, render_asset,
            )
        except FileNotFoundError as exc:
            self.statusBar().showMessage(f"Load failed: {exc}")
            return

        self._current_bundle = bundle

        self._kart_viewer.set_atlas(
            bundle.atlas_rgba, AtlasRenderer.ATLAS_WIDTH, AtlasRenderer.ATLAS_HEIGHT,
        )

        assembled = self._vertex_assembler.assemble(
            bundle.mesh, vertex_overrides=self._active_vertex_overrides(),
        )
        self._kart_viewer.set_mesh(assembled, bundle.mesh.texture_layouts)

        self._slot_triangle_mask = self._build_slot_triangle_mask(assembled, bundle)

        self._animation.reload()
        self._populate_slot_editor()
        self._populate_vertex_editor()
        self.statusBar().showMessage(
            f"{self._current_character.display_name}: "
            f"{len(bundle.slot_regions.slots)} slots, "
            f"{len(bundle.slot_regions.unmatched_palettes)} unmatched palettes, "
            f"{assembled.triangle_count} triangles",
        )

    def _on_paintjob_selection_changed(self, paintjob: Paintjob | None) -> None:
        """Active paintjob changed — repopulate the combo, restore character.

        The combo is filtered to characters whose `kart_type` matches the
        paintjob. The preview character defaults to whichever character
        the user last viewed paintjobs on (per-tab memory) or the first
        compatible one if that character isn't in the new list.
        """
        self._transform.close_pending_preview()
        self._clear_preview_render()

        if paintjob is None:
            self._populate_preview_character_combo([])
            return

        characters = self._characters_matching_kart_type(paintjob.kart_type)
        self._populate_preview_character_combo(characters)
        self._restore_preview_character(characters)

    def _characters_matching_kart_type(
        self, kart_type: KartType,
    ) -> list[CharacterProfile]:
        if self._profile is None:
            return []

        return [c for c in self._profile.characters if c.kart_type == kart_type]

    def _active_asset(self) -> Paintjob | Skin | None:
        """The asset the viewer is currently rendering. Preview mode returns
        a synthesized Paintjob merging the chosen paintjob + skin slots."""
        if self._editor_mode == EditorMode.PREVIEW:
            return self._build_preview_composite()

        if self._editor_mode == EditorMode.SKIN:
            return self._current_skin

        return self._current_paintjob

    def _build_preview_composite(self) -> Paintjob | None:
        paintjob = self._preview_paintjob
        skin = self._preview_skin
        if paintjob is None and skin is None:
            return None

        merged: dict[str, SlotColors] = {}
        if paintjob is not None:
            merged.update(paintjob.slots)

        if skin is not None:
            merged.update(skin.slots)

        return Paintjob(
            name="(preview composite)",
            kart_type=paintjob.kart_type if paintjob is not None else KartType.KART,
            slots=merged,
        )

    def _active_slot_names(self) -> set[str]:
        if self._current_character is None:
            return set()

        if self._editor_mode == EditorMode.PREVIEW:
            return (
                {s.name for s in self._current_character.kart_slots}
                | {s.name for s in self._current_character.skin_slots}
            )

        if self._editor_mode == EditorMode.SKIN:
            return {s.name for s in self._current_character.skin_slots}

        return {s.name for s in self._current_character.kart_slots}

    def _active_vertex_overrides(self) -> dict[int, Rgb888]:
        if self._editor_mode == EditorMode.PREVIEW and self._preview_skin is not None:
            return self._preview_skin.vertex_overrides

        if self._editor_mode == EditorMode.SKIN and self._current_skin is not None:
            return self._current_skin.vertex_overrides

        return {}

    def _populate_vertex_editor(self) -> None:
        if self._current_bundle is None:
            self._vertex_editor.set_colors([])
            return

        overrides = self._active_vertex_overrides()
        effective: list[Rgb888] = []
        for i, base in enumerate(self._current_bundle.mesh.gouraud_colors):
            override = overrides.get(i)

            if override is not None:
                effective.append(Rgb888(r=override.r, g=override.g, b=override.b))
            else:
                effective.append(Rgb888(r=base.r, g=base.g, b=base.b))

        self._vertex_editor.set_colors(effective)
        self._vertex_editor.set_editable(
            self._editor_mode == EditorMode.SKIN and self._current_skin is not None,
        )

    def _on_sidebar_tab_changed(self, index: int) -> None:
        """Switch editor mode and restore that tab's preview state.

        Each editing tab keeps its own (asset, preview character) pair.
        Coming back to a tab restores what you were last looking at;
        if you've never visited the tab (or the asset wasn't selected
        yet), the first asset auto-selects and renders on the first
        compatible character.
        """
        widget = self._sidebar_tabs.widget(index)

        if widget is self._paintjobs_tab:
            new_mode = EditorMode.PAINTJOB
        elif widget is self._skin_sidebar:
            new_mode = EditorMode.SKIN
        elif widget is getattr(self, "_preview_tab", None):
            new_mode = EditorMode.PREVIEW
        else:
            return

        if new_mode == self._editor_mode:
            return

        self._editor_mode = new_mode
        self._transform.close_pending_preview()
        self._update_editors_for_mode()
        self._clear_preview_render()

        if new_mode == EditorMode.PREVIEW:
            # Preview tab drives composition from its own combos; the top
            # "Preview on:" strip is redundant there.
            self._preview_strip.setVisible(False)
            self._sync_preview_sidebar_sources()
            return

        self._preview_strip.setVisible(True)
        controller = (
            self._paintjob_controller if new_mode == EditorMode.PAINTJOB
            else self._skin_controller
        )

        if controller.current is None:
            # First entry into this tab — let the controller pick the
            # first item; its selection_changed signal feeds back into
            # `_on_paintjob/_on_skin_selection_changed` which populates
            # the combo and restores the per-tab preview character.
            controller.show_initial_selection()
            return

        # Asset already selected for this tab — repopulate the combo for
        # it and restore the remembered preview character.
        asset = controller.current
        if new_mode == EditorMode.PAINTJOB:
            characters = self._characters_matching_kart_type(asset.kart_type)
        else:
            characters = self._characters_for_skin(asset)

        self._populate_preview_character_combo(characters)
        self._restore_preview_character(characters)

    def _update_editors_for_mode(self) -> None:
        """Enable or disable the right-pane editor tabs based on current mode."""
        editable = self._editor_mode in (EditorMode.PAINTJOB, EditorMode.SKIN)
        self._slot_editor.setEnabled(editable)
        self._vertex_editor.setEnabled(editable and self._editor_mode == EditorMode.SKIN)

    def _sync_preview_sidebar_sources(self) -> None:
        """Push current characters + libraries into the Preview sidebar."""
        if self._profile is None:
            return

        self._preview_sidebar.set_sources(
            self._profile.characters, self._library, self._skin_library,
        )

    def _on_preview_composition_changed(
        self, character_id: str, paintjob_index: int, skin_index: int,
    ) -> None:
        """Sidebar combos changed — rebuild the preview composite + reload."""
        if self._profile is None:
            return

        character = next(
            (c for c in self._profile.characters if c.id == character_id), None,
        )

        if 0 <= paintjob_index < self._library.count():
            self._preview_paintjob = self._library.paintjobs[paintjob_index]
        else:
            self._preview_paintjob = None

        if 0 <= skin_index < self._skin_library.count():
            self._preview_skin = self._skin_library.skins[skin_index]
        else:
            self._preview_skin = None

        if self._editor_mode != EditorMode.PREVIEW:
            return

        if character is None:
            return

        self._current_character = character
        self._reload_preview()

    def _characters_for_skin(self, skin: Skin) -> list[CharacterProfile]:
        """The single bound character a skin can be previewed on (or empty
        when the saved skin references a character missing from the
        active profile)."""
        if self._profile is None:
            return []

        return [
            c for c in self._profile.characters if c.id == skin.character_id
        ]

    def _on_skin_selection_changed(self, skin: Skin | None) -> None:
        """Active skin changed — repopulate the combo and render."""
        self._transform.close_pending_preview()
        self._clear_preview_render()

        if skin is None:
            self._populate_preview_character_combo([])
            return

        characters = self._characters_for_skin(skin)
        self._populate_preview_character_combo(characters)
        self._restore_preview_character(characters)

    def _build_slot_triangle_mask(
        self, assembled, bundle: BroughtUpCharacter,
    ) -> dict[str, list[int]]:
        """Group triangles by the slot they belong to for highlight focus."""
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
        if self._transform.is_visible():
            self._transform.refresh()

    def _populate_slot_editor(self) -> None:
        """Refresh the slot-editor swatches for the active asset + preview."""
        if self._current_bundle is None:
            self._slot_editor.set_slots([])
            return

        mode_slots = self._active_slot_names()
        visible = {
            name: regions
            for name, regions in self._current_bundle.slot_regions.slots.items()
            if name in mode_slots
        }

        slot_names = self._ordered_slot_names(visible.keys())
        dimensions = {
            name: self._slot_dimension_hint(visible[name])
            for name in slot_names
        }

        self._slot_editor.set_slots(slot_names, dimensions=dimensions)

        active = self._active_asset()
        for slot_name, slot in visible.items():
            if active is not None and slot_name in active.slots:
                colors = list(active.slots[slot_name].colors)
            else:
                colors = self._color_handler.default_slot_colors(
                    self._config.iso_root, slot,
                )

            self._slot_editor.set_slot_colors(slot_name, colors)

    def _slot_dimension_hint(self, slot_regions) -> str:
        """Pixel-space size hint shown next to a slot label in the editor."""
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
        """Sort slot names by the current character's profile order."""
        name_set = set(names)
        if self._current_character is None:
            return sorted(name_set)

        profile_order = [s.name for s in self._current_character.slots]
        ordered = [n for n in profile_order if n in name_set]
        extras = sorted(name_set - set(profile_order))
        return ordered + extras

    def _defaults_by_slot_for_current(self) -> dict[str, list[PsxColor]]:
        """VRAM-default CLUT for every slot the current character owns."""
        if self._current_bundle is None:
            return {}

        return {
            slot_name: self._color_handler.default_slot_colors(
                self._config.iso_root, slot,
            )
            for slot_name, slot in self._current_bundle.slot_regions.slots.items()
        }

    def _on_color_edit_requested(self, slot_name: str, color_index: int) -> None:
        if self._current_bundle is None or not self._require_active_asset():
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        old_color = self._current_color(slot, color_index)
        new_color = self._color_picker.pick(old_color, parent=self)
        if new_color is None or new_color.value == old_color.value:
            return

        # Apply immediately so the user sees the change, then push a
        # command that represents the same operation so it can be reversed.
        # SetSlotColorCommand's first redo is a no-op. Routes through the
        # active asset (paintjob or skin) — both have the same `.slots`
        # shape so the apply path duck-types on it.
        asset = self._active_asset()
        self.apply_color_edit_from_command(asset, slot, color_index, new_color)
        self._undo_stack.push(SetSlotColorCommand(
            self, asset, slot, color_index, old_color, new_color,
        ))

    def _on_vertex_transform_requested(self) -> None:
        """Open the vertex transform dialog and apply the result."""
        if (
            self._editor_mode != EditorMode.SKIN
            or self._current_skin is None
            or self._current_bundle is None
        ):
            return

        effective: list[Rgb888] = []
        overrides = self._current_skin.vertex_overrides
        for i, base in enumerate(self._current_bundle.mesh.gouraud_colors):
            override = overrides.get(i)
            if override is not None:
                effective.append(Rgb888(r=override.r, g=override.g, b=override.b))
            else:
                effective.append(Rgb888(r=base.r, g=base.g, b=base.b))

        from paintjob_designer.gui.dialog.vertex_transform_dialog import (
            VertexTransformDialog,
        )

        dialog = VertexTransformDialog(
            colors=effective,
            color_transformer=self._color_transformer,
            color_converter=self._color_converter,
            parent=self,
        )

        if dialog.exec() != VertexTransformDialog.DialogCode.Accepted:
            return

        new_overrides = dialog.resulting_overrides()
        if not new_overrides:
            return

        # Merge into the skin's override map and prune entries that
        # collapse back to the baked color (e.g. a hue rotation that
        # round-trips to the original RGB after quantization).
        for index, color in new_overrides.items():
            base = self._current_bundle.mesh.gouraud_colors[index]
            if (color.r, color.g, color.b) == (base.r, base.g, base.b):
                self._current_skin.vertex_overrides.pop(index, None)
            else:
                self._current_skin.vertex_overrides[index] = color

        # Re-render and refresh the swatch grid so the new colors show
        # up immediately. Reusing `_reload_preview` keeps the slot
        # editor / vertex editor / 3D viewer / status bar all in sync
        # via the same path used after any other asset mutation.
        self._reload_preview()
        self._schedule_autosave()
        self.statusBar().showMessage(
            f"Applied vertex transform: {len(new_overrides)} colors changed.",
        )

    def _on_vertex_color_edited(self, index: int, color: Rgb888) -> None:
        """Vertex-slot color pick — write the override to the active skin and re-upload the mesh."""
        if self._current_skin is None or self._current_bundle is None:
            return

        base = (
            self._current_bundle.mesh.gouraud_colors[index]
            if 0 <= index < len(self._current_bundle.mesh.gouraud_colors)
            else None
        )

        if base is not None and (color.r, color.g, color.b) == (base.r, base.g, base.b):
            self._current_skin.vertex_overrides.pop(index, None)
        else:
            self._current_skin.vertex_overrides[index] = color

        # Re-assemble with the new override set and push the updated
        # vertex-color buffer to the GL viewer. Full `_reload_preview`
        # would redo the atlas + slot regions too, which is wasted work
        # for a vertex-color edit — only the per-vertex buffer changed.
        assembled = self._vertex_assembler.assemble(
            self._current_bundle.mesh,
            vertex_overrides=self._current_skin.vertex_overrides,
        )
        self._kart_viewer.set_mesh(
            assembled, self._current_bundle.mesh.texture_layouts,
        )

        self._schedule_autosave()

    def _on_slot_reset_requested(self, slot_name: str) -> None:
        if self._current_bundle is None or not self._require_active_asset():
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        asset = self._active_asset()
        old_colors = self._snapshot_slot_colors(asset, slot.slot_name)
        self.apply_slot_reset_from_command(asset, slot)
        self._undo_stack.push(ResetSlotCommand(self, asset, slot, old_colors))

    def _on_eyedropper_picked(
        self, tex_layout_index: int, byte_u: float, byte_v: float,
    ) -> None:
        """Resolve an Alt+Click 3D pick to a (slot, color_index) and reveal it."""
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
        """Programmatic equivalent of the user clicking that slot's swatch."""
        if self._current_bundle is None or not self._require_active_asset():
            return

        old_color = self._current_color(slot, color_index)
        new_color = self._color_picker.pick(old_color, parent=self)
        if new_color is None or new_color.value == old_color.value:
            return

        asset = self._active_asset()
        self.apply_color_edit_from_command(asset, slot, color_index, new_color)
        self._undo_stack.push(SetSlotColorCommand(
            self, asset, slot, color_index, old_color, new_color,
        ))

    def _find_slot_for_texture_layout(self, layout_index: int) -> str | None:
        """Reverse-lookup: which paintjob slot owns this 0-based texture layout?"""
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
        """Find which of a slot's 16 CLUT entries was sampled at the hit pixel."""
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
        """Right-click on a swatch (color_index >= 0) or slot-row chrome (color_index == -1)."""
        if self._current_bundle is None or self._current_character is None:
            return

        slot = self._current_bundle.slot_regions.slots.get(slot_name)
        if slot is None:
            return

        # Bulk operations are available in either edit mode; each writes
        # to the active asset (paintjob or skin). Preview mode is
        # read-only — no menu.
        if self._editor_mode not in (EditorMode.PAINTJOB, EditorMode.SKIN):
            return

        menu = QMenu(self)
        menu.addAction(
            "Transform colors...",
            lambda: self._transform.show(slot_override=slot_name),
        )

        # Gradient fill / palette apply / texture import only make sense
        # on a whole slot — offered from the row-chrome menu, not the
        # per-swatch one.
        if color_index < 0:
            menu.addAction(
                "Gradient fill...",
                lambda: self._open_gradient_fill_dialog(slot_name),
            )

            self._add_apply_palette_submenu(menu, slot_name)

            # Texture import is only offered on slots whose VRAM rect is
            # dim-invariant across characters. Non-portable slots (e.g.
            # kart `floor`) skip it because the imported pixels couldn't
            # upload cleanly across all characters.
            if not self._slot_is_non_portable(slot_name):
                menu.addSeparator()
                menu.addAction(
                    "Import texture...",
                    lambda: self._on_import_slot_texture(slot_name),
                )

                asset = self._active_asset()
                if (
                    asset is not None
                    and asset.slots.get(slot_name) is not None
                    and asset.slots[slot_name].pixels
                ):
                    menu.addAction(
                        "Remove imported texture",
                        lambda: self._on_remove_slot_texture(slot_name),
                    )

        menu.exec(global_pos)

    def _add_apply_palette_submenu(self, menu: QMenu, slot_name: str) -> None:
        """Append an "Apply Color Palette" submenu listing every saved palette."""
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
        if self._current_bundle is None or not self._require_active_asset():
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

        asset = self._active_asset()
        edits = [
            BulkColorEdit(
                asset=asset,
                slot=slot,
                color_index=ci,
                old_color=current_colors[ci],
                new_color=new_color,
            )
            for ci, new_color in replacements
        ]

        self.apply_bulk_edits_from_command(
            [(e.asset, e.slot, e.color_index, e.new_color) for e in edits],
        )

        lo = replacements[0][0]
        hi = replacements[-1][0]
        label = f"Gradient fill {slot_name}[{lo}..{hi}]"
        self._undo_stack.push(BulkTransformCommand(self, label, edits))

    def _slot_is_non_portable(self, slot_name: str) -> bool:
        """True if the slot's `non_portable` flag is set in the current character's profile."""
        if self._current_character is None:
            return False

        for slot in self._current_character.slots:
            if slot.name == slot_name:
                return slot.non_portable
        
        return False

    def _on_import_slot_texture(self, slot_name: str) -> None:
        """Import a PNG as the slot's 4bpp pixel + CLUT payload.

        Targets the active asset (paintjob or skin) — both store pixel
        payloads on `SlotColors.pixels` so the same path works for either.
        """
        if (
            self._current_bundle is None
            or self._current_character is None
            or not self._require_active_asset()
        ):
            return

        if self._slot_is_non_portable(slot_name):
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

        path = self._files.pick_open_path(
            self, f"Import texture for {slot_name} ({width}x{height})",
            self._config.iso_root or None,
            "PNG images (*.png);;All files (*)",
        )

        if path is None:
            return

        path_str = str(path)

        path = Path(path_str)

        texture = self._import_png_with_prompt(path, width, height)
        if texture is None:
            return

        # Replace the slot's CLUT with the quantized palette and stash
        # pixels keyed by VRAM position so re-parsing the mesh doesn't
        # invalidate the assignment.
        asset = self._active_asset()
        asset.slots[slot_name] = SlotColors(
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

        # Texture imports invalidate undo (commands captured pre-import
        # SlotColors refs).
        self._undo_stack.clear()
        self._populate_slot_editor()
        self._reload_preview()
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
        if not self._require_active_asset():
            return

        asset = self._active_asset()
        slot = asset.slots.get(slot_name)
        if slot is None or not slot.pixels:
            return

        asset.slots[slot_name] = SlotColors(colors=list(slot.colors), pixels=[])

        self._undo_stack.clear()
        self._populate_slot_editor()
        self._reload_preview()
        self._schedule_autosave()
        self.statusBar().showMessage(f"Removed imported texture on {slot_name}")

    def apply_bulk_edits_from_command(
        self,
        operations: list[tuple[object, object, int, PsxColor]],
    ) -> None:
        """Apply N `(asset, slot, color_index, color)` changes in one batch.

        `asset` is a Paintjob OR Skin — both have the same `.slots[name]`
        shape so the color-handler path duck-types on it.
        """
        if self._current_bundle is None or not operations:
            return

        # If every edit targets a single asset that isn't the currently-
        # selected one, switch selection so Ctrl+Z doesn't silently mutate
        # an asset the user isn't looking at.
        assets = {id(op[0]) for op in operations}
        if len(assets) == 1:
            self._switch_to_asset_if_needed(operations[0][0])

        by_slot: dict[tuple[int, str], list[tuple[int, PsxColor]]] = {}
        slot_for_key: dict[tuple[int, str], object] = {}
        asset_for_key: dict[tuple[int, str], object] = {}
        for asset, slot, color_index, color in operations:
            key = (id(asset), slot.slot_name)
            by_slot.setdefault(key, []).append((color_index, color))
            slot_for_key[key] = slot
            asset_for_key[key] = asset

        for key, slot_ops in by_slot.items():
            slot = slot_for_key[key]
            asset = asset_for_key[key]
            self._color_handler.apply_edits(
                self._config.iso_root,
                self._current_bundle.atlas_rgba,
                asset,
                slot,
                slot_ops,
            )

            if asset is self._active_asset():
                for color_index, new_color in slot_ops:
                    self._slot_editor.update_color(
                        slot.slot_name, color_index, new_color,
                    )

        self._kart_viewer.set_atlas(
            self._current_bundle.atlas_rgba,
            AtlasRenderer.ATLAS_WIDTH,
            AtlasRenderer.ATLAS_HEIGHT,
        )

    def _switch_to_asset_if_needed(self, asset: Paintjob | Skin) -> None:
        """Select `asset` in its sidebar so an undo visibly reverts the edit."""
        if isinstance(asset, Skin):
            if self._current_skin is asset:
                return
            try:
                index = self._skin_library.skins.index(asset)
            except ValueError:
                return
            self._editor_mode = EditorMode.SKIN
            self._skin_controller.select_index(index)
            self._reload_preview()
            return

        if self._current_paintjob is asset:
            return
        try:
            self._library.paintjobs.index(asset)
        except ValueError:
            # Asset isn't in the library anymore (deletion should have
            # cleared undo, so this is a rare safety net).
            return
        self._editor_mode = EditorMode.PAINTJOB
        self._paintjob_controller.select_paintjob(asset)
        self._reload_preview()

    def apply_color_edit_from_command(
        self,
        asset: Paintjob | Skin,
        slot,
        color_index: int,
        new_color: PsxColor,
    ) -> None:
        """Apply a color change without going through the undo stack."""
        if self._current_bundle is None:
            return

        self._switch_to_asset_if_needed(asset)

        self._color_handler.apply_edit(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            asset,
            slot,
            color_index,
            new_color,
        )

        self._push_slot_region_to_viewer(slot)
        self._slot_editor.update_color(slot.slot_name, color_index, new_color)

    def apply_slot_reset_from_command(
        self, asset: Paintjob | Skin, slot,
    ) -> None:
        if self._current_bundle is None:
            return

        self._switch_to_asset_if_needed(asset)

        # Reset pulls colors from the asset's base character — for
        # paintjobs that's `base_character_id` (wildcard-capable), for
        # skins it's the bound `character_id` (character-locked).
        base_x, base_y = self._base_clut_coord_for(asset, slot.slot_name)

        defaults = self._color_handler.reset_slot(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            asset,
            slot,
            base_x,
            base_y,
        )

        self._push_slot_region_to_viewer(slot)
        self._slot_editor.set_slot_colors(slot.slot_name, defaults)

    def _base_clut_coord_for(
        self, asset: Paintjob | Skin, slot_name: str,
    ) -> tuple[int, int]:
        """Resolve the asset's base-character CLUT coords for a given slot."""
        base_id = (
            asset.character_id if isinstance(asset, Skin)
            else asset.base_character_id
        )

        base_char = self._find_character(base_id) or self._current_character
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
        asset: Paintjob | Skin,
        slot,
        old_colors: SlotColors | None,
    ) -> None:
        if self._current_bundle is None:
            return

        self._switch_to_asset_if_needed(asset)

        colors = self._color_handler.restore_slot(
            self._config.iso_root,
            self._current_bundle.atlas_rgba,
            asset,
            slot,
            old_colors,
        )

        self._push_slot_region_to_viewer(slot)
        self._slot_editor.set_slot_colors(slot.slot_name, colors)

    def _push_slot_region_to_viewer(self, slot) -> None:
        """Upload just the dirty rectangle of the atlas after a slot edit."""
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
        """Atlas-pixel bounding box enclosing every VRAM region of `slot`."""
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
        self, asset: Paintjob | Skin, slot_name: str,
    ) -> SlotColors | None:
        """Deep-copy a slot's entire state (colors + imported pixels)."""
        slot = asset.slots.get(slot_name)
        if slot is None:
            return None

        return SlotColors(
            colors=[PsxColor(value=c.value) for c in slot.colors],
            pixels=list(slot.pixels),
        )

    def _current_color(self, slot, color_index: int) -> PsxColor:
        """Effective color for `(slot, color_index)` in the editor right now."""
        active = self._active_asset()
        if active is not None and slot.slot_name in active.slots:
            return active.slots[slot.slot_name].colors[color_index]

        defaults = self._color_handler.default_slot_colors(self._config.iso_root, slot)
        return defaults[color_index]
