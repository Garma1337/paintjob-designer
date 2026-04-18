# coding: utf-8

from paintjob_designer.models import (
    BitDepth,
    BlendingMode,
    CtrDraw,
    CtrFrame,
    CtrMesh,
    CtrModel,
    TextureLayout,
)


class TestCtrDraw:

    def test_default_is_all_zero(self):
        draw = CtrDraw()

        assert draw.raw == 0
        assert draw.new_tristrip is False
        assert draw.swap_vertex is False
        assert draw.flip_normal is False
        assert draw.cull_backface is False
        assert draw.color_scratchpad is False
        assert draw.stack_vertex is False
        assert draw.stack_index == 0
        assert draw.color_index == 0
        assert draw.tex_index == 0

    def test_flag_bits(self):
        # Every flag bit set individually.
        assert CtrDraw(raw=1 << 31).new_tristrip is True
        assert CtrDraw(raw=1 << 30).swap_vertex is True
        assert CtrDraw(raw=1 << 29).flip_normal is True
        assert CtrDraw(raw=1 << 28).cull_backface is True
        assert CtrDraw(raw=1 << 27).color_scratchpad is True
        assert CtrDraw(raw=1 << 26).stack_vertex is True

    def test_index_fields(self):
        # stack_index = 0xAB (bits 16-23)
        # color_index = 0x55 (bits 9-15, 7 bits)
        # tex_index = 0x1A3 (bits 0-8, 9 bits)
        raw = (0xAB << 16) | (0x55 << 9) | 0x1A3
        draw = CtrDraw(raw=raw)

        assert draw.stack_index == 0xAB
        assert draw.color_index == 0x55
        assert draw.tex_index == 0x1A3

    def test_tex_index_spans_9_bits(self):
        # 0x1FF is the max tex_index (9 bits all set).
        assert CtrDraw(raw=0x1FF).tex_index == 0x1FF

    def test_color_index_spans_7_bits(self):
        assert CtrDraw(raw=0x7F << 9).color_index == 0x7F


class TestTextureLayout:

    def test_defaults(self):
        tl = TextureLayout()

        assert tl.palette_x == 0
        assert tl.palette_y == 0
        assert tl.bpp == BitDepth.Bit4
        assert tl.blending == BlendingMode.Standard
        assert TextureLayout.SIZE == 12


class TestModelsInstantiate:
    """Sanity: confirm the dataclasses default-construct without errors."""

    def test_ctr_frame(self):
        frame = CtrFrame()

        assert frame.vertices == []
        assert frame.offset.x == 0.0

    def test_ctr_mesh(self):
        mesh = CtrMesh()

        assert mesh.draw_commands == []
        assert mesh.texture_layouts == []
        assert mesh.gouraud_colors == []

    def test_ctr_model(self):
        model = CtrModel()

        assert model.meshes == []
