#!/usr/bin/env python3
"""
Transcript Cleaner for Protocol Agent recordings.

Reads .txt protocol files, sends them in chunks to an OpenAI-compatible LiteLLM
endpoint for transcription error correction, merges consecutive same-speaker
turns, and outputs clean Markdown with chapter headings.

Usage:
    python scripts/clean_transcript.py protocols-session02/*.txt -o session02.md
    python scripts/clean_transcript.py protocols-session02/*.txt --corrections-only
    python scripts/clean_transcript.py --help

LLM-Backend: LiteLLM (OpenAI-kompatibel) — setze LITELLM_API_BASE + LITELLM_API_KEY
in .env (Modell via LITELLM_MODEL oder --model, default: smartics-m-medium).
Es werden keine Zusatzpakete gebraucht (urllib). Ohne Konfiguration nur
--corrections-only (Offline-Merge ohne LLM).
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ──────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────

# LiteLLM (OpenAI-kompatibler Proxy) — einziges LLM-Backend
LITELLM_MODEL = "smartics-m-medium"

CHUNK_SIZE = 80  # turns per API call


def build_chat_url(api_base: str) -> str:
    """Baue die /chat/completions-URL aus einer LiteLLM-Basis-URL."""
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


# ──────────────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Turn:
    timestamp: str
    speaker: str
    text: str
    is_system: bool = False


# ──────────────────────────────────────────────────────────────────────
# .env loader
# ──────────────────────────────────────────────────────────────────────

def load_env(env_path: str) -> dict[str, str]:
    """Load key=value pairs from a .env file."""
    env = {}
    if not os.path.exists(env_path):
        return env
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                env[key.strip()] = value
    return env


# ──────────────────────────────────────────────────────────────────────
# LLM API call (OpenAI-kompatibel: LiteLLM)
# ──────────────────────────────────────────────────────────────────────

def call_llm(api_url: str, api_key: str, model: str,
             system_prompt: str, user_prompt: str) -> str:
    """Call an OpenAI-compatible chat endpoint and return the response text."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }).encode("utf-8")

    req = Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "clean-transcript/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"  API ERROR {e.code}: {body[:200]}", file=sys.stderr)
        raise


# ──────────────────────────────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────────────────────────────

def parse_txt_file(filepath: str) -> list[Turn]:
    """Parse a .txt protocol file into a list of Turns."""
    turns: list[Turn] = []
    line_re = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s+(.+?):\s+(.*)$")
    sys_re = re.compile(
        r"^\[(\d{2}:\d{2}:\d{2})\]\s+(>>>|<<<)\s+(.+?)\s+(joined|left)\s+the\s+meeting"
    )

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("=") or not line.strip():
                continue
            if any(line.startswith(p) for p in [
                "Meeting Protocol", "Meeting ended", "Room:", "STT Provider:",
                "--- Statistics", "Total ", "Per participant:",
            ]):
                continue
            if re.match(r"^\s+\w+:\s+\d+\s+words", line):
                continue

            sys_match = sys_re.match(line)
            if sys_match:
                ts, direction, name, action = sys_match.groups()
                symbol = "→" if direction == ">>>" else "←"
                turns.append(Turn(
                    timestamp=ts, speaker=name,
                    text=f"{symbol} {name} {'betritt' if action == 'joined' else 'verlässt'} die Sitzung",
                    is_system=True,
                ))
                continue

            line_match = line_re.match(line)
            if line_match:
                ts, speaker, text = line_match.groups()
                turns.append(Turn(timestamp=ts, speaker=speaker, text=text.strip()))

    return turns


# ──────────────────────────────────────────────────────────────────────
# Merging
# ──────────────────────────────────────────────────────────────────────

def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%H:%M:%S")


def merge_consecutive_turns(turns: list[Turn], max_gap: int = 8) -> list[Turn]:
    """Merge consecutive turns from the same speaker within max_gap seconds."""
    if not turns:
        return []
    merged: list[Turn] = []
    cur = turns[0]
    for turn in turns[1:]:
        if turn.is_system or cur.is_system:
            merged.append(cur)
            cur = turn
            continue
        if turn.speaker == cur.speaker:
            try:
                gap = (parse_ts(turn.timestamp) - parse_ts(cur.timestamp)).total_seconds()
                if gap < 0:
                    gap += 86400
            except ValueError:
                gap = 999
            if gap <= max_gap:
                cur = Turn(cur.timestamp, cur.speaker, cur.text + " " + turn.text)
                continue
        merged.append(cur)
        cur = turn
    merged.append(cur)
    return merged


# ──────────────────────────────────────────────────────────────────────
# LLM-based correction
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Du bist ein Korrektor für automatische Deepgram-Transkripte einer deutschen Pen-&-Paper-Rollenspielsitzung (FBI-Ermittlung im Stil von Delta Green / Call of Cthulhu).

TEILNEHMER:
- Handler = Spielleiter/Game Master (Robert)
- Anton = spielt Jeff "Chef" Harper, FBI-Agent
- Michael = spielt Alex Cross, FBI-Agent
- Stefan = spielt Wesley, FBI-Agent

BEKANNTE NPCs: Lena Terence, Peggy Webber, Mark Webber, Marlice Webber, Hannah Robinson, Mandy Glover, Tara White, Dr. Alan Rivers, Marcus Briggs, Sergeant Gallows, Karen Simmons (Coroner), TJ (FBI-Forensiker), Hudson George (FBI-Boss), Ben Luskowski (Spin Doctor des Governors), Mister Rollerman (Nachbar/Zeuge), Serena (Jeffs Freundin, Opferbetreuung).

BEKANNTE ORTE: Avery Club (Nachtclub, Washington Park), Woodland Country Club / Far Oaks Golf Club (Caseyville), Rivers-Klinik (200 N Broadway, Saint Louis), Morrison Avenue (Tatort), Caseyville (Illinois).

REGELN:
1. Korrigiere offensichtliche STT-Fehler und verstümmelte Wörter
2. Korrigiere Namensfehler (Lina→Lena, Bricks→Briggs, Gelos→Gallows, Ellen→Alan, Teacher/DJ/PJ→TJ, Weber→Webber, etc.)
3. ENTFERNE komplett: Zeilen die nur aus falschsprachigem Rauschen bestehen (z.B. rein spanische/englische Sätze wo Deutsch gemeint war wie "¿Qué nou?", "Este va", "Captain both for shout", "Ya deben su patron", etc.)
4. ENTFERNE komplett: Zeilen die nur aus einem einzelnen Füllwort bestehen (Yeah, Yep, Okay, Mhmm, Ja, Nein, Gut, Genau, No, Nine, Hello?, Good, Done, Nee)
5. Behalte natürlichen Umgangston bei – korrigiere nur echte Fehler, nicht den Stil
6. Korrigiere Fachbegriffe: Fragestellnummer→Fahrgestellnummer, Adoptionsbericht→Obduktionsbericht, Sycopharmaka→Psychopharmaka, Lachs/Aberlack→Luck, Corona/Korona→Coroner, Rensik→Forensik

EINGABEFORMAT: Jede Zeile kommt als `N. [Sprecher] Text` (N = fortlaufende Nummer).
AUSGABEFORMAT (WICHTIG, Token sparen):
7. Gib für JEDE Nummer GENAU eine Zeile zurück als `N. korrigierter Text` — NUR Nummer und Text, OHNE Sprecher, OHNE Zeitstempel, OHNE Klammern.
8. Eine Zeile, die laut Regel 3/4 entfernt werden soll, gib als `N. -` zurück (nur ein Bindestrich).
9. Lass NIEMALS eine Nummer aus, ändere die Nummerierung/Reihenfolge nicht, füge KEINE Kommentare/Erklärungen/Leerzeilen hinzu.

BEISPIEL —
Eingabe:
1. [Anton] Der Marcus Bricks hat den Wagen.
2. [Michael] Yeah.
3. [Handler] Und der Gelos hat die Leiche gefunden.
Ausgabe:
1. Der Marcus Briggs hat den Wagen.
2. -
3. Und der Gallows hat die Leiche gefunden."""


_NUM_RE = re.compile(r"^\s*(\d+)[.)]\s?(.*)$")
_DROP_VALUES = {"", "-", "–", "—", "[-]", "(-)"}


_RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def _process_chunk(
    chunk: "list[tuple[int, Turn]]", chunk_num: int, total: int,
    api_url: str, api_key: str, model: str, retries: int = 4,
) -> "dict[int, Turn | None]":
    """Correct one chunk via the LLM. Numbered I/O keeps output small and mapping robust.

    Returns {orig_idx: Turn|None}; None means the line was dropped (noise/filler).
    Retries transient 5xx/429 with exponential backoff; on terminal failure the
    originals are kept (no silent data loss)."""
    # Numbered input: "N. [Sprecher] Text" — the model returns "N. korrigierter Text".
    user_prompt = "\n".join(
        f"{n}. [{t.speaker}] {t.text}" for n, (_, t) in enumerate(chunk, 1)
    )

    last_err = None
    for attempt in range(retries + 1):
        try:
            result = call_llm(api_url, api_key, model, SYSTEM_PROMPT, user_prompt)
            last_err = None
            break
        except HTTPError as e:
            last_err = e
            if e.code not in _RETRYABLE_HTTP or attempt == retries:
                break
        except Exception as e:  # timeouts, connection resets, etc. -> retry
            last_err = e
            if attempt == retries:
                break
        # exponential backoff (3,6,12,24s, capped) + kleiner chunk-Versatz gegen Thundering Herd
        time.sleep(min(30.0, 3 * (2 ** attempt)) + (chunk_num % 6) * 0.5)
    if last_err is not None:
        print(f"  Chunk {chunk_num}/{total} FEHLER (Original behalten): {last_err}",
              file=sys.stderr)
        return {idx: t for idx, t in chunk}

    # Parse "N. text" back into a local-number -> text map
    parsed: dict[int, str] = {}
    for line in result.splitlines():
        m = _NUM_RE.match(line)
        if m:
            parsed[int(m.group(1))] = m.group(2).strip()

    out: dict[int, Turn | None] = {}
    for n, (idx, t) in enumerate(chunk, 1):
        if n in parsed:
            txt = parsed[n].strip()
            out[idx] = None if txt in _DROP_VALUES else Turn(t.timestamp, t.speaker, txt)
        else:
            out[idx] = t  # model skipped this number -> keep original (safety)
    return out


def fix_with_llm(turns: list[Turn], api_url: str, api_key: str, model: str,
                 chunk_size: int = 80, concurrency: int = 6) -> list[Turn]:
    """Send turns to an OpenAI-compatible LLM for correction, chunked and in parallel."""
    text_turns = [(i, t) for i, t in enumerate(turns) if not t.is_system]
    chunks = [text_turns[i:i + chunk_size] for i in range(0, len(text_turns), chunk_size)]
    total = len(chunks)

    corrected_map: dict[int, Turn | None] = {}
    lock = threading.Lock()
    done = 0

    def worker(job: "tuple[int, list[tuple[int, Turn]]]") -> "dict[int, Turn | None]":
        idx, chunk = job
        res = _process_chunk(chunk, idx + 1, total, api_url, api_key, model)
        nonlocal done
        with lock:
            done += 1
            print(f"  {model}: {done}/{total} Chunks fertig", file=sys.stderr, flush=True)
        return res

    print(f"  Parallelität: {concurrency} gleichzeitig, {total} Chunks", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        for res in ex.map(worker, enumerate(chunks)):
            corrected_map.update(res)

    # Reassemble in original order (system turns kept as-is; None = dropped)
    fixed: list[Turn] = []
    for i, turn in enumerate(turns):
        if turn.is_system:
            fixed.append(turn)
        elif i in corrected_map:
            if corrected_map[i] is not None:
                fixed.append(corrected_map[i])
        else:
            fixed.append(turn)

    return fixed


# ──────────────────────────────────────────────────────────────────────
# Chapter detection
# ──────────────────────────────────────────────────────────────────────

CHAPTER_KEYWORDS = [
    (["recap", "zusammenfassung", "letztes mal", "vermissten"], "Recap der bisherigen Ermittlung"),
    (["tatort", "hinfahren", "fahrt da", "ihr kommt da"], "Tatortbesichtigung"),
    (["george", "hudson", "boss", "büro.*boss"], "Gespräch mit dem Boss"),
    (["ben ", "luskowski", "leskowski", "republican", "gouverneur", "governor"],
     "Treffen mit Ben Luskowski"),
    (["rollerman", "nachbar.*kamera", "überwachungskamera"], "Befragung der Nachbarn"),
    (["schule", "highschool", "parkplatz.*schule"], "Ermittlung an der Schule"),
    (["werkstatt", "inhaber.*laden"], "Befragung Werkstattbesitzer"),
    (["karen", "coroner", "leiche.*untersucht", "autopsie", "obduktion"],
     "Befragung der Coroner"),
    (["zug.*kamera", "frontkamera", "fra ", "railroad", "federal railroad"],
     "Zugkamera-Recherche"),
    (["nächste.*schritt", "morgen.*termin", "plan.*nächst"], "Planung nächste Schritte"),
    (["richter", "beschluss", "datenschutz", "listen.*golfclub"],
     "Diskussion: Richterlicher Beschluss"),
    (["board", "pinwand", "visualis", "google.*sheet"], "Board-Organisation"),
    (["termin.*nächst", "vierzehnten", "ostern", "nächste woche"],
     "Terminplanung nächste Session"),
]


def detect_chapters(turns: list[Turn]) -> list[tuple[int, str]]:
    """Detect chapter breaks based on scene transitions by Handler."""
    markers: list[tuple[int, str]] = []
    used_chapters: set[str] = set()

    for i, turn in enumerate(turns):
        if turn.is_system:
            continue

        # Time gap > 3 minutes = likely scene change
        if i > 0 and not turns[i - 1].is_system:
            try:
                gap = (parse_ts(turn.timestamp) - parse_ts(turns[i - 1].timestamp)).total_seconds()
                if gap < 0:
                    gap += 86400
                if gap >= 180:
                    markers.append((i, f"*[Pause – {int(gap / 60)} Minuten]*"))
            except ValueError:
                pass

        # Scene transitions by Handler
        if turn.speaker == "Handler" and len(turn.text) > 80:
            text_lower = turn.text.lower()
            for keywords, title in CHAPTER_KEYWORDS:
                if title in used_chapters:
                    continue
                if any(re.search(kw, text_lower) for kw in keywords):
                    markers.append((i, title))
                    used_chapters.add(title)
                    break

    return markers


# ──────────────────────────────────────────────────────────────────────
# Markdown output
# ──────────────────────────────────────────────────────────────────────

def to_markdown(
    turns: list[Turn],
    title: str,
    date: str,
    participants: list[str],
    chapters: list[tuple[int, str]],
    timestamps: bool = True,
) -> str:
    lines = [f"# {title}", ""]
    if date:
        lines += [f"**Datum:** {date}", ""]
    if participants:
        lines += [f"**Teilnehmer:** {', '.join(participants)}", ""]
    lines += ["---", ""]

    chapter_map = {idx: title for idx, title in chapters}

    for i, turn in enumerate(turns):
        if i in chapter_map:
            ch = chapter_map[i]
            if ch.startswith("*["):
                lines += ["", ch, ""]
            else:
                lines += ["", f"## {ch}", ""]

        if turn.is_system:
            lines += [f"*{turn.text}*", ""]
            continue

        ts = f"`[{turn.timestamp}]` " if timestamps else ""
        lines.append(f"**{turn.speaker}:** {ts}{turn.text}")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Bereinigt Protokoll-Transkripte mit LiteLLM und erstellt Markdown."
    )
    parser.add_argument("inputs", nargs="+", help="Eingabe .txt-Dateien")
    parser.add_argument("-o", "--output", help="Ausgabe .md-Datei")
    parser.add_argument("--title", default="Session-Protokoll", help="Titel")
    parser.add_argument("--date", default="", help="Datum der Session")
    parser.add_argument("--no-timestamps", action="store_true")
    parser.add_argument("--no-system", action="store_true", help="Join/Leave weglassen")
    parser.add_argument("--merge-gap", type=int, default=8, help="Sekunden für Merge (default: 8)")
    parser.add_argument("--env", default="", help="Pfad zur .env-Datei")
    parser.add_argument("--corrections-only", action="store_true",
                        help="Nur mergen, kein LLM (offline)")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                        help=f"Zeilen pro API-Chunk (default: {CHUNK_SIZE})")
    parser.add_argument("--concurrency", type=int, default=3,
                        help="Gleichzeitige API-Requests (default: 3; Backend-schonend, 60 RPM beachten)")
    parser.add_argument("--model", default="", help="Modell überschreiben (default: smartics-m-medium)")
    parser.add_argument("--api-base", default="", help="LiteLLM API-Basis-URL überschreiben")

    args = parser.parse_args()
    chunk_size_val = args.chunk_size

    # Load config
    env_path = args.env or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    env = load_env(env_path)

    def cfg(name: str, default: str = "") -> str:
        return os.environ.get(name, env.get(name, default))

    litellm_base = args.api_base or cfg("LITELLM_API_BASE")
    api_key = cfg("LITELLM_API_KEY")
    model = args.model or cfg("LITELLM_MODEL", LITELLM_MODEL)
    api_url = build_chat_url(litellm_base) if litellm_base else ""

    if not args.corrections_only and not (litellm_base and api_key):
        print("WARNUNG: LITELLM_API_BASE/LITELLM_API_KEY fehlen in .env! "
              "Nutze --corrections-only für Offline-Modus (nur Merge, kein LLM).",
              file=sys.stderr)
        args.corrections_only = True

    # 1Password-Referenz nicht aufgelöst → über `op run` starten
    if not args.corrections_only and api_key.startswith("op://"):
        print(
            "FEHLER: LITELLM_API_KEY ist eine unaufgelöste 1Password-Referenz (op://…).\n"
            "        Über 'op run' starten, damit op die Referenz auflöst, z.B.:\n"
            "        OP_SERVICE_ACCOUNT_TOKEN=ops_… op run --env-file=.env -- \\\n"
            "          python scripts/clean_transcript.py <datei> --title '…' --no-system -o <ausgabe>\n"
            "        (Service-Account-Token aus einer Ebene unter .env beziehen, nicht in git.)",
            file=sys.stderr)
        sys.exit(2)

    # Parse input files
    all_turns: list[Turn] = []
    for fp in args.inputs:
        # Skip non-.txt files (stats, jsonl)
        if not fp.endswith(".txt"):
            continue
        print(f"Lese: {fp}", file=sys.stderr)
        turns = parse_txt_file(fp)
        if turns:
            all_turns.extend(turns)
            print(f"  {len(turns)} Zeilen", file=sys.stderr)

    if not all_turns:
        print("Keine Daten gefunden!", file=sys.stderr)
        sys.exit(1)

    # Filter empty transcripts (< 5 real turns)
    real_turns = [t for t in all_turns if not t.is_system]
    if len(real_turns) < 5:
        print("Zu wenig Inhalt – nur System-Meldungen?", file=sys.stderr)
        sys.exit(1)

    # Date from filename
    if not args.date:
        for fp in args.inputs:
            m = re.search(r"(\d{8})", fp)
            if m:
                d = m.group(1)
                args.date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                break

    # Participants
    participants = []
    seen: set[str] = set()
    for t in all_turns:
        if t.speaker not in seen and not t.is_system:
            participants.append(t.speaker)
            seen.add(t.speaker)

    # Step 1: LLM corrections
    if not args.corrections_only:
        print(f"\nLLM-Korrekturen via LiteLLM/{model} ({len(real_turns)} Zeilen)...",
              file=sys.stderr)
        all_turns = fix_with_llm(all_turns, api_url, api_key, model,
                                 chunk_size=chunk_size_val, concurrency=args.concurrency)
        corrected_count = len([t for t in all_turns if not t.is_system])
        removed = len(real_turns) - corrected_count
        print(f"  {removed} Zeilen entfernt (Rauschen/Füllwörter)", file=sys.stderr)

    # Step 2: Remove system messages
    if args.no_system:
        all_turns = [t for t in all_turns if not t.is_system]

    # Step 3: Merge
    print("Zusammenführen...", file=sys.stderr)
    before = len(all_turns)
    all_turns = merge_consecutive_turns(all_turns, args.merge_gap)
    print(f"  {before} → {len(all_turns)} Zeilen", file=sys.stderr)

    # Step 4: Chapters
    print("Kapitel erkennen...", file=sys.stderr)
    chapters = detect_chapters(all_turns)
    print(f"  {len(chapters)} Kapitelmarker", file=sys.stderr)

    # Step 5: Markdown
    md = to_markdown(
        all_turns,
        title=args.title,
        date=args.date,
        participants=participants,
        chapters=chapters,
        timestamps=not args.no_timestamps,
    )

    # Output
    if args.output:
        out_path = args.output
    else:
        base = Path(args.inputs[0]).stem
        out_path = str(Path(args.inputs[0]).parent / f"{base}_clean.md")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n✓ Geschrieben: {out_path} ({len(all_turns)} Zeilen)", file=sys.stderr)


if __name__ == "__main__":
    main()
