# coding: utf-8


class Slugifier:
    """Produces filesystem-safe slugs from free-form text."""

    def slugify(self, text: str) -> str:
        """Return `text` with whitespace collapsed to `_` and every non-alphanumeric / non-`-_` character stripped."""
        out: list[str] = []
        for ch in text.strip().lower():
            if ch.isalnum() or ch in "-_":
                out.append(ch)
            elif ch == " ":
                out.append("_")

        return "".join(out)
