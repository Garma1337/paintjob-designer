# coding: utf-8

from pathlib import Path

from paintjob_designer.color.converter import ColorConverter
from paintjob_designer.color.gradient import GradientGenerator
from paintjob_designer.color.transform import ColorTransformer
from paintjob_designer.config.iso_root_validator import IsoRootValidator
from paintjob_designer.config.store import ConfigStore
from paintjob_designer.core import Container, Slugifier
from paintjob_designer.ctr.animation import AnimationDecoder
from paintjob_designer.ctr.reader import CtrModelReader
from paintjob_designer.ctr.vertex_assembler import VertexAssembler
from paintjob_designer.gui.app_icon import AppIcon
from paintjob_designer.gui.handler.character_handler import CharacterHandler
from paintjob_designer.gui.handler.color_handler import ColorHandler
from paintjob_designer.gui.handler.project_handler import ProjectHandler
from paintjob_designer.gui.widget.color_picker import PsxColorPicker
from paintjob_designer.paintjob.reader import PaintjobReader
from paintjob_designer.paintjob.writer import PaintjobWriter
from paintjob_designer.profile.reader import ProfileReader
from paintjob_designer.profile.registry import ProfileRegistry
from paintjob_designer.render.atlas_renderer import AtlasRenderer
from paintjob_designer.render.atlas_uv_mapper import AtlasUvMapper
from paintjob_designer.render.ray_picker import RayTrianglePicker
from paintjob_designer.render.slot_region_deriver import SlotRegionDeriver
from paintjob_designer.texture.importer import TextureImporter
from paintjob_designer.texture.quantizer import TextureQuantizer
from paintjob_designer.vram.cache import VramCache
from paintjob_designer.vram.reader import VramReader


def _default_config_path() -> Path:
    """Resolve the platform's app-data directory for `paintjob-designer/config.json`.

    Lazily imports Qt so `services.py` stays importable in headless contexts that
    don't resolve `config_store` (tests, CLI tools).
    """
    from PySide6.QtCore import QStandardPaths
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "paintjob-designer" / "config.json"


container = Container()

container.register("config_store", lambda c: ConfigStore(_default_config_path()))
container.register("iso_root_validator", lambda c: IsoRootValidator())
container.register("slugifier", lambda c: Slugifier())
container.register("app_icon", lambda c: AppIcon())
container.register("color_converter", lambda c: ColorConverter())
container.register("color_transformer", lambda c: ColorTransformer(c.resolve("color_converter")))
container.register("gradient_generator", lambda c: GradientGenerator(c.resolve("color_converter")))
container.register("ray_triangle_picker", lambda c: RayTrianglePicker())
container.register("profile_reader", lambda c: ProfileReader())
container.register("profile_registry", lambda c: ProfileRegistry(c.resolve("profile_reader")))
container.register("animation_decoder", lambda c: AnimationDecoder())
container.register("ctr_model_reader", lambda c: CtrModelReader(c.resolve("animation_decoder")))
container.register("vertex_assembler", lambda c: VertexAssembler())
container.register("slot_region_deriver", lambda c: SlotRegionDeriver())
container.register("vram_reader", lambda c: VramReader())
container.register("vram_cache", lambda c: VramCache(c.resolve("vram_reader")))
container.register("atlas_renderer", lambda c: AtlasRenderer(c.resolve("color_converter")))
container.register("atlas_uv_mapper", lambda c: AtlasUvMapper())
container.register("psx_color_picker", lambda c: PsxColorPicker(c.resolve("color_converter")))
container.register("paintjob_reader", lambda c: PaintjobReader())
container.register("paintjob_writer", lambda c: PaintjobWriter())
container.register("texture_quantizer", lambda c: TextureQuantizer(c.resolve("color_converter")))
container.register("texture_importer", lambda c: TextureImporter(c.resolve("texture_quantizer")))
container.register("character_handler", lambda c: CharacterHandler(
    c.resolve("ctr_model_reader"),
    c.resolve("vram_cache"),
    c.resolve("slot_region_deriver"),
    c.resolve("atlas_renderer"),
))
container.register("color_handler", lambda c: ColorHandler(
    c.resolve("vram_cache"),
    c.resolve("atlas_renderer"),
))
container.register("project_handler", lambda c: ProjectHandler(
    c.resolve("paintjob_reader"),
    c.resolve("paintjob_writer"),
))
