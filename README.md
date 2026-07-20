# SilverLists Web

SilverLists Web erstellt aus CSV-Exporten von SilverERP druckfertige Berichte
und Ordersätze. Die Django-Anwendung erkennt anhand der CSV-Kopfzeile, welche
Auswertungen verfügbar sind, verarbeitet die Daten mit DuckDB und erzeugt eine
HTML-Vorschau sowie ein PDF.

Eine optionale Chrome-Erweiterung erkennt CSV-Downloads von
`live.silvererp.com`, legt sie in einem eigenen Downloadordner ab und bietet an,
sie direkt mit SilverLists Web zu öffnen.

## Funktionen

- CSV-Upload per Drag-and-drop
- automatische Erkennung passender Berichte
- modulare JSON-Reportdefinitionen mit DuckDB-SQL
- eigener Python-Renderer für die Ordersatz-Logik
- druckfertige PDFs mit Kopf- und Fußzeilen
- Druck-, Download- und E-Mail-Aktionen
- optionale Chrome-Integration für SilverERP-Downloads
- Docker-Deployment mit persistentem Datenvolume

## Projektstruktur

```text
silverlists-web/
├── docker-compose.yml       # Docker-/Portainer-Stack
├── extension/               # Chrome-Erweiterung und Paket-Makefile
└── web/                     # Django-Anwendung und Dockerfile
```

## Lokale Entwicklung

Voraussetzungen sind Python 3.12 oder neuer und ein aktuelles DuckDB-kompatibles
Python-System.

```bash
cd web
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Tests:

```bash
cd web
.venv/bin/pytest
```

## Deployment mit Portainer

### 1. Repository bereitstellen

Das Repository muss für Portainer erreichbar sein, beispielsweise als
GitHub-Repository. In Portainer unter **Stacks → Add stack → Repository** die
Repository-URL eintragen. Als Compose-Pfad wird verwendet:

```text
docker-compose.yml
```

Portainer baut das Image anschließend aus `web/Dockerfile`.

### 2. Umgebungsvariablen eintragen

Unter **Environment variables** mindestens folgende Werte setzen:

```dotenv
DJANGO_SECRET_KEY=<langer-zufälliger-geheimer-wert>
SILVERLISTS_BASE_URL=https://sandbox.3f-blb.local/silverlists/
SILVERLISTS_PORT=8000
```

Ein Secret kann beispielsweise so erzeugt werden:

```bash
openssl rand -base64 48
```

Für den Betrieb hinter einem HTTPS-Reverse-Proxy werden außerdem empfohlen:

```dotenv
DJANGO_DEBUG=false
DJANGO_TRUST_PROXY_HTTPS=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SECURE_SSL_REDIRECT=false
```

Alle verfügbaren Einstellungen stehen in [.env.example](.env.example). Der
Reverse-Proxy muss `X-Forwarded-Proto: https` setzen. Die File System Access API
der Chrome-Integration funktioniert außerhalb von `localhost` nur über HTTPS.
Aus `SILVERLISTS_BASE_URL` leitet Django automatisch den erlaubten Host, den
CSRF-Origin, den URL-Präfix sowie die Static- und Cookie-Pfade ab.

Für nginx muss der externe Präfix beim Weiterleiten entfernt werden:

```nginx
location /silverlists/ {
    proxy_pass http://silverlists-web:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### 3. Stack deployen

Über **Deploy the stack** wird das Image gebaut und der Container gestartet.
Beim Start führt der Entrypoint automatisch die Django-Migrationen und
`collectstatic` aus. Danach ist SilverLists Web über den in
`SILVERLISTS_PORT` eingestellten Port erreichbar.

Beim Image-Build liest eine separate Build-Stufe den Zeitstempel des letzten
Git-Commits aus und schreibt ihn als `Build YYYYMMDD-hhmm` in die
Weboberfläche. Das funktioniert auch bei einem direkt aus dem Git-Repository
gebauten Portainer-Stack; das `.git`-Verzeichnis wird nicht in das fertige
Runtime-Image kopiert. Mit `SILVERLISTS_BUILD` kann die Kennung bei Bedarf
manuell überschrieben werden.

Das benannte Volume `silverlists-data` enthält die SQLite-Datenbank, hochgeladene
CSV-Dateien und erzeugte Berichte. Dieses Volume sollte regelmäßig gesichert
werden und muss bei Stack-Updates erhalten bleiben.

### Produktbilder für Wochenangebote

Das eigenständige Berichtsmodul **Wochenangebot** erkennt Exporte aus
`Stammdaten → Preislisten-Definitionen`. Es bietet neun große Positionen auf
der Vorderseite und zwanzig kompakte Positionen auf der Rückseite. Designs
sind als austauschbare Hintergrund- und Farbdefinitionen gekapselt.

Produktbilder werden rekursiv anhand der kurzen Artikelnummer gesucht. Bei
`10-90-20-908156` muss der Bilddateiname daher mit `908156` beginnen. Zulässig
sind PNG, JPEG und WebP.

Im Wochenangebot-Editor kann der Benutzer alternativ einen lokalen
Produktbildordner über die File System Access API read-only freigeben. Chrome
speichert das Directory-Handle in IndexedDB, sucht die passenden Dateien lokal
und lädt beim Erzeugen ausschließlich Bilder positionierter Artikel zum
jeweiligen Auftrag hoch. Der lokale Pfad wird nicht an den Server übertragen.
Die Freigabe benötigt Chrome oder Edge und eine HTTPS-Verbindung.

Wenn der Bildbestand direkt auf dem Docker-Host verfügbar ist, kann er weiterhin
serverseitig read-only eingebunden werden:

```dotenv
SILVERLISTS_PRODUCT_IMAGE_HOST_DIR=/srv/silverlists/product-images
SILVERLISTS_PRODUCT_IMAGE_DIR=/product-images
```

Für kompakte Wochenangebot-PDFs werden Produktbilder nur beim Einbetten auf
maximal 480 Pixel verkleinert und als JPEG gespeichert. Die Quelldateien bleiben
unverändert. Bei Bedarf lassen sich Auflösung und Qualität anpassen:

```dotenv
SILVERLISTS_PRODUCT_IMAGE_MAX_PIXELS=480
SILVERLISTS_PRODUCT_IMAGE_JPEG_QUALITY=82
```

Neue integrierte Designs liegen unter
`web/reports/report_modules/weekly_offer_designs/<design>/`. Neben `front.jpg`
und `back.jpg` ist lediglich ein weiterer Eintrag in `DESIGNS` in
`weekly_offer.py` nötig; Import, Oberfläche und PDF-Renderer bleiben gleich.

Das Titelmotiv des Designs **Schlachthof** stammt von Jeremy Gallagher auf
[Unsplash](https://unsplash.com/photos/Cuiu5jbtZtI) und wird gemäß der
[Unsplash License](https://unsplash.com/license) verwendet. Die vollständigen
Asset-Angaben stehen in `weekly_offer_assets/STOCK_IMAGE.md`.

## Chrome-Erweiterung packen

Voraussetzungen: `make`, `node`, `python3` und `zip`.

```bash
cd extension
make package
```

Das geprüfte ZIP-Archiv wird unter `extension/dist/` erzeugt. Für die lokale
Entwicklung kann der Ordner `extension` unter `chrome://extensions` als
entpackte Erweiterung geladen werden.

## Corporate-Design-Dateien

Optionale Bilddateien für den PDF-Kopf gehören nach `web/assets/`:

- `header.png`
- `3f-logo-minibw.png`

Fehlen diese Dateien, werden die Berichte weiterhin erzeugt, jedoch ohne die
entsprechenden Bildbestandteile.

## Autor

Sebastian Walter — 3F Handelsgesellschaft mbH
