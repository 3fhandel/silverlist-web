# Architektur und Migration

## Fachliche Quellen

Als Quellen für die Migration dienen die beiden bisher vom ReportManager gestarteten Programme:

1. `3F_SilverLists/main.exe`
2. `Ordersatz/Ordersatz.exe`

Ihre technische Trennung wird nicht übernommen. Der alte ReportManager selbst wird durch das Web-Dashboard ersetzt. Dispoliste,
Preisübersicht, Bestellliste, Mailversand und PrintMan werden nicht portiert.

## Komponenten

### Django

Django ist die dauerhafte Anwendungsebene. Seine relationale Datenbank enthält
Benutzer, Upload-Metadaten, Auftragsstatus, Parameter und Ergebnisdateien. Die
erste lokale Konfiguration verwendet SQLite; produktiv ist PostgreSQL vorgesehen.

### DuckDB

DuckDB ist keine zweite Anwendungsdatenbank. Jeder Berichtsauftrag erhält eine
isolierte In-Memory-Verbindung. Die hochgeladene SilverERP-CSV wird als View
`data` gelesen, validiert und durch die Abfrage der Berichtsdefinition
transformiert. Dadurch entstehen weder langlebige DuckDB-Dateien noch konkurrierende
Schreibzugriffe zwischen Web- oder Worker-Prozessen.

### Berichtskatalog

Einfache Berichte liegen als JSON im Repository. Gegenüber den alten `.rpt`-Dateien
werden Darstellung und Datenabfrage getrennt:

- JSON: Identität, Eingabespalten, Parameter und DuckDB-SQL
- Django-Template: HTML-Darstellung
- Python-Renderer: Gruppierung, Seitenstruktur und PDF-Ausgabe

Komplexe Berichte registrieren sich als Python-Modul im selben Katalog. Der
Ordersatz ist der erste solche Bericht. Upload, automatische Erkennung, Auswahl
und Ergebnisdarstellung sind unabhängig von der Implementierungsart.

PDFs werden nicht durch Shell-Aufrufe oder `wkhtmltopdf` erzeugt. Registrierte
Renderer erhalten strukturierte Berichtsdaten und erzeugen das Dokument mit
ReportLab. Dadurch sind Deckblatt, Corporate Design, wiederholte Tabellenköpfe,
Seitenumbrüche und Seitenzahlen automatisiert testbar.

Jede Definition enthält außerdem den SilverERP-Menüpfad, eine konkrete
Exportanleitung und die fachlich benötigten Spalten. Rekonstruierte, aber noch
nicht im laufenden SilverERP bestätigte Angaben werden als solche markiert.

SQL-Parameter verwenden `{{ name }}` und werden in gebundene DuckDB-Parameter
umgewandelt. Unkontrollierte Textersetzung in SQL wird nicht übernommen.

## Verarbeitungsablauf

1. Benutzer zieht eine SilverERP-CSV auf die Uploadfläche.
2. Die Kopfzeile wird gegen alle registrierten Berichte geprüft.
3. Der Benutzer wählt aus den passenden Berichten und startet den Auftrag.
4. Die Verarbeitung validiert Encoding und benötigte Spalten erneut.
5. DuckDB führt die Berichtsabfrage aus.
6. Ein Django-Template erzeugt HTML.
7. Der PDF-Adapter erzeugt ein PDF.
8. Auftrag und Ergebnis werden im Dashboard bereitgestellt.

Die Verarbeitungsschnittstelle soll synchron testbar bleiben. Für Produktion
wird sie später durch einen Worker aufgerufen; die Fachlogik kennt die Queue nicht.

## Migrationsreihenfolge

1. Vertikaler Durchstich mit Ordersatz VK1: Upload, DuckDB, HTML, PDF.
2. Ordersatz VK2–VK6 und Variante ohne Preise.
3. Generische Berichte einzeln portieren und gegen Beispiel-CSVs vergleichen.
4. Parameterformulare und zusätzliche Datenquellen portieren.
5. Authentifizierung, Aufbewahrung, Worker und produktives Deployment.
6. Fachliche Parallelabnahme Alt gegen Neu; danach Ablösung des ReportManagers.

## Bewusste Entscheidungen

- Django 5.2 LTS statt einer kurzlebigeren Feature-Version.
- Berichtsdaten bleiben auftragsbezogen; keine zentrale ERP-Schattenkopie.
- Keine direkte Übernahme von AutoIt-`Execute` oder `execAfter`.
- Spaltenerkennung erfolgt über erforderliche Spalten, nicht über einen exakt
  identischen kompletten Header.
- HTML aus CSV-Werten wird standardmäßig escaped.
