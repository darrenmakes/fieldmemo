"""Minimal GPX reader and time-based position lookup (standard library only)."""
import bisect
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Fix:
    t: datetime
    lat: float
    lon: float
    ele: float | None


def read_gpx(path) -> list[Fix]:
    root = ET.parse(path).getroot()
    fixes = []
    for el in root.iter():
        if not el.tag.endswith("trkpt"):
            continue
        t = ele = None
        for child in el:
            if child.tag.endswith("time") and child.text:
                t = datetime.fromisoformat(child.text.strip().replace("Z", "+00:00"))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
            elif child.tag.endswith("ele") and child.text:
                ele = float(child.text)
        if t is not None:
            fixes.append(Fix(t, float(el.get("lat")), float(el.get("lon")), ele))
    fixes.sort(key=lambda f: f.t)
    return fixes


def position_at(fixes: list[Fix], when: datetime, max_gap_s: float = 300):
    """Linear interpolation between the two fixes around `when`.

    Returns (lat, lon, note). We refuse to guess (lat/lon None) if `when` is
    outside the track or the nearest fixes are more than `max_gap_s` apart,
    because a confidently wrong pin is worse than no pin.
    """
    if not fixes:
        return None, None, "no track"
    times = [f.t for f in fixes]
    i = bisect.bisect_left(times, when)
    if i == 0 and when < times[0]:
        mins = (times[0] - when).total_seconds() / 60
        return None, None, f"{mins:.0f} min before the track starts"
    if i == len(fixes):
        mins = (when - times[-1]).total_seconds() / 60
        return None, None, f"{mins:.0f} min after the track ends"
    a, b = fixes[max(i - 1, 0)], fixes[i]
    span = (b.t - a.t).total_seconds()
    if span > max_gap_s:
        return None, None, f"GPS gap of {span/60:.0f} min around this time"
    frac = 0.0 if span == 0 else (when - a.t).total_seconds() / span
    return a.lat + (b.lat - a.lat) * frac, a.lon + (b.lon - a.lon) * frac, "track"
