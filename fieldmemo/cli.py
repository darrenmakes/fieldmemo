"""fieldmemo command line.

    fieldmemo MEMO_FOLDER [--gpx track.gpx] [--out journal/]
"""
import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__
from .audio import find_memos, location_from_tags, probe
from .extract import OllamaError, ask_model, clean
from .gpx import position_at, read_gpx
from .render import write_csv, write_geojson, write_markdown
from .timing import recorded_at
from .transcribe import DEFAULT_GLOSSARY, read_glossary


def _local_zone():
    try:
        import tzlocal  # optional
        return ZoneInfo(str(tzlocal.get_localzone()))
    except Exception:
        return ZoneInfo("Europe/London")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fieldmemo", description=(
        "Turn the voice memos you recorded on a walk into a geotagged field journal. "
        "Runs fully offline with Whisper and an open-weight model via Ollama."))
    ap.add_argument("memos", type=Path, help="folder of voice memos (m4a, mp3, wav, ogg, ...)")
    ap.add_argument("--gpx", type=Path, help="GPX track of the same walk, for positions")
    ap.add_argument("--out", type=Path, help="output folder (default: MEMOS/../journal)")
    ap.add_argument("--tz", default=None, help="time zone of times in file names (default: this machine's, else Europe/London)")
    ap.add_argument("--clock-offset", type=float, default=0,
                    help="seconds to add to memo times if the recorder clock was off")
    ap.add_argument("--whisper", default="small.en", help="Whisper model size (tiny.en, base.en, small.en, ...)")
    ap.add_argument("--glossary", default=str(DEFAULT_GLOSSARY),
                    help="word list to steer Whisper ('' to disable)")
    ap.add_argument("--model", default="gemma4:e2b", help="Ollama model for the notes step")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434", help="Ollama URL")
    ap.add_argument("--retranscribe", action="store_true", help="ignore cached transcripts")
    ap.add_argument("--version", action="version", version=f"fieldmemo {__version__}")
    a = ap.parse_args(argv)

    tz = ZoneInfo(a.tz) if a.tz else _local_zone()
    files = find_memos(a.memos)
    if not files:
        sys.exit(f"No audio files found in {a.memos}")
    out = a.out or a.memos.parent / "journal"
    out.mkdir(parents=True, exist_ok=True)
    fixes = read_gpx(a.gpx) if a.gpx else []

    cache_path = out / "transcripts.json"
    cache = {} if a.retranscribe or not cache_path.exists() else json.loads(cache_path.read_text())
    transcriber = None

    memos = []
    for f in files:
        info = probe(f)
        when, source = recorded_at(f, info["tags"], tz)
        when += timedelta(seconds=a.clock_offset)
        key = f"{f.name}|{f.stat().st_size}|{a.whisper}|{a.glossary}"
        if key not in cache:
            if transcriber is None:
                from .transcribe import Transcriber
                print(f"Loading Whisper {a.whisper} ...", file=sys.stderr)
                transcriber = Transcriber(a.whisper, a.glossary or None)
            t0 = time.time()
            cache[key] = transcriber.transcribe(f)
            print(f"  heard {f.name} in {time.time()-t0:.1f}s: {cache[key]['text'] or '(no speech)'}", file=sys.stderr)
        tr = cache[key]

        lat = lon = None
        where = "no track given"
        tagged = location_from_tags(info["tags"])
        if fixes:
            # middle of the memo is a better guess than the start for long ones
            lat, lon, where = position_at(fixes, when + timedelta(seconds=info["duration"] / 2))
        if lat is None and tagged:
            (lat, lon), where = tagged, "recorder's own location tag"
        memos.append({"file": f.name, "time": when, "time_source": source,
                      "duration": info["duration"], "transcript": tr,
                      "lat": lat, "lon": lon, "where": where})
    cache_path.write_text(json.dumps(cache, indent=1))
    if fixes:
        off = [m for m in memos if "track" in m["where"] and ("before" in m["where"] or "after" in m["where"])]
        if off:
            print(f"Warning: {len(off)} memo(s) fall outside the GPX track's time span. If that's wrong, "
                  f"the recorder clock or time zone is off: try --tz (now {tz.key}) or --clock-offset.",
                  file=sys.stderr)
    memos.sort(key=lambda m: m["time"])

    glossary = read_glossary(a.glossary) if a.glossary else []
    for m in memos:
        if not m["transcript"]["text"]:
            m["notes"] = {"title": "", "items": [], "rejected": []}
            continue
        t0 = time.time()
        try:
            raw = ask_model(m["transcript"]["text"], a.model, a.ollama)
        except OllamaError as e:
            sys.exit(str(e))
        m["notes"] = clean(raw, m["transcript"]["text"], glossary)
        m["notes"]["raw"] = raw
        print(f"  noted {m['file']} in {time.time()-t0:.1f}s: "
              + "; ".join(f"{i['kind']}:{i['subject']}" for i in m["notes"]["items"]), file=sys.stderr)

    meta = {"gpx": a.gpx.name if a.gpx else None, "whisper": a.whisper, "model": a.model}
    write_markdown(memos, meta, out / "journal.md", tz)
    write_geojson(memos, fixes, out / "walk.geojson", tz)
    write_csv(memos, out / "notes.csv", tz)
    (out / "raw-model-output.json").write_text(json.dumps(
        [{"file": m["file"], "raw": m["notes"].get("raw"), "rejected": m["notes"]["rejected"]} for m in memos],
        indent=1))
    print(f"Wrote {out/'journal.md'}, {out/'walk.geojson'}, {out/'notes.csv'}", file=sys.stderr)


if __name__ == "__main__":
    main()
