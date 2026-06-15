# CLAUDE.md

@AGENTS.md

## Projekt-Doku (Pen-&-Paper-Kampagne & Betrieb)

Dieser Fork enthält neben dem LiveKit-Agents-SDK eine **Delta-Green-Kampagne** mit Obsidian-Vault
(`sessions/`) und einem **Protocol-Agent** für Session-Mitschnitte. Spezialwissen dazu liegt in `docs/`.
**Nicht alles vorab laden** — die jeweilige Datei erst lesen, wenn die Aufgabe es erfordert:

| Lies … | … wenn |
|--------|--------|
| [docs/obsidian-vault-workflow.md](docs/obsidian-vault-workflow.md) | Du im Kampagnen-Vault (`sessions/`) arbeitest: Session-Ergebnisse einarbeiten, Fakten aktualisieren/abfragen, Foundry-Chat & Bilder verarbeiten, offene Punkte (fehlende Akten / unsortierte Ressourcen) pflegen |
| [docs/protocol-agent-betrieb.md](docs/protocol-agent-betrieb.md) | Du den LiveKit-/Protocol-Agent startest/stoppst/dispatchst, eine Session aufzeichnest oder Transkripte nachbearbeitest |
| [docs/html-abzug.md](docs/html-abzug.md) | Du gestylte, druckbare **HTML-Session-Dokumente** (`protocols-sessionNN/*.html`) erstellst/änderst |
| `sessions/README.md` | Einstieg/Navigation im Vault (immer zuerst beim Vault-Arbeiten) |
| `sessions/live/README.md` | Foundry-Chat + Bilder **spoiler-sicher** exportieren (Makro/ZIP) |

> Hinweis: `docs/` steht in `.gitignore` (dort landet der pdoc-SDK-Output im CI). Diese Kampagnen-Docs
> sind bewusst **force-added** und versioniert. Beim Anlegen neuer Dateien dort `git add -f` nutzen.
