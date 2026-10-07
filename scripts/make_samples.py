"""Generate the synthetic demo walk in samples/.

Nothing in samples/ is a real recording. The voice memos are spoken by Piper
TTS (en_GB northern_english_male, trained on OpenSLR 83, CC BY-SA 4.0) and
some get brown noise mixed in to imitate wind. The GPX track is a made-up loop,
not a real route: do not navigate with it.

Needs: piper-tts (pip), ffmpeg, and the Piper voice files. Usage:
    python scripts/make_samples.py --voice path/to/en_GB-northern_english_male-medium.onnx
"""
import argparse
import math
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "samples" / "walk-2026-10-08"

# (local BST time, filename style, wind level 0..1, text)
MEMOS = [
    ("10:02:11", "name", 0.0,
     "Okay, starting from the car park. Ground is soaked from last night, "
     "the path by the first gate is basically a pond."),
    ("10:19:40", "name", 0.25,
     "Two buzzards circling over the ridge. Maybe three, hard to tell, "
     "they keep dropping behind the trees."),
    ("10:41:05", "name", 0.0,
     "Note to self, the stile after the second field has a broken step. "
     "Report it to the council rights of way team when I get home."),
    ("10:58:30", "metadata", 0.0,
     "Loads of fly agaric under the birches here. Must be a dozen red caps. "
     "Do not let the dog near them."),
    ("11:12:02", "name", 0.45,
     "Heard a green woodpecker, that laughing call. Didn't see it though."),
    ("11:20:15", "name", 0.9, None),  # pocket recording: wind only, nobody talking
    ("11:37:48", "name", 0.0,
     "Blackberries still on the hedge by the lane, but most are mushy now. "
     "Come back with a tub in early September next year."),
]

DAY = "2026-10-08"
BST = timezone(timedelta(hours=1))


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_audio(text, wind, dest, voice, creation_utc=None):
    with tempfile.TemporaryDirectory() as tmp:
        speech = Path(tmp) / "speech.wav"
        if text:
            subprocess.run(["python", "-m", "piper", "-m", voice, "-f", str(speech)],
                           input=text.encode(), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                 "-t", "9", str(speech)])
        cmd = ["ffmpeg", "-y", "-i", str(speech)]
        if wind > 0:
            # brown noise with a slow tremolo is a passable imitation of wind on a phone mic
            cmd += ["-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude={wind}:r=22050",
                    "-filter_complex",
                    "[1:a]tremolo=f=0.7:d=0.6,lowpass=f=900[w];[0:a][w]amix=inputs=2:duration=first:normalize=0[a]",
                    "-map", "[a]"]
        cmd += ["-ac", "1", "-c:a", "aac", "-b:a", "48k"]
        if creation_utc:
            cmd += ["-metadata", f"creation_time={creation_utc}"]
        cmd.append(str(dest))
        run(cmd)


def make_gpx(dest):
    """A synthetic ~6 km loop sampled every 15 s from 10:00 to 11:45 BST."""
    start = datetime.fromisoformat(f"{DAY}T10:00:00").replace(tzinfo=BST)
    end = start + timedelta(minutes=105)
    lat0, lon0 = 53.3712, -1.8165
    pts = []
    t = start
    n = int((end - start).total_seconds() // 15)
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        lat = lat0 + 0.0105 * math.sin(a) + 0.0012 * math.sin(5 * a)
        lon = lon0 + 0.0175 * (1 - math.cos(a)) + 0.0015 * math.sin(3 * a)
        ele = 260 + 180 * math.sin(a / 2) ** 2
        pts.append((lat, lon, ele, t.astimezone(timezone.utc)))
        t += timedelta(seconds=15)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<gpx version="1.1" creator="fieldmemo make_samples.py (synthetic)" '
             'xmlns="http://www.topografix.com/GPX/1/1">',
             '<trk><name>Synthetic demo loop (not a real route)</name><trkseg>']
    for lat, lon, ele, ts in pts:
        lines.append(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{ele:.1f}</ele>'
                     f'<time>{ts.strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>')
    lines += ["</trkseg></trk></gpx>", ""]
    dest.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True)
    args = ap.parse_args()
    memos = OUT / "memos"
    memos.mkdir(parents=True, exist_ok=True)
    for i, (hms, style, wind, text) in enumerate(MEMOS, 1):
        local = datetime.fromisoformat(f"{DAY}T{hms}").replace(tzinfo=BST)
        if style == "name":
            dest = memos / f"Recording_{local:%Y%m%d_%H%M%S}.m4a"
            make_audio(text, wind, dest, args.voice)
        else:
            # Like an exported iPhone memo: generic name, time only in metadata (UTC).
            dest = memos / f"New Recording {i}.m4a"
            utc = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
            make_audio(text, wind, dest, args.voice, creation_utc=utc)
        print(dest.name)
    make_gpx(OUT / "track.gpx")
    print("track.gpx")


if __name__ == "__main__":
    main()
