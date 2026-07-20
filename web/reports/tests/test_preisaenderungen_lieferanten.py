from reports.catalog import get_catalog, get_definition, matching_definitions
from reports.services.duckdb_engine import execute_report


HEADER = (
    "Artikel-Nr.", "Suchbegriff", "Bezeichnung 1", "Typ", "Referenz",
    "Zeitpunkt", "Benutzer", "Ab Menge", "Preis", "Preis neu", "Währung",
)


def test_price_change_export_matches_new_report_but_not_removed_fm_report():
    definition = get_definition("preisaenderungen-lieferanten")
    catalog_keys = {definition.key for definition in get_catalog()}
    matching_keys = {definition.key for definition in matching_definitions(HEADER)}

    assert "frischemarkt" not in catalog_keys
    assert "preisaenderungen-lieferanten" in matching_keys
    assert definition.options["cell_font_size"] == 7.0


def test_supplier_price_changes_are_filtered_and_calculated(tmp_path):
    source = tmp_path / "preisaenderungen.csv"
    source.write_text(
        ";".join(HEADER) + "\n"
        "10-1;Artikel;Testartikel;supplierArticle;Testlieferant;7920947255856;natascha;0;8,0000;8,8000;EUR\n"
        "10-1;Artikel;Testartikel;pricegroup;VK1;7920947256880;natascha;0;10,0000;11,0000;EUR\n",
        encoding="utf-8",
    )

    result = execute_report(source, get_definition("preisaenderungen-lieferanten"))

    assert result.columns == (
        "Artikel", "Lieferant", "Zeitpunkt", "Benutzer",
        "Preis alt", "Preis neu", "Rel. Änderung", "Änderungsrichtung",
    )
    assert result.rows == ((
        "10-1\nTestartikel", "Testlieferant", "15.07.2026 07:50", "natascha",
        "8,0000\n8,8800", "8,8000\n9,7680", "+10,00 %", "up",
    ),)


def test_silvererp_timestamp_uses_polynomial_decoder(tmp_path):
    source = tmp_path / "zeitpunkt.csv"
    source.write_text(
        ";".join(HEADER) + "\n"
        "10-1;Artikel;Testartikel;supplierArticle;Testlieferant;7920996852379;natascha;0;8,0000;8,8000;EUR\n",
        encoding="utf-8",
    )

    result = execute_report(source, get_definition("preisaenderungen-lieferanten"))

    assert result.rows[0][2] == "20.07.2026 14:42"
