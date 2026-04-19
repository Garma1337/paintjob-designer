# coding: utf-8


class Slugifier:
    """Produces filesystem-safe slugs from free-form text.

    Injected into callers that want to turn human-written labels
    (paintjob names, character IDs, etc.) into filenames. Stateless, but
    a class rather than a module-level function so the DI container has a
    single seam to swap in a different policy (e.g. unicode-aware
    normalisation) in the future without touching every call site.
    """

    def slugify(self, text: str) -> str:
        """Return `text` with whitespace collapsed to `_` and every
        non-alphanumeric / non-`-_` character stripped.

        Empty input returns an empty string so callers can chain a
        fallback (`slugifier.slugify(name) or fallback`).
        """
        out: list[str] = []
        for ch in text.strip().lower():
            if ch.isalnum() or ch in "-_":
                out.append(ch)
            elif ch == " ":
                out.append("_")

        return "".join(out)
