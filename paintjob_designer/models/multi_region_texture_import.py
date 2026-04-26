# coding: utf-8

from dataclasses import dataclass

from paintjob_designer.models.color import PsxColor


@dataclass
class MultiRegionTextureRegionImport:
    """One region's pixel payload after joint quantization."""
    width: int
    height: int
    pixels: bytes  # packed 4bpp, two pixels per byte


@dataclass
class MultiRegionTextureImport:
    """Output of `MultiRegionTextureImporter.import_for_regions`: a single
    16-entry CLUT shared across every region, plus per-region 4bpp pixels.
    """
    palette: list[PsxColor]
    regions: list[MultiRegionTextureRegionImport]
