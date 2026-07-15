from pathlib import Path

from reports.catalog import get_definition
from reports.services.duckdb_engine import execute_report


def test_obst_gemuese_bedarf_is_sorted_by_article_number(tmp_path: Path):
    definition = get_definition("dispoliste-og-summen")
    source = tmp_path / "disposition.csv"
    rows = [";".join(definition.required_columns)]
    index = {name: position for position, name in enumerate(definition.required_columns)}
    for article, name in [("60-20-2", "Zucchini"), ("60-10-1", "Apfel")]:
        values = [""] * len(definition.required_columns)
        values[index["Artikel-Nr."]] = article
        values[index["Bezeichnung 1"]] = name
        values[index["Menge"]] = "1,5"
        values[index["Einheit"]] = "kg"
        rows.append(";".join(values))
    source.write_text("\n".join(rows), encoding="utf-8")

    result = execute_report(source, definition)

    article_index = result.columns.index("Artikel-Nr.")
    assert [row[article_index] for row in result.rows] == ["60-10-1", "60-20-2"]
