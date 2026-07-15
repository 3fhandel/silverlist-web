# SilverLists Web

Modernisierung von SilverLists Web und Ordersatz als Django-Webanwendung mit
DuckDB als Analyse-Engine.

## Zielbild

- Django verwaltet Uploads, Aufträge, Berichtskatalog und Ergebnisse.
- DuckDB liest die SilverERP-CSV je Auftrag in eine isolierte In-Memory-
  Verbindung und führt die Auswertungs-SQL aus.
- Django-Templates erzeugen HTML. Ein PDF-Renderer wird in einer folgenden
  Ausbaustufe hinter einer klaren Schnittstelle ergänzt.
- Die alte Anwendung in `../SilverERPBerichte` bleibt unverändert und dient
  während der Migration als Referenz.

Die Architektur- und Migrationsentscheidungen stehen in
[`docs/architecture.md`](docs/architecture.md).
Der aus der Altanwendung rekonstruierte fachliche Katalog inklusive der
benötigten SilverERP-Exporte steht in
[`docs/report-inventory.md`](docs/report-inventory.md).

## Lokaler Start

Voraussetzung: Python 3.12 oder neuer.

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Tests:

```bash
.venv/bin/pytest
```

## Docker / Portainer

Docker- und Portainer-Konfiguration liegen eine Ebene höher im
Repository-Hauptverzeichnis:

```bash
cd ..
cp .env.example .env
# mindestens DJANGO_SECRET_KEY und SILVERLISTS_BASE_URL anpassen
docker compose up --build -d
```

In Portainer kann die dortige `docker-compose.yml` direkt als Stack verwendet werden. Bei
einem Git-basierten Stack muss das Repository als Build-Kontext verfügbar sein.
Alle Variablen aus der dortigen `.env.example` können im Portainer-Stack unter
„Environment variables“ hinterlegt werden. Der veröffentlichte Port wird über
`SILVERLISTS_PORT` gesteuert.

Das benannte Volume `silverlists-data` enthält:

- Djangos SQLite-Datenbank
- hochgeladene CSV-Dateien
- erzeugte HTML- und PDF-Berichte

Vor einem Umzug oder Update sollte dieses Volume gesichert werden. Migrationen
und `collectstatic` laufen bei jedem Containerstart automatisch. Gunicorn dient
die Anwendung aus; WhiteNoise liefert die statischen Dateien aus.

Für einen HTTPS-Reverse-Proxy sind typischerweise diese Werte passend:

```dotenv
DJANGO_TRUST_PROXY_HTTPS=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
SILVERLISTS_BASE_URL=https://sandbox.3f-blb.local/silverlists/
```

`DJANGO_SECURE_SSL_REDIRECT` bleibt standardmäßig aus, damit die Anwendung nicht
in eine Redirect-Schleife gerät. Es sollte erst aktiviert werden, wenn der Proxy
`X-Forwarded-Proto: https` zuverlässig setzt.

## Aktueller Funktionsumfang

Der einheitliche Workflow und die sieben Ordersatz-Varianten werden bereits synchron verarbeitet:

1. CSV per Drag-and-drop hochladen
2. Kopfzeile analysieren und passende Berichte anzeigen
3. Bericht auswählen und Auftrag starten
4. Pflichtspalten prüfen
5. Daten mit DuckDB transformieren und sortieren
6. HTML und druckfertige PDF erzeugen sowie Vorschau und Download anzeigen

Der Ordersatz besitzt bereits ein eigenes mehrseitiges PDF-Layout mit Deckblatt,
3F-Logo, Firmendaten, wiederholten Tabellenköpfen, Briefkopf und Seitenzahlen.
Generische Berichte erhalten ihr PDF-Layout jeweils über den in der Definition
benannten Renderer.

Die 25 bisherigen SilverLists-Web-Berichte sind in
`report_definitions/silverlists/` migriert. Sie verwenden denselben Upload- und
Erkennungsablauf, dynamische Parameterformulare und bei Bedarf weitere
CSV-Quellen. Einfache und gruppierte Tabellen sowie Adressetiketten werden als
PDF erzeugt; der Ordersatz bleibt ein komplexes Python-Berichtsmodul.

## Autor

Sebastian Walter — 3F Handelsgesellschaft mbH
