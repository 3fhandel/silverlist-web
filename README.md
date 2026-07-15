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
DJANGO_ALLOWED_HOSTS=silverlists.example.org
DJANGO_CSRF_TRUSTED_ORIGINS=https://silverlists.example.org
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

### 3. Stack deployen

Über **Deploy the stack** wird das Image gebaut und der Container gestartet.
Beim Start führt der Entrypoint automatisch die Django-Migrationen und
`collectstatic` aus. Danach ist SilverLists Web über den in
`SILVERLISTS_PORT` eingestellten Port erreichbar.

Das benannte Volume `silverlists-data` enthält die SQLite-Datenbank, hochgeladene
CSV-Dateien und erzeugte Berichte. Dieses Volume sollte regelmäßig gesichert
werden und muss bei Stack-Updates erhalten bleiben.

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
