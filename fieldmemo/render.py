"""Write the journal (Markdown), the map layer (GeoJSON) and a flat CSV."""
import csv
import json
from collections import defaultdict

KIND_LABEL = {"seen": "Seen", "heard": "Heard (not seen)", "hazard": "Path problems",
              "todo": "To do", "note": "Notes"}


def _hm(dt, tz):
    return dt.astimezone(tz).strftime("%H:%M")


def _osm(lat, lon):
    return f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map=17/{lat:.5f}/{lon:.5f}"


def _thing(item):
    n = f" x{item['count']}" if item.get("count") else ""
    return f"{item['subject']}{n}"


def write_markdown(memos, meta, path, tz):
    spoken = [m for m in memos if m["transcript"]["text"]]
    first, last = memos[0]["time"], memos[-1]["time"]
    zone = first.astimezone(tz).tzname()
    L = [f"# Walk on {first.astimezone(tz):%a %d %b %Y}", "",
         f"{_hm(first, tz)} to {_hm(last, tz)} {zone} · {len(memos)} memos, "
         f"{len(spoken)} with speech · track: {meta['gpx'] or 'none'}", ""]

    by_kind = defaultdict(list)
    for m in spoken:
        for it in m["notes"]["items"]:
            by_kind[it["kind"]].append((m, it))
    L += ["## At a glance", ""]
    for kind in ("seen", "heard", "hazard", "todo", "note"):
        if not by_kind[kind]:
            continue
        if kind in ("hazard", "todo"):
            L.append(f"**{KIND_LABEL[kind]}**")
            for m, it in by_kind[kind]:
                where = f" ([map]({_osm(m['lat'], m['lon'])}))" if m["lat"] is not None else ""
                L.append(f"- {_hm(m['time'], tz)} {it['subject']}: {it['details']}{where}")
            L.append("")
        else:
            L.append(f"**{KIND_LABEL[kind]}:** " + ", ".join(_thing(it) for _, it in by_kind[kind]))
            L.append("")

    L += ["## Timeline", ""]
    for m in memos:
        t = _hm(m["time"], tz)
        if not m["transcript"]["text"]:
            L += [f"### {t} · (no speech, skipped)", "",
                  f"`{m['file']}`: Whisper's voice detector found no speech. Probably a pocket recording.", ""]
            continue
        L += [f"### {t} · {m['notes']['title'] or 'Memo'}", ""]
        if m["lat"] is not None:
            L.append(f"{m['lat']:.5f}, {m['lon']:.5f} ({m['where']}) · time from {m['time_source']} · `{m['file']}`")
        else:
            L.append(f"No position: {m['where']} · time from {m['time_source']} · `{m['file']}`")
        L += ["", f"> {m['transcript']['text']}", ""]
        for it in m["notes"]["items"]:
            cnt = f" ({it['count']})" if it.get("count") else ""
            fix = f" _(corrected: {it['corrected']})_" if it.get("corrected") else ""
            L.append(f"- **{it['kind']}**: {it['subject']}{cnt}: {it['details']}{fix}")
        for it in m["notes"]["rejected"]:
            L.append(f"- ~~{it['kind']}: {it['subject']}~~ dropped by the grounding check ({it['reason']})")
        L.append("")

    L += ["---", "",
          f"Made offline by fieldmemo: speech-to-text with Whisper `{meta['whisper']}`, "
          f"notes with `{meta['model']}` via Ollama. Every item is checked against the transcript; "
          "anything the model added that you didn't say is struck out above.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def write_geojson(memos, fixes, path, tz):
    feats = []
    if fixes:
        feats.append({"type": "Feature",
                      "properties": {"name": "track"},
                      "geometry": {"type": "LineString",
                                   "coordinates": [[round(f.lon, 6), round(f.lat, 6)] for f in fixes]}})
    for m in memos:
        if m["lat"] is None or not m["transcript"]["text"]:
            continue
        items = m["notes"]["items"]
        feats.append({"type": "Feature",
                      "properties": {
                          "time": m["time"].astimezone(tz).isoformat(),
                          "title": m["notes"]["title"],
                          "kinds": sorted({i["kind"] for i in items}),
                          "summary": "; ".join(f"{i['kind']}: {_thing(i)}" for i in items),
                          "transcript": m["transcript"]["text"],
                          "file": m["file"]},
                      "geometry": {"type": "Point", "coordinates": [round(m["lon"], 6), round(m["lat"], 6)]}})
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, indent=1), encoding="utf-8")


def write_csv(memos, path, tz):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "kind", "subject", "count", "details", "lat", "lon", "file"])
        for m in memos:
            for it in m["notes"]["items"] if m["transcript"]["text"] else []:
                w.writerow([m["time"].astimezone(tz).isoformat(), it["kind"], it["subject"],
                            it["count"] if it["count"] is not None else "", it["details"],
                            f"{m['lat']:.6f}" if m["lat"] is not None else "",
                            f"{m['lon']:.6f}" if m["lon"] is not None else "", m["file"]])
