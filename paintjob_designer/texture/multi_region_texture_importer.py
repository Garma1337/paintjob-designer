# coding: utf-8

from PIL import Image

from paintjob_designer.models import (
    MultiRegionTextureImport,
    MultiRegionTextureRegionImport,
)
from paintjob_designer.texture.four_bpp_codec import FourBppCodec
from paintjob_designer.texture.texture_quantizer import TextureQuantizer


class MultiRegionTextureImporter:
    """Joint-quantizes N images into one shared 16-color PSX CLUT and
    separate 4bpp pixel buffers per region.

    The shared CLUT lets multi-region slots (one logical surface split
    across disjoint VRAM rectangles) keep visual continuity — each region
    samples the same palette so colors don't drift at the seams.

    Stitches images vertically (right-padded to max width with transparent
    pixels) before quantizing, then unpacks and slices the result per
    region. Padding bytes land on palette index 0 (the transparency
    sentinel) and are discarded when slicing.
    """

    _PIXEL_ALIGNMENT = 2  # 4bpp packs 2 pixels per byte

    def __init__(
        self, quantizer: TextureQuantizer, codec: FourBppCodec,
    ) -> None:
        self._quantizer = quantizer
        self._codec = codec

    def import_for_regions(
        self,
        images: list[Image.Image],
        region_specs: list[tuple[int, int]],
    ) -> MultiRegionTextureImport:
        if len(images) != len(region_specs):
            raise ValueError(
                f"images / region_specs length mismatch: "
                f"{len(images)} vs {len(region_specs)}",
            )

        if not images:
            raise ValueError("Need at least one region image")

        if any(w <= 0 or h <= 0 for w, h in region_specs):
            raise ValueError(f"Region dimensions must be positive: {region_specs}")

        prepared = self._prepare_per_region(images, region_specs)

        max_width = max(w for w, _ in region_specs)
        if max_width % self._PIXEL_ALIGNMENT != 0:
            max_width += 1

        total_height = sum(h for _, h in region_specs)

        stitched = Image.new("RGBA", (max_width, total_height), (0, 0, 0, 0))
        y_offset = 0
        for img, (_, h) in zip(prepared, region_specs):
            stitched.paste(img, (0, y_offset))
            y_offset += h

        quantized = self._quantizer.quantize(stitched, max_width, total_height)
        all_indices = self._codec.unpack(
            quantized.pixels, max_width * total_height,
        )

        regions: list[MultiRegionTextureRegionImport] = []
        y_offset = 0
        for (w, h) in region_specs:
            indices = self.slice_region(all_indices, max_width, y_offset, w, h)
            regions.append(MultiRegionTextureRegionImport(
                width=w, height=h, pixels=self._codec.pack(indices),
            ))
            y_offset += h

        return MultiRegionTextureImport(palette=quantized.palette, regions=regions)

    def _prepare_per_region(
        self,
        images: list[Image.Image],
        region_specs: list[tuple[int, int]],
    ) -> list[Image.Image]:
        out: list[Image.Image] = []

        for img, (w, h) in zip(images, region_specs):
            rgba = img.convert("RGBA")

            if rgba.size == (w, h):
                out.append(rgba)
            else:
                out.append(rgba.resize((w, h), Image.Resampling.LANCZOS))

        return out

    @staticmethod
    def slice_region(
        all_indices: list[int],
        stitched_width: int,
        y_offset: int,
        region_width: int,
        region_height: int,
    ) -> list[int]:
        """Pull a region_width × region_height block starting at row y_offset
        out of a row-major index buffer of width `stitched_width`. Padding
        on the right (stitched_width − region_width) is discarded.
        """
        if region_width % MultiRegionTextureImporter._PIXEL_ALIGNMENT != 0:
            raise ValueError(
                f"Region width must be even for 4bpp packing, got {region_width}",
            )

        out: list[int] = []
        for row in range(region_height):
            start = (y_offset + row) * stitched_width
            out.extend(all_indices[start:start + region_width])

        return out
