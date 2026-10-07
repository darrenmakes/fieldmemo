"""Turn a transcript into structured field notes with a local open-weight model
served by Ollama, then check every item against the transcript."""
import json
import re
import urllib.error
import urllib.request

KINDS = ["seen", "heard", "hazard", "todo", "note"]

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": KINDS},
                "subject": {"type": "string"},
                "count": {"type": ["integer", "null"]},
                "details": {"type": "string"},
            },
            "required": ["kind", "subject", "count", "details"],
        }},
    },
    "required": ["title", "items"],
}

SYSTEM = """You turn a walker's spoken voice memo into structured field notes.
Rules:
- Only use facts that are in the memo. Never invent species, numbers, colours or places.
- kind: "seen" = wildlife, plant or fungus they saw; "heard" = something heard but not seen; "hazard" = a path problem or danger (flooding, broken stile, loose cattle); "todo" = something to do later; "note" = anything else.
- subject: the species or thing in plain lowercase English, singular (e.g. "buzzard", "fly agaric", "stile").
- count: a number only if the memo gives one ("a dozen" = 12, "a pair" = 2). For a range like "two, maybe three" use the lower number and put the range in details. Otherwise null.
- details: a few words copied or closely paraphrased from the memo.
- One memo can hold several items. Do not split one sighting into two items.
- If the memo says "note to self", "remember to", "report it", "come back" or similar, add a separate "todo" item for that action, as well as any hazard or sighting.
- The memo is a speech-to-text transcript and may contain misheard words. If a word is clearly a mishearing of a countryside term (e.g. "style" for "stile"), use the correct term in subject.
- title: 3 to 6 words."""


class OllamaError(RuntimeError):
    pass


def _post(url, body, timeout):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ask_model(transcript, model, url="http://127.0.0.1:11434", timeout=600):
    body = {
        "model": model, "stream": False, "format": SCHEMA, "think": False,
        "options": {"temperature": 0},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": transcript}],
    }
    try:
        resp = _post(f"{url}/api/chat", body, timeout)
    except urllib.error.HTTPError as e:
        if e.code == 400 and "think" in e.read().decode(errors="ignore").lower():
            body.pop("think")  # model without a thinking switch
            resp = _post(f"{url}/api/chat", body, timeout)
        else:
            raise OllamaError(f"Ollama returned HTTP {e.code} for model {model!r}") from e
    except urllib.error.URLError as e:
        raise OllamaError(f"Can't reach Ollama at {url} ({e.reason}). Is `ollama serve` running?") from e
    return json.loads(resp["message"]["content"])


# ---- grounding: never let the model put something in the journal that the
# walker didn't say. Small models do invent things (in testing, Gemma 3 1B
# described fly agaric as "mostly white with a dark brown center").

_NUMBER_WORDS = {"one": 1, "a": 1, "an": 1, "two": 2, "pair": 2, "couple": 2, "three": 3, "four": 4,
                 "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                 "eleven": 11, "twelve": 12, "dozen": 12, "twenty": 20, "fifty": 50,
                 "hundred": 100}
_STOP = {"the", "a", "an", "of", "on", "in", "by", "at", "to", "and", "some", "loads", "lots"}


def _variants(word):
    """Crude singular/plural folding: 'buzzards'->'buzzard', 'birches'->'birch',
    'blackberries'->'blackberry', "blackberry's"->'blackberry', 'stiles'->'stile'."""
    w = word.lower().replace("\u2019", "'")
    out = {w}
    if w.endswith("'s"):
        w = w[:-2]
        out.add(w)
    if w.endswith("ies") and len(w) > 4:
        out.add(w[:-3] + "y")
    if w.endswith("es") and len(w) > 4:
        out.add(w[:-2])
    if w.endswith("s") and len(w) > 3:
        out.add(w[:-1])
    return out


def _stem(word):
    return min(_variants(word), key=len)


def _words(text):
    return [t for t in re.findall(r"[a-zA-Z'\u2019]+", text) if t.lower() not in _STOP]


def _edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def grounded(item, transcript, glossary=()) -> tuple[bool, str]:
    """Is every word of the subject something the walker actually said?

    One escape hatch: Whisper mishears ("style" for "stile"), and a good model
    fixes that from context. We accept a subject word that isn't in the
    transcript only if it is in the user's glossary AND a word in the
    transcript is within two letters of it. The correction is reported.
    """
    heard = _words(transcript)
    said = set().union(*[_variants(w) for w in heard]) if heard else set()
    gloss = set()
    for term in glossary:
        for w in _words(term):
            gloss |= _variants(w)
    subj = _words(item["subject"])
    if not subj:
        return False, "empty subject"
    fixes, missing = [], []
    for w in subj:
        if _variants(w) & said:
            continue
        near = [h for h in heard if _variants(w) & gloss and len(w) > 3
                and min(_edit_distance(v, h.lower()) for v in _variants(w)) <= 2]
        if near:
            fixes.append(f'heard "{near[0]}", read as "{w}"')
        else:
            missing.append(w)
    if missing:
        return False, f"subject word(s) not in memo: {', '.join(missing)}"
    return True, "; ".join(fixes)


def count_supported(count, transcript) -> bool:
    if count is None:
        return True
    words = re.findall(r"[a-zA-Z]+|\d+", transcript.lower())
    for w in words:
        if w.isdigit() and int(w) == count:
            return True
        if _NUMBER_WORDS.get(w) == count:
            return True
    return False


def clean(result, transcript, glossary=()):
    """Merge duplicates, drop unsupported counts, split kept/rejected items."""
    kept, rejected, seen_keys = [], [], {}
    for raw in result.get("items", []):
        item = {
            "kind": raw.get("kind") if raw.get("kind") in KINDS else "note",
            "subject": (raw.get("subject") or "").strip().lower(),
            "count": raw.get("count"),
            "details": (raw.get("details") or "").strip(),
        }
        ok, why = grounded(item, transcript, glossary)
        if not ok:
            rejected.append({**item, "reason": why})
            continue
        if why:
            item["corrected"] = why
        if not count_supported(item["count"], transcript):
            item["details"] += f" (model said {item['count']}; not in memo, removed)"
            item["count"] = None
        key = (item["kind"], _stem(item["subject"]))
        if key in seen_keys:  # e.g. "two buzzards" + "maybe three" as two items
            prev = seen_keys[key]
            prev["details"] = f"{prev['details']}; {item['details']}".strip("; ")
            if prev["count"] is None:
                prev["count"] = item["count"]
            continue
        seen_keys[key] = item
        kept.append(item)
    return {"title": (result.get("title") or "").strip(), "items": kept, "rejected": rejected}
