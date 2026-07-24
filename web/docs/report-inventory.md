# Fachlicher Berichtskatalog aus der Altanwendung

Diese Liste ist die Migrations-Checkliste. Ein Bericht gilt erst dann als
portiert, wenn Exportweg, Pflichtspalten, Parameter, Abfrage, Gruppierung und
Ausgabe fachlich abgeglichen wurden.

## Ordersatz

| Varianten | SilverERP-Export | Besonderheit |
|---|---|---|
| VK1 bis VK6 | **Stammdaten → Artikellisten** | Je Variante muss `PG:VK1` bis `PG:VK6` exportiert werden. |
| Ohne Preise | **Stammdaten → Artikellisten** | Preisgruppe ist nicht erforderlich. |

Der Menüpfad ist im AutoIt-Programm nicht dokumentiert. Er wurde aus den
Beispiel-Exporten und dem identischen Spaltenbild des SilverLists-Web-Berichts
`bestellliste.rpt` rekonstruiert und muss im eingesetzten SilverERP bestätigt
werden. Sicher aus dem Altcode belegt sind diese Pflichtspalten:

- `Warengruppe`
- `Artikel-Nr.`
- `Bezeichnung 1`
- `S-Einheit`
- jeweilige Preisgruppe, außer bei „ohne Preise“

## SilverLists Web

| Altbericht | SilverERP-Export laut `.rpt` |
|---|---|
| Bestellliste | Stammdaten → Artikellisten |
| Dispoliste Fleisch, Kunden | Disposition Aufträge |
| Dispoliste Fleisch, Summen | Disposition Aufträge |
| Dispoliste Obst/Gemüse, Summen | Disposition Aufträge |
| Dispoliste Tiefkühl, Kunden | Disposition Aufträge |
| EK-Sonderpreise | Gespeicherte Abfragen |
| Frischemarkt | Controlling → Gespeicherte Abfragen → Preise |
| Kundeninventur | Controlling → Kunden-Artikel-Statistik |
| Kundenbestellzettel | Kundenstamm → Info → Verkaufshistorie |
| Kundenpreisliste | Stammdaten → [D] Kundenpreise |
| Allgemeine Kundenpreisliste | Stammdaten → [D] Artikelpreise |
| Kundensonderpreise | Kundenstamm → Kundenartikel |
| Lieferanten-Bestellliste | Stammdaten → Lieferant → Lieferanten-Artikel |
| Preisliste Obst/Gemüse | Stammdaten → [D] Artikelpreise |
| Angebot per Post | Stammdaten → Preislisten-Definition; zusätzlich Kundenliste erforderlich |
| Sonderpreisliste | Stammdaten → Preislisten-Definition |
| Wochenangebot | Stammdaten → Preislisten-Definition |

Die vollständigen erwarteten Header stehen noch in den jeweiligen Dateien unter
`../SilverERPBerichte/3F_SilverLists/reports`. Beim Portieren werden daraus nur
die tatsächlich von SQL und Darstellung verwendeten Pflichtspalten übernommen.
Damit bleibt die neue Anwendung stabil, wenn SilverERP weitere Exportspalten
ergänzt oder deren Reihenfolge ändert.
