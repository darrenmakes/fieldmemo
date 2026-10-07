"""Local speech-to-text with faster-whisper (OpenAI Whisper weights, MIT)."""
from pathlib import Path

from .audio import load_audio

DEFAULT_GLOSSARY = Path(__file__).with_name("glossary_uk.txt")


def read_glossary(path) -> list[str]:
    if not path:
        return []
    words = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words


class Transcriber:
    def __init__(self, model_size="small.en", glossary=DEFAULT_GLOSSARY, threads=0):
        from faster_whisper import WhisperModel  # imported late: slow import
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8",
                                  cpu_threads=threads)
        words = read_glossary(glossary)
        # Whisper treats initial_prompt as "text that came before". Listing the
        # words we expect nudges it from "buzzers" to "buzzards" and from
        # "style" to "stile". It only holds ~224 tokens, so keep the list short.
        self.prompt = ("Voice notes from a countryside walk: " + ", ".join(words) + ".") if words else None

    def transcribe(self, path) -> dict:
        audio = load_audio(path)
        # vad_filter matters: on a wind-only pocket recording Whisper without
        # VAD "heard" the word "You". With VAD it correctly returns nothing.
        segments, info = self.model.transcribe(audio, vad_filter=True, beam_size=5,
                                               initial_prompt=self.prompt)
        segments = list(segments)
        text = " ".join(s.text.strip() for s in segments).strip()
        return {
            "text": text,
            "avg_logprob": (sum(s.avg_logprob for s in segments) / len(segments)) if segments else None,
            "speech_seconds": round(sum(s.end - s.start for s in segments), 1),
        }
