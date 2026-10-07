from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fieldmemo.audio import location_from_tags
from fieldmemo.extract import clean, count_supported, grounded
from fieldmemo.gpx import Fix, position_at
from fieldmemo.timing import from_filename, from_tags

LONDON = ZoneInfo("Europe/London")


def test_filename_times_are_local():
    dt = from_filename("Recording_20261008_101940.m4a", LONDON)
    assert dt.astimezone(timezone.utc).hour == 9  # BST is UTC+1 in October
    assert from_filename("2026-10-08 10.19.40.mp3", LONDON) == dt
    assert from_filename("New Recording 4.m4a", LONDON) is None


def test_metadata_times_are_utc():
    dt = from_tags({"creation_time": "2026-10-08T09:58:30.000000Z"})
    assert dt.astimezone(LONDON).strftime("%H:%M") == "10:58"


def test_iso6709_location():
    assert location_from_tags({"com.apple.quicktime.location.iso6709": "+53.3712-001.8165+260.000/"}) == (53.3712, -1.8165)
    assert location_from_tags({}) is None


def _track():
    t0 = datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc)
    return [Fix(t0 + timedelta(seconds=60 * i), 53.0 + 0.001 * i, -1.0, None) for i in range(10)]


def test_interpolation_and_refusal():
    fixes = _track()
    lat, lon, note = position_at(fixes, fixes[2].t + timedelta(seconds=30))
    assert abs(lat - 53.0025) < 1e-9 and note == "track"
    assert position_at(fixes, fixes[0].t - timedelta(minutes=5))[0] is None
    assert "after the track ends" in position_at(fixes, fixes[-1].t + timedelta(minutes=20))[2]


def test_grounding_rejects_invented_subjects():
    memo = "Okay, starting from the car park. The path by the first gate is basically a pond."
    assert grounded({"subject": "path"}, memo)[0]
    ok, why = grounded({"subject": "fly agaric"}, memo)
    assert not ok and "agaric" in why


def test_grounding_allows_glossary_corrections_only():
    memo = "Note to self the style after the second field has a broken step."
    assert grounded({"subject": "stile"}, memo, ["stile"]) == (True, 'heard "style", read as "stile"')
    assert not grounded({"subject": "stile"}, memo, [])[0]


def test_plurals_and_counts():
    memo = "Two buzzards circling. Must be a dozen red caps."
    assert grounded({"subject": "buzzard"}, memo)[0]
    assert count_supported(2, memo) and count_supported(12, memo)
    assert not count_supported(3, memo)


def test_clean_merges_duplicates_and_strips_bad_counts():
    memo = "Two buzzards circling over the ridge. Maybe three."
    out = clean({"title": "t", "items": [
        {"kind": "seen", "subject": "buzzard", "count": 2, "details": "circling"},
        {"kind": "seen", "subject": "buzzards", "count": None, "details": "maybe three"},
        {"kind": "seen", "subject": "kestrel", "count": 1, "details": "hovering"},
    ]}, memo)
    assert len(out["items"]) == 1 and out["items"][0]["count"] == 2
    assert out["rejected"][0]["subject"] == "kestrel"
