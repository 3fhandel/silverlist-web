import csv

from reports.catalog import get_definition
from reports.services.duckdb_engine import execute_report
from reports.services.processor import _table_context


def test_vorbestell_artikel_in_dispo_sum_is_marked_bold_italic(tmp_path):
    definition = get_definition("dispoliste-og-summen")
    source = tmp_path / "obst.csv"
    values = {column: "1" for column in definition.required_columns}
    values.update({
        "Artikel-Nr.": "60-20-12857",
        "Bezeichnung 1": "Vorbestellware",
        "Bezeichnung 2": "Vorbestell-Artikel",
        "Einheit": "kg",
        "Menge": "2,50",
        "Beleg-Nr.": "AF-100",
        "W.-Termin": "15.07.2026",
    })
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(definition.required_columns)
        writer.writerow([values[column] for column in definition.required_columns])

    result = execute_report(source, definition)
    context = _table_context(definition, result)

    assert "__vorbestellung" not in context["columns"]
    article = context["display_rows"][0][context["columns"].index("Bezeichnung")]
    warning = context["display_rows"][0][context["columns"].index("Hinweis")]
    assert article["css_class"] == "bold-italic"
    assert warning["css_class"] == "warning-icon"
    assert context["column_widths"][context["columns"].index("Bezeichnung")] > 50
