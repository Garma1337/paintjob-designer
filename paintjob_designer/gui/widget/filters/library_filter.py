# coding: utf-8


class LibraryFilter:
    """Decides whether a sidebar row matches a free-text search query.

    Case-insensitive substring match against the concatenation of every
    searchable field for that row (primary label + secondary label,
    typically). Empty / whitespace-only query matches everything so the
    list reverts to "no filter" without a separate clear path.

    Pure logic, no Qt — sits under `gui/widget/filters/` so any future
    list-style widget can plug it in without coupling to a specific
    sidebar implementation.
    """

    def matches(self, query: str, *fields: str) -> bool:
        q = (query or "").strip().casefold()
        if not q:
            return True

        haystack = " ".join(f or "" for f in fields).casefold()
        return q in haystack
