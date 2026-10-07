# Sample walk (synthetic)

Nothing here is a real recording or a real route.

- `walk-2026-10-08/memos/`: seven short voice memos spoken by [Piper](https://github.com/rhasspy/piper)
  TTS with the `en_GB-northern_english_male-medium` voice (trained on
  [OpenSLR 83](http://www.openslr.org/83/), CC BY-SA 4.0, so these clips are shared under CC BY-SA 4.0).
  Three have brown noise mixed in as fake wind; one is wind only, like a recording made by accident in a pocket.
  Six are named like Android recorder files (`Recording_YYYYMMDD_HHMMSS.m4a`, local time); one is named
  like an iPhone export (`New Recording 4.m4a`) with its time only in the file's UTC `creation_time` tag.
- `walk-2026-10-08/track.gpx`: a made-up loop sampled every 15 s. It is not a path. Don't navigate with it.
- `walk-2026-10-08/journal/`: what `fieldmemo` produced from the two, unedited.

Regenerate with `python scripts/make_samples.py --voice path/to/en_GB-northern_english_male-medium.onnx`.
