# SilverLists Web Chrome-Erweiterung

Die Manifest-V3-Erweiterung beobachtet abgeschlossene Downloads. Wenn Quelle
`live.silvererp.com` und Dateiendung `.csv` übereinstimmen, zeigt Chrome eine
kleines Chrome-Fenster. Erst nach Klick auf „Mit SilverLists Web öffnen“ wird ein
neuer Tab geöffnet.

## Lokal installieren

1. `chrome://extensions` öffnen.
2. Entwicklermodus aktivieren.
3. „Entpackte Erweiterung laden“ wählen.
4. Diesen Ordner `extension` auswählen.
5. Einen SilverERP-CSV-Export herunterladen. Die Erweiterung legt ihn unter
   `Downloads/SilverLists Web` ab und erzeugt den Unterordner dabei automatisch.
6. In SilverLists Web einmalig über „Downloadordner für SilverLists Web verbinden“ genau
   diesen Unterordner auswählen – nicht den gesamten Downloads-Ordner.

Standardmäßig wird `http://localhost:8000/` geöffnet. Unter den Optionen der
Erweiterung kann eine andere URL für SilverLists Web eingetragen werden.

## Sicherheitsmodell

- Die Erweiterung liest oder überträgt die CSV nicht.
- In der URL steht nur der Dateiname, niemals der absolute lokale Pfad.
- SilverLists Web liest die Datei über ein zuvor vom Benutzer gewährtes
  `FileSystemDirectoryHandle` und lädt sie über das normale Uploadformular hoch.
- Chrome verweigert je nach Plattform den Zugriff auf den kompletten
  Downloads-Ordner. Deshalb werden passende Exporte automatisch im dedizierten
  Unterordner `Downloads/SilverLists Web` abgelegt.

## Paket bauen

```bash
make package
```

Das installierbare ZIP-Archiv wird versionsabhängig unter `dist/` erzeugt.
`make verify` prüft vorher Manifest und JavaScript-Syntax; `make clean` entfernt
erzeugte Pakete.

## Autor

Sebastian Walter — 3F Handelsgesellschaft mbH
- Die File System Access API benötigt `localhost` oder HTTPS.
