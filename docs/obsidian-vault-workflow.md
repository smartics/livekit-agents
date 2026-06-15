# Arbeiten mit dem Obsidian-Vault (Delta-Green-Kampagne)

> **Wann lesen?** Immer, bevor du Inhalte in den Kampagnen-Vault (`sessions/`) einarbeitest,
> aktualisierst, abfragst — oder neues Material (Foundry-Chat, Bilder, Berichte) verarbeitest.

## 1. Was ist der Vault?

- **Ort:** `sessions/` — eigenes git-Repo, synchronisiert via **Obsidian LiveSync** (`_LiveSyncSettings`).
- **Zweck:** kuratierte Auswertung der Pen-&-Paper-Kampagne **„Die vermissten Mädchen von Caseyville"** (Delta Green). Die Protocol-Agent-Transkripte sind die Rohdaten, der Vault die strukturierte Ermittlungsdoku.
- **Einstieg:** immer zuerst `sessions/README.md` (Hub) lesen — Schnellzugriff, Navigation, Strukturüberblick.

⚠️ **LiveSync synct keine großen Binärdateien** (z. B. `.zip`). Solche Dateien direkt aufs Dateisystem legen, nicht über Obsidian auf einem anderen Gerät.

## 2. Struktur

```
sessions/
├── README.md                 # Hub: Schnellzugriff, Tabellen, Navigation
├── persons.base / orte.base  # Obsidian-Datenbanken (dynamische Views)
├── persons/                  # 1 Datei je Person (player/ kontakte/ fall-1/)
│   └── <gruppe>/images/      # Portraits
├── records/                  # Unveränderliche Originaldokumente
│   ├── sessions/session-NN/  # transcript, zusammenfassung, overview, next-steps
│   └── fall-1/               # Polizei-/Obduktionsberichte (+ images/ Scans)
└── documents/fall-1/         # Aktive Arbeitsdokumente
    ├── ermittlungsstand.md   # zentraler Stand: was wissen wir, was fehlt
    ├── quellen-map.md        # ⭐ Belegliste aller Kernfakten (#N)
    ├── timeline · verbindungsgraph · theorien · ermittlungstabelle · fragenkatalog
    ├── karte.md              # Geo-Übersicht (alle Koordinaten + Google-My-Maps)
    ├── fehlende-ressourcen.md# offene Punkte: fehlende Akten/Bilder
    ├── orte/ (+ orte/images/)# Orts-Dossiers
    └── unsortiert/           # noch nicht zuordenbare Chat-Ressourcen (+ unsortiert.base)
```

**Konventionen:** Frontmatter mit `title/type/subtype/case/tags/created/updated`; Wikilinks klein-mit-bindestrich (`[[tara-white]]`); Bilder in `images/`-Subfolder; Portrait via `portrait:`, Orts-Bild via `cover_image:`; Embed `![[datei.png|320]]`. Details: Memory `project_obsidian_vault`.

## 3. Session-Ergebnis einarbeiten

1. **Rohtranskript** (aus Protocol-Agent, siehe [protocol-agent-betrieb.md](protocol-agent-betrieb.md)) → `records/sessions/session-NN/transcript.md` (immutable). Dazu `zusammenfassung`, `overview` (Release-Notes-Stil), `next-steps`.
2. **Fakten verdichten → `quellen-map.md`.** Eiserne Regel:
   - Jede neue belegte Aussage **nur** als neue Zeile in `quellen-map.md` (mit Transkript-Zeitstempel, Sprecher, Record-Bezug).
   - Andere Dokumente **referenzieren** den Fakt per `[[quellen-map|#N]]` statt ihn zu duplizieren.
3. **Betroffene Dateien konsistent nachziehen** (Personen, Orte, `ermittlungsstand`, `timeline`, `verbindungsgraph`, `ermittlungstabelle`).
4. **Spieler-Hypothesen ≠ Handler-Fakten** — klar trennen (fett markierte Sprecher; Hypothesen als solche kennzeichnen).
5. **Tag `#session-N`** an neue Ergänzungen, damit sie per Suche auffindbar sind.

**Fakt-Eingabe-Protokoll:** Sagt Anton *„Fakt X aus Session N, Zeitstempel T"* → `quellen-map.md` ergänzen + alle betroffenen Dateien aktualisieren. Hinterfragt Anton einen Fakt → **zuerst in `quellen-map.md` nachschlagen**, erst dann im Transkript.

## 4. Wissen abfragen & pflegen

- **Navigation:** `README.md` (Schnellzugriff) → `ermittlungsstand` (Gesamtstand), `timeline` (Chronologie), `verbindungsgraph` (Mermaid), `theorien` (Hypothesen-Status).
- **Datenbanken:** `persons.base` (Spieler/Kontakte/Opfer/Verdächtige/Zeugen), `orte.base` (Orte inkl. Koordinaten).
- **Suche:** Tag `#session-N`; Belege immer über `quellen-map.md`.
- **Geo:** `karte.md` + `records/fall-1/karten/caseyville-karte.kml`.
- OCR/unsichere Lesungen nie als bestätigten Fakt behandeln; paraphrasierte Fakten transparent markieren.

## 5. Neues Material aus Foundry (Chat + Bilder)

**Eingangskorb:** `sessions/live/` (Foundry-Inbox; Tooling siehe `sessions/live/README.md`).

1. **Export** mit dem Makro aus `sessions/live/Foundry-Chat-Export-Skript.md` (liest **nur** `game.messages` → spoiler-sicher) → erzeugt **eine** `foundry-chat-export.zip` (Chat-Log + im Chat gepastete Bilder). Anleitung + Spoiler-Schutz + Chrome-Eigenheiten: `sessions/live/README.md`.
2. Anton legt die ZIP in `sessions/live/` → **Claude entpackt selbst** (`foundry-chat.md/.json`, `images/`).
3. **Zuordnen:**
   - Koordinaten → in `karte.md`, Orts-/Personen-Frontmatter (meist schon vorhanden → nur abgleichen).
   - **Bilder:** Porträt → passende Person (`portrait:` + Embed); Orts-Foto/Luftbild → Ort (`cover_image:` + Embed, Bild nach `orte/images/`).
   - **Chat-Fakten** → `quellen-map.md` (mit Quelle „Foundry-Chat <Datum>, <Sprecher>").
4. **Nicht zuordenbar** → `documents/fall-1/unsortiert/`: pro Ressource **eine Notiz** (`type: resource`, `status: unassigned`, `source:`), Bild nach `unsortiert/images/`. Übersicht via `unsortiert.base`.
5. **Backup + Aufräumen:** Roh-Export (ZIP, md/json, alle Bilder) nach `attic/foundry-live-<Datum>/` **außerhalb des Vaults** sichern; `sessions/live/` wieder leeren (Tooling behalten).

## 6. Offene Punkte — wo gesammelt wird

| Datei | Sammelt |
|-------|---------|
| `documents/fall-1/fehlende-ressourcen.md` | **Fehlende Unterlagen/Akten** (z. B. Porsche-**Forensik-Bericht**, DNA-Bericht, Lenas Tagebuch), fehlende **Portraits**, fehlende **Orts-Bilder** |
| `documents/fall-1/unsortiert/` + `unsortiert.base` | **Bereitgestellte, aber noch nicht zuordenbare** Bilder/Links aus dem Foundry-Chat (offene Frage: „zu wem/was gehört das?") |
| `documents/fall-1/ermittlungsstand.md` (#Beweismittel) | Status aller Beweismittel/Spuren in-game |

→ Diese drei sind die ersten Anlaufstellen, wenn Anton fragt „was fehlt noch?" oder Material liefert.

## Verwandte Docs
- [protocol-agent-betrieb.md](protocol-agent-betrieb.md) — wie die Transkripte (Rohdaten) entstehen
- `sessions/live/README.md` — Foundry-Chat/Bilder spoiler-sicher exportieren (Makro + ZIP)
- [html-abzug.md](html-abzug.md) — gestylte HTML-Session-Dokumente
