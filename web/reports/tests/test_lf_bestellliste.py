from reports.catalog import get_definition, matching_definitions
from reports.services.duckdb_engine import execute_report, inspect_csv_header


def test_current_supplier_export_is_recognized():
    header = (
        "Artikel-Nr.", "Bezeichnung 1", "Bezeichnung 2", "Lf.-Artikel-Nr.", "Preis",
        "Bestand", "S.-Einheit", "Referenz", "Archiv Artikel", "Hauptlieferant",
    )
    matches = {definition.key for definition in matching_definitions(header)}

    assert "lf-bestellliste" in matches


def test_supplier_order_list_reserves_space_for_name_and_order_quantity():
    definition = get_definition("lf-bestellliste")
    widths = definition.options["column_width_weights"]

    assert definition.options["layout"] == "internal-table"
    assert definition.options["cell_font_size"] == 9.5
    assert widths["Bezeichnung"] > widths["ArtNr"]
    assert widths["Bestellmenge"] >= widths["ArtNr"]


def test_supplier_order_list_has_requested_columns_and_values(tmp_path):
    definition = get_definition("lf-bestellliste")
    source = tmp_path / "lieferantenartikel.csv"
    source.write_text(
        "Artikel-Nr.;Bezeichnung 1;Bezeichnung 2;Lf.-Artikel-Nr.;Bestand;S.-Einheit;Archiv Artikel;Hauptlieferant\n"
        "10-40-31422;Flammkuchen Apfel und Zimt;;LF-422;10;ST;0;Ja\n"
        "10-40-88888;Artikel eines Nebenlieferanten;;LF-888;4;ST;0;Nein\n"
        "10-40-99999;Archivierter Artikel;;LF-999;2;ST;1;Ja\n",
        encoding="utf-8",
    )
    result = execute_report(source, definition, {"vorbestellartikel": "ja"})

    assert result.columns == (
        "ArtNr",
        "Bezeichnung",
        "Bestand",
        "S.-Einheit",
        "Bestellmenge",
    )
    assert result.rows == ((
        "10-40-31422\n(LF-422)", "Flammkuchen Apfel und Zimt", "10", "ST", "",
    ),)


def test_hl_is_accepted_as_short_alias_for_hauptlieferant(tmp_path):
    definition = get_definition("lf-bestellliste")
    source = tmp_path / "lieferantenartikel_mit_hl.csv"
    source.write_text(
        "Artikel-Nr.;Bezeichnung 1;Bezeichnung 2;Lf.-Artikel-Nr.;Bestand;S.-Einheit;Archiv Artikel;HL\n"
        "10-40-31422;Flammkuchen Apfel und Zimt;;;10;ST;0;Ja\n",
        encoding="utf-8",
    )

    assert "Hauptlieferant" in inspect_csv_header(source)
    result = execute_report(source, definition, {"vorbestellartikel": "ja"})
    assert len(result.rows) == 1


def test_preorder_articles_are_sorted_after_all_other_articles(tmp_path):
    definition = get_definition("lf-bestellliste")
    source = tmp_path / "lieferantenartikel.csv"
    source.write_text(
        "Artikel-Nr.;Bezeichnung 1;Bezeichnung 2;Lf.-Artikel-Nr.;Bestand;S.-Einheit;Archiv Artikel;Hauptlieferant\n"
        "10-001;Vorbestellung mit kleiner Nummer;Vorbestell-Artikel;;1;ST;0;Ja\n"
        "90-001;Regulärer Artikel;;;1;ST;0;Ja\n"
        "80-001;Artikel mit anderem Zusatz;Saisonartikel;;1;ST;0;Ja\n"
        "99-001;Weitere Vorbestellung;Vorbestell-Artikel;;1;ST;0;Ja\n",
        encoding="utf-8",
    )

    result = execute_report(source, definition, {"vorbestellartikel": "ja"})

    assert [row[0] for row in result.rows] == [
        "80-001", "90-001", "10-001", "99-001",
    ]
    assert result.rows[2][1] == (
        "Vorbestellung mit kleiner Nummer\nVB · Vorbestell-Artikel"
    )
    assert result.rows[3][1] == "Weitere Vorbestellung\nVB · Vorbestell-Artikel"


def test_preorder_articles_can_be_excluded(tmp_path):
    definition = get_definition("lf-bestellliste")
    source = tmp_path / "lieferantenartikel.csv"
    source.write_text(
        "Artikel-Nr.;Bezeichnung 1;Bezeichnung 2;Lf.-Artikel-Nr.;Bestand;S.-Einheit;Archiv Artikel;Hauptlieferant\n"
        "10-001;Vorbestellung;Vorbestell-Artikel;;1;ST;0;Ja\n"
        "20-001;Regulärer Artikel;;;1;ST;0;Ja\n",
        encoding="utf-8",
    )

    result = execute_report(source, definition, {"vorbestellartikel": "nein"})

    assert [row[0] for row in result.rows] == ["20-001"]
