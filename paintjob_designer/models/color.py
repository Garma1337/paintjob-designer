# coding: utf-8

from dataclasses import dataclass


@dataclass
class PsxColor:
    """PSX 15-bit BGR color with stencil bit.

    Bit layout (16-bit little-endian short):
        stp | bbbbb | ggggg | rrrrr
         15 | 14-10 |  9-5  |  4-0
    """
    BITS_PER_COMPONENT = 5
    MAX_COMPONENT = 31

    value: int = 0

    @property
    def r5(self) -> int:
        return self.value & 0x1F

    @property
    def g5(self) -> int:
        return (self.value >> 5) & 0x1F

    @property
    def b5(self) -> int:
        return (self.value >> 10) & 0x1F

    @property
    def stp(self) -> int:
        return (self.value >> 15) & 0x1


@dataclass
class Rgb888:
    r: int = 0
    g: int = 0
    b: int = 0
