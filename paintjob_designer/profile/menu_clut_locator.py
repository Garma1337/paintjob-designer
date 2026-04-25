# coding: utf-8

import numpy as np

from paintjob_designer.models import VramPage


class MenuClutLocator:
    """Find duplicates of a 16-entry CLUT elsewhere in VRAM by signature
    matching.

    The PSX character-select screen typically uploads a copy of a
    character's race CLUT to a different VRAM coord for menu rendering.
    Given the race coord, this locator scans the rest of VRAM for any
    16-u16 sequence that matches the source byte-for-byte.
    """

    CLUT_ENTRIES = 16

    def find_duplicates(
        self,
        vram: VramPage,
        source_x: int,
        source_y: int,
        excluded: set[tuple[int, int]] | None = None,
    ) -> list[tuple[int, int]]:
        """Return every (x, y) in `vram` whose 16-u16 CLUT matches the one
        at (source_x, source_y).

        The source position is implicitly excluded (the source itself
        always matches). Anything in `excluded` is also dropped — pass
        already-claimed menu coords in to avoid double-assignment.
        Matches that would extend past the row edge are skipped.
        """
        signature = self.read_signature(vram, source_x, source_y)
        omit = (excluded or set()) | {(source_x, source_y)}
        return self.find_matches(vram, signature, omit)

    def read_signature(
        self, vram: VramPage, x: int, y: int,
    ) -> list[int]:
        return [vram.u16_at(x + i, y) for i in range(self.CLUT_ENTRIES)]

    def find_matches(
        self,
        vram: VramPage,
        signature: list[int],
        excluded: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        if len(signature) != self.CLUT_ENTRIES:
            raise ValueError(
                f"Signature must be {self.CLUT_ENTRIES} entries, got {len(signature)}",
            )

        # numpy view for speed: VRAM is ~524 K u16 cells.
        arr = np.frombuffer(vram.data, dtype=np.uint16).reshape(
            vram.HEIGHT, vram.WIDTH,
        )

        first = signature[0]
        sig_arr = np.array(signature, dtype=np.uint16)

        candidate_ys, candidate_xs = np.where(arr == first)
        max_x = vram.WIDTH - self.CLUT_ENTRIES

        matches: list[tuple[int, int]] = []
        for y, x in zip(candidate_ys.tolist(), candidate_xs.tolist()):
            if x > max_x:
                continue

            if (x, y) in excluded:
                continue

            if np.array_equal(arr[y, x:x + self.CLUT_ENTRIES], sig_arr):
                matches.append((x, y))

        return matches

    def signature_entropy(self, signature: list[int]) -> int:
        """Number of distinct u16 entries in `signature` — useful as a
        cheap "signal vs noise" gate. All-zero CLUTs (entropy == 1) match
        thousands of VRAM positions and aren't safe to auto-locate.
        """
        return len(set(signature))
