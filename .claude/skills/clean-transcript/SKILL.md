---
name: clean-transcript
description: Bereinigt Protokoll-Transkripte von Pen-&-Paper-Sessions. Korrigiert STT-Fehler via LiteLLM (smartics-m-medium), führt Sprechertexte zusammen, erstellt Markdown mit Kapitelüberschriften.
allowed-tools: Bash, Read, Edit, Write, Glob
argument-hint: [ordner-oder-datei] [optionen]
---

# Transkript bereinigen

Bereinige die Protokoll-Transkripte aus dem Protocol Agent.

## Eingabe ermitteln

Wenn `$ARGUMENTS` angegeben ist, verwende das als Pfad. Andernfalls frage den User.

- Ist es ein **Ordner**: finde alle `.txt`-Dateien darin (ignoriere `_stats.json` und `.jsonl`)
- Ist es eine **Datei**: verwende nur diese

Filtere leere Transkripte heraus (< 10 echte Sprechzeilen, erkennbar an der `_stats.json` mit `total_turns: 0`).

## Script ausführen

Führe das Bereinigungsscript aus:

```bash
cd /home/anton/livekit/agents
python scripts/clean_transcript.py <dateien> \
  --title "<passender Titel>" \
  --no-system \
  -o <ausgabepfad>
```

### Titel bestimmen

Schaue in die ersten 50 Zeilen des Transkripts und leite einen passenden Titel ab. Für die RPG-Sessions verwende das Format:
`"Pen & Paper Session N – <Kurzbeschreibung>"`

### Ausgabepfad

Speichere die Ausgabe im selben Ordner wie die Eingabe als `session_transcript.md`.

## Nach dem Script

1. Zeige dem User die Ausgabedatei und eine kurze Zusammenfassung (Zeilenanzahl vorher/nachher)
2. Frage ob er das Ergebnis reviewen möchte
3. Falls der User Korrekturen wünscht, wende diese mit Edit auf die .md-Datei an

## LLM-Backend

Bereinigung läuft über **LiteLLM** (OpenAI-kompatibel), Modell `smartics-m-medium`.
Benötigt in `.env`: `LITELLM_API_BASE` + `LITELLM_API_KEY` (optional `LITELLM_MODEL`).
Fehlt die Konfiguration, läuft das Script automatisch im Offline-Modus (nur Merge, kein LLM).

## Optionen

Der User kann zusätzliche Optionen angeben:
- `--corrections-only` – kein LLM, nur Zusammenführen (offline)
- `--no-timestamps` – Zeitstempel weglassen
- `--chunk-size N` – Zeilen pro API-Call anpassen (default: 80)
- `--model NAME` – Modell überschreiben (default: smartics-m-medium)
- `--api-base URL` – LiteLLM-Basis-URL überschreiben

## Bekannter Kontext (für manuelle Nachbearbeitung)

Die RPG-Sessions sind eine FBI-Ermittlung (Delta Green / Call of Cthulhu):
- **Handler** = Spielleiter (Robert)
- **Anton** = Jeff "Chef" Harper (FBI-Agent)
- **Michael** = Alex Cross (FBI-Agent)
- **Stefan** = Wesley (FBI-Agent)
- Schauplatz: Saint Louis, Missouri / Illinois (Caseyville)
- Fall: Vermisste junge Frauen, Serienmörder-Verdacht
