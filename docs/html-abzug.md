# HTML-Abzug der Session-Dokumente

> **Wann lesen?** Wenn ein gestyltes, druckbares HTML-Dokument einer Session (Zusammenfassung,
> Regeln) erstellt, erweitert oder geändert werden soll.

## Was ist der „HTML-Abzug"?

Eigenständige, **in sich geschlossene HTML-Dateien** im Delta-Green-Look — gedacht zum Ansehen/Drucken (A4) und Teilen, unabhängig von Obsidian. Beispiele:

```
protocols-session01/
├── Summary-Session-01.html   # ausführliche Zusammenfassung
├── SESSION-001.html          # Session-Dokument
└── RULES-ADDITION.html       # Regel-Ergänzungen
```

Jede Datei ist **self-contained**: kein externer Build, keine JS-Abhängigkeiten, nur Inline-`<style>` + Google-Fonts-Import. Man kann sie direkt im Browser öffnen oder als PDF drucken.

> ⚠️ **Nicht verwechseln** mit dem LiveKit-**SDK**-API-Doku-Build
> (`.github/workflows/publish-docs.yml` → `pdoc --html --output-dir=docs livekit` → S3 `livekit-docs`).
> Das ist der Upstream-SDK-Docs-Pipeline und hat **nichts** mit den Kampagnen-HTML-Abzügen zu tun.
> (Außerdem: das Verzeichnis `docs/` ist in `.gitignore`, weil pdoc dort hineinschreibt — diese
> Kampagnen-Docs hier sind daher **force-added**.)

## Aufbau einer Abzug-Datei

```html
<!DOCTYPE html><html lang="de"><head>
  <meta charset="UTF-8">
  <title>…</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&family=Oswald:wght@400;700&display=swap');
    :root{
      --dg-green:#1a472a; --dg-green-light:#2d5a3d; --dg-black:#0a0a0a;
      --dg-gray:#1a1a1a;  --dg-text:#c4c4c4;        --dg-accent:#4a7c59;
      --dg-red:#8b0000;   --dg-yellow:#b8860b;
    }
    body{ font-family:'Courier Prime',monospace; background:var(--dg-black); color:var(--dg-text); font-size:11pt; line-height:1.5; }
    .page{ width:210mm; min-height:297mm; padding:15mm 20mm; margin:0 auto;
           background:linear-gradient(135deg,var(--dg-black) 0%,#111 50%,var(--dg-gray) 100%); position:relative; }
    .page::before{ /* dekoratives Overlay */ }
  </style>
</head><body>
  <div class="page"> … Inhalt … </div>
</body></html>
```

**Designsystem:**
- **Fonts:** *Courier Prime* (Fließtext, Schreibmaschinen-Look) + *Oswald* (Überschriften).
- **Farbpalette (CSS-Variablen):** DG-Grün `#1a472a`, Schwarz `#0a0a0a`, Text-Grau `#c4c4c4`, Akzent `#4a7c59`, Warn-Rot `#8b0000`, Gelb `#b8860b`.
- **Seite:** `.page` = A4 (210 × 297 mm), Rand 15/20 mm, dunkler Verlauf, dekoratives `::before`.

## Erstellen / Erweitern

Es gibt **keine automatische Pipeline** — die Dateien werden generiert (i. d. R. per LLM aus der Session-Zusammenfassung + dieser Vorlage). Vorgehen:

1. Quelle ist die Markdown-Zusammenfassung der Session (`sessions/records/sessions/session-NN/session-NN-zusammenfassung.md`).
2. Eine bestehende HTML-Datei (z. B. `Summary-Session-01.html`) als **Stil-Vorlage** verwenden — `:root`-Variablen, `.page`-Container und Komponenten-Klassen beibehalten.
3. Nur den `<body>`-Inhalt mit den neuen Session-Daten füllen; Theme/CSS unverändert lassen → einheitlicher Look.
4. **Ändern des Looks:** zentral über die `:root`-Variablen (Farben) bzw. die `.page`-Regeln (Layout/Druck). Da jede Datei das CSS inline trägt, muss eine Designänderung in **jede** Datei übernommen werden (oder ein gemeinsames Template pflegen und neu rendern).

## Verwandte Docs
- [obsidian-vault-workflow.md](obsidian-vault-workflow.md) — woher die Inhalte (Zusammenfassungen) kommen
- [protocol-agent-betrieb.md](protocol-agent-betrieb.md) — Transkripte als Rohquelle
