# fieldmemo

**Talk on the trail, read it at home.**

Keep your phone in your pocket on a walk. When you see something, press record and say it:
"two buzzards over the ridge", "stile after the second field is broken", "come back for the
blackberries next September". Afterwards, point `fieldmemo` at the folder of voice memos (and the
GPX track from your watch or phone, if you have one) and it writes:

- `journal.md`: a readable field journal. What you saw, what you heard, path problems with map links, a to-do list, and a timeline with every memo's transcript.
- `walk.geojson`: your track plus a pin per memo. Opens in QGIS, uMap, geojson.io or any GIS tool.
- `notes.csv`: one row per sighting, hazard or to-do, ready for a spreadsheet.

Everything runs on your own machine: speech-to-text with [Whisper](https://github.com/openai/whisper)
(through [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) and note-taking with
Google's open-weight [Gemma](https://ai.google.dev/gemma) served by [Ollama](https://ollama.com).
No account, no API key, no upload. Your voice and your location never leave the laptop.

## Example

From the synthetic sample walk in [`samples/`](samples/README.md) (TTS voice, fake wind, made-up track):

```
### 10:41 · Field Notes and Task

53.37750, -1.78405 (track) · time from filename · `Recording_20261008_104105.m4a`

> Note to self the style after the second field has a broken step. Report it to the council rights of way team when I get home.

- **todo**: stile: note to self the style after the second field has a broken step; report it to the council rights of way team when i get home _(corrected: heard "style", read as "stile")_
```

Full output: [`samples/walk-2026-10-08/journal/journal.md`](samples/walk-2026-10-08/journal/journal.md).

## How it works

1. **When was each memo recorded?** From the file name (`Recording_20261008_101940.m4a`, `2026-10-08 10.19.40.mp3`, read as local time, set with `--tz`), else the file's `creation_time` tag (UTC; iPhone exports), else the file's modified time. The journal says which one it used.
2. **Where was I?** The memo's mid-point time is looked up on the GPX track and interpolated between fixes. If the memo falls outside the track, or in a GPS gap longer than five minutes, it gets **no** pin rather than a wrong one. If there's no track, an ISO 6709 location tag in the file is used when present.
3. **What did I say?** Whisper (`small.en` by default) with its voice-activity filter on, so a wind-only pocket recording comes back empty instead of as a made-up word. A glossary of countryside words ([`glossary_uk.txt`](fieldmemo/glossary_uk.txt), edit it for your area) goes in as Whisper's prompt so "buzzers" becomes "buzzards".
4. **What does it mean?** Gemma gets the transcript and must answer in a fixed JSON schema (`seen`, `heard`, `hazard`, `todo`, `note`, each with subject, count and details).
5. **Did I actually say that?** Every item is checked against the transcript. If the subject isn't something you said, it's struck out and listed as dropped. A count must appear in the memo ("two", "a dozen", "12"). The one exception: if the model fixes a Whisper mishearing to a glossary word within two letters ("style" to "stile"), it's kept and labelled as a correction.

Transcripts are cached in `journal/transcripts.json`, so you can rerun the notes step with another model without waiting for Whisper again.

## Install

You need Python 3.10+, `ffmpeg` on your PATH and [Ollama](https://ollama.com/download).

```bash
git clone https://github.com/darrenmakes/fieldmemo.git && cd fieldmemo
python -m venv .venv && . .venv/bin/activate
pip install -e .

ollama pull gemma4:e2b      # default model
# low on RAM? gemma3:1b works too, but see "Choosing a model"
```

The Whisper model (~480 MB for `small.en`) downloads from Hugging Face on first run; after that everything works offline.

## Run

```bash
fieldmemo path/to/memos --gpx path/to/track.gpx
# try it on the bundled sample:
fieldmemo samples/walk-2026-10-08/memos --gpx samples/walk-2026-10-08/track.gpx --tz Europe/London --out /tmp/journal
```

Useful options:

| option | default | what it does |
|---|---|---|
| `--tz` | this machine's zone | time zone of the times in file names |
| `--clock-offset` | `0` | seconds to add if the recorder's clock was wrong |
| `--whisper` | `small.en` | Whisper size; `base.en` is faster, slightly worse |
| `--glossary` | bundled UK list | word list to steer Whisper; `''` to turn off |
| `--model` | `gemma4:e2b` | any Ollama model |
| `--ollama` | `http://127.0.0.1:11434` | Ollama URL |
| `--retranscribe` | off | ignore cached transcripts |

If memos land outside the track's time span, fieldmemo warns you: that's nearly always a time-zone or clock problem.

## Choosing a model

Measured on an 8-core CPU with no GPU, on the 7 sample memos:

| | Whisper `small.en` | notes step per memo | notes quality on the sample |
|---|---|---|---|
| Gemma 4 E2B (Q4_K_M) | 1.4 to 1.8 s per memo | 4 to 8 s once loaded | correct kinds, heard vs seen right, fixed "style" to "stile" |
| Gemma 3 1B (Q4_K_M) | same | 3 to 9 s | everything marked "seen", invented a fly agaric in the car-park memo (caught by the grounding check), counted trees |

Gemma 3 1B fits in about 1.2 GB of RAM; Gemma 4 E2B needs roughly 3 GB. Both are local and free; pick by what your machine can hold.

If `ollama pull` is blocked on your network, import a GGUF instead, which is what I did while building this:

```bash
curl -LO https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf
echo 'FROM ./gemma-4-E2B-it-Q4_K_M.gguf' > Modelfile
ollama create gemma4-e2b-local -f Modelfile
fieldmemo ... --model gemma4-e2b-local
```

## Recording tips

- Any recorder works. If yours names files with the date and time, you're set. iPhone Voice Memos keeps the time in the file's metadata instead, which fieldmemo reads.
- Start a GPX recording in whatever app you already use (OsmAnd, Strava, a watch) and export it afterwards.
- Phone and watch clocks are usually right. Cheap dictaphones often aren't: say the time at the start of a memo and use `--clock-offset`.
- Shield the mic from the wind with your hand. Whisper copes with some wind, but not a gale.

## Limits

- Only tested on the synthetic sample walk so far: a TTS voice with fake wind. Real wind on a real phone mic will be harder.
- The grounding check catches invented subjects and counts. It doesn't catch a wrong *kind* (calling something "seen" when you only heard it).
- English only for now (`*.en` Whisper models and an English prompt).
- Not a species identifier. It writes down what *you* said you saw.

## Tests

```bash
pip install -e '.[dev]' && pytest -q
```

## Credits and licences

- Code: MIT, see [LICENSE](LICENSE).
- [Whisper](https://github.com/openai/whisper) weights (MIT) via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT).
- [Gemma 4](https://ai.google.dev/gemma) (Apache 2.0); Gemma 3 is under the Gemma Terms of Use. GGUF quantisations by [unsloth](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF) and [ggml-org](https://huggingface.co/ggml-org/gemma-3-1b-it-GGUF).
- [Ollama](https://github.com/ollama/ollama) (MIT).
- Sample audio: [Piper](https://github.com/rhasspy/piper) TTS, voice trained on OpenSLR 83 (CC BY-SA 4.0).
- Built during DEV's Hacktoberfest 2026 Open-Source AI Challenge (Week 1, "Touch Grass", 5 to 11 October 2026), with help from an AI coding agent. Any commits after the 11 October deadline will be listed here.
