# Build log

What was tried, what broke and what changed, in order. Built with an AI coding agent on a Linux
machine with 8 CPU cores, no GPU and about 3 to 7 GB of free RAM. Times are UK (BST).

## 7 October 2026

**Getting a model.** `ollama pull gemma3:1b` failed on this network: `redirect target not allowed:
...r2.cloudflarestorage.com resolves to non-public 198.18.0.1`. That's the network's proxy, not Ollama.
Downloading the GGUF from Hugging Face and importing it with a one-line Modelfile
(`FROM ./gemma-3-1b-it-Q4_K_M.gguf`, then `ollama create`) worked first time. Same for Gemma 4 E2B
(unsloth `Q4_K_M`, 3.1 GB).

**Whisper wouldn't open an m4a.** faster-whisper 1.2.1 with PyAV 19.0.1:
`TypeError: open() got an unexpected keyword argument 'metadata_errors'`. Rather than pin PyAV,
fieldmemo now decodes with the `ffmpeg` binary into a 16 kHz float array and hands Whisper the
array. Side benefit: anything ffmpeg can read works.

**Sample data.** Seven memos spoken by Piper TTS (British voice), three with brown noise mixed in as
wind, one that is only wind (a pocket recording). Synthetic, and flattering: a TTS voice is much
clearer than a person talking on a hill.

**Whisper results** (`base.en`, no help):

| said | heard |
|---|---|
| buzzards | buzzers |
| fly agaric under | fly are gariconder |
| stile | style |
| council rights of way team | cancel rights of Wei Team |
| green woodpecker | green whoop cat |
| a tub in | a topping |
| (wind only) | "You" |

- The "You" on the wind-only memo is Whisper inventing speech in noise. Turning on the voice-activity
  filter (`vad_filter=True`) made it return nothing. On by default now.
- Passing a 55-word countryside glossary as Whisper's `initial_prompt` fixed buzzards, fly agaric,
  council rights of way and green woodpecker on `base.en`. `small.en` with the glossary also got
  "tub" right, so it's the default. "Stile" came out right in one run and as "style" in another after
  the prompt's wording changed slightly, which is how fragile prompt steering is.
- `small.en` took 1.4 to 1.8 s per memo (3 to 9 s clips) on CPU.

**Notes step, first try with Gemma 3 1B.** It labelled everything "seen", including a woodpecker the
memo says was heard and not seen; split "two buzzards, maybe three" into buzzards plus "trees x3";
called the car-park memo a "stile" (a word from my own example list in the prompt); and in another run
described fly agaric as "mostly white with a dark brown center", which nobody said.

**Gemma 4 E2B** on the same memos: right kinds, heard vs seen right, path flooding as a hazard and the
blackberries as a to-do. 4 to 8 s per memo after loading. It needs about 3 GB of RAM, so it's the
default and Gemma 3 1B is the low-memory option.

**Grounding check.** Every item's subject must be made of words that are in the transcript
(with crude plural folding: buzzards/buzzard, birches/birch). Counts must appear in the memo
("two", "a dozen", "12"). Items that fail are struck out in the journal, not silently dropped.
On the next Gemma 3 1B run it caught a "fly agaric ... a small, pale mushroom growing on a stone" invented in the car-park memo, which mentions no fungi at all.

**The check then rejected a correct answer.** Gemma 4 read Whisper's "style" as "stile", which was
right, and the check threw it out because "stile" wasn't in the transcript. Fix: a subject word
that isn't in the transcript is allowed only if it's in the glossary *and* a transcript word is within
two letters of it. It shows up as `corrected: heard "style", read as "stile"`.

**Prompt change.** Gemma 4 sometimes returned the broken stile as a hazard only, with no to-do.
Added: if the memo says "note to self", "report it", "come back" and so on, add a separate todo. After
that it returns the to-do. In the latest run it returns the to-do but not the hazard. Not fixed yet.

**Time zones.** File names from Android recorders are local time; iPhone exports keep the time in a
UTC `creation_time` tag; GPX is UTC. Running the sample with `--tz UTC` (wrong) moves the iPhone memo
to the top of the timeline and leaves the last two memos with no position ("27 min after the track
ends", "53 min after the track ends"). fieldmemo refuses to pin a memo outside the track and now prints
a warning pointing at `--tz` and `--clock-offset`.

**Whole run:** 7 memos, about 48 s end to end on CPU, including loading both models.
