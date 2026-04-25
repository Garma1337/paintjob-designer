# coding: utf-8

"""Backfill `clut_menu` for skin slots by signature-matching VRAM files.

For each skin slot, reads the 16 PSX u16 race CLUT from `shared.vrm` and
scans the menu VRAM (`bigfile/levels/menu_models/data.vrm`) for the same
sequence. A unique match becomes the slot's `clut_menu`.

Skin slots whose race CLUT is low-entropy (≤ 1 distinct value, e.g. all
zero) are skipped — the matcher would return false positives. Slots with
multiple matches are also skipped with a warning so the user can resolve
them manually.

Usage (from repo root with the venv active):

    PYTHONPATH=. python tools/populate_skin_menu_cluts.py \\
        --profile config/profiles/saphi.json \\
        --iso     /path/to/saphi/build/ctr-u
"""

import argparse
import json
import sys
from pathlib import Path

from paintjob_designer.profile.menu_clut_locator import MenuClutLocator
from paintjob_designer.profile.reader import ProfileReader
from paintjob_designer.schema_keys import ProfileKey
from paintjob_designer.vram.reader import VramReader

_MIN_SIGNATURE_ENTROPY = 2

_RACE_VRM_RELPATH = Path("bigfile") / "packs" / "shared.vrm"
_MENU_VRM_RELPATH = Path("bigfile") / "levels" / "menu_models" / "data.vrm"


def _load_vram(iso_root: Path, relpath: Path):
    vrm_path = iso_root / relpath
    if not vrm_path.is_file():
        raise FileNotFoundError(f"VRAM file not found at {vrm_path}")

    return VramReader().read(vrm_path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument(
        "--out", type=Path,
        help="Output JSON path; defaults to overwriting --profile.",
    )
    args = parser.parse_args()

    out_path = args.out or args.profile

    raw = json.loads(args.profile.read_text(encoding="utf-8"))
    profile = ProfileReader().read(json.dumps(raw))

    race_vram = _load_vram(args.iso, _RACE_VRM_RELPATH)
    menu_vram = _load_vram(args.iso, _MENU_VRM_RELPATH)
    locator = MenuClutLocator()

    found = 0
    skipped_low_entropy = 0
    skipped_no_match = 0
    skipped_ambiguous = 0

    raw_characters = raw.get(ProfileKey.CHARACTERS, [])

    for raw_char, char in zip(raw_characters, profile.characters):
        for raw_slot, slot in zip(
            raw_char.get(ProfileKey.SKIN_SLOTS, []), char.skin_slots,
        ):
            if slot.clut_menu is not None:
                continue

            sig = locator.read_signature(
                race_vram, slot.clut_race.x, slot.clut_race.y,
            )
            if locator.signature_entropy(sig) < _MIN_SIGNATURE_ENTROPY:
                skipped_low_entropy += 1
                print(
                    f"  skip {char.id}/{slot.name}: low-entropy CLUT "
                    f"(entropy={locator.signature_entropy(sig)})",
                    file=sys.stderr,
                )
                continue

            matches = locator.find_matches(menu_vram, sig, excluded=set())

            if not matches:
                skipped_no_match += 1
                continue

            if len(matches) > 1:
                skipped_ambiguous += 1
                preview = ", ".join(f"({x},{y})" for x, y in matches[:3])
                print(
                    f"  skip {char.id}/{slot.name}: {len(matches)} matches "
                    f"[{preview}{'...' if len(matches) > 3 else ''}]",
                    file=sys.stderr,
                )
                continue

            menu_x, menu_y = matches[0]
            raw_slot[ProfileKey.CLUT_MENU] = {
                ProfileKey.CLUT_X: menu_x,
                ProfileKey.CLUT_Y: menu_y,
            }
            found += 1

    out_path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {out_path}:")
    print(f"  populated   : {found}")
    print(f"  no match    : {skipped_no_match}")
    print(f"  ambiguous   : {skipped_ambiguous}")
    print(f"  low entropy : {skipped_low_entropy}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
