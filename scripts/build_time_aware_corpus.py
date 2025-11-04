#!/usr/bin/env python3
# scripts/build_time_aware_corpus.py
# pip install srt

import argparse, json, re, os
from typing import List, Tuple
import srt

PROMO_PATTERNS = [
    r"subtitles\s+downloaded\s+from",  # site promos
    r"kickasssubtitles\.com",
    r"opensubtitles\.org",
]

SPEAKER_RE = re.compile(r"^\s*([A-Z][A-Z0-9 .'-]{1,30}?):\s*")  # ANNOUNCER:, MIA:, etc.
MUSIC_NOTE_RE = re.compile(r"[♪♩♫♬]")
NONVERBAL_PAREN_RE = re.compile(r"^\s*\((?:[^)]|\n)+\)\s*$")  # entire cue is ( ... )
HOH_INLINE_TAG_RE = re.compile(r"\s*\((?:music|sfx|applause|crowd|gasps?|chuckles?|laughs?|siren|phone|door|radio|tv|footsteps|whispers?|screams?)\)\s*", re.I)

def is_promo(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in PROMO_PATTERNS)

def normalize_ws(text: str) -> str:
    # Collapse whitespace, keep line breaks for speaker split, but minimize noise
    # Keep line breaks because lyrics often wrap
    return re.sub(r"[ \t]+", " ", text).strip()

def classify_cue(text: str) -> str:
    """Return one of: dialogue | lyric | nonverbal | metadata"""
    # Lyrics: if any music note symbol is present
    if MUSIC_NOTE_RE.search(text):
        return "lyric"
    # Nonverbal: entire cue is parenthetical (SFX/music)
    if NONVERBAL_PAREN_RE.match(text):
        return "nonverbal"
    # Metadata: opening credits, promos, or obviously not dialogue
    if is_promo(text):
        return "metadata"
    # Otherwise treat as dialogue (could still include inline parentheticals)
    return "dialogue"

def extract_speakers(text: str) -> List[str]:
    # Capture leading SPEAKER: pattern on first line, best-effort
    first_line = text.splitlines()[0] if "\n" in text else text
    m = SPEAKER_RE.match(first_line.strip())
    if m:
        sp = m.group(1).strip()
        # Normalize multiple words like "RADIO ANNOUNCER"
        sp = re.sub(r"\s+", " ", sp)
        return [sp]
    return []

def clean_text(text: str, remove_hoh: bool, remove_speaker_label: bool) -> Tuple[str, dict]:
    """Return cleaned text and flags dict."""
    flags = {
        "has_music_note": bool(MUSIC_NOTE_RE.search(text)),
        "has_parenthetical": "(" in text and ")" in text,
        "hard_of_hearing_tags_removed": False
    }

    # Optionally remove HOH inline tags like (LAUGHS), (MUSIC PLAYING)
    if remove_hoh:
        new_text = HOH_INLINE_TAG_RE.sub(" ", text)
        if new_text != text:
            flags["hard_of_hearing_tags_removed"] = True
        text = new_text

    # Optionally remove leading SPEAKER:
    if remove_speaker_label:
        text = SPEAKER_RE.sub("", text)

    # Trim and normalize whitespace
    text = normalize_ws(text)
    return text, flags

def parse_srt_file(path: str):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    subs = list(srt.parse(content))
    cues = []
    for s in subs:
        start = s.start.total_seconds()
        end = s.end.total_seconds()
        # Preserve line breaks in the original for better speaker/lyric split
        text = s.content.replace("\r\n", "\n").strip()
        if not text:
            continue
        cues.append((start, end, text))
    # Ensure in order
    cues.sort(key=lambda x: x[0])
    return cues

def should_merge(prev_type: str, next_type: str, allow_cross_type: bool) -> bool:
    if allow_cross_type:
        return True
    # Default: only merge within same "broad" category; lyrics stay with lyrics
    if prev_type == next_type:
        return True
    return False

def chunk_cues(
    cues: List[Tuple[float, float, str]],
    max_gap_sec: float = 6.0,
    max_chars: int = 1200,
    remove_hoh: bool = True,
    remove_speaker_label: bool = False,
    allow_cross_type_merge: bool = False,
    drop_metadata: bool = True,
):
    """
    Merge consecutive cues if:
      - time gap <= max_gap_sec
      - types are compatible (unless allow_cross_type_merge)
      - size stays under max_chars
    """
    chunks = []
    if not cues:
        return chunks

    # Initialize with first cue
    s0, e0, t0 = cues[0]
    ctype0 = classify_cue(t0)
    speakers = extract_speakers(t0)
    t0_clean, flags0 = clean_text(t0, remove_hoh, remove_speaker_label)

    cur_start = s0
    cur_end = e0
    cur_text = t0_clean
    cur_type = ctype0
    cur_speakers = set(speakers)
    cur_flags = flags0.copy()

    def flush():
        if drop_metadata and cur_type == "metadata":
            return
        chunks.append({
            "t_start": round(float(cur_start), 3),
            "t_end": round(float(cur_end), 3),
            "text": cur_text.strip(),
            "cue_type": cur_type,
            "speakers": sorted(list(cur_speakers)) if cur_speakers else [],
            "flags": cur_flags
        })

    for (s, e, text) in cues[1:]:
        ctype = classify_cue(text)
        spk = extract_speakers(text)
        text_clean, flags = clean_text(text, remove_hoh, remove_speaker_label)

        gap = s - cur_end
        size_ok = (len(cur_text) + 1 + len(text_clean)) <= max_chars
        type_ok = should_merge(cur_type, ctype, allow_cross_type_merge)

        if gap <= max_gap_sec and size_ok and type_ok:
            # merge
            cur_end = e
            if cur_text and text_clean:
                cur_text = f"{cur_text}\n{text_clean}" if cur_type == "lyric" else f"{cur_text} {text_clean}"
            elif text_clean:
                cur_text = text_clean
            cur_speakers.update(spk)
            # merge flags conservatively
            cur_flags["has_music_note"] = cur_flags["has_music_note"] or flags["has_music_note"]
            cur_flags["has_parenthetical"] = cur_flags["has_parenthetical"] or flags["has_parenthetical"]
            cur_flags["hard_of_hearing_tags_removed"] = cur_flags["hard_of_hearing_tags_removed"] or flags["hard_of_hearing_tags_removed"]
        else:
            # flush previous and start new
            flush()
            cur_start, cur_end, cur_text, cur_type = s, e, text_clean, ctype
            cur_speakers = set(spk)
            cur_flags = flags.copy()

    # flush last
    flush()
    return chunks

def write_jsonl(chunks, film_id, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for ch in chunks:
            rec = {
                "film_id": film_id,
                "source_type": "subtitles",
                **ch
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {len(chunks)} chunks → {out_path}")

def main():
    ap = argparse.ArgumentParser(description="Build time-aware subtitle corpus (JSONL) for FilmBuddy.")
    ap.add_argument("--film_id", required=True, help="e.g. la_la_land")
    ap.add_argument("--subs", required=True, help="Path to .srt file")
    ap.add_argument("--out", required=True, help="Output JSONL path")
    ap.add_argument("--gap", type=float, default=6.0, help="Max gap (s) to merge consecutive cues")
    ap.add_argument("--max_chars", type=int, default=1200, help="Max characters per merged chunk")
    ap.add_argument("--keep_hoh", action="store_true", help="Keep hearing-impaired tags like (MUSIC PLAYING)")
    ap.add_argument("--keep_speaker_labels", action="store_true", help="Keep leading SPEAKER: labels")
    ap.add_argument("--allow_cross_type_merge", action="store_true", help="Allow merging across cue types (dialogue/lyric/etc.)")
    ap.add_argument("--keep_metadata", action="store_true", help="Keep metadata cues (site promos) in output")
    args = ap.parse_args()

    cues = parse_srt_file(args.subs)

    chunks = chunk_cues(
        cues,
        max_gap_sec=args.gap,
        max_chars=args.max_chars,
        remove_hoh=not args.keep_hoh,
        remove_speaker_label=not args.keep_speaker_labels,
        allow_cross_type_merge=args.allow_cross_type_merge,
        drop_metadata=not args.keep_metadata
    )

    write_jsonl(chunks, args.film_id, args.out)

if __name__ == "__main__":
    main()
