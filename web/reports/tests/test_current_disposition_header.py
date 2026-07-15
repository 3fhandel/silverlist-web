from reports.catalog import matching_definitions


CURRENT_DISPOSITION_HEADER = tuple(column.strip() for column in """
Beleg-Nr., Kunden-Nr., Name 1, Tour, Status, Artikel-Nr., Menge, Einheit,
Bezeichnung 1, Disponierbarer Bestand, S-Einheit, Reserviert,
Zur Kommission freigegebene Menge, Kommissioniert, Termin, W.-Termin,
B.-Termin, E.-Termin, Bezeichnung 2, Bezeichnung 3, Bezeichnung 4,
Versandart, WG-Code, WG Bezeichnung 1, Bestand, Beleg-Datum, Referenz,
Pos.-Netto, B.-Netto, B.-MwSt., B.-Brutto, Bestell-Nr., Bestelldatum,
Kurztext 1, Kurztext 2, Kurztext 3, Ort, Suchbegriff, Name 2, Straße, Land,
PLZ, Telefon, L.-Ort, L.-Suchbegriff, L.-Name 1, L.-Name 2, L.-Straße,
L.-Land, L.-PLZ, L.-Telefon, Liefer-Art, Abstellgenehmigung, Garantie bis,
Garantie bis Zeit, Versand ab, Versand ab Zeit, Versand bis, Versand bis Zeit,
Hilfsmittel, Avisierung, Fahrereravis, Versandhinweis 1, Versandhinweis 2,
Versandhinweis 3, Versandhinweis 4, Auftrags-Status, Länge, Breite, Stärke,
K.-Bemerkung 1, K.-Bemerkung 2, K.-Bemerkung 3, Rahmenposition, Rahmen-Nr.,
Abruf-Nr., Bestellt, Prüfbestand
""".replace("\n", " ").split(",") if column.strip())


def test_current_disposition_export_is_recognized():
    keys = {definition.key for definition in matching_definitions(CURRENT_DISPOSITION_HEADER)}
    assert {
        "dispoliste-fleisch-kunden",
        "dispoliste-fleisch-summen",
        "dispoliste-og-summen",
        "dispoliste-tiefkuehl-kunden",
        "tourenschein",
    }.issubset(keys)
