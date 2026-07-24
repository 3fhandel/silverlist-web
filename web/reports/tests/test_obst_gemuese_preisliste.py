from pathlib import Path

from reports.catalog import get_definition, matching_definitions
from reports.services.duckdb_engine import execute_report


def test_two_column_pricelist_is_the_only_obst_gemuese_report():
    compact = get_definition("obst-gemuese-preisliste-zweispaltig")

    assert compact.options["layout"] == "two-column-pricelist"
    assert len(compact.options["list_notices"]) == 3
    assert "VB = Vorbestell-Artikel." in compact.options["list_notices"]
    assert "Weitere Artikel" in compact.options["closing_notice"]

    matches = {
        definition.key
        for definition in matching_definitions(compact.required_columns)
    }
    assert "obst-gemuese-preisliste-zweispaltig" in matches
    assert "obst-gemuese-preisliste" not in matches


def test_two_column_pricelist_sorts_umlauts_and_prioritizes_new_badges(tmp_path: Path):
    definition = get_definition("obst-gemuese-preisliste-zweispaltig")
    source = tmp_path / "artikelpreise.csv"
    index = {name: position for position, name in enumerate(definition.required_columns)}
    csv_rows = [";".join(definition.required_columns)]
    for group, name, description_2 in (
        ("Birnen", "Birnen Conference", ""),
        ("Äpfel", "Elstar", "Vorbestell-Artikel"),
        ("Äpfel", "(NEU) Boskoop", "Vorbestell-Artikel"),
        ("Äpfel", "(NEU) Cox Orange", "deutsche Ware"),
    ):
        values = [""] * len(definition.required_columns)
        values[index["Bezeichnung 1"]] = name
        values[index["Bezeichnung 2"]] = description_2
        values[index["Grundpreis"]] = "1,500"
        values[index["S-Einheit"]] = "ST"
        values[index["Dispo-Kennzeichen"]] = group
        values[index["Wg.-Pfad"]] = "60-10"
        csv_rows.append(";".join(values))
    source.write_text("\n".join(csv_rows), encoding="utf-8")

    result = execute_report(source, definition)

    group_index = result.columns.index("Dispo-Kennzeichen")
    article_index = result.columns.index("Artikel")
    preorder_index = result.columns.index("VB")
    assert [row[group_index] for row in result.rows] == [
        "Äpfel", "Äpfel", "Äpfel", "Birnen",
    ]
    assert [row[article_index] for row in result.rows] == [
        "Boskoop",
        "Cox Orange – deutsche Ware",
        "Elstar",
        "Birnen Conference",
    ]
    assert [row[preorder_index] for row in result.rows] == [
        "NEU", "NEU", "VB", "",
    ]
