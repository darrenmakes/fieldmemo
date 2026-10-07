"""Work out when each memo was recorded.

Order of preference:
1. a date-time in the file name (most Android recorders; treated as local time),
2. the container's creation_time tag (iPhone exports; this one is UTC),
3. the file's modification time (last resort; often wrong after copying).

Every result records where it came from, so the journal can say how much to
trust the position it puts on the map.
"""
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_PATTERNS = [
    # 20261008_101940, 20261008-101940, 20261008101940
    re.compile(r"(?P<y>20\d\d)(?P<mo>\d\d)(?P<d>\d\d)[_\-T ]?(?P<h>\d\d)(?P<mi>\d\d)(?P<s>\d\d)"),
    # 2026-10-08 10.19.40, 2026-10-08_10-19-40, 2026-10-08T10:19:40
    re.compile(r"(?P<y>20\d\d)-(?P<mo>\d\d)-(?P<d>\d\d)[ _T](?P<h>\d\d)[.:\-](?P<mi>\d\d)(?:[.:\-](?P<s>\d\d))?"),
]


def from_filename(name: str, tz: ZoneInfo):
    for pat in _PATTERNS:
        m = pat.search(name)
        if m:
            g = m.groupdict()
            try:
                local = datetime(int(g["y"]), int(g["mo"]), int(g["d"]),
                                 int(g["h"]), int(g["mi"]), int(g["s"] or 0), tzinfo=tz)
            except ValueError:
                continue
            return local
    return None


def from_tags(tags: dict):
    val = tags.get("creation_time") or tags.get("date")
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:  # spec says UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def recorded_at(path, tags: dict, tz: ZoneInfo):
    """Return (aware datetime, source) for when recording started."""
    dt = from_filename(path.name, tz)
    if dt:
        return dt, "filename"
    dt = from_tags(tags)
    if dt:
        return dt, "metadata"
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc), "file-mtime"
