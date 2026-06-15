# Protocol-Agent & LiveKit — Betrieb

> **Wann lesen?** Wenn eine Session aufgezeichnet/transkribiert werden soll, der LiveKit-/Protocol-Agent
> gestartet/gestoppt/dispatcht wird, oder Transkripte nachbearbeitet werden.

## Überblick

Der **Protocol-Agent** (`protocol_agent.py`) transkribiert alle Teilnehmer eines LiveKit-Raums in Echtzeit (Meeting-/P&P-Mitschnitt). Pro Sprecher eine eigene STT-Session (keine Diarisierung nötig).

- **LiveKit Cloud:** `smartfoundry.livekit.cloud`
- **Umgebung:** **venv** (nicht `uv`) für den Protocol-Agent. `source venv/bin/activate`.
- **Env-Datei:** `.env.protocol` (Vorlage). Schlüssel: `LIVEKIT_URL/_API_KEY/_API_SECRET`, `DEEPGRAM_API_KEY`.

## Starten (2 Terminals)

**Terminal 1 — Worker starten:**
```bash
cd /home/anton/livekit/agents
source venv/bin/activate
python protocol_agent.py dev        # Dev-Modus (Hot-Reload)
# python protocol_agent.py start    # Produktion
# DEBUG=true python protocol_agent.py dev   # mit Debug-Logs
```
→ Warten auf **„registered worker"**.

**Terminal 2 — Agent in den Raum schicken:**
```bash
source venv/bin/activate
python dispatch_agent.py --list      # aktive Räume auflisten
python dispatch_agent.py <ROOM_NAME> # Agent dispatchen
```
Der Agent erkennt bereits anwesende Teilnehmer automatisch und beginnt zu transkribieren.

## Stoppen
- **`Ctrl+C`** in Terminal 1 → graceful (speichert Stats, schließt Dateien).
- **`pkill -f "protocol_agent.py"`** → hart.

## Konfiguration (via `.env.protocol`)
| Variable | Bedeutung | Default |
|----------|-----------|---------|
| `STT_PROVIDER` | `deepgram` (Nova-3), `speechmatics`, `openai` | deepgram |
| `STT_LANGUAGE` | `de`, `en`, `multi` (Auto) | oft `de`/`multi` |
| `OUTPUT_FORMAT` | `txt`, `json`, `both` | both |
| `IDLE_TIMEOUT_MINUTES` | Auto-Pause bei Stille (spart Credits), `0` = aus | 5 |

## Ausgabe
Verzeichnis `protocols/` — pro Mitschnitt:
- `*.txt` (lesbar), `*.jsonl` (maschinenlesbar), `*_stats.json` (Statistik).

**Deepgram-Guthaben prüfen:** `python check_deepgram_usage.py`.

## Transkript-Nachbearbeitung
- **Skill `clean-transcript`** bzw. `scripts/clean_transcript.py` — korrigiert STT-Fehler **mit Grok (xAI)**, führt Sprechertexte zusammen, erzeugt Markdown mit Kapiteln. (Für einfache LLM-Tasks **Grok bevorzugen**, nicht Anthropic-API.)
- `repair_transcripts.py` — Reparatur/Recovery beschädigter Mitschnitte.
- Das bereinigte/kuratierte Ergebnis wandert in den Vault → siehe [obsidian-vault-workflow.md](obsidian-vault-workflow.md).

## Live-Ansicht (frontail)
Der laufende Mitschnitt kann per **frontail** im Browser gestreamt werden; `frontail-highlight.json` (Repo-Root) hebt die Sprecher farbig hervor:
- Handler = blau, Michael = lila, Stefan = gelb, Anton = rot (Wort- + Zeilen-Highlight).
- Live-Mitschnitt-Frontend (im Foundry-Chat verlinkt): `https://rpgscribe.smartics.eu/`.

## Hinweise
- Vollständige Anleitung (DE/EN): `PROTOCOL_AGENT_GUIDE.md`.
- Architektur-Stichworte: Per-Teilnehmer-`AgentSession`, threadsicheres Schreiben (`threading.Lock`), Idle-Timeout zum Credit-Sparen.
