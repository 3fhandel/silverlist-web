import csv
import re

import pytest

from reports.catalog import get_catalog
from reports.services.duckdb_engine import execute_report
from reports.services.pdf_renderer import render_address_labels_pdf, render_generic_pdf


EXTRA_COLUMNS = {
    "kunden": ("Kunden-Nr.", "Name 1", "Name 2", "Straße", "PLZ", "Ort"),
    "silver": ("Beleg-Nr.", "B.-Brutto"),
}


def sample_value(column):
    name = column.lower()
    if any(part in name for part in ("datum", "termin", "gültig", "garantie")):
        return "15.07.2026"
    if any(part in name for part in (
        "preis", "netto", "brutto", "menge", "bestand", "umsatz",
        "rohgewinn", "rabatt", "gewicht", "mwst",
    )):
        return "1,00"
    if any(part in name for part in ("archiv", "status", "sperr")):
        return "0"
    if "artikel-nr" in name:
        return "601001"
    if "kunden-nr" in name:
        return "10001"
    if "beleg-nr" in name or "belegfeld 1" in name:
        return "20001"
    if "wg" in name or "warengruppe" in name:
        return "60-10"
    if "einheit" in name:
        return "kg"
    if "name" in name or "bezeichnung" in name:
        return "Test & Ware"
    if name == "monat":
        return "7"
    if name == "jahr":
        return "2026"
    if "soll/haben" in name:
        return "S"
    return "1"


def write_csv(path, columns):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(columns)
        writer.writerow([sample_value(column) for column in columns])


def parameters_for(definition):
    parameters = {}
    for variable in definition.variables:
        if variable["type"] == "userBool":
            parameters[variable["name"]] = True
        elif variable["type"] == "userSelect":
            parameters[variable["name"]] = variable["selectFrom"][0]["value"]
        elif variable["type"] == "userText":
            parameters[variable["name"]] = "30"
    return parameters


SQL_DEFINITIONS = tuple(
    definition for definition in get_catalog() if definition.implementation == "sql"
)


@pytest.mark.parametrize("definition", SQL_DEFINITIONS, ids=lambda item: item.key)
def test_every_sql_report_executes_and_renders_pdf(definition, tmp_path):
    source = tmp_path / "source.csv"
    write_csv(source, definition.required_columns)
    additional = {}
    for source_definition in definition.additional_sources:
        name = source_definition["name"]
        path = tmp_path / f"{name}.csv"
        write_csv(path, source_definition.get("required_columns", EXTRA_COLUMNS.get(name, ())))
        additional[name] = path

    result = execute_report(
        source, definition, parameters_for(definition), additional
    )
    pdf = (
        render_address_labels_pdf(definition, result)
        if definition.renderer == "address-labels"
        else render_generic_pdf(definition, result)
    )
    assert pdf.startswith(b"%PDF-")


def test_report_definitions_do_not_embed_html_in_queries_or_variables():
    html = re.compile(r"<\s*/?\s*[a-z][^>]*>|&(?:nbsp|euro);", re.IGNORECASE)
    for definition in SQL_DEFINITIONS:
        assert not html.search(definition.query), definition.key
        for variable in definition.variables:
            for field in ("value", "query", "command"):
                assert not html.search(str(variable.get(field, ""))), (
                    definition.key, variable["name"], field
                )
