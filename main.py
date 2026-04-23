# coding: utf-8

import sys

from PySide6.QtWidgets import QApplication

from paintjob_designer.gui.main_window import MainWindow
from paintjob_designer.services import container

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(container.resolve("app_icon").load())

    window = MainWindow(
        config_store=container.resolve("config_store"),
        iso_root_validator=container.resolve("iso_root_validator"),
        profile_registry=container.resolve("profile_registry"),
        character_handler=container.resolve("character_handler"),
        color_handler=container.resolve("color_handler"),
        project_handler=container.resolve("project_handler"),
        color_converter=container.resolve("color_converter"),
        color_picker=container.resolve("psx_color_picker"),
        vertex_assembler=container.resolve("vertex_assembler"),
        atlas_uv_mapper=container.resolve("atlas_uv_mapper"),
        color_transformer=container.resolve("color_transformer"),
        gradient_generator=container.resolve("gradient_generator"),
        ray_picker=container.resolve("ray_triangle_picker"),
        slugifier=container.resolve("slugifier"),
        texture_importer=container.resolve("texture_importer"),
        skin_writer=container.resolve("skin_writer"),
        message=container.resolve("message_dialog"),
        files=container.resolve("file_picker"),
        profile_holder=container.resolve("profile_holder"),
        paintjob_library_controller=container.resolve("paintjob_library_controller"),
        skin_library_controller=container.resolve("skin_library_controller"),
        palette_library_controller=container.resolve("palette_library_controller"),
    )

    window.show()
    sys.exit(app.exec())
