# coding: utf-8

"""Populate `skin_slots` for every kart-type character in a profile JSON.

For each character with `kart_slots` declared, walks its `.ctr` mesh,
collects every distinct CLUT coord that isn't already a kart slot, and
emits the difference as `extra_<vram_x>_<vram_y>` skin slots with no
`clut_menu` (since menu-VRAM positions for skins aren't recoverable
from the mesh alone).

Usage (from repo root with the venv active):

    python tools/populate_skin_slots.py \\
        --profile config/profiles/saphi.json \\
        --iso     /path/to/saphi/build/ctr-u

By default the profile is rewritten in place; pass `--out` to write
elsewhere.
"""

import argparse
import json
import sys
from pathlib import Path

from paintjob_designer.ctr.animation import AnimationDecoder
from paintjob_designer.ctr.reader import CtrModelReader
from paintjob_designer.profile.reader import ProfileReader
from paintjob_designer.profile.skin_slot_deriver import SkinSlotDeriver
from paintjob_designer.schema_keys import (
    CommonKey,
    ProfileKey,
)


def _slot_to_json(slot) -> dict:
    out = {
        CommonKey.NAME: slot.name,
        ProfileKey.CLUT_RACE: {
            ProfileKey.CLUT_X: slot.clut_race.x,
            ProfileKey.CLUT_Y: slot.clut_race.y,
        },
    }

    if slot.clut_menu is not None:
        out[ProfileKey.CLUT_MENU] = {
            ProfileKey.CLUT_X: slot.clut_menu.x,
            ProfileKey.CLUT_Y: slot.clut_menu.y,
        }

    if slot.non_portable:
        out[ProfileKey.NON_PORTABLE] = True

    return out


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

    profile_reader = ProfileReader()
    ctr_reader = CtrModelReader(AnimationDecoder())
    deriver = SkinSlotDeriver()

    raw = json.loads(args.profile.read_text(encoding="utf-8"))
    profile = profile_reader.read(json.dumps(raw))

    raw_characters = raw.get(ProfileKey.CHARACTERS, [])
    summary: list[tuple[str, int, int]] = []  # (id, before, after)

    for raw_char, char in zip(raw_characters, profile.characters):
        if not char.kart_slots:
            # Hovercraft / non-kart entries already enumerate everything
            # under skin_slots in the source profile; don't touch them.
            continue

        ctr_path = args.iso / char.mesh_source
        if not ctr_path.is_file():
            print(f"  skip {char.id}: missing mesh {ctr_path}", file=sys.stderr)
            continue

        model = ctr_reader.read(ctr_path.read_bytes())
        mesh = model.meshes[0]

        derived = deriver.derive(mesh, char.kart_slots)
        before = len(raw_char.get(ProfileKey.SKIN_SLOTS, []))
        raw_char[ProfileKey.SKIN_SLOTS] = [_slot_to_json(s) for s in derived]
        summary.append((char.id, before, len(derived)))

    out_path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {out_path}:")
    for char_id, before, after in summary:
        marker = "" if before == after else f" (was {before})"
        print(f"  {char_id}: {after} skin slots{marker}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
